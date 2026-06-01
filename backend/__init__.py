"""SoundMatch 백엔드 패키지.

버전 문자열은 여기 한 곳에서만 정의한다. FastAPI 앱(`main.app.version`)과
CLI(`cli.ENGINE_VERSION`) 가 모두 이 값을 참조하므로, 릴리즈를 cut 할 때
이 한 줄만 바꾸면 서버 응답 · CLI 출력 · User-Agent 가 한꺼번에 맞춰진다.
"""

__version__ = "1.8.5"
