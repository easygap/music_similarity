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
