"""Cache Abstraction Layer

캐시 시스템에 대한 추상화 계층을 제공합니다.
Redis를 기본으로 사용하며, 나중에 다른 캐시로 교체 가능합니다.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel


class CacheType(str, Enum):
    """캐시 유형"""

    redis = "redis"
    in_memory = "in_memory"


class CacheConfig(BaseModel):
    """캐시 설정"""

    cache_type: CacheType = CacheType.redis
    ttl: int = 3600  # 캐시 유효기간 (초)
    prefix: str = "law_search"

    # Redis 설정
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""


class Cache(ABC):
    """캐시 추상 클래스"""

    def __init__(self, config: CacheConfig):
        self.config = config

    def _make_key(self, prefix: str, *args: Any) -> str:
        """캐시 키 생성"""
        key_parts = [self.config.prefix, prefix] + [str(arg) for arg in args]
        key_string = ":".join(key_parts)

        if len(key_string) > 250:
            md5_hash = hashlib.md5(key_string.encode()).hexdigest()
            key_parts[-1] = md5_hash
            key_string = ":".join(key_parts)

        return key_string

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """캐시에서 값 가져오기"""
        pass

    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """캐시에 값 저장"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """캐시에서 값 삭제"""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """캐시 키 존재 확인"""
        pass

    @abstractmethod
    async def clear_prefix(self, prefix: str) -> int:
        """접두사로 시작하는 모든 키 삭제

        Returns:
            삭제된 키 수
        """
        pass

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """JSON 형식으로 캐시에서 값 가져오기"""
        value = await self.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    async def set_json(
        self,
        key: str,
        value: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """JSON 형식으로 캐시에 값 저장"""
        json_str = json.dumps(value, ensure_ascii=False)
        await self.set(key, json_str, ttl)


def create_cache(config: CacheConfig) -> Cache:
    """캐시 팩토리 함수

    Args:
        config: 캐시 설정

    Returns:
        Cache 인스턴스
    """
    cache_type = config.cache_type

    if cache_type == CacheType.redis:
        from .redis_cache import RedisCache

        return RedisCache(config)
    elif cache_type == CacheType.in_memory:
        from .in_memory_cache import InMemoryCache

        return InMemoryCache(config)
    else:
        raise ValueError(f"Unsupported cache type: {cache_type}")
