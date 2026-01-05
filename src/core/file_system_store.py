"""File System Vector Store Implementation

파일시스템에 벡터 데이터를 저장하는 구현입니다.
나중에 Qdrant 등 실제 벡터 DB로 쉽게 교체 가능하도록 설계되었습니다.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from .vector_store import (
    SearchResult,
    VectorDocument,
    VectorStore,
    VectorStoreConfig,
)


class FileSystemVectorStore(VectorStore):
    """파일시스템 기반 벡터 저장소

    개발 및 테스트용으로 사용합니다.
    나중에 QdrantVectorStore로 교체할 수 있습니다.
    """

    def __init__(self, config: VectorStoreConfig):
        super().__init__(config)
        self.storage_path = Path(config.fs_storage_path)
        self._initialized = False

    def _get_collection_dir(self, collection: str | None) -> Path:
        """컬렉션 디렉토리 경로 가져오기"""
        coll_name = collection or self.config.collection_name
        return self.storage_path / coll_name

    def _get_document_path(self, collection: str, doc_id: str) -> Path:
        """문서 파일 경로 가져오기"""
        coll_dir = self._get_collection_dir(collection)
        return coll_dir / f"{doc_id}.json"

    def _get_index_path(self, collection: str) -> Path:
        """인덱스 파일 경로 가져오기"""
        coll_dir = self._get_collection_dir(collection)
        return coll_dir / ".index.json"

    async def initialize(self) -> None:
        """초기화: 저장소 디렉토리 생성"""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._initialized = True

    async def close(self) -> None:
        """종료 (파일시스템이므로 별도 작업 없음)"""
        self._initialized = False

    def _save_document(self, doc: VectorDocument, collection: str) -> None:
        """문서 저장"""
        doc_path = self._get_document_path(collection, doc.id)
        doc_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "id": doc.id,
            "embedding": doc.embedding,
            "content": doc.content,
            "metadata": doc.metadata,
            "payload": doc.payload,
        }

        with open(doc_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def add_documents(
        self,
        documents: list[VectorDocument],
        collection: str | None = None,
    ) -> list[str]:
        """문서 추가"""
        coll_name = self._get_collection_name(collection)
        added_ids: list[str] = []

        for doc in documents:
            self._save_document(doc, coll_name)
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
            doc_path = self._get_document_path(coll_name, doc_id)
            if doc_path.exists():
                doc_path.unlink()
                deleted_count += 1

        return deleted_count

    def _load_document(self, doc_id: str, collection: str) -> VectorDocument | None:
        """문서 로드"""
        doc_path = self._get_document_path(collection, doc_id)
        if not doc_path.exists():
            return None

        with open(doc_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return VectorDocument(
            id=data["id"],
            embedding=data["embedding"],
            content=data["content"],
            metadata=data["metadata"],
            payload=data.get("payload"),
        )

    def _get_all_documents(self, collection: str) -> list[VectorDocument]:
        """컬렉션 내 모든 문서 로드"""
        coll_dir = self._get_collection_dir(collection)
        if not coll_dir.exists():
            return []

        documents: list[VectorDocument] = []
        for file_path in coll_dir.glob("*.json"):
            if file_path.name.startswith("."):
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                documents.append(
                    VectorDocument(
                        id=data["id"],
                        embedding=data["embedding"],
                        content=data["content"],
                        metadata=data["metadata"],
                        payload=data.get("payload"),
                    )
                )
            except Exception:
                continue

        return documents

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
        documents = self._get_all_documents(coll_name)

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

    def _lexical_search(
        self,
        query: str,
        documents: list[VectorDocument],
    ) -> list[tuple[VectorDocument, float]]:
        """어휘 기반 검색 (단순 substring 매칭)"""
        query_lower = query.lower()

        results: list[tuple[VectorDocument, float]] = []
        for doc in documents:
            score = 0.0

            searchable_text = f"{doc.content} {json.dumps(doc.metadata)}".lower()

            if query_lower in searchable_text:
                score += 0.8

            words = query_lower.split()
            for word in words:
                if word in searchable_text:
                    score += 0.2 / len(words)

            if score > 0:
                results.append((doc, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

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
        """하이브리드 검색 (벡터 + 어휘)"""
        coll_name = self._get_collection_name(collection)
        documents = self._get_all_documents(coll_name)

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

        vector_scores: dict[str, float] = {}
        for doc in filtered_docs:
            score = self._cosine_similarity(query_embedding, doc.embedding)
            vector_scores[doc.id] = score

        lexical_results = self._lexical_search(query, filtered_docs)
        lexical_scores: dict[str, float] = {doc.id: score for doc, score in lexical_results}

        combined_scores: dict[str, float] = {}
        for doc in filtered_docs:
            vec_score = vector_scores.get(doc.id, 0.0)
            lex_score = lexical_scores.get(doc.id, 0.0)
            combined_scores[doc.id] = vec_score * vector_weight + lex_score * lexical_weight

        results_with_scores: list[tuple[VectorDocument, float]] = [
            (doc, combined_scores[doc.id]) for doc in filtered_docs if doc.id in combined_scores
        ]

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

    async def count_documents(
        self,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """문서 수 계산"""
        coll_name = self._get_collection_name(collection)
        documents = self._get_all_documents(coll_name)

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
        coll_dir = self._get_collection_dir(collection)
        if coll_dir.exists():
            for item in coll_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    for sub_item in item.iterdir():
                        sub_item.unlink()
                    item.rmdir()
            coll_dir.rmdir()

    async def collection_exists(self, collection: str) -> bool:
        """컬렉션 존재 확인"""
        coll_dir = self._get_collection_dir(collection)
        return coll_dir.exists() and coll_dir.is_dir()
