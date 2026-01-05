"""In-Memory Vector Store Implementation

테스트 및 개발용 간단한 인메모리 벡터 저장소 구현입니다.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

import numpy as np

from .vector_store import (
    SearchResult,
    VectorDocument,
    VectorStore,
    VectorStoreConfig,
)


class InMemoryVectorStore(VectorStore):
    """인메모리 벡터 저장소

    테스트 및 개발용으로 사용합니다.
    실제 환경에서는 Qdrant나 다른 벡터 DB를 사용하세요.
    """

    def __init__(self, config: VectorStoreConfig):
        super().__init__(config)
        self._collections: dict[str, dict[str, VectorDocument]] = defaultdict(dict)
        self._initialized = False

    async def initialize(self) -> None:
        """초기화 (인메모리이므로 별도 작업 없음)"""
        self._initialized = True

    async def close(self) -> None:
        """종료 (인메모리이므로 별도 작업 없음)"""
        self._collections.clear()
        self._initialized = False

    def _get_collection_name(self, collection: str | None) -> str:
        """컬렉션 이름 가져오기"""
        return collection or self.config.collection_name

    async def add_documents(
        self,
        documents: list[VectorDocument],
        collection: str | None = None,
    ) -> list[str]:
        """문서 추가"""
        coll_name = self._get_collection_name(collection)
        added_ids: list[str] = []

        for doc in documents:
            self._collections[coll_name][doc.id] = doc
            added_ids.append(doc.id)

        return added_ids

    async def delete_documents(
        self,
        ids: list[str],
        collection: str | None = None,
    ) -> int:
        """문서 삭제"""
        coll_name = self._get_collection_name(collection)
        deleted_count = 0

        for doc_id in ids:
            if doc_id in self._collections[coll_name]:
                del self._collections[coll_name][doc_id]
                deleted_count += 1

        return deleted_count

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """코사인 유사도 계산"""
        arr1 = np.array(vec1)
        arr2 = np.array(vec2)

        dot_product = np.dot(arr1, arr2)
        norm1 = np.linalg.norm(arr1)
        norm2 = np.linalg.norm(arr2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """벡터 검색"""
        coll_name = self._get_collection_name(collection)
        documents = list(self._collections[coll_name].values())

        if filters:
            filtered_docs = [
                doc
                for doc in documents
                if all(doc.metadata.get(k) == v for k, v in filters.items())
            ]
        else:
            filtered_docs = documents

        if not filtered_docs:
            return []

        results_with_scores: list[tuple[VectorDocument, float]] = []
        for doc in filtered_docs:
            score = self._cosine_similarity(query_embedding, doc.embedding)
            results_with_scores.append((doc, score))

        results_with_scores.sort(key=lambda x: x[1], reverse=True)

        return [
            SearchResult(
                id=doc.id,
                score=score,
                content=doc.content,
                metadata=doc.metadata,
                payload=doc.payload,
            )
            for doc, score in results_with_scores[:top_k]
        ]

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
        """하이브리드 검색 (인메모리에서는 벡터 검색만 수행)

        실제 하이브리드 검색은 QdrantVectorStore에서 구현됩니다.
        """
        vector_results = await self.search(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # 더 많은 결과를 가져와서 재순위화
            collection=collection,
            filters=filters,
        )

        return vector_results[:top_k]

    async def count_documents(
        self,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """문서 수 계산"""
        coll_name = self._get_collection_name(collection)
        documents = list(self._collections[coll_name].values())

        if filters:
            filtered_docs = [
                doc
                for doc in documents
                if all(doc.metadata.get(k) == v for k, v in filters.items())
            ]
            return len(filtered_docs)

        return len(documents)

    async def delete_collection(self, collection: str) -> None:
        """컬렉션 삭제"""
        if collection in self._collections:
            del self._collections[collection]

    async def collection_exists(self, collection: str) -> bool:
        """컬렉션 존재 확인"""
        return collection in self._collections
