# 변경 이력

이 프로젝트의 모든 의미 있는 변경은 이 파일에 기록합니다. 형식은
[Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 를 따르고,
버전 규약은 [SemVer](https://semver.org/lang/ko/) 를 따릅니다.

## [Unreleased]

### Added
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
