# 개발에 참여하기

오류 수정, 기능 추가, 문서 개선 모두 환영합니다. 사용 방법은 [README](README.md)에 있습니다.

## 개발 환경 빠른 셋업

```bash
python -m venv .venv
source .venv/bin/activate          # Windows 라면 .venv\Scripts\activate
pip install -r requirements-dev.txt

# 개발 서버 (autoreload)
uvicorn backend.main:app --reload --port 8000

# 테스트 + 린트
pytest -q
ruff check backend tests scripts
```

오디오 화면을 수정했다면 Node.js로 파형 테스트도 실행해 주세요. 추가 패키지는 필요 없습니다.

```bash
node --test tests/frontend/audio.test.cjs
```

## 작업 흐름

1. 큰 변경은 먼저 이슈로 의도를 공유해 주세요. 작은 버그 픽스는 바로 PR 도 OK.
2. `main` 에서 분기합니다. 브랜치는 한 가지 변경에 집중해 주세요.
3. 동작 변경에는 테스트를 같이 작성해 주세요. 새 엔드포인트는 API 테스트 필수.
4. 로컬에서 `pytest` + `ruff check` 가 통과하는지 확인. CI 가 그린이어야 머지됩니다.
5. 환경 변수 / API / 동작이 바뀌면 README 도 같이 업데이트.

## 코드 스타일

- Python: `pyproject.toml` 의 ruff 규칙. `from __future__ import annotations` 사용, 내장 typing alias (`list`, `dict`) 위주.
- JS: ES2019, 빌드 스텝 없음. 모듈은 작게 — `app.js`, `i18n.js`, `visualizers.js`.
- CSS: 단일 디자인 시스템 파일. 색은 `--*` 커스텀 프로퍼티 재사용, 하드코딩 지양.
- 사용자 문구는 `frontend/js/i18n.js` 한 곳에만. 한국어/영어 모두 같은 사전에서 관리.
- 로그에는 절대 raw 파일명/음원을 남기지 마세요. `request_id` 정도가 적당.

## 커밋 메시지

- 한국어 위주로 작성합니다 (기술 용어는 영어 그대로 OK).
- 첫 줄은 70자 이내, 명사구 또는 간결한 평서문. 본문에는 "왜" 위주.
- 예시:
  ```
  레이더 차트 모바일 가로 모드 깨짐 수정

  flex-direction: column 으로 강제 전환해서 라벨이 겹치던 부분 해결.
  ```

## 보안 / 데이터 처리 원칙

- 사용자 음원은 절대 영구 저장하지 않습니다. 디스크에 무언가 쓰는 코드는 반드시 `finally` 또는 `BackgroundTasks` 정리 경로를 포함시켜 주세요.
- 외부 네트워크 호출 추가 시 명확한 이유 + CSP 갱신.
- CORS 를 환경변수 없이 더 넓히지 마세요.

## 보안 이슈 보고

공개 이슈로 올리지 말고 저장소 소유자에게 비공개로 메일을 주세요.

## 분석 방식

librosa로 길이를 포함한 58개 값을 추출하고, 길이를 제외한 57개 특성으로 비교합니다.
카탈로그로 학습한 `StandardScaler`로 단위를 맞춘 뒤 코사인 유사도를 구합니다.
화면에는 음수를 0으로 처리한 유사도에 100을 곱해 표시합니다.

곡의 앞부분 최대 30초만 분석합니다. 결과는 등록된 곡 안에서의 비교이며 표절 여부를 판단하는 데 사용할 수 없습니다.

## 데이터와 화면 자료 만들기

- API 문서: 실행한 서버의 `/docs`
- CLI: `python -m backend.cli --help`
- 카탈로그: `scripts/rebuild_dataset.py` 실행 후 `python scripts/build_landing_data.py`
- 샘플 음원과 분석값: `python scripts/build_listening_demo.py`
- UI 글꼴: 개발 환경에 `fonttools brotli`를 설치한 뒤 `python scripts/build_ui_font.py`
- 화면만 미리 보기: `python preview_server.py 8790` — 이 서버의 추천 결과는 예시 데이터입니다.
- [화면 설계와 참고 자료](docs/design-2026.md)
- [화면·기능·성능 확인 결과](docs/verification-2026.md)

## 운영 설정

환경 변수는 `backend/main.py`의 `MUSIC_*` 설정을 확인하세요.

| 설정 | 기본값 | 설명 |
| --- | --- | --- |
| `WEB_CONCURRENCY` | `1` | 요청 제한·캐시·통계가 메모리 기반입니다. 여러 워커를 쓰려면 외부 상태 저장소를 먼저 구성해야 합니다. |

배포한 버전은 다음 명령으로 확인합니다.

```bash
python -m backend.cli version
# v1.9.0 · 2026-09-18 · <git-sha>
```

## 릴리즈

1. `CHANGELOG.md`의 Unreleased 내용을 새 버전 섹션으로 옮깁니다.
2. `backend/__init__.py`와 이 문서·OpenAPI의 버전 예시를 맞춥니다.
3. main의 CI가 통과하면 `git tag vx.y.z && git push origin vx.y.z`로 태그를 올립니다.

태그·패키지 버전·CHANGELOG가 다르면 자동으로 릴리즈 생성을 중단합니다.
