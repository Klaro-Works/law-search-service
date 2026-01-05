"""In-Memory Cache Implementation

테스트 및 개발용 인메모리 캐시 구현입니다.
"""

from __future__ import annotations

import time
from typing import Any

from .cache import Cache, CacheConfig


class InMemoryCache(Cache):
    """인메모리 캐시 (테스트용)"""

    def __init__(self, config: CacheConfig):
        super().__init__(config)
        self._store: dict[str, tuple[Any, float]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """초기화 (인메모리이므로 별도 작업 없음)"""
        self._initialized = True

    async def close(self) -> None:
        """종료"""
        self._store.clear()
        self._initialized = False

    def _cleanup_expired(self) -> None:
        """만료된 항목 제거"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, expiry_time) in self._store.items() if expiry_time < current_time
        ]
        for key in expired_keys:
            del self._store[key]

    async def get(self, key: str) -> Any | None:
        """캐시에서 값 가져오기"""
        if not self._initialized:
            raise RuntimeError("Cache not initialized")

        self._cleanup_expired()

        entry = self._store.get(key)
        if entry is None:
            return None

        value, expiry_time = entry
        if time.time() > expiry_time:
            del self._store[key]
            return None

        return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """캐시에 값 저장"""
        if not self._initialized:
            raise RuntimeError("Cache not initialized")

        ttl = ttl or self.config.ttl
        expiry_time = time.time() + ttl
        self._store[key] = (value, expiry_time)

    async def delete(self, key: str) -> None:
        """캐시에서 값 삭제"""
        if not self._initialized:
            raise RuntimeError("Cache not initialized")

        if key in self._store:
            del self._store[key]

    async def exists(self, key: str) -> bool:
        """캐시 키 존재 확인"""
        value = await self.get(key)
        return value is not None

    async def clear_prefix(self, prefix: str) -> None:
        """접두사로 시작하는 모든 키 삭제"""
        if not self._initialized:
            raise RuntimeError("Cache not initialized")

        full_prefix = f"{self.config.prefix}:{prefix}:"
        keys_to_delete = [key for key in self._store if key.startswith(full_prefix)]
        for key in keys_to_delete:
            del self._store[key]

        return len(keys_to_delete)
