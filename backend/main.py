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
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from . import __version__
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


def _parse_trusted_proxies(raw: str) -> frozenset[str]:
    """`MUSIC_TRUSTED_PROXIES` 환경변수 파싱.

    콤마 구분 CIDR / 단일 IP 목록을 받아 normalize 한다. 비어 있으면
    빈 집합 → X-Forwarded-For 무시 모드.
    """
    items: set[str] = set()
    for piece in (raw or "").split(","):
        v = piece.strip()
        if v:
            items.add(v)
    return frozenset(items)


# 리버스 프록시 IP 목록. 여기 들어 있는 출발지에서 온 요청만 X-Forwarded-For 를
# 신뢰한다. 빈 값(개발 모드 / 직접 노출) 이면 항상 request.client.host 사용.
TRUSTED_PROXIES: frozenset[str] = _parse_trusted_proxies(
    os.environ.get("MUSIC_TRUSTED_PROXIES", "")
)
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

# 카탈로그 곡끼리 비교(by-catalog) 도 같은 입력이면 결과가 항상 같다 — 가볍게 캐시.
# 키는 (name, top_n). 카탈로그가 바뀌면 어차피 워커가 재시작되므로 invalidation 불필요.
_by_catalog_cache = AnalysisResultCache(
    max_entries=int(os.environ.get("MUSIC_BY_CATALOG_CACHE_MAX", 256)),
    ttl_seconds=int(os.environ.get("MUSIC_BY_CATALOG_CACHE_TTL", 1800)),
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
    "soundmatch_client_errors_total": 0,
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
    version=__version__,
    lifespan=lifespan,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """모든 응답에 시큐어 헤더를 일괄 적용한다."""

    CSP = (
        "default-src 'self'; "
        # 인라인 스크립트는 사용하지 않는다. 같은 출처에서 받은 JS 만 허용.
        "script-src 'self'; "
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
    """진짜 클라이언트 IP 를 식별한다.

    프록시 위조 방어:
      - `MUSIC_TRUSTED_PROXIES` 환경변수에 등록된 IP 에서 온 요청일 때만
        `X-Forwarded-For` / `X-Real-IP` 를 신뢰한다.
      - 그 외엔 무조건 `request.client.host` 만 사용 — 누구나 임의의 IP 헤더를
        붙여 rate limit 을 우회할 수 없게.
      - 특수 값 `*` 를 쓰면 모든 출발지를 신뢰한다. Fly.io / Render 처럼 우리
        쪽에서 edge 프록시 IP 를 정확히 알 수 없는 PaaS 위에 띄울 때 사용.
        이런 환경에서는 외부에서 직접 들어오는 경로 자체가 막혀 있으므로
        XFF 위조 위험이 없다.
    """
    peer = request.client.host if request.client else ""
    trust_all = "*" in TRUSTED_PROXIES
    if trust_all or (TRUSTED_PROXIES and peer in TRUSTED_PROXIES):
        # 신뢰 가능한 출발지에서 온 요청만 헤더를 본다.
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            # XFF 는 "client, proxy1, proxy2" 형태. 가장 앞의 IP 가 원 클라이언트.
            first = fwd.split(",", 1)[0].strip()
            if first:
                return first
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
    return peer or "unknown"


def _gc_rate_state(now: float, window: float) -> None:
    """rate-limit dict 의 옛 키를 정리한다.

    회전 IP / X-Forwarded-For 폭주 공격을 받으면 `_rate_state` 가 한도 없이
    자라서 메모리 누수로 이어진다. window(60s) 안에 활동이 없는 IP 는 키째
    삭제. 호출자는 이미 `_rate_lock` 를 잡고 있어야 한다.
    """
    cutoff = now - window
    dead = [ip for ip, hist in _rate_state.items() if not hist or hist[-1] <= cutoff]
    for ip in dead:
        _rate_state.pop(ip, None)


class RateLimitExceeded(Exception):
    """429 응답을 구조화된 JSON body 로 내려주기 위한 전용 예외.

    HTTPException 만 쓰면 body 가 ``{"detail": "..."}`` 한 줄로 끝나서
    클라이언트가 retry_after / limit / reset_at 를 헤더에서만 파싱해야 한다.
    이걸 별도 예외로 raise → 전역 핸들러가 헤더 + JSON body 양쪽에 같은
    값을 채우면 SDK / 모니터링 / 디버깅이 한층 편해진다.
    """

    def __init__(self, *, retry_after_seconds: int, limit: int, reset_at: int, detail: str) -> None:
        self.retry_after_seconds = retry_after_seconds
        self.limit = limit
        self.reset_at = reset_at
        self.detail = detail


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_exception_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """RateLimitExceeded → 429 + 헤더 + 구조화 body 한 묶음.

    헤더만으로도 표준 클라이언트는 동작하지만, SDK / 모니터링 / 사용자 도구에서는
    body 의 ``retry_after_seconds`` 를 그대로 읽을 수 있으면 backoff 로직이 훨씬 단순.
    """
    return JSONResponse(
        status_code=429,
        content={
            "detail": exc.detail,
            "retry_after_seconds": exc.retry_after_seconds,
            "limit": exc.limit,
            "reset_at": exc.reset_at,
        },
        headers={
            "Retry-After": str(exc.retry_after_seconds),
            "X-RateLimit-Limit": str(exc.limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(exc.reset_at),
        },
    )


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
        # 매 요청마다 가벼운 GC — dict 크기를 신선한 IP 수만큼만 유지.
        # 개당 O(N) 비용이지만 N 이 실제 활성 IP 수로 한정돼 안정적.
        _gc_rate_state(now, window)
        history = _rate_state.setdefault(ip, [])
        # 윈도우 밖의 오래된 항목은 정리.
        cutoff = now - window
        history[:] = [t for t in history if t > cutoff]
        if len(history) >= RATE_LIMIT_PER_MIN:
            retry = int(window - (now - history[0])) + 1
            _bump("soundmatch_rate_limited_total")
            reset_at = int(history[0] + window)
            # HTTPException 의 detail 만으로는 클라이언트가 retry_after 를 응답 body 에서
            # 파싱하기 어렵다 ("약 N초" 라는 한글 문자열만 들어있음). 별도 exception 으로
            # raise 해서 전역 핸들러가 구조화된 JSON body 까지 함께 내려주도록.
            raise RateLimitExceeded(
                retry_after_seconds=retry,
                limit=RATE_LIMIT_PER_MIN,
                reset_at=reset_at,
                detail=f"요청이 너무 잦습니다. 약 {retry}초 뒤에 다시 시도해주세요.",
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


def _parse_release_date_from_changelog() -> str | None:
    """CHANGELOG.md 의 첫 `## [X.Y.Z] — YYYY-MM-DD` 라인에서 날짜만 뽑는다.

    운영자가 "지금 떠 있는 빌드가 언제 cut 된 버전인지" 확인하는 용도. 한 번만
    파싱해서 캐시. CHANGELOG 가 없거나 형식이 안 맞으면 None — 호출 측이
    fallback 처리.
    """
    import re

    changelog = ROOT / "CHANGELOG.md"
    try:
        text = changelog.read_text(encoding="utf-8")
    except OSError:
        return None
    # `## [Unreleased]` 는 건너뛰고 그 다음 `## [<semver>] — YYYY-MM-DD` 를 잡는다.
    m = re.search(r"^## \[\d+\.\d+\.\d+\][^\n]*?(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
    return m.group(1) if m else None


def _parse_recent_releases_from_changelog(limit: int = 3) -> list[dict]:
    """CHANGELOG.md 에서 최근 ``limit`` 개의 published 릴리즈 엔트리를 구조화해 돌려준다.

    프론트엔드의 "새 기능 보기" 모달이 이걸 그대로 렌더한다.
    Unreleased 섹션은 건너뛰고, ``## [X.Y.Z] — YYYY-MM-DD`` 헤더만 잡아서:

        [
          {
            "version": "1.4.0",
            "date": "2026-05-15",
            "sections": {"Added": [...], "Changed": [...], "Fixed": [...]},
          },
          ...
        ]

    bullet item 은 원본 markdown 의 ``- `` 머리만 떼고 줄바꿈을 공백으로 합쳐 평문
    한 줄로 정규화한다. 사용자에게 보이는 영역이라 raw markdown 을 그대로
    뱉지 않는다.
    """
    import re

    changelog = ROOT / "CHANGELOG.md"
    try:
        text = changelog.read_text(encoding="utf-8")
    except OSError:
        return []

    # 1. 릴리즈 헤더 위치를 모두 찾는다 (Unreleased 제외).
    header_re = re.compile(r"^## \[(\d+\.\d+\.\d+)\][^\n]*?(\d{4}-\d{2}-\d{2})", re.MULTILINE)
    headers = list(header_re.finditer(text))
    if not headers:
        return []

    # 2. 각 헤더 위치 사이의 body 를 잘라낸다. 마지막은 파일 끝까지.
    releases: list[dict] = []
    for i, m in enumerate(headers[:limit]):
        version = m.group(1)
        date = m.group(2)
        body_start = m.end()
        body_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[body_start:body_end]

        # 3. body 안의 `### Added` / `### Changed` / `### Fixed` 섹션을 잘라 항목화.
        sections: dict[str, list[str]] = {}
        section_re = re.compile(r"^### (\w[^\n]*?)\n", re.MULTILINE)
        section_headers = list(section_re.finditer(body))
        for j, sm in enumerate(section_headers):
            name = sm.group(1).strip()
            s_start = sm.end()
            s_end = section_headers[j + 1].start() if j + 1 < len(section_headers) else len(body)
            chunk = body[s_start:s_end]
            # `- foo bar\n  baz` (들여쓰기로 이어지는 줄) → 한 줄 평문.
            items: list[str] = []
            current: list[str] = []
            for raw in chunk.splitlines():
                if raw.startswith("- "):
                    if current:
                        items.append(" ".join(current).strip())
                    current = [raw[2:].strip()]
                elif raw.strip() and current:
                    # 들여쓰기 continuation. 앞쪽 공백 정리해서 이어 붙임.
                    current.append(raw.strip())
                # 빈 줄은 무시.
            if current:
                items.append(" ".join(current).strip())
            # 같은 섹션이 두 번 나오는 경우 (예: Added/Changed/Added) 도 그대로 이어 붙인다.
            sections.setdefault(name, []).extend(items)

        releases.append({"version": version, "date": date, "sections": sections})
    return releases


def _detect_git_commit() -> str | None:
    """현재 빌드의 짧은 git SHA 를 식별한다.

    우선순위:
    1. 환경변수 ``MUSIC_GIT_COMMIT`` — 컨테이너 빌드 시 inject 하는 표준 패턴
       (Dockerfile / fly.toml / render.yaml 빌드 단계에서 ``GIT_COMMIT=$(git rev-parse --short HEAD)``).
    2. 로컬 ``.git/HEAD`` 파일 — 개발 환경에서 환경변수 없이도 자동 감지.
    3. 둘 다 실패하면 None — 호출 측이 fallback.

    SHA 는 항상 7자로 truncate (짧은 form). 운영자가 ``v1.5.0 · ab12cd3`` 형태로 보기 위함.
    """
    env_sha = os.environ.get("MUSIC_GIT_COMMIT", "").strip()
    if env_sha:
        return env_sha[:7]
    # .git/HEAD 가 있으면 거기서 HEAD 가 가리키는 ref 를 따라가 SHA 를 읽는다.
    head_file = ROOT / ".git" / "HEAD"
    try:
        head = head_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    # detached HEAD 면 그 자체가 SHA, 아니면 "ref: refs/heads/main" 형태.
    if head.startswith("ref:"):
        ref_path = head.split(":", 1)[1].strip()
        ref_file = ROOT / ".git" / ref_path
        try:
            sha = ref_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
    else:
        sha = head
    # SHA 가 hex 40자 인지만 sanity check — 아니면 None.
    if len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha.lower()):
        return None
    return sha[:7]


def _collect_dependency_versions() -> dict[str, str | None]:
    """핵심 의존 라이브러리 버전을 한 번에 수집.

    importlib.metadata 가 표준 — installed 패키지의 메타데이터를 직접 가져온다.
    런타임 import 가 실패하더라도 (예: librosa 미설치 + dev 모드) 우아하게 None.
    여기에 넣을 라이브러리 선정 기준은 "운영 디버깅에서 자주 묻는 것":
      - numpy / pandas: ML 파이프라인 핵심
      - scikit-learn: 우리 모델/유사도 계산 핵심
      - librosa: 오디오 특성 추출
      - fastapi / pydantic: 웹 프레임워크 / 응답 직렬화
      - python: 인터프리터 자체.
    """
    from importlib import metadata as _metadata

    out: dict[str, str | None] = {}
    for pkg in ("numpy", "pandas", "scikit-learn", "librosa", "fastapi", "pydantic"):
        try:
            out[pkg] = _metadata.version(pkg)
        except _metadata.PackageNotFoundError:
            out[pkg] = None

    # python 은 metadata 가 아니라 sys.version_info 로 noun 형태로 표시.
    import sys as _sys

    out["python"] = f"{_sys.version_info.major}.{_sys.version_info.minor}.{_sys.version_info.micro}"
    return out


# 모듈 로드 시 한 번만 계산. 핫리로드 안 됨 — 새 release 가 cut 되면 워커 재시작.
_RELEASE_DATE: str | None = _parse_release_date_from_changelog()
_RECENT_RELEASES: list[dict] = _parse_recent_releases_from_changelog(limit=3)
_GIT_COMMIT: str | None = _detect_git_commit()
_DEPENDENCY_VERSIONS: dict[str, str | None] = _collect_dependency_versions()


def _dataset_mtime_iso() -> str | None:
    """카탈로그 CSV 의 마지막 수정 시각을 ISO 8601 (UTC) 로 돌려준다.

    파일이 없거나 stat 권한 / FS 이슈로 실패하면 None. 운영자가 어느
    버전의 카탈로그가 떠 있는지 확인하는 용도로 /api/health 와 sitemap 의
    catalog song deep-link 의 lastmod 양쪽에 같은 값을 쓴다.
    """
    try:
        mtime = DATASET_PATH.stat().st_mtime
    except OSError:
        return None
    from datetime import datetime

    return datetime.fromtimestamp(mtime, tz=UTC).isoformat(timespec="seconds")


def _dataset_mtime_date() -> str:
    """sitemap <lastmod> 용 YYYY-MM-DD 짧은 포맷. 실패 시 오늘 날짜."""
    iso = _dataset_mtime_iso()
    if iso:
        return iso[:10]
    from datetime import date

    return date.today().isoformat()


# ----------------------------------------------------------------------
# 라우트
# ----------------------------------------------------------------------
@app.get(
    "/api/health",
    response_model=HealthResponse,
    summary="라이브니스 / 카탈로그 로딩 상태",
    tags=["system"],
    operation_id="health",
)
# HEAD 도 같은 핸들러로 처리하되 OpenAPI 에는 GET 하나만 노출한다.
# 예전엔 api_route(methods=["GET","HEAD"]) 로 묶었는데, 그러면 GET·HEAD 두
# operation 이 같은 operationId("health") 를 갖게 돼 'Duplicate Operation ID'
# 경고가 뜨고 일부 SDK 생성기가 깨졌다. HEAD 는 스키마에서 빼서 충돌을 없앤다.
@app.head("/api/health", include_in_schema=False)
def health(strict: bool = Query(False, description="True 면 librosa/sklearn 임포트 + 업로드 디렉토리 쓰기까지 검사")):  # noqa: B008
    """라이브니스 프로브.

    기본 모드는 카탈로그가 메모리에 떠 있는지만 확인한다. ``strict=true``
    이면 librosa/sklearn 임포트가 가능한지, 업로드 디렉토리에 쓰기 권한이
    있는지까지 점검한다 — Render/Fly 같은 PaaS 에 readiness probe 로 쓸 만하다.
    """
    uptime = round(time.monotonic() - _started_at, 1)
    try:
        size = get_engine().catalog_size
    except Exception as e:  # noqa: BLE001
        return JSONResponse(
            {
                "status": "degraded",
                "catalog_size": 0,
                "env": ENV,
                "version": app.version,
                "uptime_seconds": uptime,
                # 운영자가 어디서 실패했는지 단번에 보도록 reason 명시.
                # message 는 내부 노출을 피하기 위해 type 만 — detail 은 운영 로그에서.
                "reason": "engine_load_failed",
                "reason_detail": type(e).__name__,
            },
            status_code=503,
        )

    if strict:
        # librosa / sklearn 이 정말로 임포트 되는지 확인. 무거운 워밍업까진 안 함.
        try:
            import librosa  # noqa: F401
            import sklearn  # noqa: F401
        except Exception as e:  # noqa: BLE001
            return JSONResponse(
                {
                    "status": "degraded",
                    "catalog_size": size,
                    "env": ENV,
                    "version": app.version,
                    "uptime_seconds": uptime,
                    "reason": "ml_imports_unavailable",
                    "reason_detail": type(e).__name__,
                },
                status_code=503,
            )
        # 업로드 디렉토리에 임시 파일 쓰기 / 삭제까지 가능한지.
        probe = UPLOAD_DIR / f".healthcheck-{uuid.uuid4().hex}"
        try:
            probe.write_bytes(b"ok")
            probe.unlink()
        except OSError as e:
            return JSONResponse(
                {
                    "status": "degraded",
                    "catalog_size": size,
                    "env": ENV,
                    "version": app.version,
                    "uptime_seconds": uptime,
                    "reason": "upload_dir_not_writable",
                    "reason_detail": type(e).__name__,
                },
                status_code=503,
            )

    return {
        "status": "ok",
        "catalog_size": size,
        "env": ENV,
        "version": app.version,
        # /api/version 과 동일한 빌드 메타 — 운영자가 health 만 봐도 어떤 빌드가
        # 떠 있는지 알 수 있도록. /api/version 까지 추가 호출 없이도 alert 룰 작성 가능.
        "release_date": _RELEASE_DATE,
        "git_commit": _GIT_COMMIT,
        "uptime_seconds": uptime,
        "analyze_latency_p50_seconds": round(_latency_percentile(0.50), 3),
        "catalog_updated_at": _dataset_mtime_iso(),
    }


@app.post(
    "/api/client-error",
    summary="프론트엔드 글로벌 에러 비콘",
    tags=["system"],
    include_in_schema=False,
)
async def client_error(request: Request):
    """frontend window.onerror / unhandledrejection 에서 보내는 에러 비콘.

    저장이나 가공은 하지 않고, 구조화 로그 한 줄 + 카운터 1 증가만 한다.
    악의적 트래픽으로 디스크가 차는 일을 막기 위해 본문 사이즈도 cap 한다.
    """
    _bump("soundmatch_client_errors_total")
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {"raw": str(body)[:500]}
    except Exception:  # noqa: BLE001
        body = {"raw": (await request.body())[:500].decode("utf-8", errors="replace")}

    # 비콘에 PII 가 들어올 수 있으니 가능한 한 필드만 추려 로그.
    # logging.LogRecord 가 이미 가지고 있는 키('message' 등) 와 충돌하지 않도록
    # 접두사를 붙여둔다.
    client_msg = str(body.get("message", ""))[:500]
    src = str(body.get("source", ""))[:300]
    ua = (request.headers.get("user-agent") or "")[:200]
    logger.warning(
        "client_error",
        extra={
            "request_id": request_id,
            "client_message": client_msg,
            "client_source": src,
            "user_agent": ua,
            "client_lineno": body.get("lineno"),
            "client_colno": body.get("colno"),
        },
    )
    # 비콘이라 응답은 비워둔다.
    return Response(status_code=204)


@app.get(
    "/api/version",
    summary="버전 + 기능 플래그 (클라이언트 호환성 체크용)",
    tags=["system"],
)
def version_info():
    """SDK/클라이언트가 호환성을 확인할 때 가볍게 호출하는 메타 엔드포인트.

    /api/health 와 달리 데이터셋 상태에 의존하지 않으므로 항상 200 을 돌려준다.
    카탈로그 사이즈는 이미 로딩됐을 때만 채워서 보낸다 — 빠르게 응답하기 위해서.
    """
    try:
        catalog_size = _engine.catalog_size if _engine is not None else 0
    except Exception:  # noqa: BLE001
        catalog_size = 0
    # 누적 분석 횟수 (성공 기준, 캐시 히트 포함). 사용자 측에서 social proof
    # 로 사용하고, 운영자가 활동성 trend 를 빠르게 가늠하는 용도. /metrics 와
    # 동일 카운터지만 Prometheus 안 띄운 운영 환경도 한 줄 JSON 으로 확인 가능.
    analyses_total = int(_metrics_counters.get("soundmatch_analyze_success_total", 0))
    return {
        "name": "soundmatch",
        "version": app.version,
        "release_date": _RELEASE_DATE,
        # 짧은 git SHA (7자). 같은 version 으로 여러 빌드가 떠 있을 때 운영자가 정확히
        # 어느 빌드인지 식별. 환경변수 MUSIC_GIT_COMMIT 가 우선, 없으면 .git/HEAD fallback.
        "git_commit": _GIT_COMMIT,
        "env": ENV,
        "catalog_size": catalog_size,
        "analyses_total": analyses_total,
        "features": {
            "spectrogram": True,
            "by_catalog": True,
            "share_url": True,
            "metrics": True,
            "pwa": True,
            "ko_en_i18n": True,
            "result_export_svg_png": True,
            "favorites": True,
            "compare_page": True,
            "result_cache": True,
        },
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "rate_limit_per_min": RATE_LIMIT_PER_MIN,
        # 핵심 의존 라이브러리 버전. 운영자가 "어떤 numpy / sklearn 으로 떠 있는지"
        # 빠르게 확인 가능. CVE 점검 / 호환성 디버깅 / 클라이언트 SDK 가 server feature 추측 등.
        "dependencies": _DEPENDENCY_VERSIONS,
    }


@app.get(
    "/api/version/changelog",
    summary="최근 릴리즈 노트 (사용자 'What's new' 모달용)",
    tags=["system"],
)
def version_changelog(limit: int = Query(3, ge=1, le=10)):  # noqa: B008
    """CHANGELOG.md 의 최근 published 릴리즈 ``limit`` 개를 구조화해 돌려준다.

    프론트엔드의 "새 기능 보기" 모달이 이 응답을 그대로 렌더한다.
    Unreleased 섹션은 의도적으로 제외 — 사용자에게는 cut 된 버전만 노출.
    """
    payload = _RECENT_RELEASES[:limit]
    return JSONResponse(
        {"releases": payload},
        # 같은 빌드 안에서는 안 변하므로 적당히 길게 캐시. release cut 시 워커 재시작으로 갱신.
        headers={"Cache-Control": "public, max-age=600"},
    )


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
        "soundmatch_client_errors_total": "프론트엔드에서 보고된 클라이언트 에러 수",
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
    "/api/catalog/stats",
    summary="카탈로그 BPM/에너지/밝기 분포 통계",
    tags=["system"],
)
def catalog_stats(bpm_bins: int = Query(10, ge=4, le=40)):  # noqa: B008
    """카탈로그 전체에 대한 가벼운 통계를 돌려준다.

    - bpm / energy_rms / spectral_centroid_mean 의 min / max / avg.
    - BPM 분포는 ``bpm_bins`` 개 구간으로 나눈 히스토그램으로 같이 노출.

    카탈로그 페이지에서 작은 막대 차트를 그릴 때 사용한다. raw 행을 매번
    훑지만 ~1000곡 규모에선 충분히 빠르고, 결과는 5분 캐시.
    """
    eng = get_engine()
    names = eng.iter_catalog_names()
    bpms: list[float] = []
    energies: list[float] = []
    brights: list[float] = []
    for n in names:
        row = eng.catalog_row_raw(n) or {}
        try:
            bpm = float(row.get("bpm", 0.0) or 0.0)
            energy = float(row.get("rms_mean", 0.0) or 0.0)
            bright = float(row.get("spectral_centroid_mean", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if bpm > 0:
            bpms.append(bpm)
        if energy > 0:
            energies.append(energy)
        if bright > 0:
            brights.append(bright)

    def _agg(vals: list[float]) -> dict[str, float]:
        if not vals:
            return {"min": 0.0, "max": 0.0, "avg": 0.0, "count": 0}
        return {
            "min": round(min(vals), 3),
            "max": round(max(vals), 3),
            "avg": round(sum(vals) / len(vals), 3),
            "count": len(vals),
        }

    # BPM 히스토그램. 표시용으로 60~200 구간에 고정 — 그 바깥은 outlier.
    hist_min, hist_max = 60.0, 200.0
    bins = [0] * bpm_bins
    step = (hist_max - hist_min) / bpm_bins
    for b in bpms:
        if b < hist_min:
            bins[0] += 1
        elif b >= hist_max:
            bins[-1] += 1
        else:
            idx = int((b - hist_min) / step)
            bins[min(idx, bpm_bins - 1)] += 1
    bpm_hist = [
        {
            "from": round(hist_min + i * step, 1),
            "to": round(hist_min + (i + 1) * step, 1),
            "count": bins[i],
        }
        for i in range(bpm_bins)
    ]

    return JSONResponse(
        {
            "total": eng.catalog_size,
            "bpm": _agg(bpms),
            "energy": _agg(energies),
            "brightness": _agg(brights),
            "bpm_histogram": bpm_hist,
        },
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
    min_bpm: float | None = Query(None, ge=0, le=400, description="BPM 하한"),  # noqa: B008
    max_bpm: float | None = Query(None, ge=0, le=400, description="BPM 상한"),  # noqa: B008
    min_energy: float | None = Query(None, ge=0, le=1, description="RMS 에너지 하한"),  # noqa: B008
    max_energy: float | None = Query(None, ge=0, le=1, description="RMS 에너지 상한"),  # noqa: B008
    sort: str = Query("default", pattern="^(default|title|artist|bpm|energy|shuffle)$"),  # noqa: B008
):
    """카탈로그 곡 목록을 검색/페이지네이션 형태로 돌려준다.

    매번 카탈로그 전체를 메모리에서 필터링한다. 곡 수가 십수만 이상으로
    커지면 별도 인덱스(예: SQLite FTS) 가 필요하지만, 현재 1000곡 규모에선
    이 정도로 충분히 빠르다.

    필터:
        - bpm/energy 범위: 카탈로그 raw 행에서 직접 확인.
        - sort: default(사전식) / title / artist / bpm / energy 오름차순.
    """
    eng = get_engine()
    names = _filter_and_sort_catalog(
        eng,
        q=q,
        min_bpm=min_bpm,
        max_bpm=max_bpm,
        min_energy=min_energy,
        max_energy=max_energy,
        sort=sort,
    )

    total = len(names)
    start = (page - 1) * size
    end = start + size
    # 페이지에 들어가는 N곡만 메트릭(bpm/energy/brightness) 까지 함께 채워서 응답한다.
    # frontend 의 카탈로그 카드가 작은 라인으로 BPM/에너지를 보여주는 데 필요.
    # 페이로드는 24~96곡 × 3 float 이라 부담 없음.
    items: list[dict[str, object]] = []
    for n in names[start:end]:
        base = _split_catalog_name(n)
        row = eng.catalog_row_raw(n) or {}
        bpm = float(row.get("bpm", 0.0) or 0.0)
        rms = float(row.get("rms_mean", 0.0) or 0.0)
        sc = float(row.get("spectral_centroid_mean", 0.0) or 0.0)
        # 0 인 값은 표시 의미 없으므로 None 으로 내려서 frontend 가 안전하게 분기.
        base["metrics"] = {
            "bpm": round(bpm, 1) if bpm > 0 else None,
            "energy_rms": round(rms, 3) if rms > 0 else None,
            "brightness": round(sc, 0) if sc > 0 else None,
        }
        items.append(base)
    # shuffle 모드는 매 호출이 새 순서여야 하므로 캐시 금지. 일반 정렬은 짧게.
    cache_header = "no-store" if sort == "shuffle" else "public, max-age=120"
    return JSONResponse(
        {
            "total": total,
            "page": page,
            "size": size,
            "has_more": end < total,
            "items": items,
        },
        headers={"Cache-Control": cache_header},
    )


def _split_catalog_name(full: str) -> dict[str, str]:
    """"곡명 - 아티스트" 키를 title/artist 딕셔너리로 안전 분리."""
    title, _, artist = full.partition(" - ")
    return {"title": title.strip() or full, "artist": artist.strip() or "Unknown"}


def _filter_and_sort_catalog(
    eng,
    *,
    q: str = "",
    min_bpm: float | None = None,
    max_bpm: float | None = None,
    min_energy: float | None = None,
    max_energy: float | None = None,
    sort: str = "default",
) -> list[str]:
    """카탈로그 이름 목록에 검색/필터/정렬을 적용한다 (페이지네이션 없음).

    catalog_search 와 catalog_export_csv 가 동일한 필터 로직을 공유하도록 분리.
    엔드포인트별로 살짝씩 다른 동작을 하지 않게 — 즉 "검색 결과 화면에서 보던 곡 = 내보낸 CSV 행" 이
    항상 일치하도록 보장하는 것이 이 함수의 핵심 책임.
    """
    needle = (q or "").strip().lower()
    names = eng.iter_catalog_names()

    # 이름 키워드 부분일치.
    if needle:
        names = [n for n in names if needle in n.lower()]

    # BPM/에너지 범위 필터.
    if any(v is not None for v in (min_bpm, max_bpm, min_energy, max_energy)):
        filtered: list[str] = []
        for n in names:
            row = eng.catalog_row_raw(n) or {}
            bpm = float(row.get("bpm", 0.0) or 0.0)
            energy = float(row.get("rms_mean", 0.0) or 0.0)
            if min_bpm is not None and bpm < min_bpm:
                continue
            if max_bpm is not None and bpm > max_bpm:
                continue
            if min_energy is not None and energy < min_energy:
                continue
            if max_energy is not None and energy > max_energy:
                continue
            filtered.append(n)
        names = filtered

    # 정렬.
    if sort == "title":
        names = sorted(names, key=lambda n: _split_catalog_name(n)["title"].lower())
    elif sort == "artist":
        names = sorted(names, key=lambda n: _split_catalog_name(n)["artist"].lower())
    elif sort == "bpm":
        names = sorted(names, key=lambda n: float((eng.catalog_row_raw(n) or {}).get("bpm", 0.0) or 0.0))
    elif sort == "energy":
        names = sorted(names, key=lambda n: float((eng.catalog_row_raw(n) or {}).get("rms_mean", 0.0) or 0.0))
    elif sort == "shuffle":
        # 무작위 셔플. 매 요청마다 다른 순서가 나오도록 seed 를 안 박는다.
        # discovery 용도라 페이지를 넘겨도 같은 무작위 순서가 유지될 필요는
        # 없음 — 새로고침 = 새로운 셔플. 캐시 헤더도 함께 짧게 가져간다.
        import random as _random

        names = list(names)
        _random.shuffle(names)
    # default 정렬은 이미 iter_catalog_names 가 사전식으로 반환.
    return names


@app.get(
    "/api/catalog/export.csv",
    summary="필터 적용된 카탈로그 전체를 CSV 로 내보내기",
    tags=["system"],
)
def catalog_export_csv(
    q: str = Query("", description="제목/아티스트 부분 일치"),  # noqa: B008
    min_bpm: float | None = Query(None, ge=0, le=400),  # noqa: B008
    max_bpm: float | None = Query(None, ge=0, le=400),  # noqa: B008
    min_energy: float | None = Query(None, ge=0, le=1),  # noqa: B008
    max_energy: float | None = Query(None, ge=0, le=1),  # noqa: B008
    sort: str = Query("default", pattern="^(default|title|artist|bpm|energy|shuffle)$"),  # noqa: B008
):
    """``/api/catalog/search`` 와 동일한 필터/정렬을 적용한 결과 **전체**를
    한 장의 CSV 로 내려준다. 페이지네이션 없음.

    Music supervisor / 큐레이터가 외부 도구 (Excel / Numbers / pandas) 로
    가져가 분석하는 용도. 1000곡 규모에서는 응답이 수십 KB 수준이라
    streaming 까지 갈 필요 없이 한 번에 빌드해 내려보낸다.

    CSV injection 회피: 셀 첫 문자가 ``= + - @`` 면 ``'`` 를 prepend.
    Excel 류에서 수식으로 해석되는 위험을 차단 — 사용자가 받은 CSV 를
    그대로 열어도 안전하다.
    """
    import csv as _csv
    import io as _io

    eng = get_engine()
    names = _filter_and_sort_catalog(
        eng,
        q=q,
        min_bpm=min_bpm,
        max_bpm=max_bpm,
        min_energy=min_energy,
        max_energy=max_energy,
        sort=sort,
    )

    def _safe_cell(value: object) -> str:
        # None / 빈 값은 빈 문자열로. CSV injection 방어를 위해 leading ``= + - @`` 차단.
        s = "" if value is None else str(value)
        if s and s[0] in "=+-@":
            return "'" + s
        return s

    buf = _io.StringIO()
    # lineterminator 를 명시하지 않으면 환경에 따라 \r\n / \n 이 섞일 수 있어 일관되게 \n 으로.
    writer = _csv.writer(buf, lineterminator="\n")
    writer.writerow(["title", "artist", "bpm", "energy_rms", "brightness", "full_name"])
    for n in names:
        base = _split_catalog_name(n)
        row = eng.catalog_row_raw(n) or {}
        bpm = float(row.get("bpm", 0.0) or 0.0)
        rms = float(row.get("rms_mean", 0.0) or 0.0)
        sc = float(row.get("spectral_centroid_mean", 0.0) or 0.0)
        writer.writerow([
            _safe_cell(base["title"]),
            _safe_cell(base["artist"]),
            f"{bpm:.1f}" if bpm > 0 else "",
            f"{rms:.3f}" if rms > 0 else "",
            f"{sc:.0f}" if sc > 0 else "",
            _safe_cell(n),
        ])

    # BOM 을 붙여 Excel 한글 환경에서 인코딩 깨짐을 방지. 다른 도구는 BOM 을 자동 스킵.
    body = "﻿" + buf.getvalue()
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            # 파일명은 ASCII 고정 — 한글 파일명을 강제하면 일부 클라이언트에서 깨진다.
            "Content-Disposition": 'attachment; filename="catalog.csv"',
            # 사용자가 필터를 바꾸자마자 새 CSV 를 받기를 기대하므로 캐시 금지.
            "Cache-Control": "no-store",
        },
    )


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
    같은 (name, top_n) 입력은 LRU 캐시에서 즉시 응답한다.
    """
    eng = get_engine()
    raw = eng.catalog_row_raw(name)
    if raw is None:
        raise HTTPException(status_code=404, detail="카탈로그에서 해당 곡을 찾을 수 없습니다.")

    cache_key = _by_catalog_cache.make_key(name, top_n)
    # copy=True 로 받아 캐시 entry 가 호출 측 수정에 오염되지 않게 보장.
    cached_payload = _by_catalog_cache.get(cache_key, copy=True)
    if cached_payload is not None:
        # cached 플래그를 켜서 클라이언트가 알 수 있게.
        cached_payload["cached"] = True
        return JSONResponse(cached_payload, headers={"Cache-Control": "public, max-age=300"})

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
    payload = {
        "source": "catalog",
        "name": name,
        "title": title.strip() or name,
        "artist": artist.strip() or "Unknown",
        "summary": summary_metrics(features),
        "tags": derive_tags(features),
        "results": results,
        "catalog_size": eng.catalog_size,
        "engine_version": app.version,
        "cached": False,
    }
    _by_catalog_cache.set(cache_key, payload)
    return JSONResponse(payload, headers={"Cache-Control": "public, max-age=300"})


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
    # 이 요청이 실제로 increment 까지 도달했는지 추적해서, finally 에서 짝이
    # 맞는 decrement 만 수행한다. (extension/size 검증 단계에서 raise 된 경우엔
    # 다른 정상 요청의 카운터를 잘못 깎아 metrics 가 어긋나는 문제를 막음.)
    global _inflight_analyses
    inflight_incremented = False

    try:
        async with _analysis_semaphore:
            # in-flight 카운터 증가. /metrics 에서 게이지로 노출된다.
            with _inflight_lock:
                _inflight_analyses += 1
            inflight_incremented = True
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
            # copy=True 로 받아 캐시 entry 의 results / summary 같은 중첩
            # 구조가 호출 측 수정에 오염되지 않도록. 현재 코드는 dict 최상위
            # 필드만 갈아끼지만 future-proofing 차원.
            cached_value = _result_cache.get(cache_key, copy=True)
            if cached_value is not None:
                _bump("soundmatch_cache_hits_total")
                _bump("soundmatch_analyze_success_total")
                # 동적 필드만 새 요청용으로 교체. 나머지는 그대로 재사용.
                payload = cached_value
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
        # in-flight 카운터 차감. 이 요청이 실제로 증가까지 도달한 경우에만.
        if inflight_incremented:
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

    @app.get("/theme-init.js", include_in_schema=False)
    def theme_init_js():
        return _cached_file_response(FRONTEND_DIR / "js" / "theme-init.js")

    @app.get("/sw-register.js", include_in_schema=False)
    def sw_register_js():
        return _cached_file_response(FRONTEND_DIR / "js" / "sw-register.js")

    @app.get("/error-boundary.js", include_in_schema=False)
    def error_boundary_js():
        return _cached_file_response(FRONTEND_DIR / "js" / "error-boundary.js")

    @app.get("/site-nav.js", include_in_schema=False)
    def site_nav_js():
        # 서브페이지(카탈로그/비교 등) 공용 네비게이션 배선. HTML 은 루트 경로로
        # 부르지만 실제 파일은 js/ 아래에 있어 다른 스크립트들과 같은 방식으로 매핑.
        return _cached_file_response(FRONTEND_DIR / "js" / "site-nav.js")

    @app.get("/catalog.js", include_in_schema=False)
    def catalog_js():
        """카탈로그 페이지 전용 스크립트."""
        return _cached_file_response(FRONTEND_DIR / "js" / "catalog.js")

    @app.get("/compare.js", include_in_schema=False)
    def compare_js():
        """비교 페이지 전용 스크립트."""
        return _cached_file_response(FRONTEND_DIR / "js" / "compare.js")

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
        """정적 페이지 + 카탈로그 곡 딥링크 전부를 sitemap 에 노출한다.

        곡 딥링크는 /catalog?song=<encoded name> 형태. 모달이 자동으로 열리도록
        와이어링되어 있어서, 검색 봇이 와도 곡 단위 유일한 URL 이 보장된다.

        sitemap 표준이 한 파일당 50k URL / 50MB 라 781곡 규모는 충분히 한 파일.
        """
        from datetime import date
        from urllib.parse import quote

        today = date.today().isoformat()
        # 카탈로그 곡 deep-link 의 lastmod 는 실제 dataset.csv mtime 으로
        # 잡아준다 — 검색 봇 입장에서 데이터셋이 안 바뀌었으면 재크롤할 동기가
        # 없고, 바뀌었으면 곡별로 lastmod 가 바뀐 게 보여서 인덱스가 정확해진다.
        catalog_lastmod = _dataset_mtime_date()
        # 정적 페이지 (loc, priority, changefreq)
        static_entries = [
            ("/", "1.0", "weekly"),
            ("/catalog", "0.7", "weekly"),
            ("/compare", "0.6", "monthly"),
            ("/privacy", "0.4", "yearly"),
            ("/terms", "0.4", "yearly"),
        ]
        url_blocks = [
            f"<url><loc>{loc}</loc><lastmod>{today}</lastmod>"
            f"<changefreq>{cf}</changefreq><priority>{pri}</priority></url>"
            for loc, pri, cf in static_entries
        ]
        # 카탈로그 곡 — 모달 딥링크. 곡명에 한글/공백이 흔해서 quote(safe="") 로
        # 모든 특수문자를 percent-encoding 한다. sitemap 표준상 loc 안의 & 는
        # &amp; 로 escape 해야 하지만 quote 통과 후엔 & 가 등장하지 않으니 안전.
        try:
            engine = get_engine()
            for name in engine.iter_catalog_names():
                encoded = quote(name, safe="")
                url_blocks.append(
                    f"<url><loc>/catalog?song={encoded}</loc>"
                    f"<lastmod>{catalog_lastmod}</lastmod>"
                    "<changefreq>monthly</changefreq><priority>0.5</priority></url>"
                )
        except Exception:  # noqa: BLE001 - sitemap 은 절대 5xx 로 죽지 않아야 함
            logger.warning("sitemap_catalog_skip", exc_info=True)
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + "".join(url_blocks)
            + "</urlset>"
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

    # 알 수 없는 경로 처리 — 브라우저 navigation 이면 styled 404.html, API 호출이면
    # 기존 JSON 응답 그대로. API 응답을 깨지 않으면서 사람한테는 친절한 페이지.
    @app.exception_handler(StarletteHTTPException)
    async def _styled_404_handler(request: Request, exc: StarletteHTTPException):  # noqa: D401
        # 다른 HTTP 에러는 모두 기본 동작에 위임.
        if exc.status_code != 404:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        # API / 정적 자산 경로는 JSON 응답이 더 다루기 쉽다.
        path = request.url.path or ""
        if path.startswith(("/api/", "/static/", "/metrics", "/docs", "/openapi")):
            return JSONResponse({"detail": exc.detail or "Not Found"}, status_code=404)
        # 브라우저 navigation 만 styled 페이지로.
        accept = (request.headers.get("accept") or "").lower()
        if "text/html" in accept or "*/*" in accept:
            nf = FRONTEND_DIR / "404.html"
            if nf.exists():
                return FileResponse(
                    str(nf),
                    status_code=404,
                    headers={"Cache-Control": "no-store"},
                )
        # HTML 도 아니고 알려진 정적 경로도 아니면 그냥 plain text.
        return Response("Not Found", status_code=404, media_type="text/plain")
