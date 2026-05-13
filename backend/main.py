"""FastAPI application entry point.

Serves the frontend (static files) and exposes the music similarity API.

Endpoints
---------
GET  /              -> frontend index.html
GET  /api/catalog   -> catalog size and feature column list
POST /api/analyze   -> multipart file upload; returns similarity ranking
GET  /api/health    -> liveness probe
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections.abc import Iterable
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .audio_features import extract_features, summary_metrics
from .reason_engine import explain_match, report_to_dict
from .similarity import MusicSimilarityEngine

# ----------------------------------------------------------------------
# Path setup
# ----------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = Path(os.environ.get("MUSIC_DATASET_PATH", ROOT / "data" / "dataset.csv"))
FRONTEND_DIR = Path(os.environ.get("MUSIC_FRONTEND_DIR", ROOT / "frontend"))
UPLOAD_DIR = Path(os.environ.get("MUSIC_UPLOAD_DIR", ROOT / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
MAX_UPLOAD_BYTES = int(os.environ.get("MUSIC_MAX_UPLOAD_BYTES", 25 * 1024 * 1024))  # 25 MB

# Magic byte sniffing so we don't trust filename extensions blindly.
# (sig_bytes, accepted_extensions)
_MAGIC_SIGNATURES: list[tuple[bytes, frozenset[str]]] = [
    (b"RIFF", frozenset({".wav"})),
    (b"ID3", frozenset({".mp3"})),
    (b"\xff\xfb", frozenset({".mp3"})),
    (b"\xff\xf3", frozenset({".mp3"})),
    (b"\xff\xf2", frozenset({".mp3"})),
    (b"fLaC", frozenset({".flac"})),
    (b"OggS", frozenset({".ogg"})),
    # MP4/M4A boxes (ftyp at offset 4)
]

ENV = os.environ.get("MUSIC_ENV", "development")
ALLOWED_ORIGINS_ENV = os.environ.get("MUSIC_ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS: list[str] = (
    [o.strip() for o in ALLOWED_ORIGINS_ENV.split(",") if o.strip()]
    if ALLOWED_ORIGINS_ENV
    else (["*"] if ENV != "production" else [])
)

# Concurrency cap: librosa decode is CPU-bound; even on threadpool we don't
# want a single client to spin up unbounded threads.
MAX_CONCURRENT_ANALYSES = int(os.environ.get("MUSIC_MAX_CONCURRENT", 4))
_analysis_semaphore = asyncio.Semaphore(MAX_CONCURRENT_ANALYSES)

# Simple in-process rate limiter (per IP, sliding window).
RATE_LIMIT_PER_MIN = int(os.environ.get("MUSIC_RATE_LIMIT_PER_MIN", 12))
_rate_state: dict[str, list[float]] = {}
_rate_lock = asyncio.Lock()

logger = logging.getLogger("music_similarity")

# ----------------------------------------------------------------------
# Engine — load lazily so worker startup doesn't crash on bad CSV
# ----------------------------------------------------------------------
_engine: MusicSimilarityEngine | None = None


def get_engine() -> MusicSimilarityEngine:
    global _engine
    if _engine is None:
        _engine = MusicSimilarityEngine(DATASET_PATH)
        logger.info(
            "catalog_loaded",
            extra={"catalog_size": _engine.catalog_size, "path": str(DATASET_PATH)},
        )
    return _engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure logging once at startup.
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=os.environ.get("MUSIC_LOG_LEVEL", "INFO"),
            format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
        )
    try:
        get_engine()
    except Exception:  # noqa: BLE001
        logger.exception("engine_load_failed")
    yield


# ----------------------------------------------------------------------
# App
# ----------------------------------------------------------------------
app = FastAPI(
    title="SoundMatch · Music Similarity API",
    description="Upload a song and find the most acoustically similar tracks from the catalog.",
    version="1.1.0",
    lifespan=lifespan,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply hardening headers to every response."""

    CSP = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "media-src 'self' blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "microphone=(), camera=(), geolocation=()")
        # CSP for HTML responses only — JSON/SVG/etc are fine.
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers.setdefault("Content-Security-Policy", self.CSP)
        if ENV == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        # Attach to request state so handlers can pull it.
        request.state.request_id = request_id
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "elapsed_ms": round(elapsed_ms, 1),
                },
            )
            raise
        elapsed_ms = (time.perf_counter() - t0) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_done",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": round(elapsed_ms, 1),
            },
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLogMiddleware)

# CORS: when no explicit origins are configured in production, the middleware
# is omitted entirely. Same-origin requests work without CORS.
if ALLOWED_ORIGINS:
    # We never enable credentials with a wildcard origin (browser rejects it).
    allow_credentials = "*" not in ALLOWED_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


async def _rate_limit(request: Request) -> None:
    """Per-IP sliding-window limiter (RATE_LIMIT_PER_MIN in 60s)."""
    ip = _client_ip(request)
    now = time.time()
    window = 60.0
    async with _rate_lock:
        history = _rate_state.setdefault(ip, [])
        # Drop entries older than window.
        cutoff = now - window
        history[:] = [t for t in history if t > cutoff]
        if len(history) >= RATE_LIMIT_PER_MIN:
            retry = window - (now - history[0])
            raise HTTPException(
                status_code=429,
                detail=f"요청이 너무 잦습니다. 약 {int(retry) + 1}초 뒤에 다시 시도해주세요.",
                headers={"Retry-After": str(int(retry) + 1)},
            )
        history.append(now)


def _sniff_audio(head: bytes, ext: str) -> bool:
    if len(head) < 4:
        return False
    for sig, accepted in _MAGIC_SIGNATURES:
        if head.startswith(sig) and ext in accepted:
            return True
    # MP4/M4A: 'ftyp' box at offset 4
    if ext == ".m4a" and len(head) >= 12 and head[4:8] == b"ftyp":
        return True
    # OGG handled above; FLAC handled above.
    return False


def _safe_filename(name: str | None) -> str:
    """Strip directory components and dangerous characters from a display name."""
    if not name:
        return "upload"
    base = os.path.basename(name).replace("\x00", "")
    return base[:200] or "upload"


def _all_finite(values: Iterable[float]) -> bool:
    arr = np.asarray(list(values), dtype=float)
    return bool(np.isfinite(arr).all())


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------
@app.get("/api/health")
def health():
    try:
        size = get_engine().catalog_size
    except Exception:  # noqa: BLE001
        return JSONResponse({"status": "degraded", "catalog_size": 0}, status_code=503)
    return {"status": "ok", "catalog_size": size, "env": ENV, "version": app.version}


@app.get("/api/catalog")
def catalog_info():
    eng = get_engine()
    return {
        "catalog_size": eng.catalog_size,
        "feature_count": len(eng.feature_columns),
        "features": eng.feature_columns,
    }


@app.post("/api/analyze", dependencies=[Depends(_rate_limit)])
async def analyze(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),  # noqa: B008 — FastAPI dep-injection pattern
    top_n: int = Query(5, ge=1, le=20),  # noqa: B008
):
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
    safe_name = _safe_filename(file.filename)
    ext = Path(safe_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. ({', '.join(sorted(ALLOWED_EXTENSIONS))})",
        )

    # Pre-flight size check via Content-Length if the client provided it.
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_UPLOAD_BYTES + 4096:
        raise HTTPException(
            status_code=413,
            detail=f"파일이 너무 큽니다. 최대 {MAX_UPLOAD_BYTES // (1024*1024)}MB.",
        )

    dest = UPLOAD_DIR / f"{request_id}{ext}"

    # Drop temp file even on cancellation / handler exception.
    def _cleanup(path: Path) -> None:
        try:
            os.remove(path)
        except OSError:
            pass

    background_tasks.add_task(_cleanup, dest)

    try:
        async with _analysis_semaphore:
            # Stream upload to disk with running size cap, sniff first 16 bytes.
            written = 0
            head_bytes = b""
            with dest.open("wb") as out:
                while chunk := await file.read(1024 * 1024):
                    if not head_bytes:
                        head_bytes = chunk[:16]
                    written += len(chunk)
                    if written > MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail=f"파일이 너무 큽니다. 최대 {MAX_UPLOAD_BYTES // (1024*1024)}MB.",
                        )
                    out.write(chunk)
            if written == 0:
                raise HTTPException(status_code=400, detail="빈 파일입니다.")
            if not _sniff_audio(head_bytes, ext):
                raise HTTPException(
                    status_code=400,
                    detail="파일 내용이 오디오 형식과 일치하지 않습니다. 확장자를 확인해주세요.",
                )

            # Feature extraction is sync/CPU-bound — push to threadpool so the
            # event loop stays free for other requests.
            t0 = time.perf_counter()
            try:
                features = await run_in_threadpool(extract_features, dest)
            except HTTPException:
                raise
            except (ValueError, RuntimeError) as e:
                # librosa raises these for malformed audio.
                logger.warning(
                    "feature_extraction_failed",
                    extra={"request_id": request_id, "error": str(e)},
                )
                raise HTTPException(
                    status_code=400,
                    detail="오디오 분석에 실패했습니다. 손상된 파일이거나 너무 짧을 수 있습니다.",
                ) from e
            except Exception as e:  # noqa: BLE001
                logger.exception(
                    "feature_extraction_crashed",
                    extra={"request_id": request_id},
                )
                raise HTTPException(
                    status_code=500, detail="서버 내부 오류가 발생했습니다."
                ) from e
            feature_seconds = time.perf_counter() - t0

            if not _all_finite(features.values.values()):
                logger.warning(
                    "non_finite_features",
                    extra={"request_id": request_id},
                )
                raise HTTPException(
                    status_code=422,
                    detail="분석 결과에 유효하지 않은 값이 포함되어 있습니다. 다른 파일로 시도해주세요.",
                )

            eng = get_engine()
            t1 = time.perf_counter()
            try:
                hits, _q_scaled = await run_in_threadpool(eng.find_similar, features, top_n=top_n)
            except Exception as e:  # noqa: BLE001
                logger.exception("similarity_failed", extra={"request_id": request_id})
                raise HTTPException(
                    status_code=500, detail="유사도 계산에 실패했습니다."
                ) from e
            similarity_seconds = time.perf_counter() - t1

            if hits and hits[0].similarity < 0:
                # Defensive — if the top match is negative, something is
                # numerically off (e.g. all-NaN catalog row). Log loudly.
                logger.error(
                    "negative_top_similarity",
                    extra={"request_id": request_id, "top": hits[0].similarity},
                )

            results: list[dict] = []
            from .audio_features import AudioFeatureVector

            for hit in hits:
                catalog_full_name = f"{hit.name} - {hit.artist}"
                catalog_raw = eng.catalog_row_raw(catalog_full_name) or {}
                report = explain_match(
                    query_raw=features.values,
                    catalog_raw=catalog_raw,
                    distances_scaled=hit.feature_distances,
                )

                # Reuse summary_metrics on the catalog row so the radar chart
                # has comparable axes for query vs. each hit.
                if catalog_raw:
                    # `length` may not be present in feature_columns; provide a
                    # safe default so summary_metrics never KeyErrors.
                    safe_catalog = dict(catalog_raw)
                    safe_catalog.setdefault("length", 0.0)
                    match_summary = summary_metrics(
                        AudioFeatureVector(name=catalog_full_name, values=safe_catalog)
                    )
                else:
                    match_summary = None

                results.append(
                    {
                        "rank": hit.rank,
                        "title": hit.name,
                        "artist": hit.artist,
                        "similarity": hit.similarity,
                        "similarity_percent": hit.similarity_percent,
                        "youtube_search_url": _youtube_search_url(hit.name, hit.artist),
                        "spotify_search_url": _spotify_search_url(hit.name, hit.artist),
                        "match_summary": match_summary,
                        "reason": report_to_dict(report),
                    }
                )

            logger.info(
                "analyze_done",
                extra={
                    "request_id": request_id,
                    "filename_ext": ext,
                    "bytes": written,
                    "feature_seconds": round(feature_seconds, 3),
                    "similarity_seconds": round(similarity_seconds, 3),
                    "top_sim": round(hits[0].similarity, 4) if hits else None,
                    "top_n": top_n,
                },
            )

            return JSONResponse(
                {
                    "request_id": request_id,
                    "filename": safe_name,
                    "summary": summary_metrics(features),
                    "results": results,
                    "timing": {
                        "feature_extraction_seconds": round(feature_seconds, 3),
                        "similarity_seconds": round(similarity_seconds, 3),
                    },
                    "catalog_size": eng.catalog_size,
                }
            )
    finally:
        # Force-cleanup synchronously too, so disk is freed before the
        # background task runs (covers cases where the task is cancelled).
        _cleanup(dest)


def _youtube_search_url(title: str, artist: str) -> str:
    import urllib.parse

    q = urllib.parse.quote_plus(f"{title} {artist}")
    return f"https://www.youtube.com/results?search_query={q}"


def _spotify_search_url(title: str, artist: str) -> str:
    import urllib.parse

    q = urllib.parse.quote_plus(f"{title} {artist}")
    return f"https://open.spotify.com/search/{q}"


# ----------------------------------------------------------------------
# Frontend (static)
# ----------------------------------------------------------------------
def _cached_file_response(path: Path, *, immutable: bool = False) -> FileResponse:
    """Serve a file with a sensible Cache-Control header.

    immutable=True is for fingerprinted/static assets that never change;
    other paths get a short revalidation window.
    """
    if immutable:
        cache = "public, max-age=31536000, immutable"
    else:
        cache = "public, max-age=300, must-revalidate"
    return FileResponse(str(path), headers={"Cache-Control": cache})


if FRONTEND_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="static",
    )

    @app.get("/", include_in_schema=False)
    def index():
        index_html = FRONTEND_DIR / "index.html"
        if not index_html.exists():
            raise HTTPException(status_code=404, detail="Frontend not built.")
        return _cached_file_response(index_html, immutable=False)

    # Asset shortcuts so the HTML can write <link href="/style.css"> etc.
    @app.get("/style.css", include_in_schema=False)
    def style_css():
        return _cached_file_response(FRONTEND_DIR / "css" / "style.css")

    @app.get("/app.js", include_in_schema=False)
    def app_js():
        return _cached_file_response(FRONTEND_DIR / "js" / "app.js")

    @app.get("/i18n.js", include_in_schema=False)
    def i18n_js():
        return _cached_file_response(FRONTEND_DIR / "js" / "i18n.js")

    @app.get("/visualizers.js", include_in_schema=False)
    def visualizers_js():
        return _cached_file_response(FRONTEND_DIR / "js" / "visualizers.js")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon():
        return _cached_file_response(FRONTEND_DIR / "assets" / "favicon.svg", immutable=True)

    @app.get("/robots.txt", include_in_schema=False)
    def robots():
        return Response(
            "User-agent: *\nAllow: /\n",
            media_type="text/plain",
            headers={"Cache-Control": "public, max-age=86400"},
        )
