# 변경 이력

이 프로젝트의 모든 의미 있는 변경은 이 파일에 기록합니다. 형식은
[Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 를 따르고,
버전 규약은 [SemVer](https://semver.org/lang/ko/) 를 따릅니다.

## [Unreleased]

### Added
- 카탈로그 페이지의 모든 필터 상태(검색어 · BPM/에너지 범위 · 정렬 · 페이지 ·
  즐겨찾기 토글) 를 URLSearchParams 로 양방향 동기화. 같은 URL 을 공유하면
  동일한 화면이 그대로 열리고, 새로고침 / 뒤로가기에도 상태가 유지된다.
  쓰기는 180ms 디바운스 + `history.replaceState` 라 히스토리 스택을 망치지 않음.
- 즐겨찾기 JSON 백업 / 복원. 메인 페이지 "내 즐겨찾기" 섹션에 `내보내기` /
  `가져오기` 버튼 추가. 백업 포맷은 `{format: "soundmatch.favorites", version,
  exportedAt, items}` 이고, 가져오기는 기본적으로 **병합** 모드 — 기존 즐겨찾기에
  새 항목만 더한다. raw 배열만 들어와도 받아들이도록 sanitize 후 처리.
- `SoundMatchFavorites.exportJson` / `importJson` / `replaceAll` 공개 API.
  외부에서 직접 호출해 백업 자동화 / 복원 스크립트를 짤 수 있다.
- `tests/test_frontend_assets.py` — 새 기능이 회귀로 지워지지 않도록 정적
  검사를 추가 (12 케이스). 총 116 케이스.

### Added (earlier)
- `GET /api/catalog/stats` — BPM / 에너지 / 밝기의 min/max/avg + BPM 분포
  히스토그램(기본 10 bin, 60~200 BPM 고정 범위). 5분 캐시.
- 카탈로그 페이지 상단에 BPM 분포 미니 막대 차트 (`/api/catalog/stats`).
  곡 수 / 평균 BPM 라벨도 옆에 노출.
- 결과 hit 카드 안에 매칭 곡 vs 업로드 곡의 핵심 메트릭(Tempo/에너지/밝기)
  를 가로 mini-bar 로 비교. 같은 정규화 범위라 한 눈에 차이가 보임.

### Added (earlier)
- `/api/catalog/search` 확장: `min_bpm`, `max_bpm`, `min_energy`, `max_energy`,
  `sort=default|title|artist|bpm|energy` 쿼리 추가. 카탈로그 페이지에
  BPM/에너지 범위 input + 정렬 select UI 노출.
- `POST /api/client-error` 비콘 엔드포인트 + `soundmatch_client_errors_total`
  카운터. 프론트엔드 글로벌 에러 boundary 가 `navigator.sendBeacon` 으로
  에러 메타(없으면 fetch keepalive)를 백엔드로 전송. 1초 디바운스.

### Added (earlier)
- 결과 페이지 정렬 옵션 — 유사도 (기본) / Tempo 차이 / 에너지 차이 기준으로
  카드 순서가 즉시 재배치된다. rank 라벨은 그대로 유지.
- CLI `compare` 서브커먼드: `python -m backend.cli compare a.wav b.wav`.
  같은 카탈로그로 두 곡을 분석해 메트릭 표 / 태그 / 각자의 1위 매칭을 한 번에
  비교. `--json` 으로 기계 가독 출력.
- `.github/workflows/release.yml` — `v*.*.*` 태그를 푸시하면 CHANGELOG 의 해당
  버전(또는 Unreleased) 섹션을 발췌해서 GitHub Release 를 자동 생성.

### Added (earlier)
- `GET /api/version` — 버전 / 환경 / 카탈로그 사이즈 / 기능 플래그 / 업로드 한도
  / rate limit 한도를 한 번에 돌려준다. SDK / 클라이언트 호환성 체크용.
- `/api/analyze/by-catalog` 에 LRU 캐시 적용. 같은 (name, top_n) 입력은
  두 번째 호출부터 `cached: true` 로 즉시 응답.
- 분석이 끝나면 결과를 `location.hash` 에 자동으로 직렬화 (history.replaceState).
  새로고침 / 북마크 만으로도 결과가 살아남는다. URL 이 8KB 를 넘으면 안전상 skip.
- `python -m backend.cli serve [--host] [--port] [--reload]` 서브커먼드.
  uvicorn 실행 단축어, `pip install` 없이 호출 가능 (uvicorn 누락 시 친절 에러).

### Added / Changed (earlier)
- 엔진이 카탈로그의 중복 키(같은 "곡명 - 아티스트") 를 자동으로 제거하고
  `dropped_duplicate_count` 로 노출. 첫 번째 행을 유지하고 나머지를 떨군다.
  중복이 있으면 운영 로그에 `catalog_duplicates_dropped` 경고.
- `python -m backend.cli dedupe-dataset <csv> --out <new.csv>` 서브커먼드.
  입력과 같은 파일을 덮어쓸 땐 `--overwrite` 명시 필요.
- 실제 `data/dataset.csv` 를 dedupe 해서 785 → 781행으로 정리해 같이 커밋.
- 결과 페이지 PNG 저장 버튼 추가. SVG 카드를 canvas 로 2× 스케일 래스터화 후
  toBlob 으로 다운로드. SVG 변환 실패 시 토스트로 안내.

### Added (earlier)
- 결과 페이지 "카드 이미지 저장" 버튼. 클라이언트에서 직접 SVG 문자열을
  짜서 Blob 다운로드. 외부 라이브러리 없음. 다크 톤 + 그라데이션 막대 + 태그.
- `python -m backend.cli validate-dataset <csv>` 서브커먼드. 행 수 / 중복키 /
  NaN/Inf 행 / 분산 0 컬럼을 리포트하고 실제 엔진 로딩까지 시도.
- Hero stat 의 "평균 분석 시간" 을 `/api/health.analyze_latency_p50_seconds`
  로 정직화. 샘플이 없으면 기본 문구 유지.
- 카탈로그 페이지 모달의 결과 항목에 ★ 토글 + "→" 시드 재탐색 버튼.
  모달 안에서 깊이 탐색 가능.

### Added (earlier)
- ★ 즐겨찾기 기능 (`frontend/js/favorites.js`).
  - 카탈로그 페이지 카드 / 결과 hit 카드에 ★ 토글.
  - 메인 페이지에 "내 즐겨찾기" 섹션 (저장된 곡 있을 때만 노출).
  - 카탈로그 페이지에 "즐겨찾기만 보기" 체크박스.
  - 즐겨찾기 카드를 누르면 그 곡 기준으로 카탈로그 재분석 (시드 탐색 흐름 재사용).
  - localStorage 키 `soundmatch.favorites.v1`, max 200곡.

### Added (earlier)
- 결과 카드의 매칭 곡에 "이 곡으로 다시 찾기" 버튼. 누르면 그 곡을
  `/api/analyze/by-catalog` 로 새 시드 분석한다. 결과 헤더에 "← 이전 분석으로"
  스택 1단계 백 버튼이 함께 노출 (한 단계만 보관).
- `/api/health` 응답에 `uptime_seconds` 필드 추가.
- `/metrics` 에 `soundmatch_uptime_seconds`, `_analyze_latency_p50_seconds`,
  `_analyze_latency_p95_seconds` 게이지 신규. 최근 256건 분석 latency 의 분포.

### Added (earlier)
- `GET /api/analyze/by-catalog?name=&top_n=` — 카탈로그에 이미 있는 곡 이름을
  넣으면 그 곡의 raw 특성으로 즉시 유사도를 돌려준다. librosa 호출이 없어
  체감 응답 시간은 ~10ms 수준. 1위는 자기 자신이라 자동 제외.
- `/catalog` 페이지 카드를 클릭하면 그 곡과 유사한 다른 곡 5건을 모달로
  바로 보여준다 (Esc / 백드롭 클릭으로 닫힘, 포커스 복귀까지 처리).
- CLI batch 모드: `python -m backend.cli batch <폴더> --out results.csv`.
  폴더 안 음원을 전부 분석하고 (파일 × top_n) 행짜리 CSV 출력. 실패 파일
  스킵하면서 진행 표시.

### Added (earlier)
- 명령줄 도구 `python -m backend.cli analyze <파일> [--top-n N] [--json]`.
  서버 없이도 같은 엔진으로 카탈로그 비교를 돌릴 수 있다. 사람-가독 또는 JSON 출력.
- `GET /api/catalog/random?n=` 엔드포인트. 메인 페이지 카탈로그 미리보기에
  "다른 곡 보기" 버튼 신설 — 누르면 무작위 12곡으로 교체.
- 부팅 시점 librosa / numba 워밍업. 짧은 사인파 한 번 흘려서 첫 사용자
  분석 latency 를 줄임. `MUSIC_SKIP_WARMUP=1` 로 비활성화 가능.

### Added (earlier)
- 카탈로그 검색 + 페이지네이션 API (`GET /api/catalog/search?q=&page=&size=`).
  곡명/아티스트 부분 일치(대소문자 무시) + has_more 플래그 포함.
- `/catalog` 페이지. 검색창 (한글 IME 280ms 디바운스) + 카드 그리드 + 페이지네이션.
- nav 에 "카탈로그" 링크 추가 (ko/en i18n).
- PWA `beforeinstallprompt` 가로채는 자체 설치 배너 — 7일 닫힘 기억.
- `GET /api/health?strict=1` 모드: librosa/sklearn 임포트 + 업로드 디렉토리
  쓰기 권한까지 점검해서 운영 환경 readiness probe 로 사용 가능.
- `/metrics` 에 `soundmatch_inflight_analyses` gauge 추가 (동시 분석 수).

### Added (earlier)
- 분석 결과 in-memory LRU 캐시 (`backend/cache.py`). 같은 파일을 다시 올리면
  SHA-256 키로 즉시 응답. raw 음원은 들고 있지 않고 해시만. 환경변수:
  `MUSIC_CACHE_TTL_SECONDS` (기본 600), `MUSIC_CACHE_MAX_ENTRIES` (기본 64).
- AnalyzeResponse 에 `analyzed_at`, `engine_version`, `cached` 메타 필드.
  결과 JSON 을 나중에 다시 봐도 어떤 엔진 버전 / 언제 분석된 결과인지 명확.
- 결과 카드 펼침 / 접힘 토글. 1위 카드만 펼친 상태로 두고 나머지는 접어둠.
  결과가 5~10개여도 첫 인상이 깔끔하고 모바일 스크롤이 짧다.
- `HEAD /api/health` 메서드 지원 (UptimeRobot 같은 모니터 도구 친화).
- `/sitemap.xml` 에 `/`, `/compare`, `/privacy`, `/terms` 가 명시적으로 포함.
- `/metrics` 에 `soundmatch_cache_hits_total`, `_misses_total`,
  `soundmatch_cache_entries` 추가.

### Added (earlier in this cycle)
- 휴리스틱 장르 태깅 (`backend/tagging.py`): BPM, RMS, 스펙트럴 센트로이드,
  ZCR, HPSS 비율을 보고 "빠른 템포 / 에너지 폭발 / 밝은 톤" 같은 칩을 생성.
  AnalyzeResponse 에 `tags: list[str]` 필드 추가.
- 결과 페이지 상단에 태그 칩 렌더 (i18n 키 nav.compare 추가).
- 두 곱 비교 페이지 (`/compare`, `frontend/compare.html`):
  localStorage 히스토리에서 두 분석을 골라 메트릭 / 태그 / Top1 매칭을 나란히 비교.
- Rate limit 헤더 노출: 분석 응답에 `X-RateLimit-Limit`, `X-RateLimit-Remaining`,
  `X-RateLimit-Reset` 자동 첨부 (`_rate_limit` 의존성 → request.state →
  RequestLogMiddleware 가 일괄 헤더 전파).
- Prometheus 호환 `/metrics` 엔드포인트 (외부 라이브러리 의존 없이 직접 직렬화):
  `soundmatch_requests_total`, `_analyze_success_total`, `_analyze_failed_total`,
  `_rate_limited_total`, `_catalog_size`.
- 결과 페이지에서 "공유 링크 복사" 버튼으로 분석 결과를 URL 한 번에 전달.
  CompressionStream 으로 gzip 압축 후 base64url 인코딩해 URL hash 에 직렬화.
  같은 URL 을 다시 열면 별도 분석 없이 결과가 자동 복원됨.
- 정적 페이지 `/privacy`, `/terms` 추가. 푸터에서 링크.
- 카탈로그 일부 미리보기 카드 + `GET /api/catalog/sample` 엔드포인트.
- `.github/dependabot.yml` 으로 pip / GitHub Actions 의존성 자동 PR.
- `SECURITY.md`, `CODE_OF_CONDUCT.md` 추가 (한국어 톤).
- i18n 키 누락 자동 감지 테스트.

### Changed
- 분석 실패 / 성공 카운터를 in-process metric 으로 노출.
- README 톤 정리. 배지/이모지 폭격 빼고, 자랑 문구 줄이고, in-memory rate
  limit 한계나 카탈로그 사이즈 같은 알아둘 것까지 솔직하게 적도록 다시 씀.

## [1.2.0] — 2026-05-13

### Added
- PWA 지원: `manifest.webmanifest`, Service Worker (stale-while-revalidate),
  `offline.html` 폴백, 모바일 홈 화면 추가 가능.
- 멜 스펙트로그램 SVG 응답: librosa + numpy 만으로 96×48 그리드 생성,
  `/api/analyze` 응답에 `spectrogram_svg` 포함.
- Web Share API 통합 — 모바일 네이티브 공유 시트.
- OpenAPI 응답 모델 정의 (`HealthResponse`, `CatalogResponse`,
  `AnalyzeResponse` 등) — `/docs` Swagger UI 가 깔끔해짐.
- 글로벌 JS 에러 boundary (window.onerror + unhandledrejection).

## [1.1.0] — 2026-05-13

### Added
- 백엔드 동시성: `extract_features` 를 `run_in_threadpool` 로 분리해
  이벤트 루프 블로킹 제거. `asyncio.Semaphore` 로 동시 분석 cap.
- IP별 sliding-window rate limiter (`MUSIC_RATE_LIMIT_PER_MIN`).
- Magic byte 검증으로 확장자만 믿지 않는 업로드 검사.
- `SecurityHeadersMiddleware`: CSP/HSTS/X-CTO/X-Frame-Options/
  Referrer-Policy/Permissions-Policy 자동 적용.
- `RequestLogMiddleware`: 구조화된 JSON 로그 + X-Request-ID 라운드트립.
- StandardScaler 안전성: NaN/Inf 행 제거, zero-variance 컬럼 자동 drop.
- 프론트엔드 Web Audio 파형 + SVG 레이더 차트 + 다크/라이트 테마 +
  한국어/영어 i18n + 최근 분석 5건 히스토리 + JSON 내보내기.
- pytest 31개 (이후 32→37) + ruff 린트 + GitHub Actions CI 매트릭스 +
  Render/Fly.io 배포 설정.

## [1.0.0] — 2026-05-12

### Added
- 최초 릴리스. FastAPI + librosa + scikit-learn 기반 음악 유사도 분석 서비스.
- 캡스톤 데이터셋과 동일한 58개 특성 + StandardScaler + cosine_similarity.
- 단일 페이지 다크 프론트엔드, 드래그&드롭 업로드, 결과 카드 + "닮은 이유".
