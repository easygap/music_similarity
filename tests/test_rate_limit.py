"""Rate limiter 의 IP 식별 / GC 동작 회귀 테스트.

핵심 보안 보장:
  - X-Forwarded-For 는 trusted proxy 에서 온 요청에서만 신뢰한다.
  - 회전 IP / XFF 폭주에도 `_rate_state` 가 무한 증가하지 않는다.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


@pytest.fixture()
def mod():
    """테스트마다 깨끗한 모듈 상태로 시작하기 위해 reload."""
    os.environ.setdefault("MUSIC_SKIP_WARMUP", "1")
    import importlib

    from backend import main as backend_main

    importlib.reload(backend_main)
    return backend_main


def _fake_request(peer: str, *, xff: str | None = None, xrip: str | None = None):
    """`_client_ip` 호출에 필요한 최소 Request 더미."""
    headers: dict[str, str] = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    if xrip is not None:
        headers["x-real-ip"] = xrip

    class _C:
        host = peer

    class _Req:
        client = _C()

        def __init__(self, h):
            self.headers = h

    return _Req(headers)


def test_client_ip_ignores_xff_when_no_trusted_proxies(mod):
    """기본(개발) 환경에서는 XFF 가 와도 항상 peer IP 만 사용해야 한다."""
    mod.TRUSTED_PROXIES = frozenset()
    req = _fake_request("198.51.100.7", xff="1.2.3.4")
    assert mod._client_ip(req) == "198.51.100.7"


def test_client_ip_honors_xff_only_from_trusted_proxy(mod):
    """trusted proxy 에서 온 요청만 XFF 의 첫 IP 를 진짜 클라이언트로 본다."""
    mod.TRUSTED_PROXIES = frozenset({"10.0.0.1"})
    trusted = _fake_request("10.0.0.1", xff="1.2.3.4, 10.0.0.1")
    assert mod._client_ip(trusted) == "1.2.3.4"
    spoofed = _fake_request("8.8.8.8", xff="1.2.3.4")
    # spoofed: peer 가 신뢰 목록에 없으므로 헤더는 무시.
    assert mod._client_ip(spoofed) == "8.8.8.8"


def test_client_ip_trusts_all_with_wildcard(mod):
    """`MUSIC_TRUSTED_PROXIES=*` 면 출발지 검사 없이 XFF 의 첫 IP 사용."""
    mod.TRUSTED_PROXIES = frozenset({"*"})
    # peer 가 어떤 값이든 신뢰. PaaS edge IP 처럼 정확한 주소를 모를 때.
    req = _fake_request("66.241.125.18", xff="1.2.3.4, 5.6.7.8")
    assert mod._client_ip(req) == "1.2.3.4"
    # XFF 가 없으면 X-Real-IP 로 폴백.
    req2 = _fake_request("66.241.125.18", xrip="9.9.9.9")
    assert mod._client_ip(req2) == "9.9.9.9"
    # 두 헤더 모두 없으면 peer 그대로 (PaaS edge 의 source).
    req3 = _fake_request("66.241.125.18")
    assert mod._client_ip(req3) == "66.241.125.18"


def test_client_ip_falls_back_to_x_real_ip(mod):
    """XFF 가 없고 X-Real-IP 만 있을 때도 trusted 일 때만 신뢰."""
    mod.TRUSTED_PROXIES = frozenset({"10.0.0.1"})
    req = _fake_request("10.0.0.1", xrip="5.5.5.5")
    assert mod._client_ip(req) == "5.5.5.5"


def test_parse_trusted_proxies_handles_csv_and_whitespace(mod):
    out = mod._parse_trusted_proxies("10.0.0.1, 10.0.0.2 ,, 192.168.1.1")
    assert out == frozenset({"10.0.0.1", "10.0.0.2", "192.168.1.1"})
    # 빈 / None 입력은 빈 집합.
    assert mod._parse_trusted_proxies("") == frozenset()


def test_gc_rate_state_drops_idle_ips(mod):
    """`_gc_rate_state` 가 윈도우 밖의 IP 키를 dict 에서 삭제해야 한다."""
    mod._rate_state.clear()
    mod._rate_state["fresh.ip"] = [100.0]
    mod._rate_state["stale.ip"] = [0.0]
    mod._rate_state["empty.ip"] = []
    mod._gc_rate_state(now=120.0, window=60.0)
    # fresh: 100 > (120-60)=60 → 유지.
    assert "fresh.ip" in mod._rate_state
    # stale: 0 ≤ 60 → 삭제.
    assert "stale.ip" not in mod._rate_state
    # empty history 도 삭제.
    assert "empty.ip" not in mod._rate_state


def test_rate_state_does_not_grow_unbounded_under_ip_rotation(mod):
    """회전 IP 시나리오: 1000 개의 IP 가 한 번씩 요청해도, 60s 윈도우 후엔 GC 됨."""
    import asyncio

    async def hit(ip: str, fake_now: float):
        # 직접 internal 만 만지는 게 더 결정적 — TestClient 경유는 시간이 흐름.
        async with mod._rate_lock:
            mod._gc_rate_state(fake_now, 60.0)
            mod._rate_state.setdefault(ip, []).append(fake_now)

    mod._rate_state.clear()
    with patch("time.time", return_value=1000.0):
        for i in range(1000):
            asyncio.run(hit(f"203.0.113.{i % 256}-{i}", 1000.0))
        assert len(mod._rate_state) == 1000  # 모두 0초에 들어옴

    # 충분히 미래 시점에 다시 한 번 GC 가 도는 호출이 일어나면 모두 비어야 한다.
    asyncio.run(hit("198.51.100.1", 2000.0))
    # GC 가 윈도우 밖 IP 들을 모두 삭제하고 새 IP 하나만 남는다.
    assert len(mod._rate_state) == 1
    assert "198.51.100.1" in mod._rate_state


def test_client_ip_unknown_when_no_client(mod):
    """request.client 가 None 인 극단 케이스(테스트/유닛) 에서 'unknown' 반환."""
    mod.TRUSTED_PROXIES = frozenset()

    class _Req:
        client = None
        headers: dict[str, str] = {}

    assert mod._client_ip(_Req()) == "unknown"


def test_rate_limit_exception_body_includes_retry_after_fields(mod):
    """RateLimitExceeded 핸들러가 헤더와 동일한 값을 JSON body 에도 채워야 한다.

    클라이언트가 헤더 파싱 없이 body 만으로도 backoff 로직을 짤 수 있어야
    SDK / 모니터링 도구가 단순해진다.
    """
    import asyncio

    exc = mod.RateLimitExceeded(
        retry_after_seconds=42,
        limit=12,
        reset_at=1_700_000_000,
        detail="요청이 너무 잦습니다. 약 42초 뒤에 다시 시도해주세요.",
    )
    response = asyncio.run(mod._rate_limit_exception_handler(request=None, exc=exc))
    # 상태 코드 + 헤더 검증.
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "42"
    assert response.headers["X-RateLimit-Limit"] == "12"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert response.headers["X-RateLimit-Reset"] == "1700000000"
    # body 도 같은 값.
    import json

    body = json.loads(response.body)
    assert body["detail"].startswith("요청이")
    assert body["retry_after_seconds"] == 42
    assert body["limit"] == 12
    assert body["reset_at"] == 1_700_000_000
