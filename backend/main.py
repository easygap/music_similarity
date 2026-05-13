"""FastAPI 진입점.

정적 프론트엔드를 서빙하면서 음악 유사도 API를 노출한다.

엔드포인트
---------
GET  /              -> 프론트엔드 index.html
GET  /api/catalog   -> 카탈로그 크기 + 사용 중인 특성 컬럼
POST /api/analyze   -> 멀티파트 업로드 후 유사도 순위 반환
GET  /api/health    -> 라이브니스 프로브
GET  /sitemap.xml   -> SEO용 사이트맵
GET  /robots.txt    -> 검색 봇 정책
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
import uuid
from collections.abc import Iterable
from contextlib import asynccontextmanager
from datetime import UTC
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

from .audio_features import AudioFeatureVector, extract_features, summary_metrics
from .cache import AnalysisResultCache
from .reason_engine import explain_match, report_to_dict
from .schemas import AnalyzeResponse, CatalogResponse, HealthResponse
from .similarity import MusicSimilarityEngine
from .spectrogram import build_mel_spectrogram_svg
from .tagging import derive_tags

# ----------------------------------------------------------------------
# 경로 / 설정
# ----------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = Path(os.environ.get("MUSIC_DATASET_PATH", ROOT / "data" / "dataset.csv"))
FRONTEND_DIR = Path(os.environ.get("MUSIC_FRONTEND_DIR", ROOT / "frontend"))
UPLOAD_DIR = Path(os.environ.get("MUSIC_UPLOAD_DIR", ROOT / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
MAX_UPLOAD_BYTES = int(os.environ.get("MUSIC_MAX_UPLOAD_BYTES", 25 * 1024 * 1024))  # 25 MB

# 매직 바이트 시그니처. 확장자만 믿고 받지 않도록 첫 16바이트와 대조한다.
# (sig_bytes, accepted_extensions)
_MAGIC_SIGNATURES: list[tuple[bytes, frozenset[str]]] = [
    (b"RIFF", frozenset({".wav"})),
    (b"ID3", frozenset({".mp3"})),
    (b"\xff\xfb", frozenset({".mp3"})),
    (b"\xff\xf3", frozenset({".mp3"})),
    (b"\xff\xf2", frozenset({".mp3"})),
    (b"fLaC", frozenset({".flac"})),
    (b"OggS", frozenset({".ogg"})),
    # MP4/M4A 컨테이너는 offset 4의 'ftyp' 박스로 검출(아래 _sniff_audio 참고)
]

ENV = os.environ.get("MUSIC_ENV", "development")
ALLOWED_ORIGINS_ENV = os.environ.get("MUSIC_ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS: list[str] = (
    [o.strip() for o in ALLOWED_ORIGINS_ENV.split(",") if o.strip()]
    if ALLOWED_ORIGINS_ENV
    else (["*"] if ENV != "production" else [])
)

# librosa 디코드는 CPU bound 이라 threadpool로 빠지더라도 한 클라이언트가
# 스레드를 무제한 소비하면 다른 요청이 죽는다. 동시 분석 수를 제한한다.
MAX_CONCURRENT_ANALYSES = int(os.environ.get("MUSIC_MAX_CONCURRENT", 4))
_analysis_semaphore = asyncio.Semaphore(MAX_CONCURRENT_ANALYSES)

# 간단한 in-process rate limiter (IP별 sliding window).
# 트래픽이 더 커지면 redis 백엔드 limiter 로 옮기는 게 좋음.
RATE_LIMIT_PER_MIN = int(os.environ.get("MUSIC_RATE_LIMIT_PER_MIN", 12))
_rate_state: dict[str, list[float]] = {}
_rate_lock = asyncio.Lock()

# 분석 결과 캐시 — 같은 파일을 두 번 올리면 즉시 응답.
# raw 음원은 보관하지 않고 SHA-256 해시만 키로 쓴다.
CACHE_TTL_SECONDS = int(os.environ.get("MUSIC_CACHE_TTL_SECONDS", 600))
CACHE_MAX_ENTRIES = int(os.environ.get("MUSIC_CACHE_MAX_ENTRIES", 64))
_result_cache = AnalysisResultCache(
    max_entries=CACHE_MAX_ENTRIES,
    ttl_seconds=CACHE_TTL_SECONDS,
)

logger = logging.getLogger("music_similarity")

# ----------------------------------------------------------------------
# Observability — Prometheus 호환 간단한 인-프로세스 카운터/게이지.
# 라이브러리 의존성을 더 늘리지 않으려고 직접 작성한다.
# (단일 워커에서만 정확하다. 여러 worker 환경에선 별도 exporter 필요.)
# ----------------------------------------------------------------------
_metrics_counters: dict[str, int] = {
    "soundmatch_requests_total": 0,
    "soundmatch_analyze_success_total": 0,
    "soundmatch_analyze_failed_total": 0,
    "soundmatch_rate_limited_total": 0,
    "soundmatch_cache_hits_total": 0,
    "soundmatch_cache_misses_total": 0,
}

# 현재 동시에 처리 중인 분석 요청 수. 게이지로 노출.
_inflight_analyses = 0
_inflight_lock = threading.Lock()

# 프로세스 부팅 시각. health/metrics uptime 계산용.
_started_at = time.monotonic()

# 최근 N 건 분석 latency (초). ring buffer 로 들고 있다가 P50/P95 노출.
# 단순한 in-process 추적이라 worker 별로 분리됨 — 큰 트래픽이면 Prometheus
# histogram 으로 옮겨야 하지만, 현재 규모에선 이 정도로 충분.
_latency_buffer: list[float] = []
_latency_buffer_max = 256
_latency_lock = threading.Lock()


def _record_latency(seconds: float) -> None:
    with _latency_lock:
        _latency_buffer.append(seconds)
        if len(_latency_buffer) > _latency_buffer_max:
            # 가장 오래된 샘플부터 버린다. list 슬라이싱이 가장 단순.
            del _latency_buffer[: len(_latency_buffer) - _latency_buffer_max]


def _latency_percentile(p: float) -> float:
    """샘플이 있으면 p 분위수(0.0~1.0)를 반환. 없으면 0."""
    with _latency_lock:
        if not _latency_buffer:
            return 0.0
        s = sorted(_latency_buffer)
        idx = max(0, min(len(s) - 1, int(round(p * (len(s) - 1)))))
        return s[idx]


def _bump(name: str, delta: int = 1) -> None:
    _metrics_counters[name] = _metrics_counters.get(name, 0) + delta

# ----------------------------------------------------------------------
# 엔진 — CSV가 깨져 있어도 worker 시작은 살아있게 lazy 로딩한다
# ----------------------------------------------------------------------
_engine: MusicSimilarityEngine | None = None


def get_engine() -> MusicSimilarityEngine:
    """엔진 싱글톤 접근자. 최초 호출 시점에 카탈로그를 로딩한다."""
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
    # 애플리케이션 부팅 시 한 번만 로깅을 구성.
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=os.environ.get("MUSIC_LOG_LEVEL", "INFO"),
            format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
        )
    # 부팅 시점에 카탈로그 로딩을 시도해본다. 실패해도 worker 자체는 죽이지 않음
    # (health 가 503을 돌려주도록 함).
    try:
        get_engine()
    except Exception:  # noqa: BLE001
        logger.exception("engine_load_failed")

    # librosa / sklearn / numba JIT 워밍업.
    # 첫 사용자 분석이 1.5~2초 걸리는 이유의 상당 부분이 BLAS / numba 첫 호출이라
    # 부팅 시점에 짧은 더미 신호 한 번 흘려두면 첫 응답이 빨라진다.
    # MUSIC_SKIP_WARMUP=1 환경변수로 비활성화 가능 (테스트나 cold-start 측정용).
    if os.environ.get("MUSIC_SKIP_WARMUP") != "1":
        try:
            # 0.4초 짜리 사인파를 임시 파일에 써서 extract_features 한 바퀴 돌려둔다.
            # 호출 자체로 librosa 가 로드되고 numba JIT 가 워밍된다.
            await run_in_threadpool(_warmup_pipeline)
            logger.info("warmup_done")
        except Exception:  # noqa: BLE001
            logger.exception("warmup_failed")

    yield


def _warmup_pipeline() -> None:
    """librosa / numba JIT 를 짧은 사인파로 미리 돌려둔다.

    여기서 발생한 예외는 lifespan 에서 잡아 로그만 남기고 무시한다 — 워밍업
    실패가 서비스 자체를 막아선 안 된다.
    """
    import math
    import wave

    import numpy as np

    from .audio_features import extract_features

    sr = 22050
    duration = 0.4
    nframes = int(sr * duration)
    tmp = UPLOAD_DIR / ".warmup.wav"
    try:
        with wave.open(str(tmp), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            frames = bytearray()
            for n in range(nframes):
                v = int(8000 * math.sin(2 * math.pi * 330 * n / sr))
                frames.extend(v.to_bytes(2, "little", signed=True))
            w.writeframes(bytes(frames))
        # 결과는 버린다. 임포트 + JIT + BLAS 한 번씩만 돌려보는 게 목적.
        _ = extract_features(tmp, max_duration=duration)
        # numpy / similarity 도 한 번 가볍게 두드린다.
        _ = np.linalg.norm(np.zeros(8))
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


# ----------------------------------------------------------------------
# FastAPI 앱
# ----------------------------------------------------------------------
app = FastAPI(
    title="SoundMatch · Music Similarity API",
    description="음원을 업로드하면 카탈로그에서 가장 닮은 곡을 찾아 순위와 함께 돌려준다.",
    version="1.3.0",
    lifespan=lifespan,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """모든 응답에 시큐어 헤더를 일괄 적용한다."""

    CSP = (
        "default-src 'self'; "
        # 인라인 SW 등록 + 글로벌 에러 boundary 가 index.html 에 inline script 로
        # 들어 있어 'unsafe-inline' 이 필요. 외부 JS 는 같은 출처만 허용한다.
        "script-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        "media-src 'self' blob:; "
        "connect-src 'self'; "
        "worker-src 'self'; "
        "manifest-src 'self'; "
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
        # CSP는 HTML 응답에만. JSON/SVG 등에 끼우면 데브툴에서 시끄러워진다.
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers.setdefault("Content-Security-Policy", self.CSP)
        if ENV == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


class RequestLogMiddleware(BaseHTTPMiddleware):
    """요청별로 request_id 를 부여하고 종료 후 구조화된 로그를 남긴다.

    rate-limit 정보가 request.state 에 들어있으면 응답 헤더에도 전파한다.
    """

    async def dispatch(self, request: Request, call_next):
        # 클라이언트가 보낸 X-Request-ID가 있으면 그대로 사용 (분산 추적용).
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        t0 = time.perf_counter()
        # /metrics 같은 운영 경로는 카운터에 안 잡는다 (의미 없는 노이즈).
        is_business = not request.url.path.startswith(("/metrics", "/sw.js"))
        if is_business:
            _bump("soundmatch_requests_total")
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
        # rate-limit 메타데이터가 의존성에서 채워졌으면 응답에 함께 노출.
        rl = getattr(request.state, "rate_limit", None)
        if rl:
            response.headers["X-RateLimit-Limit"] = str(rl["limit"])
            response.headers["X-RateLimit-Remaining"] = str(rl["remaining"])
            response.headers["X-RateLimit-Reset"] = str(rl["reset"])
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

# CORS: 프로덕션에서 명시적 origin이 없으면 미들웨어 자체를 끼우지 않는다.
# 같은 origin 요청은 CORS 미들웨어 없이도 동작.
if ALLOWED_ORIGINS:
    # 와일드카드 origin과 credentials 조합은 브라우저가 거부하므로 차단.
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
# 보조 함수
# ----------------------------------------------------------------------
def _client_ip(request: Request) -> str:
    """리버스 프록시 뒤에 있을 수 있으니 X-Forwarded-For 의 첫 IP를 우선 사용."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


async def _rate_limit(request: Request) -> None:
    """IP별 sliding-window rate limiter (RATE_LIMIT_PER_MIN / 60s).

    제한에 안 걸린 요청에 대해서는 ``request.state.rate_limit`` 에 limit /
    remaining / reset 정보를 채워둔다. RequestLogMiddleware 가 이걸 응답
    헤더로 노출한다.
    """
    ip = _client_ip(request)
    now = time.time()
    window = 60.0
    async with _rate_lock:
        history = _rate_state.setdefault(ip, [])
        # 윈도우 밖의 오래된 항목은 정리.
        cutoff = now - window
        history[:] = [t for t in history if t > cutoff]
        if len(history) >= RATE_LIMIT_PER_MIN:
            retry = window - (now - history[0])
            _bump("soundmatch_rate_limited_total")
            reset_at = int(history[0] + window)
            raise HTTPException(
                status_code=429,
                detail=f"요청이 너무 잦습니다. 약 {int(retry) + 1}초 뒤에 다시 시도해주세요.",
                headers={
                    "Retry-After": str(int(retry) + 1),
                    "X-RateLimit-Limit": str(RATE_LIMIT_PER_MIN),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                },
            )
        history.append(now)
        remaining = max(0, RATE_LIMIT_PER_MIN - len(history))
        reset_at = int((history[0] if history else now) + window)
        request.state.rate_limit = {
            "limit": RATE_LIMIT_PER_MIN,
            "remaining": remaining,
            "reset": reset_at,
        }


def _sniff_audio(head: bytes, ext: str) -> bool:
    """첫 바이트로 실제 오디오 컨테이너인지 가볍게 확인한다."""
    if len(head) < 4:
        return False
    for sig, accepted in _MAGIC_SIGNATURES:
        if head.startswith(sig) and ext in accepted:
            return True
    # MP4/M4A: 4바이트 size + 'ftyp' 박스 헤더
    if ext == ".m4a" and len(head) >= 12 and head[4:8] == b"ftyp":
        return True
    return False


def _safe_filename(name: str | None) -> str:
    """디렉토리 구분자와 NUL 같은 위험 문자를 잘라낸 표시용 파일명."""
    if not name:
        return "upload"
    base = os.path.basename(name).replace("\x00", "")
    return base[:200] or "upload"


def _all_finite(values: Iterable[float]) -> bool:
    """반복자의 모든 값이 finite 인지 확인."""
    arr = np.asarray(list(values), dtype=float)
    return bool(np.isfinite(arr).all())


# ----------------------------------------------------------------------
# 라우트
# ----------------------------------------------------------------------
@app.api_route(
    "/api/health",
    methods=["GET", "HEAD"],
    response_model=HealthResponse,
    summary="라이브니스 / 카탈로그 로딩 상태",
    tags=["system"],
    operation_id="health",
)
def health(strict: bool = Query(False, description="True 면 librosa/sklearn 임포트 + 업로드 디렉토리 쓰기까지 검사")):  # noqa: B008
    """라이브니스 프로브.

    기본 모드는 카탈로그가 메모리에 떠 있는지만 확인한다. ``strict=true``
    이면 librosa/sklearn 임포트가 가능한지, 업로드 디렉토리에 쓰기 권한이
    있는지까지 점검한다 — Render/Fly 같은 PaaS 에 readiness probe 로 쓸 만하다.
    """
    uptime = round(time.monotonic() - _started_at, 1)
    try:
        size = get_engine().catalog_size
    except Exception:  # noqa: BLE001
        return JSONResponse(
            {
                "status": "degraded",
                "catalog_size": 0,
                "env": ENV,
                "version": app.version,
                "uptime_seconds": uptime,
            },
            status_code=503,
        )

    if strict:
        # librosa / sklearn 이 정말로 임포트 되는지 확인. 무거운 워밍업까진 안 함.
        try:
            import librosa  # noqa: F401
            import sklearn  # noqa: F401
        except Exception:  # noqa: BLE001
            return JSONResponse(
                {
                    "status": "degraded",
                    "catalog_size": size,
                    "env": ENV,
                    "version": app.version,
                    "uptime_seconds": uptime,
                },
                status_code=503,
            )
        # 업로드 디렉토리에 임시 파일 쓰기 / 삭제까지 가능한지.
        probe = UPLOAD_DIR / f".healthcheck-{uuid.uuid4().hex}"
        try:
            probe.write_bytes(b"ok")
            probe.unlink()
        except OSError:
            return JSONResponse(
                {
                    "status": "degraded",
                    "catalog_size": size,
                    "env": ENV,
                    "version": app.version,
                    "uptime_seconds": uptime,
                },
                status_code=503,
            )

    return {
        "status": "ok",
        "catalog_size": size,
        "env": ENV,
        "version": app.version,
        "uptime_seconds": uptime,
    }


@app.get(
    "/api/catalog",
    response_model=CatalogResponse,
    summary="카탈로그 메타데이터",
    tags=["system"],
)
def catalog_info():
    """카탈로그 크기와 사용 중인 특성 컬럼을 돌려준다."""
    eng = get_engine()
    return {
        "catalog_size": eng.catalog_size,
        "feature_count": len(eng.feature_columns),
        "features": eng.feature_columns,
    }


@app.get(
    "/metrics",
    summary="Prometheus exposition (in-process counters)",
    tags=["system"],
    include_in_schema=False,
)
def metrics():
    """Prometheus 호환 텍스트 노출. 외부 라이브러리 없이 직접 직렬화한다.

    단일 worker 환경에서만 정확한 값. 다중 worker 라면 결과가 worker 별로
    파편화되므로 push gateway 또는 statsd exporter 같은 별도 솔루션이 필요.
    """
    try:
        catalog_size = get_engine().catalog_size
    except Exception:  # noqa: BLE001
        catalog_size = 0

    lines: list[str] = []
    # Counter 들 — 누적값, monotonic.
    counter_help = {
        "soundmatch_requests_total": "전체 비즈니스 HTTP 요청 수",
        "soundmatch_analyze_success_total": "분석이 성공한 횟수 (캐시 히트 포함)",
        "soundmatch_analyze_failed_total": "분석이 실패한 횟수 (4xx/5xx)",
        "soundmatch_rate_limited_total": "rate limit 으로 차단된 요청 수",
        "soundmatch_cache_hits_total": "결과 캐시 히트 — librosa 재실행 안 한 케이스",
        "soundmatch_cache_misses_total": "결과 캐시 미스 — 새로 분석한 케이스",
    }
    for name, doc in counter_help.items():
        lines.append(f"# HELP {name} {doc}")
        lines.append(f"# TYPE {name} counter")
        lines.append(f"{name} {_metrics_counters.get(name, 0)}")

    # Gauge: 현재 카탈로그 사이즈, 현재 캐시 항목 수.
    lines.append("# HELP soundmatch_catalog_size 현재 메모리에 적재된 카탈로그 곡 수")
    lines.append("# TYPE soundmatch_catalog_size gauge")
    lines.append(f"soundmatch_catalog_size {catalog_size}")
    lines.append("# HELP soundmatch_cache_entries 현재 결과 캐시에 들어 있는 항목 수")
    lines.append("# TYPE soundmatch_cache_entries gauge")
    lines.append(f"soundmatch_cache_entries {_result_cache.size}")
    with _inflight_lock:
        inflight = _inflight_analyses
    lines.append("# HELP soundmatch_inflight_analyses 지금 동시 처리 중인 분석 수")
    lines.append("# TYPE soundmatch_inflight_analyses gauge")
    lines.append(f"soundmatch_inflight_analyses {inflight}")

    uptime = round(time.monotonic() - _started_at, 3)
    lines.append("# HELP soundmatch_uptime_seconds 프로세스 부팅 후 경과 시간(초)")
    lines.append("# TYPE soundmatch_uptime_seconds gauge")
    lines.append(f"soundmatch_uptime_seconds {uptime}")

    # 분석 latency 분포 — ring buffer 기반 P50/P95.
    p50 = round(_latency_percentile(0.50), 4)
    p95 = round(_latency_percentile(0.95), 4)
    lines.append(
        "# HELP soundmatch_analyze_latency_p50_seconds 최근 분석 latency P50(초)"
    )
    lines.append("# TYPE soundmatch_analyze_latency_p50_seconds gauge")
    lines.append(f"soundmatch_analyze_latency_p50_seconds {p50}")
    lines.append(
        "# HELP soundmatch_analyze_latency_p95_seconds 최근 분석 latency P95(초)"
    )
    lines.append("# TYPE soundmatch_analyze_latency_p95_seconds gauge")
    lines.append(f"soundmatch_analyze_latency_p95_seconds {p95}")

    body = "\n".join(lines) + "\n"
    return Response(
        body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@app.get(
    "/api/catalog/sample",
    summary="카탈로그 일부 미리보기",
    tags=["system"],
)
def catalog_sample(limit: int = Query(12, ge=1, le=50)):  # noqa: B008
    """카탈로그에 어떤 곡들이 들어 있는지 사용자가 가볍게 훑어볼 수 있게 일부만 반환.

    랜덤이 아니라 사전식 정렬 기준 앞쪽을 그대로 돌려준다 — 매번 같은 결과가
    나오므로 캐시도 잘 먹고 사용자가 "또 봐도 같은 곡들이 있다" 는 신뢰감을 받는다.
    """
    eng = get_engine()
    names = eng.iter_catalog_names()[:limit]
    items = [_split_catalog_name(n) for n in names]
    return JSONResponse(
        {"total": eng.catalog_size, "items": items},
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get(
    "/api/catalog/random",
    summary="카탈로그에서 무작위 곡 추천",
    tags=["system"],
)
def catalog_random(n: int = Query(6, ge=1, le=24)):  # noqa: B008
    """카탈로그에서 N곡을 무작위로 뽑아 돌려준다.

    프론트엔드 메인 페이지의 "카탈로그 미리보기" 새로고침 버튼이 이 엔드포인트를
    호출한다. 매번 다른 결과라서 캐시는 짧게 (60초).
    """
    import random

    eng = get_engine()
    names = eng.iter_catalog_names()
    if not names:
        return JSONResponse({"total": 0, "items": []})
    picked = random.sample(names, k=min(n, len(names)))
    items = [_split_catalog_name(n) for n in picked]
    return JSONResponse(
        {"total": eng.catalog_size, "items": items},
        headers={"Cache-Control": "public, max-age=60"},
    )


@app.get(
    "/api/catalog/search",
    summary="카탈로그 검색 + 페이지네이션",
    tags=["system"],
)
def catalog_search(
    q: str = Query("", description="제목/아티스트 부분 일치(대소문자 무시). 빈 값이면 전체 목록."),  # noqa: B008
    page: int = Query(1, ge=1, le=10_000),  # noqa: B008
    size: int = Query(24, ge=1, le=100),  # noqa: B008
):
    """카탈로그 곡 목록을 검색/페이지네이션 형태로 돌려준다.

    매번 카탈로그 전체를 메모리에서 필터링한다. 곡 수가 십수만 이상으로
    커지면 별도 인덱스(예: SQLite FTS) 가 필요하지만, 현재 1000곡 규모에선
    이 정도로 충분히 빠르다.
    """
    eng = get_engine()
    needle = (q or "").strip().lower()
    names = eng.iter_catalog_names()
    if needle:
        names = [n for n in names if needle in n.lower()]
    total = len(names)
    start = (page - 1) * size
    end = start + size
    items = [_split_catalog_name(n) for n in names[start:end]]
    return JSONResponse(
        {
            "total": total,
            "page": page,
            "size": size,
            "has_more": end < total,
            "items": items,
        },
        headers={"Cache-Control": "public, max-age=120"},
    )


def _split_catalog_name(full: str) -> dict[str, str]:
    """"곡명 - 아티스트" 키를 title/artist 딕셔너리로 안전 분리."""
    title, _, artist = full.partition(" - ")
    return {"title": title.strip() or full, "artist": artist.strip() or "Unknown"}


@app.get(
    "/api/analyze/by-catalog",
    summary="카탈로그 내 곡끼리 즉시 비교 (librosa 호출 없음)",
    tags=["analysis"],
)
def analyze_by_catalog(
    name: str = Query(..., min_length=1, max_length=400, description="카탈로그 곡 키 ('곡명 - 아티스트' 형식)"),  # noqa: B008
    top_n: int = Query(5, ge=1, le=20),  # noqa: B008
):
    """카탈로그에 이미 있는 곡 이름을 받아서 그 곡의 raw 특성으로 분석을 돌린다.

    파일 업로드도 librosa 호출도 없으므로 ``/api/analyze`` 보다 훨씬 빠르다.
    카탈로그 페이지에서 "이 곡과 비슷한 다른 곡 보기" 액션을 위해 만들었다.
    """
    eng = get_engine()
    raw = eng.catalog_row_raw(name)
    if raw is None:
        raise HTTPException(status_code=404, detail="카탈로그에서 해당 곡을 찾을 수 없습니다.")

    features = AudioFeatureVector(name=name, values=raw)
    hits, _ = eng.find_similar(features, top_n=top_n + 1)
    # 1위는 자기 자신이라 제외하고 top_n 개만 노출. rank 도 1부터 다시 매긴다.
    filtered = [h for h in hits if f"{h.name} - {h.artist}" != name][:top_n]

    results: list[dict] = []
    for idx, hit in enumerate(filtered, start=1):
        full = f"{hit.name} - {hit.artist}"
        cat_raw = eng.catalog_row_raw(full) or {}
        report = explain_match(
            query_raw=features.values,
            catalog_raw=cat_raw,
            distances_scaled=hit.feature_distances,
        )
        if cat_raw:
            safe_cat = dict(cat_raw)
            safe_cat.setdefault("length", 0.0)
            match_summary = summary_metrics(AudioFeatureVector(name=full, values=safe_cat))
        else:
            match_summary = None
        results.append({
            "rank": idx,
            "title": hit.name,
            "artist": hit.artist,
            "similarity": hit.similarity,
            "similarity_percent": hit.similarity_percent,
            "youtube_search_url": _youtube_search_url(hit.name, hit.artist),
            "spotify_search_url": _spotify_search_url(hit.name, hit.artist),
            "match_summary": match_summary,
            "reason": report_to_dict(report),
        })

    title, _, artist = name.partition(" - ")
    return JSONResponse(
        {
            "source": "catalog",
            "name": name,
            "title": title.strip() or name,
            "artist": artist.strip() or "Unknown",
            "summary": summary_metrics(features),
            "tags": derive_tags(features),
            "results": results,
            "catalog_size": eng.catalog_size,
            "engine_version": app.version,
        },
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.post(
    "/api/analyze",
    dependencies=[Depends(_rate_limit)],
    response_model=AnalyzeResponse,
    summary="음원 업로드 + 유사도 분석",
    tags=["analysis"],
)
async def analyze(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),  # noqa: B008 — FastAPI 의존성 주입 패턴
    top_n: int = Query(5, ge=1, le=20),  # noqa: B008
):
    """업로드된 음원을 분석해 상위 N개 유사 곡을 반환한다."""
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
    safe_name = _safe_filename(file.filename)
    ext = Path(safe_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. ({', '.join(sorted(ALLOWED_EXTENSIONS))})",
        )

    # 클라이언트가 Content-Length 를 보내면 사전에 거른다. 25MB 초과면 디스크 I/O
    # 자체를 일으키지 않음. 약간의 여유(+4KB)는 multipart 헤더 분량.
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_UPLOAD_BYTES + 4096:
        raise HTTPException(
            status_code=413,
            detail=f"파일이 너무 큽니다. 최대 {MAX_UPLOAD_BYTES // (1024*1024)}MB.",
        )

    dest = UPLOAD_DIR / f"{request_id}{ext}"

    # 핸들러가 어떤 식으로 끝나더라도 임시 파일은 지운다.
    def _cleanup(path: Path) -> None:
        try:
            os.remove(path)
        except OSError:
            pass

    background_tasks.add_task(_cleanup, dest)

    # in-flight 카운터를 증가/감소하기 위해 함수 진입 직후에 global 선언.
    global _inflight_analyses

    try:
        async with _analysis_semaphore:
            # in-flight 카운터 증가. /metrics 에서 게이지로 노출된다.
            with _inflight_lock:
                _inflight_analyses += 1
            # 스트리밍 업로드. 누적 사이즈를 체크하면서 첫 16바이트로 매직 시그니처를 확인한다.
            # 동시에 SHA-256 해시도 계산해서 결과 캐시 키로 쓴다 — raw 바이트는 저장 안 함.
            import hashlib

            hasher = hashlib.sha256()
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
                    hasher.update(chunk)
                    out.write(chunk)
            if written == 0:
                raise HTTPException(status_code=400, detail="빈 파일입니다.")
            if not _sniff_audio(head_bytes, ext):
                raise HTTPException(
                    status_code=400,
                    detail="파일 내용이 오디오 형식과 일치하지 않습니다. 확장자를 확인해주세요.",
                )

            # 결과 캐시 hit 이면 librosa/sklearn 다 건너뛰고 바로 응답.
            cache_key = _result_cache.make_key(hasher.hexdigest(), top_n)
            cached_value = _result_cache.get(cache_key)
            if cached_value is not None:
                _bump("soundmatch_cache_hits_total")
                _bump("soundmatch_analyze_success_total")
                # 동적 필드만 새 요청용으로 교체. 나머지는 그대로 재사용.
                payload = dict(cached_value)
                payload["request_id"] = request_id
                payload["filename"] = safe_name
                payload["cached"] = True
                logger.info(
                    "analyze_cache_hit",
                    extra={
                        "request_id": request_id,
                        "filename_ext": ext,
                        "bytes": written,
                    },
                )
                return JSONResponse(payload)
            _bump("soundmatch_cache_misses_total")

            # librosa.load 는 동기/CPU bound 이므로 threadpool 로 넘긴다.
            # 이벤트 루프를 점유하면 health 체크나 다른 정적 파일 요청도 같이 막힌다.
            t0 = time.perf_counter()
            try:
                features = await run_in_threadpool(extract_features, dest)
            except HTTPException:
                raise
            except (ValueError, RuntimeError) as e:
                # 손상된 오디오/너무 짧은 파일 등에서 librosa 가 던지는 오류들.
                _bump("soundmatch_analyze_failed_total")
                logger.warning(
                    "feature_extraction_failed",
                    extra={"request_id": request_id, "error": str(e)},
                )
                raise HTTPException(
                    status_code=400,
                    detail="오디오 분석에 실패했습니다. 손상된 파일이거나 너무 짧을 수 있습니다.",
                ) from e
            except Exception as e:  # noqa: BLE001
                # 그 외 예외는 내부 오류로 처리. 자세한 traceback 은 서버 로그로.
                _bump("soundmatch_analyze_failed_total")
                logger.exception(
                    "feature_extraction_crashed",
                    extra={"request_id": request_id},
                )
                raise HTTPException(
                    status_code=500, detail="서버 내부 오류가 발생했습니다."
                ) from e
            feature_seconds = time.perf_counter() - t0

            if not _all_finite(features.values.values()):
                # NaN/Inf 가 섞이면 코사인 유사도가 깨지므로 분석 진행 차단.
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
                _bump("soundmatch_analyze_failed_total")
                logger.exception("similarity_failed", extra={"request_id": request_id})
                raise HTTPException(
                    status_code=500, detail="유사도 계산에 실패했습니다."
                ) from e
            similarity_seconds = time.perf_counter() - t1

            if hits and hits[0].similarity < 0:
                # 1위 유사도가 음수면 카탈로그가 의심스러운 상태(예: NaN 행 통과).
                # 사용자에게는 그대로 보여주되 운영 로그에 큰 소리로 남긴다.
                logger.error(
                    "negative_top_similarity",
                    extra={"request_id": request_id, "top": hits[0].similarity},
                )

            # 결과 직렬화. match_summary 는 레이더 차트에 쓰려고 함께 내려준다.
            results: list[dict] = []
            for hit in hits:
                catalog_full_name = f"{hit.name} - {hit.artist}"
                catalog_raw = eng.catalog_row_raw(catalog_full_name) or {}
                report = explain_match(
                    query_raw=features.values,
                    catalog_raw=catalog_raw,
                    distances_scaled=hit.feature_distances,
                )

                # summary_metrics 는 length 키를 참조하므로 안전 디폴트를 채워둔다.
                if catalog_raw:
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

            # 보너스: 멜 스펙트로그램 SVG. 시각화 실패는 분석 자체를 막지 않는다.
            try:
                spectrogram_svg = await run_in_threadpool(build_mel_spectrogram_svg, dest)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "spectrogram_failed",
                    extra={"request_id": request_id},
                )
                spectrogram_svg = ""

            # 휴리스틱 태그 (예: 빠른 템포 / 에너지 폭발 / 밝은 톤).
            tags = derive_tags(features)

            _bump("soundmatch_analyze_success_total")
            _record_latency(feature_seconds + similarity_seconds)
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
                    "has_spectrogram": bool(spectrogram_svg),
                    "tags": tags,
                },
            )

            from datetime import datetime

            payload = {
                "request_id": request_id,
                "filename": safe_name,
                "summary": summary_metrics(features),
                "tags": tags,
                "results": results,
                "timing": {
                    "feature_extraction_seconds": round(feature_seconds, 3),
                    "similarity_seconds": round(similarity_seconds, 3),
                },
                "catalog_size": eng.catalog_size,
                "spectrogram_svg": spectrogram_svg,
                "analyzed_at": datetime.now(UTC).isoformat(),
                "engine_version": app.version,
                "cached": False,
            }
            # 다음 같은 파일 업로드를 위해 캐시에 저장. request_id 같은 동적 필드는
            # 캐시에서 꺼낼 때 새로 갈아낀다 (위쪽 cache hit 분기 참고).
            _result_cache.set(cache_key, payload)
            return JSONResponse(payload)
    finally:
        # 동기적으로 한 번 더 정리. BackgroundTask 가 취소된 경우 대비.
        _cleanup(dest)
        # in-flight 카운터 차감. 0 미만으로는 떨어지지 않게 가드.
        with _inflight_lock:
            if _inflight_analyses > 0:
                _inflight_analyses -= 1


def _youtube_search_url(title: str, artist: str) -> str:
    """YouTube 검색 결과 페이지로 향하는 URL 생성."""
    import urllib.parse

    q = urllib.parse.quote_plus(f"{title} {artist}")
    return f"https://www.youtube.com/results?search_query={q}"


def _spotify_search_url(title: str, artist: str) -> str:
    """Spotify 검색 결과 페이지로 향하는 URL 생성."""
    import urllib.parse

    q = urllib.parse.quote_plus(f"{title} {artist}")
    return f"https://open.spotify.com/search/{q}"


# ----------------------------------------------------------------------
# 프론트엔드 정적 서빙
# ----------------------------------------------------------------------
def _cached_file_response(path: Path, *, immutable: bool = False) -> FileResponse:
    """캐시 헤더가 붙은 FileResponse 헬퍼.

    immutable=True 는 파비콘처럼 절대 안 바뀌는 자산용,
    그 외에는 짧게(5분) 잡고 revalidate 시킨다.
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
            raise HTTPException(status_code=404, detail="프론트엔드 빌드 결과를 찾지 못했습니다.")
        return _cached_file_response(index_html, immutable=False)

    # HTML 에서 <link href="/style.css"> 식으로 짧게 쓰기 위한 단축 라우트들.
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

    @app.get("/favorites.js", include_in_schema=False)
    def favorites_js():
        return _cached_file_response(FRONTEND_DIR / "js" / "favorites.js")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon():
        return _cached_file_response(FRONTEND_DIR / "assets" / "favicon.svg", immutable=True)

    @app.get("/og-image.svg", include_in_schema=False)
    def og_image():
        """SNS 공유용 OpenGraph 이미지 (SVG)."""
        return _cached_file_response(FRONTEND_DIR / "assets" / "og-image.svg", immutable=True)

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        """PWA manifest. 홈 화면 추가 + 색상/단축키 메타."""
        return FileResponse(
            str(FRONTEND_DIR / "manifest.webmanifest"),
            media_type="application/manifest+json",
            headers={"Cache-Control": "public, max-age=300, must-revalidate"},
        )

    @app.get("/sw.js", include_in_schema=False)
    def service_worker():
        """SW 자체는 캐싱하지 않는다. 새 버전 배포 시 즉시 반영되어야 함."""
        return FileResponse(
            str(FRONTEND_DIR / "sw.js"),
            media_type="application/javascript",
            headers={"Cache-Control": "no-store", "Service-Worker-Allowed": "/"},
        )

    @app.get("/offline.html", include_in_schema=False)
    def offline_page():
        """SW 캐시 미스 + 네트워크 끊김일 때 보여줄 폴백 페이지."""
        return _cached_file_response(FRONTEND_DIR / "offline.html")

    @app.get("/privacy", include_in_schema=False)
    def privacy_page():
        """개인정보 처리 방침. 시중 서비스 신뢰감을 위해 가시화."""
        return _cached_file_response(FRONTEND_DIR / "privacy.html")

    @app.get("/terms", include_in_schema=False)
    def terms_page():
        """이용 약관."""
        return _cached_file_response(FRONTEND_DIR / "terms.html")

    @app.get("/compare", include_in_schema=False)
    def compare_page():
        """두 분석 결과를 나란히 비교하는 페이지. 데이터는 localStorage 히스토리에서."""
        return _cached_file_response(FRONTEND_DIR / "compare.html")

    @app.get("/catalog", include_in_schema=False)
    def catalog_page():
        """카탈로그 전체를 검색/페이지네이션으로 탐색하는 페이지."""
        return _cached_file_response(FRONTEND_DIR / "catalog.html")

    @app.get("/robots.txt", include_in_schema=False)
    def robots():
        body = "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n"
        return Response(
            body,
            media_type="text/plain",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    @app.get("/sitemap.xml", include_in_schema=False)
    def sitemap():
        """정적으로 노출되는 페이지 전부를 sitemap 에 적어둔다.

        결과 페이지(hash URL) 같은 동적 경로는 SEO 대상이 아니라 제외.
        """
        from datetime import date

        today = date.today().isoformat()
        # (loc, priority, changefreq)
        entries = [
            ("/", "1.0", "weekly"),
            ("/catalog", "0.7", "weekly"),
            ("/compare", "0.6", "monthly"),
            ("/privacy", "0.4", "yearly"),
            ("/terms", "0.4", "yearly"),
        ]
        url_blocks = "".join(
            f"<url><loc>{loc}</loc><lastmod>{today}</lastmod>"
            f"<changefreq>{cf}</changefreq><priority>{pri}</priority></url>"
            for loc, pri, cf in entries
        )
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{url_blocks}"
            "</urlset>"
        )
        return Response(
            body,
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.get("/404", include_in_schema=False)
    def not_found_page():
        """존재하지 않는 경로 처리용 페이지."""
        nf = FRONTEND_DIR / "404.html"
        if nf.exists():
            return FileResponse(
                str(nf),
                status_code=404,
                headers={"Cache-Control": "no-store"},
            )
        return Response("Not Found", status_code=404, media_type="text/plain")
