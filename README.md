# music_similarity

졸업작품으로 팀원들과 만들었던
[easygap/capstone_music](https://github.com/easygap/capstone_music) 을 다시
만지면서, 혼자서도 끝까지 가져갈 수 있는 형태로 정리한 프로젝트.

음원을 업로드하면 사전에 추출해둔 카탈로그와 코사인 유사도로 비교해서
닮은 곡 순위와 그 이유를 보여준다.

[![CI](https://github.com/easygap/music_similarity/actions/workflows/ci.yml/badge.svg)](https://github.com/easygap/music_similarity/actions/workflows/ci.yml)

## 동작 원리

원작 노트북의 알고리즘을 그대로 가져왔다. 흐름만 다시 정리하면:

1. librosa 로 RMS, BPM, 스펙트럴 센트로이드 / 대역폭 / 롤오프, 제로 크로싱,
   크로마, 20-MFCC 등 58개 특성을 뽑는다.
2. 카탈로그(`data/dataset.csv`) 를 startup 시점에 `StandardScaler` 로 정규화해
   메모리에 들고 있는다. 같은 scaler 인스턴스로 새 쿼리도 변환.
3. `cosine_similarity` 로 카탈로그 전곡과 비교, 내림차순 정렬해 상위 N곡 반환.
4. 동시에 특성별 z-score 거리를 음악적 그룹(템포·음색·화성 등) 으로 묶어
   "왜 이 곡이 닮았는지" 한국어 문장으로 풀어준다.

원작과 달라진 건 비동기 FastAPI 서버 + 정적 SPA + Docker 로 다시 묶은 정도.

## 실행

로컬:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn backend.main:app --reload --port 8000
```

Docker 가 편하면 `docker compose up --build`.

명령줄에서 한 파일만 분석해보고 싶다면:

```bash
python -m backend.cli analyze ./mysong.wav --top-n 5
python -m backend.cli analyze ./mysong.wav --json > result.json
```

폴더 단위로 한 번에 분석하고 결과를 CSV 로 떨구려면:

```bash
python -m backend.cli batch ./songs --out results.csv --top-n 5
```

서버를 띄우지 않고도 같은 엔진으로 동작한다 (배치 작업 / 디버깅 용).

librosa / sklearn 깔지 않고 디자인만 돌려볼 때:

```bash
python preview_server.py 8765
```

`/api/analyze` 에 더미 응답을 돌려주는 가벼운 서버. 정적 자산만 띄운다.

## 기능 정리

- 드래그앤드롭 업로드, 결과 카드(순위 / 유사도 % / 닮은 이유).
- 업로드 음원 미리듣기 + 직접 그린 파형(Web Audio), 1위 매칭과의 6축 레이더 차트,
  멜 스펙트로그램(matplotlib 안 쓰고 numpy + SVG).
- 휴리스틱 태그 — "빠른 템포", "에너지 폭발", "밝은 톤" 같은 즉시 와닿는 라벨.
- 두 곡 나란히 비교 페이지(`/compare`), 최근 분석 5건 히스토리(localStorage).
- 카탈로그 둘러보기 페이지(`/catalog`) — 곡명·아티스트 검색 + 페이지네이션.
  카드를 누르면 그 곡 기준 유사한 다른 곡 5건을 모달로 즉시 표시
  (`/api/analyze/by-catalog`, librosa 호출 없음).
- ★ 즐겨찾기 — 카탈로그 / 결과 카드의 별 버튼으로 곡을 모아둘 수 있다.
  localStorage 기반, 메인 페이지 "내 즐겨찾기" 섹션에 모이고, 카탈로그
  페이지에서 "즐겨찾기만 보기" 토글로 필터링 가능.
- 결과 카드의 매칭 곡에 "이 곡으로 다시 찾기" 버튼. 누르면 그 곡을 새 시드로
  카탈로그 비교를 다시 돌려서 결과를 갱신한다. 한 번이면 "← 이전 분석으로"
  버튼으로 되돌아갈 수도 있음.
- PWA `beforeinstallprompt` 이벤트를 가로채서 메인 화면에 자체 설치 배너 노출
  (한 번 닫으면 7일간 다시 안 뜸).
- 결과 공유: 클립보드 텍스트 / JSON 다운로드 / 결과를 URL hash 에 압축해 담는
  공유 링크(같은 URL 을 다시 열면 분석 없이 결과 복원).
- 같은 파일을 다시 올리면 SHA-256 기반 LRU 결과 캐시로 즉시 응답 (raw 음원은
  안 들고 있고 해시만 키로 사용). 응답에 `cached: true` 로 표시.
- 결과 카드 펼침/접힘 토글 — 1위는 펼쳐서 두고 2위부터는 접어둬서 모바일에서
  스크롤 부담을 줄임.
- 한국어 / 영어 토글, 다크 / 라이트 테마, PWA(오프라인 폴백).
- 백엔드: threadpool 으로 librosa 분리, IP별 rate limit, magic-byte 검증,
  CSP / HSTS / X-Frame-Options 등 시큐어 헤더, 구조화 JSON 로그.

## API

```
POST /api/analyze              # multipart 업로드, top_n=1~20
GET  /api/analyze/by-catalog   # 카탈로그 곡끼리 즉시 비교 (librosa 호출 없음)
GET  /api/health               # 라이브니스, ?strict=1 이면 librosa/디스크까지 점검
GET  /api/catalog              # 사용 중인 특성 컬럼
GET  /api/catalog/sample       # 카탈로그 일부 미리보기
GET  /api/catalog/random       # 카탈로그에서 무작위 N곡 추천
GET  /api/catalog/search       # ?q=&page=&size= 제목/아티스트 검색 + 페이지네이션
GET  /docs                     # FastAPI 자동 Swagger UI
GET  /metrics                  # Prometheus exposition (uptime, latency P50/P95 포함)
GET  /catalog /compare /privacy /terms /sw.js /manifest.webmanifest /offline.html /404
```

응답에는 `X-Request-ID` 가 항상 붙는다. 분석 응답에는 `X-RateLimit-Limit /
Remaining / Reset` 도 같이 내려간다.

```bash
curl -X POST http://localhost:8000/api/analyze \
    -F "file=@./mysong.wav" \
    "?top_n=5"
```

응답 형태는 `/docs` 또는 [`backend/schemas.py`](backend/schemas.py) 참고.

## 환경 변수

| 이름 | 기본 | 설명 |
| --- | --- | --- |
| `MUSIC_ENV` | `development` | `production` 이면 HSTS 활성, CORS 명시 origin 필수 |
| `MUSIC_DATASET_PATH` | `data/dataset.csv` | 카탈로그 CSV |
| `MUSIC_UPLOAD_DIR` | `uploads/` | 임시 업로드 디렉토리 |
| `MUSIC_MAX_UPLOAD_BYTES` | `26214400` | 25MB 한도 |
| `MUSIC_MAX_CONCURRENT` | `4` | 동시 분석 처리 한도 |
| `MUSIC_RATE_LIMIT_PER_MIN` | `12` | IP당 분당 요청 한도 |
| `MUSIC_CACHE_TTL_SECONDS` | `600` | 결과 캐시 TTL (10분) |
| `MUSIC_CACHE_MAX_ENTRIES` | `64` | 결과 캐시 최대 항목 수 |
| `MUSIC_SKIP_WARMUP` | "" | `1` 이면 부팅 시 librosa 워밍업 생략 (cold-start 측정 / 테스트용) |
| `MUSIC_ALLOWED_ORIGINS` | "" (개발은 `*`) | CORS 허용 origin, 콤마 구분 |
| `MUSIC_LOG_LEVEL` | `INFO` | JSON 로그 레벨 |
| `PORT` | `8000` | 리스닝 포트 (Fly.io 등 PaaS 호환) |
| `WEB_CONCURRENCY` | `2` | uvicorn worker 수 |

## 카탈로그 다시 만들기

본인의 음원 폴더로 카탈로그를 다시 만들고 싶다면:

```bash
python scripts/rebuild_dataset.py --audio-dir ./songs --out data/dataset.csv
```

파일명 규칙은 원작 그대로 `"Song Title - Artist Name.wav"` 형태.
UI 에서 " - " 로 잘라서 아티스트를 분리 표시한다.

## 디렉토리

```
backend/      FastAPI 앱 (라우트 + 미들웨어 + ML 파이프라인)
frontend/    SPA + PWA 자산
data/        카탈로그 CSV
tests/       pytest 모음 (현재 56 케이스)
scripts/     개발/카탈로그 재빌드 스크립트
```

세부 모듈 역할은 각 파일 상단 docstring 참고.

## 테스트와 CI

```bash
pytest -q
ruff check backend tests scripts
```

CI 는 Python 3.11 / 3.12 매트릭스로 같은 검사를 매 PR 마다 돌린다. 통과 후
Docker 이미지 빌드까지 캐시 적용해서 한 번 더 확인.

## 한계 / 알아둘 것

- in-memory rate limit + metrics 라서 다중 worker 환경에선 값이 worker 별로
  파편화된다. 트래픽이 커지면 Redis 백엔드 limiter + push gateway 같은 별도
  구성이 필요함.
- 카탈로그는 약 1000곡 규모. 더 커지면 `cosine_similarity` 그대로는 메모리가
  부담이라 Annoy / FAISS 같은 ANN 구조로 바꾸는 게 맞다.
- 분석은 짧은 곡 30초만 사용한다 (`extract_features(max_duration=30)`). 가장
  특징적인 인트로 / 후렴구가 안 잡힐 수 있다는 의미.
- 사용자 음원은 분석이 끝나는 즉시 디스크에서 삭제. 모델 학습이나 카탈로그
  확장에 사용되지 않는다.
- 결과는 학술 / 취미 용도. 저작권 / 라이선스 판단의 근거가 될 수 없다.

## 라이선스

MIT. 원작 캡스톤 데이터셋과 코드는
[easygap/capstone_music](https://github.com/easygap/capstone_music) 에서 확인 가능.
