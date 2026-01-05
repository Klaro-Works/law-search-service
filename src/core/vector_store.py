"""Vector Store Abstraction Layer

이 모듈은 벡터 저장소(Vector Store)에 대한 추상화 계층을 제공합니다.
나중에 Qdrant, Pinecone, Weaviate 등 다양한 벡터 DB로 교체 가능합니다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class SearchType(str, Enum):
    """검색 유형"""

    vector = "vector"
    lexical = "lexical"
    hybrid = "hybrid"


class VectorStoreType(str, Enum):
    """벡터 저장소 유형"""

    qdrant = "qdrant"
    pinecone = "pinecone"
    weaviate = "weaviate"
    in_memory = "in_memory"
    file_system = "file_system"


@dataclass
class VectorDocument:
    """벡터 문서 데이터 모델"""

    id: str
    embedding: list[float]
    content: str
    metadata: dict[str, Any]
    payload: Optional[dict[str, Any]] = None


class SearchResult(BaseModel):
    """검색 결과 모델"""

    id: str
    score: float
    content: Optional[str] = None
    metadata: dict[str, Any] = {}
    payload: Optional[dict[str, Any]] = None


class VectorStoreConfig(BaseModel):
    """벡터 저장소 설정"""

    store_type: VectorStoreType = VectorStoreType.in_memory
    embedding_dimension: int = 1536  # OpenAI text-embedding-3-small 기본값
    collection_name: str = "default"

    # Qdrant 설정
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    qdrant_local_persistence: bool = True

    # Pinecone 설정
    pinecone_api_key: Optional[str] = None
    pinecone_environment: Optional[str] = None
    pinecone_index: Optional[str] = None

    # Weaviate 설정
    weaviate_url: Optional[str] = None
    weaviate_api_key: Optional[str] = None

    # File System 설정
    fs_storage_path: str = "./vector_data"


class VectorStore(ABC):
    """벡터 저장소 추상 클래스

    모든 벡터 저장소 구현체는 이 클래스를 상속받아야 합니다.
    """

    def __init__(self, config: VectorStoreConfig):
        self.config = config

    def _get_collection_name(self, collection: str | None) -> str:
        """컬렉션 이름 가져오기 (기본값 사용)"""
        return collection or self.config.collection_name

    @abstractmethod
    async def initialize(self) -> None:
        """벡터 저장소 초기화"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """벡터 저장소 연결 종료"""
        pass

    @abstractmethod
    async def add_documents(
        self,
        documents: list[VectorDocument],
        collection: Optional[str] = None,
    ) -> list[str]:
        """문서 추가

        Args:
            documents: 추가할 문서 리스트
            collection: 컬렉션 이름 (None이면 기본 컬렉션 사용)

        Returns:
            추가된 문서 ID 리스트
        """
        pass

    @abstractmethod
    async def delete_documents(
        self,
        ids: list[str],
        collection: Optional[str] = None,
    ) -> int:
        """문서 삭제

        Args:
            ids: 삭제할 문서 ID 리스트
            collection: 컬렉션 이름

        Returns:
            삭제된 문서 수
        """
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        collection: Optional[str] = None,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[SearchResult]:
        """벡터 검색

        Args:
            query_embedding: 쿼리 임베딩
            top_k: 반환할 결과 개수
            collection: 컬렉션 이름
            filters: 메타데이터 필터

        Returns:
            검색 결과 리스트
        """
        pass

    @abstractmethod
    async def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int = 10,
        collection: Optional[str] = None,
        filters: Optional[dict[str, Any]] = None,
        vector_weight: float = 0.7,
        lexical_weight: float = 0.3,
    ) -> list[SearchResult]:
        """하이브리드 검색 (벡터 + 텍스트)

        Args:
            query: 텍스트 쿼리
            query_embedding: 쿼리 임베딩
            top_k: 반환할 결과 개수
            collection: 컬렉션 이름
            filters: 메타데이터 필터
            vector_weight: 벡터 검색 가중치 (0-1)
            lexical_weight: 텍스트 검색 가중치 (0-1)

        Returns:
            검색 결과 리스트
        """
        pass

    @abstractmethod
    async def count_documents(
        self,
        collection: Optional[str] = None,
        filters: Optional[dict[str, Any]] = None,
    ) -> int:
        """문서 수 계산

        Args:
            collection: 컬렉션 이름
            filters: 메타데이터 필터

        Returns:
            문서 수
        """
        pass

    @abstractmethod
    async def delete_collection(
        self,
        collection: str,
    ) -> None:
        """컬렉션 삭제

        Args:
            collection: 컬렉션 이름
        """
        pass

    @abstractmethod
    async def collection_exists(
        self,
        collection: str,
    ) -> bool:
        """컬렉션 존재 확인

        Args:
            collection: 컬렉션 이름

        Returns:
            컬렉션 존재 여부
        """
        pass


def create_vector_store(config: VectorStoreConfig) -> VectorStore:
    """Vector Store 팩토리 함수

    Args:
        config: 벡터 저장소 설정

    Returns:
        VectorStore 인스턴스
    """
    store_type = config.store_type

    if store_type == VectorStoreType.qdrant:
        from .qdrant_store import QdrantVectorStore

        return QdrantVectorStore(config)
    elif store_type == VectorStoreType.in_memory:
        from .in_memory_store import InMemoryVectorStore

        return InMemoryVectorStore(config)
    elif store_type == VectorStoreType.file_system:
        from .file_system_store import FileSystemVectorStore

        return FileSystemVectorStore(config)
    else:
        raise ValueError(f"Unsupported vector store type: {store_type}")
