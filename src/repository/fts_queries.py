"""PostgreSQL Full-Text Search (FTS) helper functions

PostgreSQL의 GIN 인덱스를 활용한 고성능 텍스트 검색 기능을 제공합니다.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def fts_search_laws(
    db: AsyncSession,
    *,
    query: str,
    top_k: int = 10,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """법령 FTS 검색

    Args:
        db: DB 세션
        query: 검색어 (한글/영어 모두 지원)
        top_k: 반환할 결과 개수
        filters: 메타데이터 필터

    Returns:
        검색 결과 리스트 (dict 형태)
    """
    from src.models.entities import Law

    where_clauses = ["tsv @@ websearch_to_tsquery('korean', :query)"]
    params: dict[str, Any] = {"query": query}

    if filters:
        if filters.get("department"):
            where_clauses.append("department = ANY(:departments)")
            params["departments"] = filters["department"]
        if filters.get("law_type"):
            where_clauses.append("law_type = ANY(:law_types)")
            params["law_types"] = filters["law_type"]
        if filters.get("status"):
            where_clauses.append("status = ANY(:statuses)")
            params["statuses"] = filters["status"]

    where_clause = " AND ".join(where_clauses)

    sql = text(f"""
        SELECT
            law_id,
            law_name_kr,
            law_abbr,
            department,
            law_type,
            status,
            enforce_date,
            promulgate_date,
            detail_link,
            ts_rank(tsv, websearch_to_tsquery('korean', :query)) as score
        FROM laws
        WHERE {where_clause}
        ORDER BY score DESC, law_name_kr
        LIMIT :top_k
    """)

    params["top_k"] = top_k

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    return [dict(row) for row in rows]


async def fts_search_articles(
    db: AsyncSession,
    *,
    law_id: str,
    query: str,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """조문 FTS 검색

    Args:
        db: DB 세션
        law_id: 법령 ID
        query: 검색어
        top_k: 반환할 결과 개수

    Returns:
        검색 결과 리스트 (dict 형태)
    """
    sql = text("""
        SELECT
            article_no,
            title,
            content,
            ts_rank(tsv, websearch_to_tsquery('korean', :query)) as score
        FROM law_articles
        WHERE
            law_id = :law_id
            AND tsv @@ websearch_to_tsquery('korean', :query)
        ORDER BY score DESC, article_no
        LIMIT :top_k
    """)

    params = {"law_id": law_id, "query": query, "top_k": top_k}

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    return [dict(row) for row in rows]
