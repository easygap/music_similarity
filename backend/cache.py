"""분석 결과를 메모리에 잠깐 들고 있다가, 같은 파일이 다시 올라오면
즉시 응답해주는 LRU 캐시.

요점:
    - 키는 ``(파일 내용 SHA-256, top_n)``. raw 음원은 절대 보관하지 않는다.
    - 값은 ``/api/analyze`` 응답 JSON 그대로. 멜 스펙트로그램 SVG 까지 포함.
    - TTL 이 지났거나 사이즈 cap 을 넘으면 가장 오래된 항목부터 버린다.
    - 캐시는 단일 프로세스 메모리. 다중 worker 환경에선 worker 별로 따로 채워진다.

값을 그대로 돌려주기 전에 호출 측에서 ``request_id``, ``cached`` 같은 동적 필드만
교체하면 새 응답으로 사용 가능.
"""
from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from copy import deepcopy as _deepcopy
from typing import Any


def hash_bytes(blob: bytes) -> str:
    """파일 콘텐츠의 SHA-256 헥스다이제스트. 짧은 식별자로만 쓴다."""
    return hashlib.sha256(blob).hexdigest()


class AnalysisResultCache:
    """간단한 thread-safe LRU + TTL 캐시."""

    def __init__(self, *, max_entries: int = 64, ttl_seconds: int = 600):
        self._max = max_entries
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        # key -> (expires_at, value)
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(sha256_hex: str, top_n: int) -> str:
        return f"{sha256_hex}:{top_n}"

    def get(self, key: str, *, copy: bool = False) -> Any | None:
        """캐시 항목을 조회한다.

        ``copy=True`` 면 ``deepcopy`` 된 사본을 돌려준다. 호출 측이 결과를
        제자리 수정하더라도 캐시 entry 자체가 오염되지 않도록 보장. 결과
        payload 처럼 중첩 dict / list 가 있는 값에 안전. 기본값 False 는
        호출 측이 read-only 로만 다룰 때 (혹은 명시적으로 자기 사본을
        만들 때) 성능 부담 없이 그대로 반환.
        """
        now = time.time()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self.misses += 1
                return None
            expires_at, value = entry
            if expires_at < now:
                # 만료된 항목은 통째로 제거하고 miss 로 처리.
                self._data.pop(key, None)
                self.misses += 1
                return None
            # LRU 갱신: 가장 최근 사용으로 표시.
            self._data.move_to_end(key)
            self.hits += 1
            return _deepcopy(value) if copy else value

    def set(self, key: str, value: Any) -> None:
        now = time.time()
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (now + self._ttl, value)
            # 사이즈 cap 을 넘으면 가장 오래된 것부터 evict.
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def clear(self) -> None:
        """테스트나 운영 시 수동 비우기 용도."""
        with self._lock:
            self._data.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._data)
