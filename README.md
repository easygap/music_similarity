<div align="center">

# 🎧 SoundMatch · AI Music Similarity

**Drop a song — get the closest matches and a plain-language explanation of why.**

[![CI](https://github.com/easygap/music_similarity/actions/workflows/ci.yml/badge.svg)](https://github.com/easygap/music_similarity/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.4-F7931E?logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![librosa](https://img.shields.io/badge/librosa-0.10-5C2D91)](https://librosa.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Deploy on Render](https://render.com/deploy?repo=https://github.com/easygap/music_similarity) ·
[Deploy on Fly.io](https://fly.io/docs/getting-started/launch/) ·
[Live demo (your own)](#-quick-start)

</div>

졸업작품으로 만들었던 [easygap/capstone_music](https://github.com/easygap/capstone_music)을
**시중 서비스급의 단일 웹 서비스**로 처음부터 다시 설계한 프로젝트입니다.
FastAPI + librosa + scikit-learn 기반, 다크/라이트 테마, 한국어·영어 지원,
Docker · Render · Fly.io 원클릭 배포까지 모두 포함되어 있어요.

---

## ✨ 핵심 기능

- 🎼 **드래그&드롭 음원 업로드** — `.wav .mp3 .flac .ogg .m4a` (25MB 한도, 클라이언트+서버 양쪽 검증)
- 🤖 **58개 오디오 특성 추출** (librosa) — RMS · BPM · 스펙트럴 · 크로마 · 20-MFCC
- 📐 **코사인 유사도 매칭** — sklearn `StandardScaler` + `cosine_similarity`
- 🥇 **순위 + 유사도 % + 진행 게이지** UI
- 💡 **닮은 이유 자동 생성** — z-score 거리를 음악적 그룹으로 묶어 한국어/영어 문장으로
- 🎚️ **업로드 음원 미리듣기 + 직접 그린 파형(Web Audio API)** — 클릭으로 탐색 가능
- 📊 **레이더 차트** — 1위 매칭과 6축 비교 (Tempo · 에너지 · 밝기 · 거친 정도 · 화성비 · 크로마)
- 🛈 **특성 툴팁** — 결과 페이지의 각 메트릭에 마우스 올리면 한 줄 설명
- 🎛 **멜 스펙트로그램** — 백엔드에서 직접 SVG 로 그려서 응답에 첨부 (matplotlib 없이 numpy 만)
- 🕘 **로컬 히스토리** — 최근 5건 자동 저장(localStorage), 클릭 한 번으로 결과 복원
- 🔗 **공유 가능한 URL** — 분석 결과를 gzip+base64url 로 압축해 URL hash 에 직렬화. 같은 URL 을 열면 별도 분석 없이 결과가 자동 복원
- 📤 **다양한 공유 방식** — Web Share API (모바일 네이티브 공유 시트) · 상위 3곡 텍스트 복사 · 결과 JSON 다운로드 · 공유 링크 복사
- ⌨️ **키보드 단축키** — `/` 업로드 포커스 · `Esc` 결과 닫기 · `Space` 재생/일시정지
- 🛡️ **분석 중 이탈 경고** — `beforeunload` 로 실수 이탈 시 한 번 확인
- 🌗 **다크/라이트 테마 토글** — OS 환경설정 자동 감지 + `prefers-reduced-motion` 존중
- 🌐 **한국어 + 영어** i18n — 토글 한 번으로 전체 UI 교체
- 🔍 **SEO/SNS 친화** — OG 이미지(SVG), sitemap.xml, robots.txt, 깔끔한 404 페이지
- 📑 **정책 페이지** — `/privacy`, `/terms` 정적 페이지를 같은 디자인 시스템으로 제공
- 🧾 **카탈로그 미리보기** — `/api/catalog/sample` + 메인 페이지 하단 카드
- 📱 **PWA 지원** — `manifest.webmanifest` + Service Worker + 오프라인 폴백 (`offline.html`). 모바일에서 "홈 화면에 추가" 가능
- 🧯 **글로벌 JS 에러 boundary** — 사이드 스크립트가 깨져도 사용자에게 친절한 토스트만 보이고 사이트는 계속 동작
- 📜 **OpenAPI 응답 모델** — `/docs` Swagger UI 에서 모든 응답 타입을 깔끔히 확인 가능
- ⚡ **API 안정성** — 비동기 threadpool, 동시 요청 cap, IP별 rate limit, magic-byte 검증, CSP/HSTS 등 시큐어 헤더, 구조화된 JSON 로그
- 🧪 **pytest 43개 케이스** + ruff lint + GitHub Actions CI + Docker multi-stage + Python 3.11/3.12 매트릭스
- 🤖 **Dependabot** 으로 pip / GitHub Actions / Docker 의존성 자동 PR
- 📜 **CHANGELOG / SECURITY / CODE_OF_CONDUCT** 까지 갖춘 협업 인프라

---

## 🏗️ 아키텍처

```
┌──────────────────────────────────┐   POST   ┌────────────────────────────────────────┐
│   Browser (HTML5 + WebAudio)     │  ──────▶│           FastAPI app                  │
│   - drag&drop upload             │          │  ├─ SecurityHeadersMiddleware (CSP/…)  │
│   - waveform · radar · history   │  ◀──────│  ├─ RequestLogMiddleware (req_id JSON)  │
│   - theme + i18n toggles         │   JSON   │  ├─ rate_limit dep · semaphore         │
│                                  │          │  ├─ run_in_threadpool(extract_features)│
└──────────────────────────────────┘          │  ├─ similarity.py (sklearn cosine)     │
                                              │  └─ reason_engine.py (KO/JSON)         │
                                              └────────────────────────────────────────┘
                                                                │
                                                                ▼
                                                  data/dataset.csv (catalog)
```

| 파일 | 역할 |
| --- | --- |
| `backend/audio_features.py` | librosa로 58개 특성 추출 (BPM·RMS·spectral·chroma·MFCC) |
| `backend/similarity.py` | `StandardScaler` + `cosine_similarity` (NaN 차단, zero-variance 컬럼 drop) |
| `backend/reason_engine.py` | 그룹별 z-score 거리 → 한국어/영어 문장 |
| `backend/spectrogram.py` | 멜 스펙트로그램 → 가벼운 SVG (matplotlib 의존성 없이) |
| `backend/schemas.py` | OpenAPI 응답 모델 (HealthResponse / CatalogResponse / AnalyzeResponse 등) |
| `backend/main.py` | FastAPI 엔드포인트 + 미들웨어 + 정적 프론트엔드 + 캐시 헤더 |
| `frontend/index.html` | SPA 단일 페이지 — 시맨틱 HTML, ARIA, skip-link, 글로벌 JS 에러 boundary |
| `frontend/css/style.css` | 다크/라이트 디자인 시스템, focus-visible, 반응형, reduced-motion |
| `frontend/js/app.js` | 메인 컨트롤러 (업로드/결과/히스토리/공유/테마/단축키) |
| `frontend/js/i18n.js` | 한국어/영어 사전 + 토글 |
| `frontend/js/visualizers.js` | Web Audio 파형 + SVG 레이더 차트 |
| `frontend/sw.js` | Service Worker (정적 리소스 캐시 + 오프라인 폴백) |
| `frontend/manifest.webmanifest` | PWA manifest |
| `frontend/offline.html` · `frontend/404.html` | 오프라인 / 잘못된 경로용 폴백 페이지 |
| `data/dataset.csv` | 곡 카탈로그 + 사전 추출된 특성값 |

---

## 🚀 빠른 시작

### 1. 로컬 (개발)

```bash
git clone https://github.com/easygap/music_similarity.git
cd music_similarity

# 가상환경 + 의존성
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 개발 서버 실행 (autoreload)
uvicorn backend.main:app --reload --port 8000
# → http://localhost:8000
```

### 2. Docker

```bash
docker compose up --build
# → http://localhost:8000
```

### 3. 디자인만 빠르게 확인 (librosa 없이)

```bash
python preview_server.py 8765
# → http://127.0.0.1:8765
```

ML 의존성 없이 정적 프론트엔드만 띄우고 `/api/analyze`에 더미 응답을 돌려줍니다.
디자인/UX 변경을 빠르게 확인하고 싶을 때 사용하세요.

### 4. 시중 배포

| 플랫폼 | 명령 |
| --- | --- |
| **Render** | `render.yaml` 포함 — GitHub repo를 Render Blueprint로 가져오면 1클릭 배포 |
| **Fly.io** | `fly launch --no-deploy && fly deploy` — `fly.toml` 포함 (Tokyo 리전 기본) |
| **Docker / VPS** | `docker compose up -d` 후 nginx 등 리버스 프록시 + Let's Encrypt 권장 |

---

## ⚙️ 환경 변수

| 이름 | 기본 | 설명 |
| --- | --- | --- |
| `MUSIC_ENV` | `development` | `production`이면 HSTS 등 추가 헤더 활성화, CORS 명시적 origin만 허용 |
| `MUSIC_DATASET_PATH` | `data/dataset.csv` | 카탈로그 CSV 경로 |
| `MUSIC_UPLOAD_DIR` | `uploads/` | 임시 업로드 디렉토리 |
| `MUSIC_MAX_UPLOAD_BYTES` | `26214400` (25MB) | 업로드 사이즈 한도 |
| `MUSIC_MAX_CONCURRENT` | `4` | 동시 분석 처리 한도 (CPU 보호) |
| `MUSIC_RATE_LIMIT_PER_MIN` | `12` | IP당 분당 요청 한도 |
| `MUSIC_ALLOWED_ORIGINS` | (개발: `*`, 프로덕션: 빈 문자열) | CORS 허용 출처 콤마 구분 |
| `MUSIC_LOG_LEVEL` | `INFO` | 구조화된 JSON 로그 레벨 |
| `PORT` | `8000` | Uvicorn 리스닝 포트 (Fly.io 등 PaaS 호환) |
| `WEB_CONCURRENCY` | `2` | Uvicorn worker 개수 (Docker) |

---

## 🧪 테스트 & 품질

```bash
# 전체 테스트
pytest -q

# lint
ruff check backend tests scripts

# 커버리지
pytest --cov=backend --cov-report=html
```

총 **31개** pytest 케이스가 다음을 검증합니다:
- 오디오 특성 추출 (실제 librosa 호출, 짧은 클립, 빈 파일 거부)
- 유사도 엔진 (랭킹, 단일 row 시나리오, NaN/Inf/zero-variance 안전 처리)
- 이유 엔진 (한국어 조사 정확도, 음수 mfcc 처리, JSON 직렬화 안전성)
- FastAPI 엔드포인트 (security headers, request_id, magic-byte 검증, rate-limit, 정상 흐름, 임시 파일 정리)

CI는 Python 3.11 + 3.12 매트릭스로 동일 테스트 + ruff + Docker build를 매 PR마다 실행합니다.

---

## 🧪 API 사용법

### `POST /api/analyze`

```bash
curl -X POST http://localhost:8000/api/analyze \
  -F "file=@./my_song.wav" \
  "?top_n=5"
```

응답 일부:
```json
{
  "request_id": "f3a9...",
  "filename": "my_song.wav",
  "summary": { "tempo_bpm": 128.0, "brightness": 3120.5, "...": "..." },
  "results": [
    {
      "rank": 1,
      "title": "Invincible",
      "artist": "DEAF KEV",
      "similarity_percent": 91.2,
      "match_summary": { "tempo_bpm": 130.5, "...": "..." },
      "youtube_search_url": "https://...",
      "spotify_search_url": "https://...",
      "reason": {
        "summary": "두 곡은 **템포 & 리듬** 측면이 닮았습니다.",
        "groups": [
          { "label": "템포 & 리듬", "match_score": 0.96, "summary": "...", "detail": ["..."] }
        ]
      }
    }
  ],
  "timing": { "feature_extraction_seconds": 1.42, "similarity_seconds": 0.012 },
  "catalog_size": 1006
}
```

| 엔드포인트 | 설명 |
| --- | --- |
| `GET /api/health` | 라이브니스 — 카탈로그 사이즈 + 환경 + 버전 (카탈로그 로드 실패 시 503) |
| `GET /api/catalog` | 카탈로그 크기 + 사용 중인 특성 컬럼 |
| `POST /api/analyze` | 음원 업로드 + 유사도 분석 (`top_n`은 1~20). 응답에 멜 스펙트로그램 SVG 포함 |
| `GET /docs` · `/openapi.json` | FastAPI 자동 생성 API 문서. 모든 응답 모델이 타입까지 정의되어 있음 |
| `GET /manifest.webmanifest` | PWA manifest (홈 화면 추가 / 단축키 메타) |
| `GET /sw.js` | Service Worker. 같은 출처 정적 리소스를 stale-while-revalidate 로 캐시 |
| `GET /offline.html` | 네트워크가 끊겼을 때 보여주는 폴백 페이지 |
| `GET /api/catalog/sample` | 카탈로그 일부 미리보기 (limit 1~50, 기본 12). `Cache-Control: max-age=300` |
| `GET /privacy` · `/terms` | 개인정보 처리방침 / 이용약관 (같은 디자인 시스템) |
| `GET /robots.txt` | 검색 봇 정책 (Allow: all + sitemap 위치) |
| `GET /sitemap.xml` | 단일 페이지 사이트맵 (SEO 수집용) |
| `GET /og-image.svg` | SNS 공유 카드용 1200×630 OpenGraph 이미지 |
| `GET /404` | 잘못된 경로 접근 시 안내 페이지 (`frontend/404.html`) |

모든 응답은 `X-Request-ID` 헤더를 포함하며 클라이언트가 보낸 헤더를 우선합니다.

---

## 🔒 보안 / 개인정보

- **TLS 권장** — 프로덕션 배포 시 nginx/Cloudflare 등으로 HTTPS 종단
- **HSTS · CSP · X-Frame-Options · Referrer-Policy · Permissions-Policy** 모두 자동 적용
- **CSP** — `default-src 'self'` 기본, 폰트 CDN만 명시 허용
- **업로드 검증** — 확장자 + magic byte + content-length pre-flight + 25MB 캡
- **CORS** — 프로덕션 기본 비활성화(`MUSIC_ALLOWED_ORIGINS=""`); 와일드카드와 credentials 조합 금지
- **자동 삭제** — 업로드된 음원은 분석 종료 즉시 디스크에서 삭제(`finally` + `BackgroundTasks`)
- **Non-root container** — Docker 이미지는 `uid 1001`로 실행
- **Rate limit** — IP별 분당 12회 기본 (환경변수로 조절)
- **카탈로그에 학습되지 않습니다** — 사용자 음원은 모델에도 카탈로그에도 들어가지 않음

---

## 🧰 카탈로그 다시 만들기

자신의 음원 폴더로 카탈로그를 다시 빌드:

```bash
python scripts/rebuild_dataset.py \
    --audio-dir ./my_songs \
    --out data/dataset.csv
```

파일명 규칙: `"Song Title - Artist Name.wav"` (UI에서 아티스트를 분리해 표시할 때 사용).

---

## 📂 디렉토리 구조

```
music_similarity/
├── backend/                  # FastAPI app
│   ├── audio_features.py
│   ├── similarity.py
│   ├── reason_engine.py
│   └── main.py
├── frontend/                 # vanilla SPA
│   ├── index.html
│   ├── css/style.css
│   ├── js/
│   │   ├── app.js
│   │   ├── i18n.js
│   │   └── visualizers.js
│   └── assets/favicon.svg
├── data/dataset.csv
├── tests/                    # pytest suite
│   ├── conftest.py
│   ├── test_audio_features.py
│   ├── test_similarity.py
│   ├── test_reason_engine.py
│   └── test_api.py
├── scripts/
│   ├── dev.sh · dev.ps1
│   └── rebuild_dataset.py
├── .github/workflows/ci.yml
├── render.yaml · fly.toml
├── Dockerfile · docker-compose.yml
├── pyproject.toml
└── requirements.txt · requirements-dev.txt
```

---

## 🗺️ 향후 로드맵 아이디어

- [ ] Annoy/FAISS 기반 ANN 검색으로 10만곡+ 카탈로그 지원
- [ ] 30초 미리듣기 (Spotify oEmbed) 직접 임베드
- [ ] 사용자 직접 카탈로그 업로드(관리자 페이지)
- [ ] 다국어 추가 (JA / ZH)
- [ ] PWA · 오프라인 캐시
- [ ] WebSocket 기반 실시간 진행률 (큰 파일용)

---

## 📜 라이선스

MIT License. 자유롭게 포크 후 사용하세요.

원작 캡스톤 데이터셋과 코드는
[easygap/capstone_music](https://github.com/easygap/capstone_music) 에서 확인할 수 있습니다.

---

> Made with 🎵 by [@easygap](https://github.com/easygap)
