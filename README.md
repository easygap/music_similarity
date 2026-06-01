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

# 단축어로 띄우고 싶다면:
python -m backend.cli serve --reload
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

두 곡을 같은 카탈로그로 한 번에 비교하고 싶다면:

```bash
python -m backend.cli compare a.wav b.wav
# JSON 으로 받고 싶으면 --json
```

운영 중인 서버가 살아 있는지 cron / shell 한 줄로 확인하려면:

```bash
python -m backend.cli status --url http://localhost:8000
python -m backend.cli status --url https://내-서비스.example --ready
# CI / 모니터링 친화 — JSON 만 흘리고 싶으면 --json. 503 / 접속 실패면 0 이 아닌 exit code.
```

배포된 빌드가 기대한 SHA 와 일치하는지 (CI / Smoke test 용):

```bash
python -m backend.cli version
# v1.8.3 · 2026-06-01 · <git-sha>
python -m backend.cli version --json    # jq 파이프 친화
```

카탈로그 CSV 가 엔진에 잘 로딩될지 미리 점검하고, 중복된 키를 정리하려면:

```bash
python -m backend.cli validate-dataset data/dataset.csv
python -m backend.cli dedupe-dataset data/dataset.csv --out data/clean.csv
```

데이터셋을 한 번 들여다보고 싶다면:

```bash
python -m backend.cli dataset-stats data/dataset.csv
# JSON 으로 받고 싶으면 --json
```

카탈로그를 갱신한 뒤 뭐가 들고 나갔는지 확인하고 싶다면:

```bash
python -m backend.cli dataset-diff data/dataset.old.csv data/dataset.csv
# 긴 목록은 --limit 0 로 무제한, 또는 --json
```

카탈로그를 필터링해서 새 CSV 로 내보내고 싶다면 (API export 의 CLI 미러):

```bash
# 빠른 BPM 의 곡만 따로 모아 export
python -m backend.cli export-catalog --min-bpm 140 -o fast_tracks.csv

# 검색 + 정렬 + stdout 파이프
python -m backend.cli export-catalog -q remix --sort artist --stdout | head
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
- 카탈로그 둘러보기 페이지(`/catalog`) — 곡명·아티스트 검색 + 페이지네이션 +
  BPM / 에너지 범위 필터 + 곡명/아티스트/BPM/에너지 정렬 + 🎲 무작위 정렬.
  카드를 누르면 그 곡 기준 유사한 다른 곡 5건을 모달로 즉시 표시
  (`/api/analyze/by-catalog`, librosa 호출 없음).
  검색 input 에 × 버튼 + Esc 키, 매칭 부분 mark 강조, BPM 분포 막대 클릭
  시 그 구간으로 자동 필터, "즐겨찾기만 보기" 토글 옆에 카운트 chip,
  필터로 0건 나오면 "필터 초기화" 버튼 자동 노출.
- ★ 즐겨찾기 — 카탈로그 / 결과 카드의 별 버튼으로 곡을 모아둘 수 있다.
  localStorage 기반, 메인 페이지 "내 즐겨찾기" 섹션에 모이고, 카탈로그
  페이지에서 "즐겨찾기만 보기" 토글로 필터링 가능.
  즐겨찾기 섹션에서 "내보내기" 로 JSON 백업을 받고, "가져오기" 로 다른 기기에서
  복원 가능. 백업 포맷은 `{format, version, items}` 형태라 손으로 합치기도 쉬움.
- 카탈로그 페이지의 검색어 · BPM / 에너지 범위 · 정렬 · 페이지 · 즐겨찾기 토글이
  모두 URL 쿼리에 저장된다. 같은 링크를 다른 사람과 공유하면 동일한 필터 상태로
  열리고, 새로고침이나 뒤로가기에도 상태가 그대로 유지됨.
  `/catalog?song=Title%20-%20Artist` 로 곡 하나의 유사 곡 모달을 바로 열 수도 있다
  (모달 열림/닫힘이 URL 에 양방향 반영).
- 결과를 한 페이지 SVG / PNG 카드 또는 JSON / CSV 로 다운로드.
  SVG 는 클라이언트에서 직접 직렬화, PNG 는 그 SVG 를 canvas 로 2× 스케일
  래스터화. CSV 는 RFC 4180 escape + UTF-8 BOM 으로 엑셀에서 한글 안 깨짐.
  외부 라이브러리 없음.
- 결과 정렬 옵션 — 유사도 / Tempo 차이 / 에너지 차이 기준으로 카드 재배치.
  rank 번호는 그대로 유지하고 시각적 순서만 바뀐다.
- 결과 카드 안에 매칭 곡과 업로드 곡의 핵심 메트릭(Tempo/에너지/밝기) 을
  가로 mini-bar 로 직접 비교.
- 카탈로그 페이지 상단에 BPM 분포 미니 히스토그램 (`/api/catalog/stats`).
- Hero stat 의 "평균 분석 시간" 은 `/api/health` 가 함께 내려주는
  `analyze_latency_p50_seconds` 로 갱신된다 (샘플 누적 후부터). 카탈로그
  마지막 갱신 일자도 작은 라인으로 노출 (`catalog_updated_at` 활용).
  Hero 영역에는 누적 분석 횟수도 작은 social proof 라인으로 표시
  (`/api/version.analyses_total`).
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
  스크롤 부담을 줄임. "모두 펼치기 / 모두 접기" 헤더 토글로 일괄 변경 가능
  하고, 사용자 선호는 localStorage 에 저장돼 다음 분석에도 유지된다.
- 결과 페이지 키보드 네비 — `j`/`k` (↓/↑) 로 hit 카드 이동, `Enter` 로
  선택된 카드 펼침 토글. 선택된 카드는 accent ring 으로 시각 강조.
- 결과를 그대로 인쇄 / PDF 변환 가능 — `@media print` 로 nav / 컨트롤 /
  오디오 플레이어를 숨기고 카드만 흑백 톤으로 깔끔하게 출력.
- 한국어 / 영어 토글, 다크 / 라이트 테마, PWA(오프라인 폴백).
  메인 / 카탈로그 / 비교 페이지 전부 i18n 적용 — Language 토글 한 번이면 모든
  서브 페이지의 정적·동적 텍스트가 같이 바뀐다.
- 백엔드: threadpool 으로 librosa 분리, IP별 rate limit, magic-byte 검증,
  CSP / HSTS / X-Frame-Options 등 시큐어 헤더, 구조화 JSON 로그.
- 메인 페이지 업로드 카드 하단에 "🎧 샘플로 분석해보기" 버튼. 음원 준비 없이
  카탈로그에서 무작위 한 곡을 골라 결과 페이지를 그대로 체험할 수 있다.
- "새 기능 보기" 배너 — 사이트 접속 시 `/api/version.release_date` 가 사용자가
  마지막으로 확인한 값과 다르면 상단에 작은 배너가 뜨고, 클릭하면 최근 3개
  릴리즈 노트를 모달로 보여준다. 처음 방문자에게는 안 띄움.
- 카탈로그 카드에 화살표 키 네비게이션 (←/→/↑/↓ 이동, Home/End 점프).
  페이저 이동 시 새 페이지 첫 카드에 자동 포커스. 그리드에 `aria-keyshortcuts`
  부착으로 스크린리더 친화.
- 카탈로그 모달에 "🔗 링크" 공유 버튼 — 그 곡의 deep link URL 을 클립보드에 복사
  + 토스트 피드백.
- 카탈로그 필터링 결과를 CSV 로 내보내기 (UI 버튼 / API / CLI 동일 코드 경로 공유).

## API

```
POST /api/analyze              # multipart 업로드, top_n=1~20
GET  /api/analyze/by-catalog   # 카탈로그 곡끼리 즉시 비교 (librosa 호출 없음, LRU 캐시)
GET  /api/version              # 버전 + 기능 플래그 + git_commit + dependencies
GET  /api/version/changelog    # 최근 published 릴리즈 노트 (?limit=N)
GET  /api/health               # 라이브니스, ?strict=1 이면 librosa/디스크까지 점검
                               # degraded 시 reason 식별자 + release_date/git_commit 노출
GET  /api/ready                # 배포 readiness. /api/health?strict=true 와 같은 검사
GET  /api/catalog              # 사용 중인 특성 컬럼
GET  /api/catalog/sample       # 카탈로그 일부 미리보기
GET  /api/catalog/random       # 카탈로그에서 무작위 N곡 추천
GET  /api/catalog/stats        # BPM/에너지/밝기 min/max/avg + BPM 히스토그램
GET  /api/catalog/search       # ?q=&page=&size=&min_bpm=&max_bpm=&min_energy=&max_energy=&sort=
GET  /api/catalog/export.csv   # 같은 필터 조건으로 전체를 한 장의 CSV 로 (UTF-8 BOM + injection 방어)
POST /api/client-error         # 프론트엔드 글로벌 에러 비콘 (sendBeacon)
GET  /docs                     # FastAPI 자동 Swagger UI
GET  /metrics                  # Prometheus exposition (uptime, latency P50/P95 포함)
GET  /catalog /compare /privacy /terms /sw.js /manifest.webmanifest /offline.html /404
```

응답에는 `X-Request-ID` 가 항상 붙는다. 분석 응답에는 `X-RateLimit-Limit /
Remaining / Reset` 도 같이 내려간다. CORS 환경에서도 이 헤더들과 `Retry-After` 는
브라우저 JS 에서 읽을 수 있도록 노출한다. 429 응답은 표준 `Retry-After` 헤더 +
JSON body 안에도 `retry_after_seconds` / `limit` / `reset_at` 머신-친화 필드.

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
| `MUSIC_TRUSTED_PROXIES` | "" | 콤마 구분 프록시 IP. 여기 있는 출발지만 `X-Forwarded-For` 신뢰. 비어 있으면 헤더 무시. PaaS 위에 띄울 때처럼 edge IP 가 자동 발급이면 `*` 을 써서 와일드카드 신뢰 (Fly / Render 기본값) |
| `MUSIC_CACHE_TTL_SECONDS` | `600` | 결과 캐시 TTL (10분) |
| `MUSIC_CACHE_MAX_ENTRIES` | `64` | 결과 캐시 최대 항목 수 |
| `MUSIC_SKIP_WARMUP` | "" | `1` 이면 부팅 시 librosa 워밍업 생략 (cold-start 측정 / 테스트용) |
| `MUSIC_ALLOWED_ORIGINS` | "" (개발은 `*`) | CORS 허용 origin, 콤마 구분 |
| `MUSIC_LOG_LEVEL` | `INFO` | JSON 로그 레벨 |
| `PORT` | `8000` | 리스닝 포트 (Fly.io 등 PaaS 호환) |
| `WEB_CONCURRENCY` | `1` | uvicorn worker 수. Docker / Render / Fly 기본값은 단일 worker. rate limit / 결과 캐시 / metrics 가 in-memory 라 다중 워커면 한도가 워커 수만큼 곱해진다. 트래픽이 커져 여러 worker 를 쓰려면 Redis 같은 외부 상태 저장소를 먼저 붙여야 한다. |
| `MUSIC_GIT_COMMIT` | "" | 빌드 시 inject 하는 짧은 git SHA. `/api/version` · `/api/health` 응답에 노출. 비어 있으면 `.git/HEAD` 파일에서 자동 감지 (개발 환경). Dockerfile 의 `ARG GIT_COMMIT` 도 같은 변수를 채운다. 수동 Docker 빌드는 `--build-arg GIT_COMMIT=$(git rev-parse --short HEAD)` 로 넘긴다. |

## 릴리즈

1. `CHANGELOG.md` 의 `[Unreleased]` 내용을 `## [x.y.z] — YYYY-MM-DD` 섹션으로 옮긴다.
2. `backend/__init__.py` 의 `__version__` 을 같은 `x.y.z` 로 올린다.
3. main CI 가 초록인지 확인한 뒤 `git tag vx.y.z && git push origin vx.y.z`.

태그가 푸시되면 GitHub Release 워크플로가 실행된다. 이때 태그 버전,
`backend.__version__`, `CHANGELOG.md` 의 릴리즈 섹션이 하나라도 다르면
릴리즈 생성을 중단한다.

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
tests/       pytest 모음 (CI 매트릭스에서 매 PR 실행)
scripts/     개발/카탈로그 재빌드 스크립트
```

세부 모듈 역할은 각 파일 상단 docstring 참고.

## 테스트와 CI

```bash
pytest -q
ruff check backend tests scripts
```

CI 는 Python 3.11 / 3.12 / 3.14 매트릭스로 같은 검사를 매 PR 마다 돌린다. 통과 후
Docker 이미지 빌드까지 캐시 적용해서 한 번 더 확인한다. 이 빌드는
`GIT_COMMIT=${{ github.sha }}` build-arg 를 넘겨 `/api/version.git_commit` 으로
이미지 출처를 확인할 수 있게 한다.

Dockerfile / docker-compose / Render / Fly healthcheck 는 `/api/ready` 를 호출한다.
`/api/ready` 는 `/api/health?strict=true` 와 같은 readiness probe 라서 카탈로그
로드뿐 아니라 librosa/sklearn import 와 업로드 디렉토리 쓰기까지 확인한다.
프로세스는 떠 있지만 실제 분석 업로드가 실패하는 상태를 더 빨리 잡기 위해서다.

## 한계 / 알아둘 것

- in-memory rate limit + metrics 라서 다중 worker 환경에선 값이 worker 별로
  파편화된다. 트래픽이 커지면 Redis 백엔드 limiter + push gateway 같은 별도
  구성이 필요함.
- 카탈로그는 현재 781곡 규모. 더 커지면 `cosine_similarity` 그대로는 메모리가
  부담이라 Annoy / FAISS 같은 ANN 구조로 바꾸는 게 맞다.
- 분석은 짧은 곡 30초만 사용한다 (`extract_features(max_duration=30)`). 가장
  특징적인 인트로 / 후렴구가 안 잡힐 수 있다는 의미.
- 사용자 음원은 분석이 끝나는 즉시 디스크에서 삭제. 모델 학습이나 카탈로그
  확장에 사용되지 않는다.
- 결과는 학술 / 취미 용도. 저작권 / 라이선스 판단의 근거가 될 수 없다.

## 라이선스

MIT. 원작 캡스톤 데이터셋과 코드는
[easygap/capstone_music](https://github.com/easygap/capstone_music) 에서 확인 가능.
