"""Redis Cache Implementation

Redis를 사용한 캐시 구현입니다.
"""

from __future__ import annotations

import asyncio
from typing import Any

import redis.asyncio as redis
from redis.asyncio import Redis

from .cache import Cache, CacheConfig


class RedisCache(Cache):
    """Redis 기반 캐시"""

    def __init__(self, config: CacheConfig):
        super().__init__(config)
        self.client: Redis | None = None

    async def initialize(self) -> None:
        """Redis 클라이언트 초기화"""
        self.client = redis.from_url(
            f"redis://:{self.config.redis_password}@{self.config.redis_host}:{self.config.redis_port}/{self.config.redis_db}"
            if self.config.redis_password
            else f"redis://{self.config.redis_host}:{self.config.redis_port}/{self.config.redis_db}",
            encoding="utf-8",
            decode_responses=True,
        )

    async def close(self) -> None:
        """Redis 연결 종료"""
        if self.client:
            await self.client.close()
            self.client = None

    async def get(self, key: str) -> Any | None:
        """캐시에서 값 가져오기"""
        if not self.client:
            raise RuntimeError("Cache not initialized")
        return await self.client.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """캐시에 값 저장"""
        if not self.client:
            raise RuntimeError("Cache not initialized")

        ttl = ttl or self.config.ttl
        await self.client.setex(key, ttl, value)

    async def delete(self, key: str) -> None:
        """캐시에서 값 삭제"""
        if not self.client:
            raise RuntimeError("Cache not initialized")
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        """캐시 키 존재 확인"""
        if not self.client:
            raise RuntimeError("Cache not initialized")
        return bool(await self.client.exists(key))

    async def clear_prefix(self, prefix: str) -> int:
        """접두사로 시작하는 모든 키 삭제"""
        if not self.client:
            raise RuntimeError("Cache not initialized")

        full_prefix = f"{self.config.prefix}:{prefix}:*"
        keys = []
        async for key in self.client.scan_iter(match=full_prefix):
            keys.append(key)

        if keys:
            await self.client.delete(*keys)

        return len(keys)
