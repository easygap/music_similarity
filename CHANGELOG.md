# 변경 이력

이 프로젝트의 모든 의미 있는 변경은 이 파일에 기록합니다. 형식은
[Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 를 따르고,
버전 규약은 [SemVer](https://semver.org/lang/ko/) 를 따릅니다.

## [Unreleased]

## [1.8.15] — 2026-06-02

v1.8.14 릴리즈 직후 운영에 노출되는 `release_date` 메타데이터가 실제 GitHub
Release publish 일자와 어긋날 수 있던 부분을 보정한 패치 릴리즈.

### Fixed
- `CHANGELOG.md` 최상단 published 섹션과 `backend.__version__` 을 `1.8.15` 로
  맞춰 `/api/version`, `/api/health`, CLI `version`, 프리뷰 서버가 모두
  `2026-06-02` 릴리즈 날짜를 노출하게 했다.
- 실제 2026-06-02 에 배포된 `v1.8.14` 섹션 날짜도 같은 날짜로 정정했다.

### Tests
- 최상단 CHANGELOG 릴리즈가 패키지 버전/README CLI 예시와 같은 버전·날짜를
  쓰는지 확인하는 릴리즈 메타데이터 회귀 테스트를 추가했다.

## [1.8.14] — 2026-06-02

v1.8.13 이후 디자인 프리뷰 서버의 PWA 자산 drift 를 없앤 패치 릴리즈.
운영 FastAPI 와 프리뷰 서버가 같은 루트 정적 자산 경로를 제공하도록 맞췄다.

### Fixed
- `preview_server.py` 가 `/og-image.svg`, `/app-icon-192.png`,
  `/app-icon-512.png`, `/maskable-icon-512.png`, `/apple-touch-icon.png` 를
  `frontend/assets/` 아래 실제 파일로 alias 하도록 했다. 이제 프리뷰에서
  manifest, 서비스워커 shell, apple touch icon 링크가 같은 경로로 동작한다.

### Tests
- 프리뷰 서버가 favicon, OG 이미지, PWA PNG 아이콘 루트 경로를 200 으로
  서빙하고 파일 시그니처와 Content-Type 이 맞는지 확인하는 회귀 테스트를
  추가했다.

## [1.8.13] — 2026-06-01

v1.8.12 이후 PWA 설치 품질을 보강한 패치 릴리즈. 홈 화면에 추가했을 때
브라우저/OS 별 아이콘 처리 차이가 덜 나도록 SVG favicon 만 의존하던 구성을
PNG 앱 아이콘 세트로 확장했다.

### Added
- 192px / 512px PNG 앱 아이콘, maskable 512px 아이콘, iOS 용
  `apple-touch-icon.png` 를 추가했다.
- manifest 의 `icons` 와 shortcut 아이콘이 PNG 자산을 함께 가리키도록 정리했다.
- 카탈로그 / 비교 / 개인정보 / 이용약관 / 오프라인 / 404 페이지 head 에도
  manifest, theme color, apple touch icon 메타를 노출했다.

### Changed
- 새 PWA 아이콘 자산이 오프라인 shell 에 포함되도록 서비스워커 캐시 버전을
  `soundmatch-v12` 로 올렸다.

### Tests
- manifest PNG/maskable 아이콘, 루트 PNG 아이콘 서빙, shell 페이지의 PWA head
  메타, SW shell 아이콘 포함 여부를 검증하는 회귀 테스트를 추가/갱신했다.

## [1.8.12] — 2026-06-01

v1.8.11 이후 배포된 홈 화면을 메신저나 SNS 에 공유할 때 카드 메타데이터가
실제 서비스 주소를 가리키도록 정리한 패치 릴리즈. GitHub 저장소 주소가 앱
대표 URL 처럼 노출되던 정적 기본값을 걷어냈다.

### Fixed
- 홈 HTML 의 canonical, `og:url`, `og:image`, `twitter:image` 를 현재 요청의
  Host 기준 절대 URL 로 내려주도록 했다. Render/Fly 같은 신뢰 프록시 뒤에서는
  `X-Forwarded-Proto` / `X-Forwarded-Host` 를 반영해 외부 HTTPS 주소가 공유
  카드에 들어간다.
- 정적 `index.html` 의 `og:url` 기본값을 GitHub 저장소 주소가 아닌 `/` 로
  바꿔, 프리뷰/정적 확인에서도 앱 자체 URL 이 기준이 되게 했다.

### Tests
- 홈 공유 메타가 요청 Host 와 신뢰 프록시 헤더를 따라가는지 확인하는 API
  회귀 테스트를 추가했다.

## [1.8.11] — 2026-06-01

v1.8.10 이후 이용약관을 실제 기능 범위에 맞춰 갱신한 패치 릴리즈. 공유 링크,
내보내기, 브라우저 저장, 오류 비콘처럼 이미 제품에 들어간 기능의 책임 경계를
사용자가 한 페이지에서 확인할 수 있게 정리했다.

### Changed
- `/terms` 최종 업데이트 날짜를 2026-06-01 로 맞추고 공유 링크, 내보내기,
  즐겨찾기/localStorage, 클라이언트 오류 비콘, Rate limit/남용 금지, 결과의
  법적 판단 한계를 명시했다.
- PWA shell 에 캐시되는 `terms.html` 변경이 바로 반영되도록 SW VERSION 을
  `soundmatch-v11` 로 올렸다.

### Tests
- 이용약관 주요 고지와 서비스워커 캐시 버전 bump 를 확인하는 프론트엔드 정적
  회귀 테스트를 추가/갱신했다.

## [1.8.10] — 2026-06-01

v1.8.9 이후 공개 운영 보조 API 의 방어선을 보강한 패치 릴리즈. 프론트엔드
오류 비콘 엔드포인트가 큰 본문을 먼저 읽고 파싱하지 않도록 제한을 추가했다.

### Fixed
- `/api/client-error` 가 `MUSIC_CLIENT_ERROR_MAX_BYTES` (기본 8KB) 보다 큰
  본문을 받으면 내용을 버리거나 cap 처리한 뒤 204 로 끝내도록 했다. 정상
  브라우저 비콘은 기존처럼 처리하되, 악성/오작동 클라이언트가 큰 JSON 으로
  메모리 / 로그 비용을 키우는 상황을 줄였다.

### Added
- `/metrics` 에 `soundmatch_client_error_payloads_capped_total` 카운터를 추가해
  크기 제한에 걸린 오류 비콘 수를 운영자가 확인할 수 있게 했다.

## [1.8.9] — 2026-06-01

v1.8.8 이후 디자인 프리뷰 서버의 릴리즈 메타데이터 drift 를 없앤 패치
릴리즈. 로컬 프리뷰에서 보는 footer / 새 기능 모달 / 버전 API 가 실제 앱
버전과 어긋나지 않도록 정리했다.

### Fixed
- `preview_server.py` 의 `/api/version`, `/api/health`, `/api/version/changelog`
  응답이 더 이상 `1.7.0` 과 오래된 릴리즈 날짜를 하드코딩하지 않게 했다.
  프리뷰 서버는 가벼운 CHANGELOG 파서와 `backend.__version__` 을 사용해 현재
  릴리즈 버전 / 날짜 / 최근 릴리즈 노트를 그대로 내려준다.

### Tests
- 프리뷰 서버 회귀 테스트가 `/api/version`, `/api/health`,
  `/api/version/changelog` 의 첫 릴리즈가 현재 앱 버전과 같은지 확인하도록
  강화됐다.

## [1.8.8] — 2026-06-01

v1.8.7 이후 모바일 결과 카드에서 사용자가 다음 행동을 더 쉽게 고를 수 있게
CTA 우선순위를 정리한 패치 릴리즈. 외부 스트리밍 링크보다 재탐색 / 저장 /
카탈로그 확인을 먼저 보여주도록 결과 카드의 하단 액션 흐름을 다듬었다.

### Changed
- 결과 카드 하단 액션의 DOM 순서를 `이 곡으로 다시 찾기 → 즐겨찾기 →
  카탈로그에서 보기 → YouTube → Spotify` 로 바꿨다. 스크린리더 / 키보드
  순서도 화면의 제품 내 행동 우선순위와 같아진다.
- 모바일 결과 카드 액션을 2열 grid 로 정리했다. 재탐색 / 즐겨찾기 / 카탈로그
  버튼은 전체 폭 CTA 로 두고, YouTube / Spotify 는 보조 외부 링크로 2열 배치해
  360px 폭에서도 40px 터치 면적과 가로 overflow 없는 상태를 유지한다.

### Tests
- 프론트엔드 정적 회귀 테스트에 결과 카드 CTA 순서와 모바일 CTA 레이아웃 조건을
  추가했다.

## [1.8.7] — 2026-06-01

v1.8.6 이후 모바일 터치 사용성을 다듬은 패치 릴리즈. 홈 / 카탈로그 /
비교 화면의 주요 버튼과 폼 컨트롤이 작은 화면에서도 손가락으로 안정적으로
눌리도록 터치 면적을 맞췄다.

### Changed
- 공용 네비게이션 아이콘 버튼, pill 버튼, select, 결과 액션 버튼의 최소 높이를
  40px 기준으로 맞췄다. 모바일 flex 축소로 햄버거 / 테마 버튼이 32~35px 까지
  줄어들던 문제도 `flex: 0 0 40px` 로 막았다.
- 카탈로그 검색 clear, 필터 숫자 입력 / 정렬 select, CSV 내보내기, 페이지 이동,
  최근 본 곡 칩, 모달 액션, 카드 즐겨찾기 별 버튼의 터치 타깃을 40px 이상으로
  정리했다. 특히 카드 별 버튼은 보이는 별 크기는 유지하면서 hit area 만 키웠다.

## [1.8.6] — 2026-06-01

v1.8.5 이후 샘플/업로드 분석이 끝나는 순간의 접근성 흐름을 다듬은 패치
릴리즈. 결과가 화면에 나타났다는 사실을 키보드와 스크린리더 사용자도 바로
알 수 있게 했다.

### Fixed
- 분석 완료 후 결과 영역으로 스크롤만 이동하고 키보드 포커스는 남아 있던 흐름을
  보강했다. 결과 섹션을 제목으로 라벨링하고 새 결과가 렌더링되면 `분석 결과`
  제목에 포커스를 보내 스크린리더 / 키보드 사용자도 상태 전환을 바로 알 수 있게
  했다. 정렬이나 언어 변경처럼 이미 결과를 보고 있는 내부 재렌더에서는 포커스를
  훔치지 않는다.

## [1.8.5] — 2026-06-01

v1.8.4 이후 사용자에게 보이는 릴리즈 안내, 법적 고지, PWA 오프라인 접근,
검색 엔진 색인 표면을 정리한 패치 릴리즈. 기능 추가보다는 배포 후 신뢰와
운영/SEO 정확도를 맞추는 데 집중했다.

### Changed
- `/sitemap.xml` 의 `<loc>` 와 `/robots.txt` 의 `Sitemap:` 값을 요청 Host /
  신뢰 프록시의 `X-Forwarded-Proto`, `X-Forwarded-Host` 기준 절대 URL 로
  바꿨다. 배포 도메인에서 검색 봇이 그대로 읽을 수 있는 표준 sitemap 형태에
  맞췄다.
- PWA 서비스워커 shell 캐시에 `/privacy`, `/terms` 를 추가했다. 설치형 앱이나
  오프라인 재방문에서도 개인정보 처리방침 / 이용약관을 바로 열 수 있게 했다.
- 개인정보 처리방침의 localStorage / 클라이언트 오류 비콘 설명을 실제 기능과
  맞췄다. 즐겨찾기, 최근 검색/최근 본 곡, 결과 펼침 선호, 설치/새 기능 배너
  상태까지 브라우저 저장 범위를 명확히 적었다.
- 프리캐시되는 카탈로그 / 비교 / 개인정보 / 이용약관 페이지에서도
  `sw-register.js` 를 직접 로드하게 했다. 사용자가 서브페이지로 바로 들어와도
  오래된 서비스워커 shell 캐시를 더 빨리 새 버전으로 교체한다.

### Fixed
- "새 기능 보기" 배너가 `release_date` 만 기억하던 문제를 고쳤다. 같은 날
  패치 릴리즈가 여러 번 나와도 `version + release_date` 조합으로 판단해 새
  릴리즈 배너가 빠지지 않게 했다.

## [1.8.4] — 2026-06-01

v1.8.3 이후 배포 healthcheck 와 운영 smoke test 를 같은 readiness 기준으로
맞춘 패치 릴리즈. 컨테이너 이미지 의존성을 줄이고, Docker / compose / Render /
Fly 에서 실제 분석 가능 상태를 더 일찍 검출하도록 정리했다.

### Changed
- Docker 이미지 healthcheck 를 `curl` 대신 Python 표준 라이브러리로 실행하도록
  바꿨다. 런타임에 이미 있는 Python 만 사용해 불필요한 OS 패키지 설치를 줄였다.
- `/api/ready` path-only readiness 엔드포인트를 추가하고 Dockerfile /
  docker-compose / Render / Fly healthcheck 를 이 경로로 통일했다. 기존
  `/api/health?strict=true` 와 같은 검사를 수행하되, PaaS 설정에서 query string
  처리 차이를 신경 쓰지 않아도 된다.
- `python -m backend.cli status --ready` 옵션을 추가해 배포 healthcheck 와 같은
  `/api/ready` 경로를 CLI smoke test 에서도 바로 확인할 수 있게 했다.

## [1.8.3] — 2026-06-01

v1.8.2 이후 운영자가 배포 이미지를 식별하고, 프론트가 서버 설정과 같은 기준으로
동작하도록 맞춘 패치 릴리즈. 외부 도메인에서 붙는 클라이언트도 rate limit 상태를
브라우저에서 읽을 수 있게 CORS 노출 헤더까지 정리했다.

### Fixed
- CI Docker 이미지 빌드에 `GIT_COMMIT=${{ github.sha }}` build-arg 를 전달해,
  `.git` 이 제외된 이미지에서도 `/api/version.git_commit` 이 배포 커밋을
  가리키도록 했다.
- 업로드 카드의 파일 크기 안내와 브라우저 사전 검증이 `/api/version.max_upload_bytes`
  값을 따르도록 했다. 운영에서 `MUSIC_MAX_UPLOAD_BYTES` 를 바꿔도 화면은 25MB 로
  고정되어 보이던 불일치를 줄였다.
- CORS 응답의 `Access-Control-Expose-Headers` 에 rate limit 헤더와 `Retry-After`
  를 포함했다. 다른 도메인에서 붙는 SDK / 프론트도 브라우저에서 남은 요청 수와
  재시도 시점을 읽을 수 있게 했다.

## [1.8.2] — 2026-06-01

v1.8.1 이후 바로 확인된 사용성/운영 기본값 보정 패치. 비교 페이지 첫 방문
흐름이 막히지 않도록 다음 행동을 제공하고, Docker 기본 worker 설정을 실제
운영 모델과 맞췄다.

### Fixed
- `/compare` 에 히스토리가 없는 첫 방문자를 위한 CTA 를 추가했다. 기존에는
  안내 문장만 보여서 다음 행동이 막혔는데, 이제 메인 분석 시작과 카탈로그
  둘러보기로 바로 이동할 수 있다.
- Dockerfile / docker-compose 의 기본 `WEB_CONCURRENCY` 를 1로 맞췄다.
  rate limit, 결과 캐시, metrics 가 in-memory 라 다중 worker 기본값은 실제
  운영 한도와 카운터를 왜곡할 수 있었다.

## [1.8.1] — 2026-06-01

v1.8.0 이후 남아 있던 출시 품질 이슈를 정리한 패치 릴리즈. 정적 서브페이지의
CSP 런타임 문제, 릴리즈 자동화 가드, Dependabot 의존성 제안을 한 번에 반영해
운영 배포 전에 프론트엔드 동작과 빌드/릴리즈 경로를 더 단단하게 맞췄다.

### Changed
- 계산 스택을 `numpy 2.4.6`, `pandas 3.0.3`, `scikit-learn 1.8.0` 으로
  업데이트하고 Docker 런타임을 `python:3.14-slim` 으로 올렸다. Python 3.14
  런타임도 실제 테스트 매트릭스에 포함해, 이미지 빌드만 통과하는 상태가 아니라
  서버/분석 테스트까지 같이 확인하도록 했다.
- 오디오 분석 스택을 `librosa 0.11.0`, `soundfile 0.13.1`,
  `audioread 3.1.0` 으로 업데이트하고, `setuptools` 핀을 `>=82.0.1,<83`
  범위로 올렸다. 기존 `librosa 0.10.1` 은 `pkg_resources` 에 의존해서
  최신 setuptools 에서 테스트가 깨졌고, 이 때문에 setuptools 를 80.x 이하로
  묶어두고 있었다.
- FastAPI 를 `0.110.0` 에서 `0.136.3` 로 업데이트했다. 현재 테스트 스위트와
  분석 API 동작을 기준으로 호환성을 다시 확인해 오래된 웹 프레임워크 의존성을
  줄였다.
- CI / Release workflow 의 GitHub Actions 의존성을 현재 Dependabot 제안 버전으로
  정리했다. `actions/checkout` v6, `actions/setup-python` v6,
  `docker/setup-buildx-action` v4, `docker/build-push-action` v7 로 올려 오래된
  Actions 런타임을 줄이고, 같은 파일을 건드리던 Dependabot PR 들을 한 번에
  정리할 수 있게 했다.

### Fixed
- Release workflow 가 태그 버전, `backend.__version__`, `CHANGELOG.md` 릴리즈
  섹션이 서로 맞는지 먼저 확인하도록 보강. 예전엔 잘못된 태그를 밀어도
  `[Unreleased]` 를 폴백 릴리즈 노트로 삼아 GitHub Release 가 만들어질 수
  있었는데, 이제 셋 중 하나라도 어긋나면 릴리즈 생성을 중단한다. README 에도
  실제 릴리즈 순서를 추가했다.
- `/catalog` / `/compare` 의 페이지 스크립트를 인라인에서 `catalog.js` /
  `compare.js` 로 분리. CSP 가 `script-src 'self'` 로 인라인 스크립트를 막고
  있었는데 두 서브페이지는 아직 인라인 스크립트에 의존해서, 실제 브라우저에서
  카탈로그 카드와 비교 로직이 실행되지 않았다. 루트 JS 라우트와 SW 셸 캐시도
  같이 추가하고, 인라인 스크립트 회귀 테스트 정규식을 `<` 포함 코드까지 잡도록
  고쳤다.
- CSS 전역에서 `[hidden]` 을 `display: none !important` 로 보존. 컴포넌트별
  `display: flex/block` 규칙이 HTML `hidden` 속성을 덮어 빈 social proof 점과
  카탈로그 검색창 X 버튼이 초기 화면에 보이던 문제를 막았다.
- 히어로 제목의 핵심 문구를 한 덩어리로 묶어 모바일/데스크톱에서 `곡` 한 글자만
  따로 떨어지지 않게 정리. 영어 문구도 같은 줄바꿈 구조로 맞췄다.
- PWA 설치 지원 메타에 표준 `mobile-web-app-capable` 을 추가해 Chromium 계열
  브라우저의 deprecated 경고를 없앴다.
- `sw-register.js` 가 등록 직후 `registration.update()` 를 호출하고, 새
  서비스워커가 활성화되면 기존 사용자에게 한 번만 새로고침을 걸도록 보강.
  셸 자산 구조가 바뀐 배포에서 오래된 캐시 HTML 이 잠깐 남아 서브페이지가
  깨지는 시간을 줄이기 위한 처리다.
- README 의 `python -m backend.cli version` 출력 예시와 OpenAPI 스키마 예시
  버전을 패키지 릴리즈 버전 기준으로 맞췄다.
- 업로드 음원 파형을 키보드 / 스크린리더로도 시킹할 수 있게 보조 슬라이더 추가.
  파형 캔버스는 마우스 클릭 전용(`aria-hidden`)이라 키보드 사용자는 재생 위치를
  옮길 방법이 없었다(WCAG 2.1.1 키보드). 시각적으로 숨긴(`sr-only`)
  `input[type=range]` 를 두어 화살표 키 / 스크린리더로 시킹할 수 있게 하고,
  재생 중에는 `aria-valuetext` 로 현재 시각을 함께 안내한다. 화면 디자인 변화는
  없다. 신규 i18n `results.seekLabel` (ko/en parity).

## [1.8.0] — 2026-05-29

v1.7.x 마감 이후 누적된 기능 + 폴리시를 한 번에 묶은 릴리즈. 카탈로그 모달과
비교 페이지에 새 기능을 더하고, 그동안 메인에만 있던 공용 헤더/푸터와 테마/언어
토글을 서브페이지(카탈로그 / 비교 / 약관 / 개인정보) 전반으로 넓혀 페이지 간
일관성을 맞췄다. 정적 페이지 마감(오프라인 양방향 + CSP 버그 수정), 배포·문서
정합성, i18n/카피 정리까지 출시 직전 다듬기를 함께 담았다.

### Added
- 카탈로그 모달 헤더에 시드 곡의 BPM / E / Hz mini-row + ★ 즐겨찾기 토글
  추가. 기존엔 모달이 시드의 매칭 곡 5건만 보여주고 정작 시드 곡 자체의
  메트릭/즐겨찾기는 모달 안에서 볼/조작할 방법이 없었다. 카드의 메트릭
  표시(`cat-metrics`) 와 ★ 버튼 패턴을 그대로 가져와 모달 안에서도
  같은 동작을 제공. 즐겨찾기 전용 모드에서 시드 ★ 를 풀면 카드 그리드가
  자동 갱신되도록 `load()` 트리거. 신규 i18n `catalog.modalFavSeed`
  (ko/en parity).
- 카탈로그 페이지에 "최근 본 곡" 섹션 추가. 모달을 열어본 곡을
  `localStorage` (`soundmatch.catalog.recently-viewed`, 최대 8건, 최신순)
  에 기록해 필터 행 아래 칩 행으로 노출한다. 칩을 누르면 그 곡의 유사
  곡 모달이 바로 열려, 여러 곡을 오가며 탐색할 때 카드 그리드를 다시
  스크롤할 필요가 없다. "지우기" 버튼으로 기록 초기화 가능, 비어 있으면
  섹션 통째로 숨김. 즐겨찾기 / 최근 검색어와 동일한 localStorage 패턴.
  신규 i18n `catalog.recentViewed` / `catalog.recentClear` (ko/en parity).
- 비교 페이지(`/compare`)에 A ↔ B 스왑 버튼 추가. 두 픽커 사이의 원형
  버튼을 누르면 왼쪽 / 오른쪽 선택이 통째로 맞바뀌고 카드도 좌우로
  재배치된다. 클릭할 때마다 아이콘이 180° 누적 회전해 "맞바꿨다"는
  시각 피드백을 주고, 모바일에서 픽커가 세로로 쌓이면 버튼도 90° 돌아
  위 / 아래 스왑 의미로 보인다 (`prefers-reduced-motion` 환경에선 회전
  애니메이션 생략). 버튼 톤은 네비의 `.icon-btn` 을 그대로 따랐다.
  신규 i18n `compare.swapAria` (ko/en parity).
- 비교 페이지에서 왼쪽 / 오른쪽에 같은 곡을 고르면 "같은 곡입니다"
  안내 배너를 노출. 렌더 자체는 막지 않는다 — 같은 곡끼리도 메트릭이
  동일함을 확인하는 용도가 될 수 있어 차단 대신 경고색 안내로만 알린다.
  라이트 테마에선 amber(`--accent-warn`) 가 흰 배경 대비 부족해 더 진한
  톤(#b45309)으로 보정. 신규 i18n `compare.sameSongWarn` (ko/en parity).
- 카탈로그 / 비교 페이지에 메인과 동일한 공용 헤더(브랜드 + 네비 + 테마/언어
  토글)와 푸터를 이식. 그동안 두 페이지는 "← 메인으로" 링크 하나뿐이라 그
  안에서는 테마/언어를 바꿀 수도, 브랜드 네비로 이동할 수도 없어 다른
  사이트처럼 보였다. 서브페이지용 경량 `site-nav.js`(테마/언어 토글 + 모바일
  햄버거 + 푸터 연도)를 새로 두고(app.js 의 같은 로직에서 분석 페이지 전용
  부수효과만 뺀 것), 마크업은 첫 페인트 깜빡임을 막으려 인라인으로 넣었다.
  중복 백링크는 제거하고 현재 페이지 링크에 `aria-current` 강조.
  `/site-nav.js` 라우트(main.py)와 SW 셸 등록도 함께 추가.

### Changed
- 메인 업로드 카드의 "또는" 구분선과 개인정보 안내 문구를 i18n / 정본과
  맞췄다. "또는" 이 하드코딩이라 영어에서도 한국어로 보였는데 신규
  `upload.or` 키(ko/en parity)로 번역되게 했고, 업로드 카드 하단 개인정보
  문구의 HTML 기본값을 i18n ko 정본(전체 문장)과 일치시켜 첫 페인트 / JS
  비활성에서 짧은 버전이 잠깐 보이던 흔들림을 없앴다. 셸 자산(app.js /
  i18n.js)이 바뀌었으므로 SW 캐시 버전을 `v4` → `v5` 로 올려 재방문자에게도
  반영되게 했다(직전 정적 페이지 변경분도 함께 무효화).
- `.dockerignore` 추가. 그동안 빌드 컨텍스트에 `.venv`(수백 MB) / `.git` /
  `tests` 같은 게 통째로 데몬에 전송돼 `docker build` 가 느렸고, 의도치
  않은 파일이 컨텍스트에 섞일 위험도 있었다. 이미지에 실제로 필요한
  `backend/` `frontend/` `data/` `requirements.txt` `CHANGELOG.md` 외에는
  모두 제외하도록 정리.
- 문서·예시 수치 정합성 정리. README 의 테스트 수(고정 "252 케이스" → "CI
  매트릭스에서 매 PR 실행"), 카탈로그 규모(약 1000곡 → 실제 781곡), CLI
  `version` 예시 출력(v1.6.0 → v1.7.1)을 현행화하고, OpenAPI 스키마 예시
  (`HealthResponse.catalog_size` 1006→781, `version` / `engine_version`
  1.5.0·1.2.0 → 1.7.1)와 디자인 프리뷰 서버의 더미 카탈로그 수(1006→781)도
  실제 값에 맞췄다.
- 디자인 프리뷰 서버(`preview_server.py`)를 `ThreadingHTTPServer` 로 전환.
  단일 스레드라 서비스워커가 셸 자산을 `cache.addAll` 로 한꺼번에 받을 때
  페이지 요청과 경합해 렌더가 멈추는 일이 있었다. SW 오프라인 셸 캐시
  버전도 `v3` → `v4` 로 올려 새 자산(`/site-nav.js`)을 반영.
- 정적 페이지 마감 — 오프라인 / 개인정보 / 약관. 오프라인 페이지를 ko/en
  i18n 으로 전환(신규 `offline.*` 키, ko/en parity)하고, 개인정보·약관에
  메인과 동일한 공용 헤더/푸터를 이식해 그 안에서도 테마/언어 토글과 네비를
  쓸 수 있게 했다(중복 백링크 제거). 약관/개인정보 본문은 한국어 정본을
  유지하되, 상단에 "본 문서는 한국어로 제공됩니다 · provided in Korean" 안내를
  ko/en 병기로 두어 영어 사용자도 의도를 알 수 있게 했다.

### Fixed
- 영어 화면에서 결과 카드의 순위 라벨 자리가 빈 칸으로 남던 문제 수정.
  순위 단위(`results.hitRankUnit`)가 ko 는 "위", en 은 빈 문자열이라 숫자
  밑에 빈 라벨 노드가 공간만 차지했다. 단위가 비면 라벨 노드를 `hidden` 처리해
  영어에선 순위 숫자만 깔끔히 보이도록.
- 오프라인 폴백 페이지의 "다시 시도" 버튼이 동작하지 않던 문제 수정. 인라인
  `onclick="location.reload()"` 을 쓰고 있었는데 CSP(`script-src 'self'`,
  unsafe-inline 제거)에서 인라인 이벤트 핸들러가 차단돼 클릭이 먹지 않았다
  (서비스워커가 캐시한 응답에도 CSP 헤더가 함께 있어 오프라인에서도 동일).
  CSP 안전한 `<a href="/">` 앵커로 교체.
- 정의되지 않은 `var(--accent)` 토큰을 참조하던 hover 스타일 4곳을 실제
  토큰으로 교정. `:root` 에는 `--accent-1` / `--accent-2` 만 있고 바닥
  `--accent` 는 정의된 적이 없어, 메인의 "샘플로 분석해보기" 버튼과
  카탈로그의 "최근 본 곡 지우기" / 모달 "링크 복사" / "CSV 내보내기"
  버튼의 hover 색이 조용히 죽어 있었다(상속색으로 튀거나 무반응).
  배경 틴트가 cyan 인 샘플 버튼·링크 복사는 `--accent-2`, 보라 계열
  카탈로그 버튼은 `--accent-1` 로 원래 의도에 맞춰 연결.
- `/api/health` 의 'Duplicate Operation ID health' 경고 제거. GET·HEAD 를
  `api_route(methods=[...])` 로 한 핸들러에 묶어 두 operation 이 같은
  `operationId` 를 갖던 것을, GET 만 스키마에 노출(`operation_id="health"`)하고
  HEAD 는 `include_in_schema=False` 로 분리했다. `/docs` · `/openapi.json`
  접근 때마다 뜨던 경고와 일부 SDK 생성기 충돌이 사라진다.
- Docker 프로덕션 이미지에 `CHANGELOG.md` 가 빠져 있던 문제 수정.
  `/api/version` · `/api/health` 의 `release_date` 와 "새 기능 보기" 모달이
  런타임에 CHANGELOG 를 파싱하는데, Dockerfile 이 이를 COPY 하지 않아
  이미지 안에선 이 값들이 전부 비어 있었다. `COPY CHANGELOG.md` 추가로 해결.
- CLI `ENGINE_VERSION` 하드코딩(`1.3.0`) 제거. 앱 버전이 1.7.x 로 올라가는
  동안 CLI 의 `engine_version` 출력과 `User-Agent` 만 네 개 마이너 버전이나
  뒤처져 있었다. 버전을 `backend/__init__.py` 의 `__version__` 단일 소스로
  옮기고 서버(`app.version`)·CLI 가 함께 참조하도록 정리.

## [1.7.1] — 2026-05-22

v1.7.0 직후의 마감 패치. 실제 브라우저 렌더 검증에서 잡은 디자인
프리뷰 서버 버그를 고치고, 카탈로그 로딩 상태 / 마이크로 인터랙션 /
포커스 글리치 같은 자잘한 완성도 디테일을 한 묶음으로 정리했다.
기능 동작 변화는 없고 전부 폴리시 + 개발 도구 수정.

### Changed
- 마이크로 인터랙션 마감 2건:
  - 업로드 드롭존의 드래그 중(`.is-drag`) 시각 신호를 단순 hover 와
    뚜렷이 구분. 점선 → 실선 테두리, 더 진한 배경, 살짝 scale-up +
    그림자, 업로드 아이콘 bounce 애니메이션으로 "여기 놓으세요" 를
    확실히 전달.
  - 분석 결과 hit 카드에 staggered 등장 애니메이션 추가. 1위부터
    차례로 (90ms 간격) 살짝 fade-up 하며 나타난다. 앞 5장만 지연을
    주고 그 뒤는 즉시 — 카드가 많아도 마지막까지 안 기다리게.
  - 둘 다 `prefers-reduced-motion` 환경에서는 애니메이션을 끈다.

### Fixed
- 디자인 프리뷰 서버의 정적 자산 / 페이지 라우트 누락 수정 (실제 브라우저
  렌더 검증 중 발견). HTML 이 `<script src="/app.js">` 처럼 루트 경로로
  부르는 JS 중 `theme-init.js` / `favorites.js` / `error-boundary.js` /
  `sw-register.js` 가 alias 목록에서 빠져 있어 콘솔에 404 가 떴고,
  확장자 없는 페이지 라우트(`/catalog` `/compare` `/privacy` `/terms`)
  와 `/api/catalog/sample` 도 처리되지 않았다. 이제 `.js` / `.css` 는
  하위 디렉토리(`js/` `css/`) 를 자동 탐색하고, pretty 페이지 라우트는
  `PAGE_ALIASES` 로 매핑한다. 회귀 테스트도 루트 JS 7종 / pretty
  route 4종 / catalog sample 까지 커버하도록 보강.
- 디자인 프리뷰 서버(`preview_server.py`) 현행화. 그동안 백엔드에 새
  엔드포인트가 여러 개 추가됐는데 프리뷰 서버는 `/api/catalog` /
  `/api/health` / `/api/analyze` 만 더미로 처리해서, librosa 없이
  디자인만 보려고 띄우면 카탈로그 페이지 / 샘플 버튼 / 새 기능 배너 /
  footer 빌드 정보가 전부 깨졌다. 이제 `/api/version`,
  `/api/version/changelog`, `/api/catalog/search` (q 필터 + 페이지네이션),
  `/api/catalog/random`, `/api/catalog/stats`, `/api/catalog/export.csv`,
  `/api/analyze/by-catalog` 까지 모두 더미 응답으로 처리한다. 합성 카탈로그
  30곡을 들고 있어 검색·필터·정렬 UI 가 실제처럼 동작. 백엔드와의 drift
  를 잡는 회귀 테스트(`tests/test_preview_server.py`, 6건) 도 추가 —
  서버를 백그라운드 스레드로 띄워 각 엔드포인트 응답을 검증.

### Changed
- 카탈로그 카드를 클릭하면 모달 데이터 fetch 동안 그 카드에 로딩 상태를
  표시한다. 기존에는 카드를 눌러도 카드 자체엔 아무 변화가 없어 클릭이
  먹혔는지 잠깐 알 수 없었다. 이제 accent 테두리 + 은은한 펄스로 "처리
  중" 을 시각화하고 `aria-busy="true"` 로 보조기기에도 알린다. 성공/
  실패 무관하게 `finally` 에서 상태를 해제하고, `prefers-reduced-motion`
  환경은 펄스 애니메이션을 끈다.

### Fixed
- 전역 `:focus-visible` 규칙이 `border-radius: 6px` 를 강제하던 것을 제거.
  pill 버튼(`.ghost-pill`, `border-radius: 999px`) 처럼 자체 radius 를
  가진 요소가 포커스 순간 모서리가 6px 로 튀는 시각 글리치가 있었다.
  모던 브라우저는 outline 을 요소의 실제 `border-radius` 에 맞춰 자동으로
  둥글게 그려주므로 이 줄은 불필요했다.

### Changed
- 카탈로그 페이지가 검색 / 필터 / 페이지 이동 중에 로딩 스켈레톤 카드를
  그리도록 개선. 기존에는 fetch 동안 직전 결과 카드가 그대로 남아 있어
  "새 결과인지 옛 결과인지" 헷갈리고, 빈 그리드면 레이아웃이 출렁였다
  (CLS). 이제 직전 페이지 카드 수만큼 (6~12개) shimmer 스켈레톤을 깔아
  자리를 유지한다. 공용 `skel-shimmer` 애니메이션 / `--panel-skel`
  토큰을 재사용.

## [1.7.0] — 2026-05-22

전문 디자인 감사를 한 차례 돌리고 그 지적 사항을 모두 반영한 릴리즈.
모바일 네비게이션 출시 블로커를 잡았고, 펼침 애니메이션 / 내보내기
메뉴 / 접근성 / 대비 등 "상품 완성도" 디테일을 한 묶음으로 끌어올렸다.
사용자에게 결과 신뢰도를 솔직하게 알려주는 안내 배너도 추가됐다.

### Fixed
- 접근성 / 대비 마감 (디자인 감사 후속):
  - 비교 페이지의 delta 색상(`.delta-up` / `.delta-down`) 이 다크 배경
    기준 밝은 톤이라 라이트 테마 흰 배경에서 대비가 부족했다. 라이트
    테마용 진한 변형(`#c0392b` / `#0f8a5f`) 으로 보정.
  - 결과 hit 카드의 유사도 막대(`role="progressbar"`) 에 `aria-label`
    부재 → 스크린리더가 값(%)만 읽고 무슨 값인지 알 수 없었다.
    "곡명 유사도 NN%" 형태 라벨을 JS 에서 부착.
  - 분석 로딩 중 경과 시간(`#loading-elapsed`) 이 700ms 마다 갱신되는데
    부모가 `aria-live` 라 스크린리더가 매번 읽어 소음이 됐다.
    `aria-hidden="true"` 로 시각 표시만 유지.

### Changed
- 결과 액션 행의 내보내기 버튼 4종(JSON / CSV / SVG / PNG) 을 native
  `<details>` 드롭다운 "내보내기" 메뉴로 묶었다. 액션 행에 버튼이 10개나
  깔려 모바일에서 3~4줄까지 쌓이고 핵심 액션("새 음악 분석") 이 묻히던
  문제를 완화. 항목 클릭 / 바깥 클릭 / Esc 시 메뉴가 닫히고 (Esc 는
  포커스를 summary 로 복귀), 캐럿 아이콘이 열림 상태에 따라 회전.
  버튼 id 는 그대로라 기존 핸들러는 변경 없음. 신규 i18n
  `results.exportMenu` (ko/en parity).
- 결과 hit 카드의 펼침/접힘이 `display:none` 토글이라 순간이동처럼 툭
  끊기던 것을 `grid-template-rows` `0fr↔1fr` 트랜지션으로 부드럽게 개선.
  내부 콘텐츠를 `.hit-details-inner` 로 한 겹 감싸 (`overflow:hidden`)
  높이가 자연스럽게 늘었다 줄었다 한다. `prefers-reduced-motion` 환경은
  기존 전역 규칙이 트랜지션을 0.001s 로 죽여 즉시 토글되고, 인쇄 시에는
  `grid-template-rows:1fr` 강제로 항상 펼친 상태 유지.

### Fixed
- 모바일(<600px) 에서 상단 네비게이션의 텍스트 링크(카탈로그 / 사용법 /
  비교 / GitHub) 가 통째로 숨겨져 메인 외 페이지로 이동할 방법이 아예
  없던 문제 수정. 햄버거 토글 버튼 + 드롭다운 메뉴를 추가해 모든 링크에
  다시 접근 가능. 토글은 `aria-expanded` / `aria-controls` 로 접근성
  보장, 바깥 클릭 / Esc / 링크 클릭 시 자동으로 닫히고 Esc 는 포커스를
  토글 버튼으로 되돌린다. 신규 i18n `nav.menuToggle` / `nav.menuClose`
  (ko/en parity).

### Added
- 분석 결과에 신뢰도 안내 배너 추가. 1위 매칭 유사도가 낮으면 사용자에게
  솔직하게 "카탈로그에 잘 맞는 곡이 없었다" 는 점을 알려준다. 50% 미만은
  warn 톤 (⚠) 으로 "참고용으로만 봐주세요", 50~65% 는 차분한 info 톤 (ℹ)
  으로 "느슨하게 닮은 정도" 안내. 65% 이상이면 배너 없음. 카탈로그가
  ~1000곡 규모라 새로운 장르를 올리면 1위도 50%대로 떨어지는 일이 흔한데,
  순위만 보고 사용자가 결과를 과신하지 않도록 하는 장치. 인쇄 시에도
  흑백 톤으로 유지 (결과 해석에 중요한 맥락이라). 신규 i18n
  `results.confidenceLow` / `confidenceMid` (ko/en parity).
- index / catalog / compare 페이지에 `<noscript>` 폴백 추가. JavaScript 가
  꺼져 있는 환경 (corporate proxy / 일부 a11y 도구 / strict Tor / 사용자
  설정) 에서 SPA 가 빈 페이지로 깨지지 않고, 명확한 한글/영문 안내 +
  GitHub 저장소 링크가 노출된다. CSP `style-src 'unsafe-inline'` 가
  허용되어 있어 인라인 스타일로 작성 — 운영 디버깅 시 외부 CSS 의존성
  없이 noscript 만 보면 즉시 진단 가능. 회귀 테스트 1건 추가.

### Changed
- README 갱신 — v1.5 / v1.6 에서 추가된 기능 / 엔드포인트 / 환경변수 /
  CLI 서브커먼드를 본문에 반영. 테스트 케이스 수도 211 → 252 로 갱신.
  새로 추가된 항목: `python -m backend.cli version`, `/api/version/changelog`,
  `/api/catalog/export.csv`, `MUSIC_GIT_COMMIT` 환경변수, 샘플 분석 버튼 /
  새 기능 알림 배너 / 카탈로그 모달 공유 링크 / 화살표 키 nav 기능 설명.
  Rate limit 응답이 body 에도 머신-친화 필드를 노출한다는 문구도 추가.

## [1.6.0] — 2026-05-21

운영 가시성 (build SHA / 의존 버전 / health 통합 / rate-limit body) 과
사용자 첫 인상 (샘플 분석 버튼 · OS 테마 실시간 동기) 을 한 번에 묶은
릴리즈. 같은 날 cut 된 1.5.0 직후의 누적 변경 7건을 정리한다.

### Added
- `/api/version` 응답에 `dependencies` 딕셔너리 추가. 운영자가 떠 있는
  서버의 numpy / pandas / scikit-learn / librosa / fastapi / pydantic /
  python 버전을 한 번의 호출로 확인 가능. CVE 점검 · 호환성 디버깅 ·
  클라이언트 SDK 가 server feature 추측하는 시나리오에 유용.
  `importlib.metadata` 로 installed 패키지 메타데이터 읽고, 패키지가
  없으면 graceful 하게 null. 모듈 로드 시 한 번만 수집 (캐시).

### Changed
- 테마 시스템이 사용자가 명시적으로 토글한 적 없으면 OS `prefers-color-scheme`
  변경을 실시간으로 따라간다. 초기 페인트는 기존처럼 theme-init.js 가 처리하고,
  추가로 `matchMedia(...).addEventListener("change")` 로 라이브 listener 를 부착.
  사용자가 한 번이라도 토글하면 `localStorage` 값이 우선되어 listener 효과
  없음 (명시 선택을 OS 가 덮어쓰지 않음). 테마 변경 시 `theme:change`
  CustomEvent 를 dispatch 해서 파형 canvas 처럼 CSS 변수에 묶인 요소가
  다시 그려지도록 app.js 에서 후처리.
- Rate limit 429 응답이 헤더뿐 아니라 JSON body 에도 `retry_after_seconds`
  / `limit` / `reset_at` 를 함께 내려준다. 기존에도 `Retry-After` +
  `X-RateLimit-*` 헤더는 있었지만 body 에는 한글 detail 문자열만 있어
  SDK / 모니터링 도구가 retry backoff 로직을 짤 때 헤더만 파싱해야 했다.
  body 에도 같은 머신-친화 필드를 두어 클라이언트 구현이 단순해진다.
  전용 `RateLimitExceeded` 예외 + 전역 핸들러로 헤더/바디 single source.

### Added
- 메인 페이지 업로드 카드 하단에 "🎧 샘플로 분석해보기" 버튼 추가. 클릭
  하면 `/api/catalog/random?n=1` 으로 카탈로그에서 무작위 한 곡을 뽑아
  `/api/analyze/by-catalog` 로 즉시 분석 결과를 보여준다. 첫 방문자가
  음원 준비 단계 없이 결과 페이지 / 차트 / 매칭 설명을 바로 체험할 수
  있어 conversion 개선. 누를 때마다 다른 곡이 뽑혀 discovery 성도 동반.
  기존 `seedFromHit()` 헬퍼를 재사용해 결과 렌더 코드는 한 군데로 유지.
  로딩 중에는 버튼 disabled + "샘플 준비 중…" 라벨로 상태 시각화. 신규
  i18n `upload.sampleButton` / `sampleHint` / `sampleLoading` (ko/en
  parity). 모바일에서는 divider 텍스트가 자기 줄로 떨어지도록 반응형 처리.
- `/api/health` 응답에도 `release_date` / `git_commit` 필드 추가. 운영자가
  `/api/version` 까지 추가 호출하지 않고도 health 한 번 만에 "어떤 빌드가
  떠 있는지" 확인 가능. alert 룰 (`status=degraded AND git_commit=X`)
  작성이 단일 응답으로 가능해진다. `HealthResponse` Pydantic 모델에도
  옵션 필드로 반영 → OpenAPI / Swagger UI 자동 갱신. `python -m backend.cli
  status` 출력 표에도 두 라인이 추가되어 cron / monitoring 용 한 화면이
  더 풍부해진다.
- `python -m backend.cli version` 서브커먼드 신설. `/api/version` 과 동일한
  정보 (version / release_date / git_commit) 를 서버 없이 즉시 출력. CI 가
  배포 후 "deploy 된 빌드가 기대한 SHA 와 일치하는지" 검증하는 용도에 적합.
  기본은 한 줄 사람-가독 (`v1.5.0 · 2026-05-21 · 7cf785a`), `--json` 으로 jq
  파이프 친화 형태도 지원. backend.main 의 `_GIT_COMMIT` / `_RELEASE_DATE`
  / `app.version` 을 single source of truth 로 끌어다 쓴다.
- `/api/version` 응답에 `git_commit` 필드 추가 (짧은 7자 SHA). 같은
  version 으로 여러 빌드가 떠 있을 때 운영자가 정확히 어느 빌드인지
  식별 가능. 우선순위는 환경변수 `MUSIC_GIT_COMMIT` → `.git/HEAD`
  파일 fallback → 둘 다 실패하면 null. Dockerfile 에 `ARG GIT_COMMIT`
  를 추가해 `docker build --build-arg GIT_COMMIT=$(git rev-parse --short HEAD)`
  로 빌드 시 주입 가능하고, 빌드 시스템 (Render / fly.io / Actions)
  이 자동으로 채울 수도 있다. 프론트엔드 footer 빌드 정보 라인이
  `v1.5.0 · 2026-05-21 · abc1234` 형태로 git_commit 까지 노출하도록
  업데이트.
- 카탈로그 카드에 화살표 키 네비게이션 추가. 카드에 포커스가 있는
  상태에서 ←/→ (또는 ↑/↓) 로 이전/다음 카드로 이동, Home/End 로
  첫/마지막 카드로 점프, Enter 로 상세 모달 오픈. 페이저 next/prev/
  first/last 버튼을 누르면 새 페이지의 첫 카드에 자동으로 포커스가
  이동 — 키보드만 써서 1000곡 카탈로그를 빠르게 훑을 수 있다. 그리드
  컨테이너에 `aria-keyshortcuts` + `aria-description` 부착해 스크린리더
  사용자에게도 단축키가 안내된다. 신규 i18n `catalog.gridShortcuts`
  (ko/en parity).

## [1.5.0] — 2026-05-21

이번 릴리즈는 사용자에게 보이는 polish (새 기능 알림 배너 · 카탈로그 공유 링크) 와
운영자가 자주 쓰는 도구 (CSV 내보내기 · CLI export-catalog · health degraded 이유)
를 한꺼번에 묶었다. 백엔드/CLI/UI 가 같은 catalog 필터 코드 경로를 공유하도록
정리해서 "검색 화면에서 보던 곡 = CSV 행 = CLI 결과" 가 항상 일치한다.

### Added
- 카탈로그 모달 헤더에 "🔗 링크" 공유 버튼 추가. 사용자가 모달을 연 곡의
  deep link URL (`/catalog?song=<encoded>`) 을 클립보드로 복사. 토스트
  배너로 "링크가 복사되었습니다" 피드백 + 버튼 자체에 1.5초간 accent
  하이라이트로 시각 확인. `navigator.clipboard` 가 안 되는 환경(구형
  Safari · file:// · 권한 거부) 은 `document.execCommand("copy")` legacy
  경로로 fallback. 신규 i18n 4 키 (`catalog.copyLink` / `copyLinkAria` /
  `linkCopied` / `linkCopyFail`, ko/en parity). 토스트 컨테이너는 page-wide
  `aria-live="polite"` 로 스크린리더 친화.
- `python -m backend.cli export-catalog` 서브커먼드 신설. 백엔드의 `/api/catalog/export.csv`
  와 같은 필터/정렬/컬럼/CSV injection 방어를 CLI 로도 노출. CI · cron ·
  Makefile 단계에서 서버 띄우지 않고도 동일한 결과물을 생성할 수 있다.
  옵션은 API 와 정확히 매핑: `-q` (검색), `--min-bpm` / `--max-bpm`,
  `--min-energy` / `--max-energy`, `--sort` (default/title/artist/bpm/energy).
  `-o` 로 파일 출력 (기본 `./catalog-export.csv`), `--stdout` 로 파이프
  친화 (BOM 없이 표준 CSV). 파일 출력은 Excel 한글 호환 BOM 선두. exit
  code: 정상 0 / 파일 없음 2 / CSV 로딩 실패 3 / 필수 컬럼 누락 4. README
  "실행" 섹션에 사용 예시 2개 추가.
- "새 기능" 알림 배너 + 모달 추가. 사이트 진입 시 `/api/version.release_date`
  가 사용자의 마지막 확인 값 (localStorage `soundmatch.lastSeenRelease`)
  과 다르면 상단에 작은 배너가 뜨고, 클릭하면 최근 3개 릴리즈의 노트를
  모달로 표시. 처음 방문자에게는 띄우지 않고 silent 하게 현재 릴리즈만
  기록 (onboarding 시점의 다른 시그널과 겹치지 않도록). 배포된 새 빌드를
  사용자가 자연스럽게 인지하게 만들어 retention 에 기여하는 패턴.
  - 신규 백엔드 엔드포인트 `GET /api/version/changelog?limit=N` —
    CHANGELOG.md 의 published 릴리즈 (Unreleased 제외) 를 구조화해 응답.
    각 항목: `version`, `date`, `sections: {Added/Changed/Fixed: [...]}`.
    모듈 로드 시 한 번 파싱 + 600초 public 캐시.
  - 신규 i18n 섹션 `whatsNew.*` (ko/en parity, 8 키).
  - 배경 색을 PWA install 배너 (보라) 와 다른 청록 계열로 차별화 →
    두 배너가 동시에 떠도 시각 구분 가능. 라이트 모드 보정 포함.
- 카탈로그 페이지 필터 행에 **CSV 내보내기** 버튼 추가 + 백엔드
  `/api/catalog/export.csv` 엔드포인트 신설. 현재 적용된 q / BPM / 에너지 /
  정렬 조건을 그대로 받아 페이지네이션 없이 전체 결과를 CSV 한 장으로
  다운로드. 컬럼: `title, artist, bpm, energy_rms, brightness, full_name`.
  Music supervisor / 큐레이터가 외부 도구 (Excel · Numbers · pandas) 로
  가져가 분석하는 시나리오용. UTF-8 BOM 을 선두에 두어 한글 환경 Excel
  깨짐을 방지하고, CSV injection 방어 (`= + - @` 로 시작하는 셀에 `'`
  prefix) 도 함께. 즐겨찾기 전용 모드에서는 클라이언트가 localStorage
  로 직접 Blob 다운로드 (서버는 즐겨찾기 모르므로). 신규 i18n 키
  `catalog.exportCsv` / `catalog.exportCsvHint` (ko/en parity).

### Changed
- `catalog_search` 의 필터/정렬 로직을 `_filter_and_sort_catalog` 헬퍼로
  추출. `/api/catalog/search` 와 `/api/catalog/export.csv` 가 동일한 함수를
  공유 → "검색 결과 화면 = 내보낸 CSV" 가 항상 일치하도록 단일 진입점화.

### Changed
- `/api/health` 의 degraded 응답에 `reason` / `reason_detail` 필드 추가. 503
  이 떨어졌을 때 운영자가 "왜 떨어졌는지" 응답 본문만 보고도 분류 가능.
  reason enum: `engine_load_failed` (카탈로그 CSV 로드 실패) /
  `ml_imports_unavailable` (strict 모드에서 librosa·sklearn import 실패) /
  `upload_dir_not_writable` (strict 모드에서 업로드 디렉토리 쓰기 실패).
  `reason_detail` 은 exception 클래스명만 노출 — 내부 traceback / 경로는
  운영 로그 쪽에서만 확인 가능하게 의도적으로 축약. 정상(ok) 응답에서는
  두 필드 모두 null 이라 알람 룰 작성이 단순.

### Added
- 카탈로그 모달의 매칭 곡 5건에도 BPM/에너지/밝기 mini-row 표시. 카탈로그
  카드와 같은 `buildMetricsLine` 헬퍼를 재사용 — `match_summary` 응답 필드
  (`tempo_bpm` / `energy_rms` / `brightness`) 를 변환해 그대로 넘김. 모달 안
  에서는 줄바꿈을 위해 `.modal-hits .cat-metrics { display: flex; ... }`
  CSS 추가.
- 카탈로그 카드 아래에 BPM / 에너지 / 밝기 mini-row 표시. 사용자가 카드를
  클릭하지 않고도 한눈에 곡의 핵심 메트릭을 확인 가능. `/api/catalog/search`
  응답의 각 item 에 `metrics: {bpm, energy_rms, brightness}` 필드 추가
  (24~96곡 × 3 float, 페이로드 부담 없음). 0 값은 None 으로 내려와 frontend
  가 안전하게 skip — line 자체 안 그리거나 일부 항목만 표시.
- 카탈로그 검색 input 에 최근 검색어 자동완성 (datalist) 추가. 같은 단어를
  자주 칠 때 한 글자만 쳐도 드롭다운에서 골라잡을 수 있다. 저장은
  `localStorage` 키 `soundmatch.catalog.recent-searches` 에 최대 5건, 같은
  검색어가 반복되면 맨 위로 끌어올린다. 의미 있는 결과(>0건) 가 나온 검색만
  기록 — 0건 노이즈 차단. 한 글자 검색도 기록 안 함.

### Changed
- 결과 메타 footer 의 분석 시각이 UTC ISO 그대로 표시되던 것을 사용자 로컬
  타임존(한국 사용자 KST) 으로 변환해 표시. `formatLocalTimestamp()` 헬퍼
  추가 — `Date(iso).toLocaleString(lang)` 활용, 파싱 실패 시 원본 ISO
  fallback. 언어 토글 시 자동으로 ko-KR / en-US 로케일 반영 (기존
  `i18n:change` 리스너가 결과 영역 재렌더).

### Added
- 결과 hit 카드의 액션 영역에 "카탈로그에서 보기" 딥링크 버튼 추가.
  `/catalog?song=<encoded>` 로 이동해 그 곡 기준 유사 곡 모달이 자동
  오픈. 사용자가 매칭 결과에서 흥미로운 곡을 발견하면 곧바로 카탈로그
  맥락으로 넘어가 더 깊이 탐색 가능. 신규 i18n 키
  `results.openInCatalog` (ko/en parity).
- `python -m backend.cli dataset-diff <old> <new>` 서브커먼드 신설. 두 카탈로그
  CSV 간 추가된 곡 / 제거된 곡 / 유지된 곡 카운트를 콘솔에 표 형태로 출력.
  `--limit` 옵션(기본 50, 0 이면 무제한) 으로 긴 목록을 잘라 보여주고,
  `--json` 옵션으로 jq 파이프 친화 출력. 카탈로그 갱신 후 어떤 곡이 들고
  나갔는지 운영자가 즉시 확인 가능.
- `python -m backend.cli dataset-stats <csv>` 서브커먼드 신설. 운영자가
  카탈로그 갱신 후 BPM / 에너지 / 밝기 / 길이 분포 (min/max/avg/p50/n) 와
  중복 키 개수를 콘솔에 한 화면으로 확인. `--json` 옵션은 jq 파이프
  친화. 백엔드 띄울 필요 없이 CSV 만 있으면 동작.
- 메인 페이지 footer 에 빌드 정보 라인 (`v1.4.0 · 2026-05-15`) 추가. 사용자가
  지금 보고 있는 사이트가 어떤 버전 / 어느 날짜에 cut 된 빌드인지 한눈에
  확인 가능. `/api/version.release_date` (PR #49) 활용 — `loadSocialProof`
  의 같은 응답에서 함께 채우므로 새 요청 없음. release_date 가 null 이면
  버전만 표시.
- 카탈로그 페이지 필터 행에 "페이지당" select 추가 (24 / 48 / 96). 사용자가
  한 페이지에 더 많은 곡을 보고 싶을 때 직접 조정 가능. URL 영구화는 이미
  되어 있고, 기본 24 와 다를 때만 `?size=` 가 URL 에 노출되어 짧게 유지.
  `resetFilters()` 도 size 를 기본값으로 되돌리도록 갱신. 신규 i18n
  `catalog.sizeLabel` (ko/en parity).
- `/api/version` 응답에 `release_date` 필드 추가. CHANGELOG.md 의 첫
  `## [X.Y.Z] — YYYY-MM-DD` 헤더에서 날짜만 파싱해서 노출. 운영자가 떠 있는
  빌드가 언제 cut 된 버전인지 한 줄 JSON 으로 확인 가능. 모듈 로드 시 한 번만
  파싱하므로 응답 cost 0.
- 메인 페이지 "내 즐겨찾기" 섹션에 정렬 select 추가 — 최근 추가순(기본) /
  곡명 / 아티스트. 사용자 선호는 localStorage 키 `soundmatch.fav-sort` 에
  저장되어 다음 방문에도 유지된다. 정렬은 `localeCompare(undefined, {
  sensitivity: "base" })` 로 한글/영문 자연 정렬. 신규 i18n 키
  `favorites.sortLabel` / `sortRecent` / `sortTitle` / `sortArtist`
  (ko/en parity).
- 결과 영역 끝에 분석 메타 footer 라인. `분석 시각 · 카탈로그 N곡 · v<엔진버전> ·
  캐시된 결과` 형태로 monospace 톤으로 노출. 사용자가 결과 신뢰성을 가늠하거나
  디버깅할 때 단서. 캐시 응답이면 `cached` 라벨이 accent 색으로 강조. 신규
  i18n 키 `results.metaAnalyzedAt` / `metaCatalogSize` / `metaCached`
  (ko/en parity).

## [1.4.0] — 2026-05-15

이번 사이클의 테마: **운영 가시성 + 일상 UX polish**. 운영자 측 (CLI status,
dataset mtime, sitemap lastmod, social proof) 과 사용자 측 (j/k 키보드 네비,
'?' 도움말, 검색 highlight / × 버튼, 카탈로그 페이저 점프, CSV 다운로드,
shuffle, 결과 카드 펼침 모드 저장 등) 을 같이 다듬음.

### Added
- 카탈로그 페이저에 ⇤ / ⇥ (처음 / 마지막 페이지 점프) 버튼 추가. 큰 카탈로그
  (~1000곡) 에서 한 번에 마지막 페이지로 이동 가능. `Math.ceil(total/size)`
  로 마지막 페이지 계산. 4개 페이저 버튼의 disabled 동기화는
  `syncPagerControls()` 헬퍼 한 군데로 통합. 신규 i18n `catalog.first` /
  `catalog.last` (ko/en parity).
- `python -m backend.cli status` 서브커먼드 신설. 운영자가 떠 있는 서버의
  `/api/health` 응답을 사람-가독 표 형태로 확인 가능. `--strict` 로 strict
  모드 호출, `--json` 으로 JSON 그대로 흘리기, `--timeout` 으로 네트워크
  타임아웃 조정. exit code 도 운영자/CI 친화 — 정상 ok=0, degraded=3,
  네트워크 실패=4, JSON 파싱 실패=5. cron / 모니터링에 그대로 꽂아 쓸 수 있다.
  README "실행" 섹션에 사용 예시 추가.

### Accessibility
- 신규 단축키 도움말 모달에도 카탈로그 모달과 동일한 focus trap 적용 —
  Tab / Shift+Tab 으로 모달 내부 요소만 순환, 닫힐 때 이전 포커스 복원.
  키보드 / 스크린리더 사용자가 모달에 들어왔다가 흐름을 잃지 않도록.

### Added
- `?` 키로 토글되는 키보드 단축키 도움말 모달 신설. `/`, `Space`, `j`/`k`,
  `Enter`, `Esc`, `?` 모든 단축키를 한 화면에서 확인 가능. backdrop 클릭 /
  `Esc` 로 닫기. 모달이 열려 있는 동안은 다른 단축키 안 잡힘 (예측 가능한
  동작). 신규 i18n 섹션 `shortcuts.*` (ko/en parity). controls.shortcuts
  라벨에도 `? 도움말` 힌트 추가.
- 결과 페이지에 키보드 네비게이션 추가 — `j` / `ArrowDown` 으로 다음 hit
  카드, `k` / `ArrowUp` 으로 이전 카드 선택. 선택된 카드는 accent ring 으로
  시각적으로 강조 + smooth scrollIntoView. `Enter` 키로 선택된 카드의
  펼침/접힘 토글. input/textarea 안에서는 동작하지 않아 일반 타이핑에
  방해 안 됨. shortcuts 라벨도 갱신.
- 카탈로그 검색 input 안에 clear (×) 버튼. 검색어가 있을 때만 노출되며,
  클릭하면 검색 상태 + URL 영구화 + 결과 grid 가 한 번에 초기화된다.
  Esc 키를 눌러도 같은 동작. WebKit 의 기본 search 클리어 아이콘은 숨기고
  자체 디자인으로 통일. 신규 i18n 키 `catalog.searchClear` (ko/en parity).
- 카탈로그 페이지 "즐겨찾기만 보기" 토글 옆에 현재 즐겨찾기 카운트 chip
  표시. 비어 있으면 토글 자체가 흐리게 비활성(`cursor: not-allowed`) 으로
  바뀌어 "지금 누를 의미 없다" 신호. 다른 페이지에서 즐겨찾기를 토글하면
  `favorites:change` CustomEvent 로 즉시 동기화.
- `/api/version` 응답에 `analyses_total` 추가 — 누적 분석 횟수 (성공 기준,
  캐시 히트 포함). `_metrics_counters` 와 같은 출처라서 비용 거의 0.
  Prometheus 안 띄운 환경에서도 한 줄 JSON 으로 활동성 확인 가능.
- 메인 페이지 Hero 영역에 작은 "지금까지 N회 분석된 사이트" 라인 추가
  (social proof). 점이 깜빡이는 accent 도트 + monospace 숫자. 누적 분석이
  0 이면 자동으로 숨김. 신규 i18n 키 `hero.totalAnalyses` (ko/en parity).
- 메인 페이지 Hero stat 카드의 "분석 가능한 곡" 아래에 카탈로그 마지막 갱신
  일자(`최근 갱신 · 2026-05-15` / `Updated · 2026-05-15`) 를 작게 노출. 사용자
  입장에서 데이터 신선도 / 운영 상태가 한눈에 보임. 신규 i18n 키
  `hero.catalogFresh` (ko/en). `/api/health.catalog_updated_at` 활용.
- `/api/health` 응답에 `catalog_updated_at` (ISO 8601 UTC) 필드 추가. 운영자가
  현재 떠 있는 카탈로그가 언제 갱신된 데이터인지 즉시 확인 가능. 파일 stat
  실패 시 null.
- `/sitemap.xml` 의 catalog song deep-link `<lastmod>` 를 정적 페이지의 today
  대신 실제 dataset.csv mtime 으로 매핑. 검색 봇 입장에서 곡 데이터가 안
  바뀌었으면 재크롤 동기가 줄어들고, 바뀌었으면 lastmod 가 같이 변해 인덱스
  정확도가 올라간다. 정적 페이지 lastmod 는 오늘 그대로.
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
