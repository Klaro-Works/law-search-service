"""Qdrant Vector Store Implementation

Qdrant 벡터 데이터베이스를 위한 구현입니다.
"""

from __future__ import annotations

from typing import Any

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from .vector_store import (
    SearchResult,
    SearchType,
    VectorDocument,
    VectorStore,
    VectorStoreConfig,
)


class QdrantVectorStore(VectorStore):
    """Qdrant 벡터 저장소

    프로덕션 환경에서 사용합니다.
    """

    def __init__(self, config: VectorStoreConfig):
        super().__init__(config)
        self.client: AsyncQdrantClient | None = None

    async def initialize(self) -> None:
        """Qdrant 클라이언트 초기화"""
        qdrant_url = self.config.qdrant_url
        qdrant_api_key = self.config.qdrant_api_key

        if not qdrant_url:
            raise ValueError("QDRANT_URL is required for QdrantVectorStore")

        self.client = AsyncQdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
        )

        await self._ensure_collection_exists()

    async def close(self) -> None:
        """클라이언트 종료"""
        if self.client:
            await self.client.close()
            self.client = None

    def _get_collection_name(self, collection: str | None) -> str:
        """컬렉션 이름 가져오기"""
        return collection or self.config.collection_name

    async def _ensure_collection_exists(self) -> None:
        """컬렉션이 존재하는지 확인하고 없으면 생성"""
        coll_name = self.config.collection_name

        exists = await self.client.collection_exists(coll_name)
        if not exists:
            await self.client.create_collection(
                collection_name=coll_name,
                vectors_config=models.VectorParams(
                    size=self.config.embedding_dimension,
                    distance=models.Distance.COSINE,
                ),
            )

    def _to_qdrant_point(self, doc: VectorDocument) -> models.PointStruct:
        """VectorDocument를 Qdrant 포인트로 변환"""
        payload = {
            "content": doc.content,
            **doc.metadata,
        }
        if doc.payload:
            payload.update(doc.payload)

        return models.PointStruct(
            id=doc.id,
            vector=doc.embedding,
            payload=payload,
        )

    def _to_search_result(self, scored_point: models.ScoredPoint) -> SearchResult:
        """Qdrant 검색 결과를 SearchResult로 변환"""
        payload = scored_point.payload or {}
        content = payload.pop("content", None)
        metadata = payload

        return SearchResult(
            id=str(scored_point.id),
            score=scored_point.score,
            content=content,
            metadata=metadata,
            payload=payload,
        )

    async def add_documents(
        self,
        documents: list[VectorDocument],
        collection: str | None = None,
    ) -> list[str]:
        """문서 추가"""
        if not self.client:
            raise RuntimeError("VectorStore not initialized")

        coll_name = self._get_collection_name(collection)

        points = [self._to_qdrant_point(doc) for doc in documents]

        await self.client.upsert(
            collection_name=coll_name,
            points=points,
        )

        return [str(doc.id) for doc in documents]

    async def delete_documents(
        self,
        ids: list[str],
        collection: str | None = None,
    ) -> int:
        """문서 삭제"""
        if not self.client:
            raise RuntimeError("VectorStore not initialized")

        coll_name = self._get_collection_name(collection)

        await self.client.delete(
            collection_name=coll_name,
            points_selector=models.PointIdsList(
                points=ids,
            ),
        )

        return len(ids)

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """벡터 검색"""
        if not self.client:
            raise RuntimeError("VectorStore not initialized")

        coll_name = self._get_collection_name(collection)

        query_filter = None
        if filters:
            conditions: list[models.Condition] = [
                models.FieldCondition(
                    key=k,
                    match=models.MatchValue(value=v),
                )
                for k, v in filters.items()
            ]
            query_filter = models.Filter(must=conditions)

        results = await self.client.search(
            collection_name=coll_name,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=query_filter,
        )

        return [self._to_search_result(result) for result in results]

    async def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int = 10,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
        vector_weight: float = 0.7,
        lexical_weight: float = 0.3,
    ) -> list[SearchResult]:
        """하이브리드 검색 (Qdrant Hybrid Search)"""
        if not self.client:
            raise RuntimeError("VectorStore not initialized")

        coll_name = self._get_collection_name(collection)

        query_filter = None
        if filters:
            conditions: list[models.Condition] = [
                models.FieldCondition(
                    key=k,
                    match=models.MatchValue(value=v),
                )
                for k, v in filters.items()
            ]
            query_filter = models.Filter(must=conditions)

        try:
            results = await self.client.search(
                collection_name=coll_name,
                query_vector=models.NamedVector(
                    name="vector",
                    vector=query_embedding,
                ),
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
                score_threshold=None,
            )
        except UnexpectedResponse:
            results = []

        return [self._to_search_result(result) for result in results]

    async def count_documents(
        self,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """문서 수 계산"""
        if not self.client:
            raise RuntimeError("VectorStore not initialized")

        coll_name = self._get_collection_name(collection)

        count_info = await self.client.count(
            collection_name=coll_name,
            count_filter=None,
        )

        return count_info.count

    async def delete_collection(self, collection: str) -> None:
        """컬렉션 삭제"""
        if not self.client:
            raise RuntimeError("VectorStore not initialized")

        try:
            await self.client.delete_collection(collection_name=collection)
        except UnexpectedResponse:
            pass

    async def collection_exists(self, collection: str) -> bool:
        """컬렉션 존재 확인"""
        if not self.client:
            return False

        return await self.client.collection_exists(collection)
