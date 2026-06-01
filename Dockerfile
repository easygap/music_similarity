# ---------------- 프로덕션 이미지 -----------------------------------------
FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MUSIC_ENV=production \
    PORT=8000 \
    WEB_CONCURRENCY=1

# librosa / soundfile / audioread 가 의존하는 시스템 라이브러리.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# 소스는 캐시 적중률을 높이려고 마지막에 복사.
COPY backend /app/backend
COPY frontend /app/frontend
COPY data /app/data
# 런타임에 /api/version · /api/health · "새 기능 보기" 모달이 CHANGELOG 를
# 파싱한다(_parse_release_date_from_changelog). 이미지에 빠지면 release_date 와
# 릴리즈 노트가 통째로 비어버리므로 함께 복사한다.
COPY CHANGELOG.md /app/CHANGELOG.md

# 빌드 타임에 git SHA 를 주입 — `/api/version.git_commit` 으로 노출된다.
# 같은 version 으로 여러 빌드가 떠 있을 때 운영자가 어느 빌드인지 식별하기 위한 정보.
# 빌드 시 `docker build --build-arg GIT_COMMIT=$(git rev-parse --short HEAD)` 로 전달하거나,
# GitHub Actions 처럼 빌드 시스템에서 현재 SHA 를 명시적으로 넘긴다.
ARG GIT_COMMIT=""
ENV MUSIC_GIT_COMMIT=${GIT_COMMIT}

# 업로드 임시 디렉토리. MUSIC_UPLOAD_DIR 로 위치 변경 가능.
RUN mkdir -p /app/uploads && chmod 0775 /app/uploads

# non-root 사용자로 전환.
RUN useradd --create-home --uid 1001 app && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health?strict=true' % os.environ.get('PORT', '8000'), timeout=3).read()"]

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}"]
