# 컨트리뷰션 가이드

오픈소스 형태로 기여를 받습니다. 이슈/PR 환영해요.

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
