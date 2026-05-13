# ---------------- 프로덕션 이미지 -----------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MUSIC_ENV=production \
    PORT=8000

# librosa / soundfile / audioread 가 의존하는 시스템 라이브러리.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# 소스는 캐시 적중률을 높이려고 마지막에 복사.
COPY backend /app/backend
COPY frontend /app/frontend
COPY data /app/data

# 업로드 임시 디렉토리. MUSIC_UPLOAD_DIR 로 위치 변경 가능.
RUN mkdir -p /app/uploads && chmod 0775 /app/uploads

# non-root 사용자로 전환.
RUN useradd --create-home --uid 1001 app && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://localhost:${PORT}/api/health" || exit 1

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
