"""Core Package for Law Search Service

이 패키지는 벡터 저장소 추상화 계층을 포함합니다.
"""

from .vector_store import (
    VectorStore,
    VectorStoreConfig,
    VectorStoreType,
    VectorDocument,
    SearchResult,
    SearchType,
    create_vector_store,
)
from .cache import (
    Cache,
    CacheConfig,
    CacheType,
    create_cache,
)

__all__ = [
    # Vector Store
    "VectorStore",
    "VectorStoreConfig",
    "VectorStoreType",
    "VectorDocument",
    "SearchResult",
    "SearchType",
    "create_vector_store",
    # Cache
    "Cache",
    "CacheConfig",
    "CacheType",
    "create_cache",
]
