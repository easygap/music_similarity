# 변경 이력

이 프로젝트의 모든 의미 있는 변경은 이 파일에 기록합니다. 형식은
[Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 를 따르고,
버전 규약은 [SemVer](https://semver.org/lang/ko/) 를 따릅니다.

## [Unreleased]

### Added
- 결과 페이지 인쇄 / PDF 변환 친화 CSS (`@media print`). nav / footer /
  install 배너 / audio player / radar / spectrogram / 액션 버튼 같은 화면 전용
  요소는 모두 숨기고, 결과 카드만 흑백 톤으로 깔끔하게 남긴다. 다크 테마
  사용자가 인쇄해도 토너 / 잉크가 절약되도록 강제 light 톤 + 카드 사이
  `break-inside: avoid` 로 페이지가 카드 중간에서 끊기지 않게.
- 카탈로그 페이지 검색 결과에 매칭 부분 highlight. 검색어와 case-insensitive
  로 일치하는 곡명/아티스트 substring 을 `<mark class="cat-highlight">` 로
  강조해서, 왜 이 곡이 결과에 떴는지 한눈에 보인다. dark/light 두 테마 모두
  accent 계열 톤으로 자연스럽게 녹아들도록 CSS 조정.
- 카탈로그 페이지에 🎲 무작위 정렬 옵션. `/api/catalog/search?sort=shuffle` 도
  지원. 매 요청마다 새 순서가 나오도록 응답에 `Cache-Control: no-store`.
  사용자가 카탈로그를 둘러볼 때 늘 같은 알파벳 순서만 보지 않고 우연히
  새 곡을 발견할 수 있게. URL 영구화 / lang 토글 / 회귀 안전망 모두 적용.
  신규 i18n 키 `catalog.sortShuffle` (ko/en parity).

### Changed
- `AnalysisResultCache.get()` 에 `copy=True` 옵션 추가. 캐시 entry 의 중첩
  구조(예: `results` 리스트, `summary` dict) 가 호출 측의 제자리 수정에
  오염되지 않도록 deepcopy 사본을 반환한다. `/api/analyze` 와
  `/api/analyze/by-catalog` 의 캐시 hit 경로를 모두 `copy=True` 로 갈아끼움.
  현재 코드는 dict 최상위 필드만 갈아끼지만 future-proofing 차원의 안전망.
  기본값(`copy=False`) 은 성능을 위해 같은 참조를 그대로 반환 — 읽기 전용
  케이스용. 신규 회귀 테스트 2 케이스 (총 193 passed).

### Added
- 결과 영역에 "모두 펼치기 / 모두 접기" 토글 버튼. 사용자가 선택한 모드는
  localStorage 키 `soundmatch.hit-expand-mode` 에 저장되어 다음 분석에도 유지.
  default 는 기존 동작 (1위만 펼치고 2위부터 접힘) 그대로 — 처음 진입 사용자
  경험에 변화 없음. 신규 i18n 키 `results.expandAll` / `results.collapseAll`
  (ko/en parity).
- 결과 영역에 "CSV 저장" 버튼 추가. JSON 외에 엑셀 친화 CSV 로도 결과를 받을
  수 있다. RFC 4180 escape (쌍따옴표 두 번, 본문은 quote 감싸기) + UTF-8 BOM
  으로 한글이 엑셀에서 깨지지 않게. 파일명에 ISO date stamp 포함
  (`<원본>.soundmatch-2026-05-15.csv`). 신규 i18n 키 `results.exportCsv` (ko/en).

## [1.3.0] — 2026-05-15

이번 사이클의 테마: **production-grade hardening**. 5개의 audit finding 을 모두
처리하고 추가로 다수의 UX·접근성 polish 를 적용. 외부 노출 직전 단계로 끌어올림.

### Tests
- `tests/test_middleware.py` 신규 6 케이스 — X-Request-ID 분기(헤더 없으면 새
  UUID, 있으면 그대로), `/metrics` 와 `/sw.js` 가 `requests_total` 카운터에
  잡히지 않는지, 모든 응답에 시큐어 헤더 부착, `get_engine()` 실패 시 503 +
  status=degraded, strict 모드에서 업로드 디렉토리 쓰기 실패 시 503 모두 회귀
  안전망 추가. lifespan 의 degraded path 와 미들웨어 분기를 명시적으로 보호.

### Added
- 카탈로그 BPM 히스토그램 막대 클릭 → 그 구간으로 자동 필터링. 같은 막대를
  다시 누르면 토글로 해제. 막대는 `<button>` 으로 그려서 키보드 탭 / Enter
  모두 동작. 현재 필터 범위와 정확히 일치하는 막대에는 시각적 active 표시
  (가속 색 underline). 신규 i18n 키 `catalog.histClickHint` (ko/en).

### Fixed
- 분석 진행 중에 새 파일을 올리거나 "새 분석" 으로 돌아갈 때 이전 fetch 가
  그대로 끝까지 진행되어 두 결과가 뒤섞이는 race. `runAnalysis` 에
  `AbortController` 를 도입해 이전 요청을 cancel, 응답이 도착할 때 controller
  identity 가 바뀌어 있으면 화면 갱신을 건너뛴다. 리셋 버튼도 진행 중인
  분석을 같이 cancel. `AbortError` 는 에러 화면을 안 띄우고 조용히 종료.
- 글로벌 에러 boundary 의 토스트 문구가 한국어로 하드코딩되어 EN 토글
  상태의 사용자에게도 한국어로 보이던 위화감. `error-boundary.js` 가
  `window.i18n` 을 가능하면 사용하고, 없으면 한국어로 폴백.
- 신규 i18n 키 `error.globalToast`, `error.unhandledToast` (ko/en parity).
- 분석 히스토리 항목이 ~320KB 짜리 멜 스펙트로그램 SVG 를 통째로
  localStorage 에 저장해서, 5건만 쌓여도 1.6MB. 즐겨찾기와 같은 5MB 도메인
  쿼터를 빠르게 잠식하던 문제. 히스토리 저장 시 SVG 필드를 비운
  trimmed 페이로드만 보관. 결과 화면을 다시 그릴 때 SVG 가 없어도 카드가
  자동으로 숨겨지도록 이미 처리되어 있어 UX 영향 없음.
- writeHistory / favorites write 가 쿼터 초과 / 시크릿 모드 등으로 실패해도
  silently 무시되어 사용자가 영문도 모르고 히스토리·즐겨찾기가 안 늘어나던
  문제. 토스트로 안내하고, favorites.js 는 `favorites:storage-full`
  CustomEvent 를 쏘아 app.js 에서 일괄 처리.
- 신규 i18n 키 `history.storageFull`, `favorites.storageFull` (ko/en parity).
- PaaS(Fly.io / Render) 배포 환경에서 rate limiter 가 사실상 무력화되던
  문제. edge 프록시 IP 가 자동 발급이라 trusted proxies 화이트리스트가
  비어 있어 `_client_ip` 가 동일 edge IP 한 개만 보고 모든 사용자를 같은
  버킷에 묶었음. 한 사용자만 빠르게 두드려도 전체가 429 에 빠짐.
  `MUSIC_TRUSTED_PROXIES=*` 와일드카드 옵션 추가 — 모든 출발지에서 온 XFF
  를 신뢰한다. `fly.toml` / `render.yaml` 도 이 값으로 설정.
- 다중 워커 시 `_rate_state` / 결과 캐시 / metrics 카운터가 워커별로 파편화
  되어 한도가 워커 수만큼 곱해지던 문제. `WEB_CONCURRENCY=1` 을 production
  기본값으로 명시(fly.toml / render.yaml). 정확한 한도가 필요하면 Redis
  백엔드 도입까지는 단일 워커 + 수직 확장으로 처리.

### Security
- CSP `script-src` 에서 `'unsafe-inline'` 제거. 그동안 모든 인라인 스크립트
  실행을 허용해서, 결과 카드 어딘가에 `escapeHtml` 하나만 빠져도 그대로 XSS
  가 됐었음. 이제 같은 출처에서 받은 외부 JS 만 실행 가능.
- 인라인이던 테마 초기화 / SW 등록 / 글로벌 에러 boundary 코드를 각각
  `frontend/js/theme-init.js`, `sw-register.js`, `error-boundary.js` 로 분리.
  `theme-init.js` 는 모든 HTML 페이지가 공통으로 사용, 나머지 둘은 메인
  페이지에서만. SW SHELL 에도 새 파일 3개 + VERSION bump (v2 → v3).
- 회귀 안전망 3개: CSP 에 unsafe-inline 다시 들어오면 / 새 JS 파일이
  404 가 되면 / HTML 페이지에 인라인 `<script>` 본문이 살아 있으면 모두 fail.

### Tests
- `tests/test_spectrogram.py` 신규 13 케이스 — `_downsample_2d`, `_color_for`,
  `_render_svg`, `build_mel_spectrogram_svg` 의 경계 / 극단값 / aria-label /
  hex 컬러 포맷 / 평균 풀링 정확도 등을 헬퍼 단위로 직접 검증. 그동안 통합
  경로 한 줄로만 묶여 있어 swallow 되던 회귀를 잡는다.
- `/api/client-error` 비콘 엣지 케이스 3종 — 비-dict (배열) 본문 / 깨진 JSON /
  oversize message+source 모두 204 로 안전하게 받아야 한다.

### Fixed
- analyze() 의 in-flight 카운터 race — extension/size 검증 단계에서 일찍
  실패한 요청이 finally 에서 다른 정상 요청의 카운터를 잘못 깎아 `/metrics`
  의 `soundmatch_inflight_analyses` 게이지가 실제 동시 처리 수와 어긋나던
  문제. 로컬 boolean 으로 increment 여부를 추적해 짝이 맞는 decrement 만
  수행.
- "이 곡으로 다시 찾기" 버튼이 by-catalog fetch 실패 시 에러 화면을 띄우면서
  사용자가 이전 분석 결과 화면을 통째로 잃던 회귀. 실패 시엔 토스트만 띄우고
  이전 결과 카드를 그대로 다시 그리도록 정정.
- 결과 카드의 mini-metric 라벨이 "Tempo / 에너지 / 밝기" 로 하드코딩되어 있어
  EN 토글 상태에서도 한국어로 보이던 문제. `summary.tempo / energy / brightness`
  i18n 키를 재사용하도록 정정 — 토글 즉시 라벨이 같이 바뀜.
- 신규 `results.seedFailedToast` i18n 키 (ko/en).

### Security
- Rate limiter 가 `X-Forwarded-For` 헤더를 무조건 신뢰해 누구나 헤더 위조로
  분당 요청 한도를 우회할 수 있던 문제 해결. 신규 환경변수
  `MUSIC_TRUSTED_PROXIES` 에 등록된 출발지에서 온 요청에서만 `X-Forwarded-For`
  / `X-Real-IP` 를 신뢰하고, 그 외엔 `request.client.host` 만 사용.
- `_rate_state` dict 가 회전 IP 공격에 한도 없이 자라 메모리 누수가 되던 문제
  해결. 매 요청마다 가벼운 GC 로 윈도우(60s) 밖의 idle IP 키를 정리.

### Accessibility
- 카탈로그 모달이 열리면 Tab / Shift+Tab 으로 모달 안의 조작 가능 요소만
  순환하도록 포커스 트랩 적용. 닫기 / ★ / → 시드 / 모달 카드 요소를 빠짐없이
  순회. 열림 직후엔 첫 번째 조작 가능 요소(닫기 버튼) 로 자동 포커스 — 키보드 /
  스크린리더 사용자가 모달 안에서만 키를 잡고 있도록.

### Added
- 알 수 없는 경로 접근 시 styled `/404` 페이지로 자동 폴백. 브라우저 navigation
  (Accept: text/html) 만 styled HTML 응답, 그 외 (API / metrics 등) 는 기존
  JSON 응답을 유지해서 클라이언트 호환성은 그대로 둔다.
- 404.html 도 i18n 적용 — `notFound.title` / `sub` / `home` 세 키 신규 (ko/en).
- 카탈로그 빈 결과 상태에 "필터 초기화" 버튼. 검색어 / BPM / 에너지 / 정렬 /
  즐겨찾기만 보기 / 페이지 / song 모달까지 한 번에 기본값으로 되돌린다.
  필터가 한 개라도 걸린 상태에서만 노출.

### Fixed
- Service Worker 의 precache SHELL 에 `/catalog`, `/compare`, `/favorites.js`
  가 빠져 있던 문제. 오프라인 첫 진입에서 이 페이지들이 비어 보이던 회귀를 막음.
  버전을 `soundmatch-v1` → `soundmatch-v2` 로 bump 해서 옛 캐시는 자동 폐기.
- stale-while-revalidate 경로에서 캐시가 있을 때 백그라운드 갱신을 안전하게
  무시하도록 정리. 네트워크 실패가 더 이상 콘솔 노이즈로 전파되지 않는다.

### Added
- `/sitemap.xml` 에 카탈로그 곡 딥링크 전부 노출. 새로 들어온 `/catalog?song=`
  와이어링과 결합해서 검색 봇이 곡 단위 유일한 URL 을 인덱싱할 수 있다.
  현재 시드 카탈로그 기준 781 곡 + 5 정적 페이지 = 786 URL.
- 카탈로그 모달 딥링킹 — `/catalog?song=Title%20-%20Artist` 형태로 URL 을 직접
  치거나 공유하면 그 곡 기준 유사 곡 모달이 자동으로 열린다. 모달을 열고 닫는
  동작도 URL 에 양방향으로 반영되어서 뒤로가기 / 새로고침 / 북마크 / 카카오톡
  링크 공유 모두 자연스럽게 동작.

### Fixed
- `/catalog` 와 `/compare` 페이지에서 `i18n.js` 가 로딩되지 않아 메인 페이지의
  Language 토글이 서브 페이지에는 반영되지 않던 문제. 두 페이지 모두 i18n.js
  를 직접 불러오고 정적/동적 텍스트를 모두 `data-i18n` + `i18n.t()` 로 교체.
  `i18n:change` 이벤트 구독으로 lang 토글 시 즉시 다시 그린다.

### Added
- i18n 사전에 `catalog.*` / `compare.*` 키 세트 신규 추가(ko/en 동일 트리).
  카탈로그 페이지 정렬 옵션, 페이저, 모달 안의 "분석 중", 매칭 없음, 다시
  시도 메시지 등 23개 키. compare 페이지는 메트릭 라벨 6개 + 헤더 + 빈
  상태 안내까지 모두 i18n 화.
- `tests/test_frontend_assets.py` 에 catalog/compare i18n 회귀 안전망 19개
  추가. 총 135 케이스.

### Added (earlier)
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
