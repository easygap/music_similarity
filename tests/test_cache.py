"""분석 결과 캐시 단위 테스트."""
from __future__ import annotations

import time

from backend.cache import AnalysisResultCache, hash_bytes


def test_hash_bytes_is_deterministic():
    assert hash_bytes(b"hello") == hash_bytes(b"hello")
    assert hash_bytes(b"hello") != hash_bytes(b"hello!")


def test_cache_set_then_get_returns_same_value():
    cache = AnalysisResultCache(max_entries=4, ttl_seconds=60)
    key = cache.make_key("abc", 5)
    cache.set(key, {"x": 1})
    assert cache.get(key) == {"x": 1}
    assert cache.hits == 1
    assert cache.misses == 0


def test_cache_miss_increments_counter():
    cache = AnalysisResultCache(max_entries=4, ttl_seconds=60)
    assert cache.get("nope") is None
    assert cache.misses == 1
    assert cache.hits == 0


def test_cache_eviction_when_full():
    cache = AnalysisResultCache(max_entries=2, ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)  # a 가 evict 되어야 한다 (LRU).
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_cache_lru_orders_by_recent_use():
    cache = AnalysisResultCache(max_entries=2, ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    # a 를 한 번 조회해서 더 최근으로 만들어둔다.
    cache.get("a")
    cache.set("c", 3)  # 이제 b 가 evict 되어야 한다.
    assert cache.get("b") is None
    assert cache.get("a") == 1


def test_cache_ttl_expires_value():
    cache = AnalysisResultCache(max_entries=2, ttl_seconds=0)
    cache.set("a", 1)
    # ttl 0 이면 다음 호출에서 바로 만료된다.
    time.sleep(0.01)
    assert cache.get("a") is None


def test_make_key_format():
    key = AnalysisResultCache.make_key("deadbeef", 7)
    assert key == "deadbeef:7"


def test_cache_get_copy_returns_independent_object():
    """copy=True 면 호출 측이 그 결과를 제자리 수정해도 캐시 entry 가 오염되면 안 된다."""
    cache = AnalysisResultCache(max_entries=2, ttl_seconds=60)
    key = cache.make_key("hash", 5)
    cache.set(key, {"results": [{"rank": 1, "title": "x"}], "meta": {"v": 1}})

    snapshot = cache.get(key, copy=True)
    assert snapshot is not None
    # 호출 측이 중첩 객체를 자유롭게 변형.
    snapshot["results"][0]["title"] = "TAMPERED"
    snapshot["meta"]["v"] = 999
    snapshot["new_top_field"] = "client-only"

    # 다시 조회했을 때 원본은 그대로여야 한다.
    again = cache.get(key, copy=True)
    assert again["results"][0]["title"] == "x"
    assert again["meta"]["v"] == 1
    assert "new_top_field" not in again


def test_cache_get_without_copy_shares_reference():
    """기본값(copy=False) 은 성능을 위해 동일 참조를 돌려준다 (read-only 용도)."""
    cache = AnalysisResultCache(max_entries=2, ttl_seconds=60)
    key = cache.make_key("hash", 5)
    payload = {"results": [{"rank": 1}]}
    cache.set(key, payload)

    fetched = cache.get(key)
    # 동일 reference. (의도된 동작 — copy=True 가 비싸서 명시적으로 요청해야 함.)
    assert fetched is payload
