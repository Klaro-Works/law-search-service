"""src.main

FastAPI entrypoint for the Law Search Service.

MVP scope (current repo state):
- Implements REST endpoints:
  - GET  /api/v1/health
  - POST /api/v1/law/search
- The search endpoint currently proxies to law.go.kr via `src.pipeline.collectors.law_collector`.

Future scope (documented in API_SPEC.md / MCP_TOOLS_SPEC.md):
- PostgreSQL + Qdrant hybrid search
- Law detail/article endpoints
- MCP server
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.pipeline.collectors.law_collector import (
    fetch_law_detail as collector_fetch_law_detail,
    search_law as collector_search_law,
)
from src.repository.db import get_db_session
from src.utils.logger import get_logger
from src.models.entities import Law, LawArticle

logger = get_logger(__name__)


class SearchType(str, Enum):
    lexical = "lexical"
    semantic = "semantic"
    hybrid = "hybrid"


class SortBy(str, Enum):
    enforce_date = "enforce_date"
    law_name_kr = "law_name_kr"
    updated_at = "updated_at"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"

class LawSearchFilters(BaseModel):
    department: Optional[list[str]] = None
    law_type: Optional[list[str]] = None
    status: Optional[list[str]] = None
    enforce_date_from: Optional[str] = None
    enforce_date_to: Optional[str] = None


class LawSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="검색어")
    search_type: SearchType = Field(default=SearchType.hybrid, description="검색 방식")
    top_k: int = Field(default=20, ge=1, le=100, description="반환할 결과 개수")
    filters: Optional[LawSearchFilters] = None
    include_articles: bool = False
    rerank: bool = False


class LawSearchResult(BaseModel):
    law_id: str
    law_name_kr: str
    law_abbr: Optional[str] = None
    department: Optional[str] = None
    law_type: Optional[str] = None
    status: Optional[str] = None
    enforce_date: Optional[str] = None
    promulgate_date: Optional[str] = None
    score: Optional[float] = None
    snippet: Optional[str] = None
    detail_link: Optional[str] = None
    matched_articles: Optional[Any] = None


class LawSearchMetadata(BaseModel):
    search_type: SearchType
    lexical_count: int
    semantic_count: int
    cache_hit: bool
    note: Optional[str] = None


class LawSearchResponse(BaseModel):
    results: list[LawSearchResult]
    total_count: int
    search_time_ms: float
    search_metadata: LawSearchMetadata


class LawArticleDetail(BaseModel):
    article_no: str
    title: Optional[str] = None
    content: str
    vector_id: Optional[str] = None


class LawDetailResponse(BaseModel):
    law_id: str
    law_serial: Optional[str] = None
    law_name_kr: str
    law_abbr: Optional[str] = None
    department: Optional[str] = None
    law_type: Optional[str] = None
    status: Optional[str] = None
    enforce_date: Optional[str] = None
    promulgate_date: Optional[str] = None
    detail_link: Optional[str] = None
    full_text: Optional[str] = None
    articles: Optional[list[LawArticleDetail]] = None
    article_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class Pagination(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class LawListItem(BaseModel):
    law_id: str
    law_name_kr: str
    law_abbr: Optional[str] = None
    department: Optional[str] = None
    law_type: Optional[str] = None
    status: Optional[str] = None
    enforce_date: Optional[str] = None
    detail_link: Optional[str] = None


class LawListResponse(BaseModel):
    items: list[LawListItem]
    pagination: Pagination


class LawStatsResponse(BaseModel):
    total_laws: int
    total_articles: int
    by_department: dict[str, int]
    by_law_type: dict[str, int]
    by_status: dict[str, int]
    last_updated: Optional[str] = None


class ArticleSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="조문 내 검색어")
    search_type: SearchType = Field(default=SearchType.semantic, description="검색 방식")
    top_k: int = Field(default=10, ge=1, le=20, description="반환할 조문 개수")


class ArticleSearchResult(BaseModel):
    article_no: str
    title: Optional[str] = None
    content: str
    score: float
    snippet: str


class ArticleSearchResponse(BaseModel):
    law_id: str
    law_name_kr: Optional[str] = None
    results: list[ArticleSearchResult]
    total_count: int
    search_time_ms: float


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[dict[str, Any]] = None
    timestamp: str
    request_id: str


app = FastAPI(
    title="Law Search Service",
    version=settings.service_version,
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def _error_response(
    request: Request,
    *,
    status_code: int,
    error: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=error,
        message=message,
        details=details,
        timestamp=datetime.now(timezone.utc).isoformat(),
        request_id=getattr(request.state, "request_id", ""),
    ).model_dump()
    return JSONResponse(status_code=status_code, content=payload)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Allow raising HTTPException(detail={...}) with our standard schema.
    if isinstance(exc.detail, dict) and "error" in exc.detail and "message" in exc.detail:
        return _error_response(
            request,
            status_code=exc.status_code,
            error=str(exc.detail.get("error")),
            message=str(exc.detail.get("message")),
            details=exc.detail.get("details"),
        )

    return _error_response(
        request,
        status_code=exc.status_code,
        error="HTTPException",
        message=str(exc.detail),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Normalize FastAPI/Pydantic validation errors into the project's error envelope.
    return _error_response(
        request,
        status_code=400,
        error="ValidationError",
        message="요청 파라미터 검증 실패",
        details={"errors": exc.errors()},
    )


@app.get("/api/v1/health")
async def health():
    # For now, only confirms the API process is running.
    # Deeper checks (Postgres/Qdrant/Redis/MinIO) will be added once those layers exist.
    return {
        "status": "healthy",
        "version": settings.service_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": "not_implemented",
            "qdrant": "not_implemented",
            "redis": "not_implemented",
            "minio": "not_implemented",
            "law_api_key": "configured" if bool(settings.law_api_key) else "not_configured",
        },
    }


@app.get("/api/v1/law", response_model=LawListResponse)
async def list_laws(
    request: Request,
    page: int = 1,
    page_size: int = 50,
    department: Optional[str] = None,
    law_type: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: SortBy = SortBy.enforce_date,
    sort_order: SortOrder = SortOrder.desc,
    db: AsyncSession = Depends(get_db_session),
):
    # Input guard
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "ValidationError",
                "message": "page/page_size 파라미터가 올바르지 않습니다.",
                "details": {"page": page, "page_size": page_size},
            },
        )

    try:
        filters = []
        if department:
            filters.append(Law.department == department)
        if law_type:
            filters.append(Law.law_type == law_type)
        if status:
            filters.append(Law.status == status)

        total_items = int(
            await db.scalar(select(func.count()).select_from(Law).where(*filters))  # type: ignore[arg-type]
            or 0
        )

        # Sort mapping
        sort_col = {
            SortBy.enforce_date: Law.enforce_date,
            SortBy.law_name_kr: Law.law_name_kr,
            SortBy.updated_at: Law.updated_at,
        }[sort_by]

        order_expr = sort_col.asc() if sort_order == SortOrder.asc else sort_col.desc()

        offset = (page - 1) * page_size
        stmt = (
            select(Law)
            .where(*filters)  # type: ignore[arg-type]
            .order_by(order_expr)
            .offset(offset)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()

        items = [
            LawListItem(
                law_id=r.law_id,
                law_name_kr=r.law_name_kr,
                law_abbr=r.law_abbr,
                department=r.department,
                law_type=r.law_type,
                status=r.status,
                enforce_date=r.enforce_date,
                detail_link=r.detail_link,
            )
            for r in rows
        ]

        total_pages = (total_items + page_size - 1) // page_size if total_items else 0

        return LawListResponse(
            items=items,
            pagination=Pagination(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
            ),
        )
    except Exception as e:
        logger.exception("DB error in list_laws")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ServiceUnavailable",
                "message": "PostgreSQL에 연결할 수 없습니다. DB 설정/실행 상태를 확인하세요.",
                "details": {"cause": str(e)},
            },
        )


@app.get("/api/v1/law/stats", response_model=LawStatsResponse)
async def law_stats(request: Request, db: AsyncSession = Depends(get_db_session)):
    try:
        total_laws = int(await db.scalar(select(func.count()).select_from(Law)) or 0)
        total_articles = int(await db.scalar(select(func.count()).select_from(LawArticle)) or 0)

        by_department_rows = (
            await db.execute(
                select(Law.department, func.count()).group_by(Law.department).order_by(func.count().desc())
            )
        ).all()
        by_law_type_rows = (
            await db.execute(select(Law.law_type, func.count()).group_by(Law.law_type).order_by(func.count().desc()))
        ).all()
        by_status_rows = (
            await db.execute(select(Law.status, func.count()).group_by(Law.status).order_by(func.count().desc()))
        ).all()

        last_updated = await db.scalar(select(func.max(Law.updated_at)))
        last_updated_iso = last_updated.isoformat() if last_updated else None

        return LawStatsResponse(
            total_laws=total_laws,
            total_articles=total_articles,
            by_department={str(k or "unknown"): int(v) for k, v in by_department_rows},
            by_law_type={str(k or "unknown"): int(v) for k, v in by_law_type_rows},
            by_status={str(k or "unknown"): int(v) for k, v in by_status_rows},
            last_updated=last_updated_iso,
        )
    except Exception as e:
        logger.exception("DB error in law_stats")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ServiceUnavailable",
                "message": "PostgreSQL에 연결할 수 없습니다. DB 설정/실행 상태를 확인하세요.",
                "details": {"cause": str(e)},
            },
        )


def _map_collector_result(item: dict) -> LawSearchResult:
    return LawSearchResult(
        law_id=str(item.get("법령ID") or ""),
        law_name_kr=str(item.get("법령명한글") or ""),
        law_abbr=(item.get("법령약칭명") or None),
        department=(item.get("소관부처명") or None),
        status=(item.get("현행연혁코드") or None),
        enforce_date=(item.get("시행일자") or None),
        promulgate_date=(item.get("공포일자") or None),
        detail_link=(item.get("법령상세링크") or None),
        # Not available from current collector.
        law_type=None,
        score=None,
        snippet=None,
        matched_articles=None,
    )


def _lexical_score(text: str, query: str) -> float:
    q = query.strip().lower()
    if not q:
        return 0.0

    t = text.lower()
    score = 0.0

    if q in t:
        score += 0.8

    tokens = [tok for tok in re.split(r"\s+", q) if tok]
    if tokens:
        hits = sum(1 for tok in tokens if tok in t)
        score += 0.2 * (hits / len(tokens))

    # Bound to [0, 1]
    return float(max(0.0, min(1.0, score)))


def _make_snippet(text: str, query: str, window: int = 120) -> str:
    q = query.strip()
    if not q:
        return (text[:window] + ("..." if len(text) > window else "")).strip()

    lower_text = text.lower()
    lower_q = q.lower()
    idx = lower_text.find(lower_q)

    highlight_target = q
    if idx == -1:
        tokens = [tok for tok in re.split(r"\s+", q) if tok]
        for tok in tokens:
            j = lower_text.find(tok.lower())
            if j != -1:
                idx = j
                highlight_target = tok
                break

    if idx == -1:
        return (text[:window] + ("..." if len(text) > window else "")).strip()

    start = max(0, idx - window // 2)
    end = min(len(text), idx + len(highlight_target) + window // 2)
    snippet = text[start:end]

    # Basic highlight (case-insensitive), without changing the original casing too much.
    try:
        snippet = re.sub(
            re.escape(highlight_target),
            f"<em>{highlight_target}</em>",
            snippet,
            flags=re.IGNORECASE,
        )
    except re.error:
        pass

    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}".strip()


def _split_query_list(query: str) -> list[str]:
    if not isinstance(query, str):
        return []
    return [part.strip() for part in query.split(",") if part.strip()]


def _apply_search_filters(where: list[Any], filters: LawSearchFilters | None) -> None:
    if not filters:
        return

    if filters.department:
        where.append(Law.department.in_(filters.department))
    if filters.law_type:
        where.append(Law.law_type.in_(filters.law_type))
    if filters.status:
        where.append(Law.status.in_(filters.status))

    # Dates are stored as YYYYMMDD strings; lexicographical compare works.
    if filters.enforce_date_from:
        where.append(Law.enforce_date >= filters.enforce_date_from)
    if filters.enforce_date_to:
        where.append(Law.enforce_date <= filters.enforce_date_to)


def _law_row_to_search_result(law: Law, query: str) -> LawSearchResult:
    searchable = " ".join(
        [p for p in [law.law_name_kr, law.law_abbr or "", law.department or "", law.law_id] if p]
    ).strip()
    score = _lexical_score(searchable, query)
    return LawSearchResult(
        law_id=law.law_id,
        law_name_kr=law.law_name_kr,
        law_abbr=law.law_abbr,
        department=law.department,
        law_type=law.law_type,
        status=law.status,
        enforce_date=law.enforce_date,
        promulgate_date=law.promulgate_date,
        score=score,
        snippet=_make_snippet(searchable, query) if score > 0 else None,
        detail_link=law.detail_link,
        matched_articles=None,
    )


async def _db_search_laws(
    db: AsyncSession,
    *,
    query: str,
    top_k: int,
    filters: LawSearchFilters | None,
) -> list[LawSearchResult]:
    query_list = _split_query_list(query)
    if not query_list:
        return []

    per_query = max(1, top_k // len(query_list))
    by_id: dict[str, LawSearchResult] = {}

    for q in query_list:
        tokens = [tok for tok in re.split(r"\s+", q) if tok]
        patterns = [f"%{tok}%" for tok in (tokens or [q])]

        like_clauses: list[Any] = [Law.law_id == q]
        for pat in patterns:
            like_clauses.append(Law.law_name_kr.ilike(pat))
            like_clauses.append(Law.law_abbr.ilike(pat))
            like_clauses.append(Law.department.ilike(pat))

        where: list[Any] = [or_(*like_clauses)]
        _apply_search_filters(where, filters)

        # Fetch a small candidate pool then score/rank in Python.
        candidate_limit = min(max(per_query * 30, top_k * 5), 300)
        rows = (await db.execute(select(Law).where(*where).limit(candidate_limit))).scalars().all()

        scored: list[LawSearchResult] = []
        for law in rows:
            r = _law_row_to_search_result(law, q)
            if (r.score or 0.0) <= 0:
                continue
            scored.append(r)

        scored.sort(key=lambda r: (-(r.score or 0.0), r.law_name_kr))
        for r in scored[:per_query]:
            prev = by_id.get(r.law_id)
            if prev is None or (r.score or 0.0) > (prev.score or 0.0):
                by_id[r.law_id] = r

    results = list(by_id.values())
    results.sort(key=lambda r: (-(r.score or 0.0), r.law_name_kr))
    return results[:top_k]


async def _cache_search_results_to_db(db: AsyncSession, raw: list[dict]) -> None:
    for item in raw:
        law_id = str(item.get("법령ID") or "").strip()
        if not law_id:
            continue

        insert_values = {
            "law_id": law_id,
            "law_name_kr": str(item.get("법령명한글") or law_id),
            "law_abbr": item.get("법령약칭명") or None,
            "department": item.get("소관부처명") or None,
            "law_type": None,
            "status": item.get("현행연혁코드") or None,
            "enforce_date": item.get("시행일자") or None,
            "promulgate_date": item.get("공포일자") or None,
            "detail_link": item.get("법령상세링크") or None,
            "raw": item,
        }
        update_values = dict(insert_values)
        update_values.pop("law_id", None)

        stmt = pg_insert(Law).values(**insert_values).on_conflict_do_update(
            index_elements=[Law.law_id],
            set_=update_values,
        )
        await db.execute(stmt)


async def _cache_law_detail_to_db(db: AsyncSession, detail: dict) -> None:
    law_id = str(detail.get("law_id") or "").strip()
    if not law_id:
        return

    insert_values = {
        "law_id": law_id,
        "law_serial": detail.get("law_serial"),
        "law_name_kr": str(detail.get("law_name_kr") or law_id),
        "law_abbr": detail.get("law_abbr"),
        "department": detail.get("department"),
        "law_type": detail.get("law_type"),
        "status": detail.get("status"),
        "enforce_date": detail.get("enforce_date"),
        "promulgate_date": detail.get("promulgate_date"),
        "detail_link": detail.get("detail_link"),
        "raw": detail,
    }
    update_values = dict(insert_values)
    update_values.pop("law_id", None)

    await db.execute(
        pg_insert(Law)
        .values(**insert_values)
        .on_conflict_do_update(index_elements=[Law.law_id], set_=update_values)
    )

    # Replace articles (simplest; good enough for MVP ingestion).
    articles = detail.get("articles")
    if isinstance(articles, list):
        await db.execute(delete(LawArticle).where(LawArticle.law_id == law_id))

        rows: list[dict[str, Any]] = []
        for art in articles:
            if not isinstance(art, dict):
                continue
            rows.append(
                {
                    "law_id": law_id,
                    "article_no": str(art.get("article_no") or "").strip() or "(unknown)",
                    "title": art.get("title"),
                    "content": str(art.get("content") or "").strip(),
                    "vector_id": art.get("vector_id"),
                    "raw": art,
                }
            )

        if rows:
            await db.execute(pg_insert(LawArticle), rows)


async def _get_law_detail_from_db(
    db: AsyncSession,
    *,
    law_id: str,
    include_articles: bool,
    include_full_text: bool,
) -> dict | None:
    law = await db.get(Law, law_id)
    if not law:
        return None

    article_rows: list[LawArticle] = []
    if include_articles or include_full_text:
        article_rows = (
            (
                await db.execute(
                    select(LawArticle).where(LawArticle.law_id == law_id).order_by(LawArticle.id.asc())
                )
            )
            .scalars()
            .all()
        )

    articles = (
        [
            {
                "article_no": a.article_no,
                "title": a.title,
                "content": a.content,
                "vector_id": a.vector_id,
            }
            for a in article_rows
        ]
        if include_articles
        else None
    )

    full_text: Optional[str] = None
    if include_full_text and article_rows:
        chunks = []
        for a in article_rows:
            header = " ".join([a.article_no, a.title or ""]).strip()
            chunks.append("\n".join([p for p in (header, a.content) if p]).strip())
        full_text = "\n\n".join([c for c in chunks if c]).strip() or None

    return {
        "law_id": law.law_id,
        "law_serial": law.law_serial,
        "law_name_kr": law.law_name_kr,
        "law_abbr": law.law_abbr,
        "department": law.department,
        "law_type": law.law_type,
        "status": law.status,
        "enforce_date": law.enforce_date,
        "promulgate_date": law.promulgate_date,
        "detail_link": law.detail_link,
        "full_text": full_text,
        "articles": articles,
        "article_count": len(article_rows),
        "created_at": law.created_at.isoformat() if getattr(law, "created_at", None) else None,
        "updated_at": law.updated_at.isoformat() if getattr(law, "updated_at", None) else None,
    }


@app.post("/api/v1/law/search", response_model=LawSearchResponse)
async def law_search(
    body: LawSearchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    started = time.perf_counter()
    results: list[LawSearchResult] = []
    source: str | None = None
    db_error: Exception | None = None

    # 1) DB-first (PostgreSQL)
    try:
        results = await _db_search_laws(db, query=body.query, top_k=body.top_k, filters=body.filters)
        if results:
            source = "postgres"
    except Exception as e:
        db_error = e
        logger.exception("DB error in law_search (fallback to law.go.kr if possible)")

    # 2) Fallback: law.go.kr (if configured) + best-effort cache into DB
    if not results and settings.law_api_key:
        try:
            raw = await collector_search_law(body.query, top_k=body.top_k)
            results = [_map_collector_result(item) for item in raw]
            source = "law.go.kr"

            # Cache minimal metadata into DB (best-effort)
            try:
                await _cache_search_results_to_db(db, raw)
                await db.commit()
            except Exception:
                try:
                    await db.rollback()
                except Exception:
                    pass
        except Exception as e:
            logger.exception("Failed to call law.go.kr collector")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "InternalServerError",
                    "message": "법령 검색 중 서버 오류가 발생했습니다.",
                    "details": {"cause": str(e)},
                },
            )

    # 3) If both DB and law.go.kr are unavailable/unconfigured, return empty results with guidance
    if not results and not settings.law_api_key and db_error is not None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ServiceUnavailable",
                "message": "PostgreSQL에 연결할 수 없고 LAW_API_KEY도 설정되어 있지 않습니다.",
                "details": {"cause": str(db_error)},
            },
        )

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    note_parts: list[str] = []
    if body.search_type != SearchType.lexical:
        note_parts.append(
            "현재는 lexical 검색만 제공되며 semantic/hybrid는 lexical로 대체 실행됩니다."
        )
    if source:
        note_parts.append(f"source={source}")
    if not settings.law_api_key and source is None:
        note_parts.append("DB에 데이터가 없거나(또는 미적재) LAW_API_KEY가 없어 원격 조회를 할 수 없습니다.")

    return LawSearchResponse(
        results=results,
        total_count=len(results),
        search_time_ms=elapsed_ms,
        search_metadata=LawSearchMetadata(
            search_type=body.search_type,
            lexical_count=len(results),
            semantic_count=0,
            cache_hit=(source == "postgres"),
            note="; ".join(note_parts) if note_parts else None,
        ),
    )


@app.get("/api/v1/law/{law_id}", response_model=LawDetailResponse)
async def get_law_detail(
    law_id: str,
    request: Request,
    include_articles: bool = True,
    include_full_text: bool = False,
    db: AsyncSession = Depends(get_db_session),
):
    started = time.perf_counter()
    detail: dict | None = None
    source: str | None = None
    db_error: Exception | None = None

    # 1) DB-first
    try:
        detail = await _get_law_detail_from_db(
            db,
            law_id=law_id,
            include_articles=include_articles,
            include_full_text=include_full_text,
        )
        if detail:
            source = "postgres"
    except Exception as e:
        db_error = e
        logger.exception("DB error in get_law_detail (fallback to law.go.kr if possible)")

    # 2) Fallback: law.go.kr
    if detail is None and settings.law_api_key:
        detail = await collector_fetch_law_detail(
            law_id=law_id,
            include_articles=include_articles,
            include_full_text=include_full_text,
        )
        if detail:
            source = "law.go.kr"
            # Cache into DB (best-effort)
            try:
                await _cache_law_detail_to_db(db, detail)
                await db.commit()
            except Exception:
                try:
                    await db.rollback()
                except Exception:
                    pass

    elapsed_ms = (time.perf_counter() - started) * 1000.0

    if not detail:
        if db_error is not None and not settings.law_api_key:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "ServiceUnavailable",
                    "message": "PostgreSQL에 연결할 수 없고 LAW_API_KEY도 설정되어 있지 않습니다.",
                    "details": {"cause": str(db_error)},
                },
            )

        raise HTTPException(
            status_code=404,
            detail={
                "error": "NotFound",
                "message": f"law_id '{law_id}'에 해당하는 법령을 찾을 수 없습니다.",
                "details": {
                    "hint": "DB에 적재되어 있지 않다면 scripts/collect_laws.py로 먼저 적재하거나 LAW_API_KEY를 설정하세요."
                },
            },
        )

    logger.info(
        "GET /api/v1/law/%s include_articles=%s include_full_text=%s source=%s (%.1fms)",
        law_id,
        include_articles,
        include_full_text,
        source,
        elapsed_ms,
    )

    raw_articles = detail.get("articles")
    articles = (
        [LawArticleDetail(**a) for a in raw_articles]
        if isinstance(raw_articles, list)
        else None
    )

    return LawDetailResponse(
        law_id=str(detail.get("law_id") or law_id),
        law_serial=detail.get("law_serial"),
        law_name_kr=str(detail.get("law_name_kr") or law_id),
        law_abbr=detail.get("law_abbr"),
        department=detail.get("department"),
        law_type=detail.get("law_type"),
        status=detail.get("status"),
        enforce_date=detail.get("enforce_date"),
        promulgate_date=detail.get("promulgate_date"),
        detail_link=detail.get("detail_link"),
        full_text=detail.get("full_text"),
        articles=articles,
        article_count=int(detail.get("article_count") or 0),
        created_at=detail.get("created_at"),
        updated_at=detail.get("updated_at"),
    )


@app.post("/api/v1/law/{law_id}/articles/search", response_model=ArticleSearchResponse)
async def search_articles(
    law_id: str,
    body: ArticleSearchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    started = time.perf_counter()
    law_name_kr: Optional[str] = None
    results: list[ArticleSearchResult] = []
    total_count = 0
    source: str | None = None
    db_error: Exception | None = None
    need_remote_fallback = False

    # 1) DB-first (PostgreSQL)
    try:
        law = await db.get(Law, law_id)
        if law:
            law_name_kr = law.law_name_kr

            article_total = int(
                await db.scalar(
                    select(func.count()).select_from(LawArticle).where(LawArticle.law_id == law_id)
                )
                or 0
            )

            if article_total == 0:
                # Law exists but no articles were ingested.
                need_remote_fallback = True
            else:
                q = body.query.strip()
                tokens = [tok for tok in re.split(r"\s+", q) if tok]
                patterns = [f"%{tok}%" for tok in (tokens or [q])]

                like_clauses: list[Any] = []
                for pat in patterns:
                    like_clauses.append(LawArticle.article_no.ilike(pat))
                    like_clauses.append(LawArticle.title.ilike(pat))
                    like_clauses.append(LawArticle.content.ilike(pat))

                stmt = (
                    select(LawArticle)
                    .where(LawArticle.law_id == law_id, or_(*like_clauses))
                    .order_by(LawArticle.id.asc())
                    .limit(500)
                )
                rows = (await db.execute(stmt)).scalars().all()

                scored: list[ArticleSearchResult] = []
                for row in rows:
                    searchable = " ".join([row.article_no, row.title or "", row.content]).strip()
                    score = _lexical_score(searchable, q)
                    if score <= 0:
                        continue

                    scored.append(
                        ArticleSearchResult(
                            article_no=row.article_no,
                            title=row.title,
                            content=row.content,
                            score=score,
                            snippet=_make_snippet(searchable, q),
                        )
                    )

                scored.sort(key=lambda r: (-r.score, r.article_no))
                total_count = len(scored)
                results = scored[: body.top_k]
                source = "postgres"
        else:
            need_remote_fallback = True
    except Exception as e:
        db_error = e
        need_remote_fallback = True
        logger.exception("DB error in search_articles (fallback to law.go.kr if possible)")

    # 2) Fallback: law.go.kr (only if needed and configured)
    if need_remote_fallback and settings.law_api_key:
        detail = await collector_fetch_law_detail(
            law_id=law_id,
            include_articles=True,
            include_full_text=False,
        )
        if not detail:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NotFound",
                    "message": f"law_id '{law_id}'에 해당하는 법령을 찾을 수 없습니다.",
                },
            )

        law_name_kr = detail.get("law_name_kr")
        articles = detail.get("articles") or []

        scored: list[ArticleSearchResult] = []
        for art in articles:
            if not isinstance(art, dict):
                continue
            article_no = str(art.get("article_no") or "").strip()
            title = art.get("title")
            content = str(art.get("content") or "").strip()

            searchable = " ".join([article_no, title or "", content]).strip()
            score = _lexical_score(searchable, body.query)
            if score <= 0:
                continue

            scored.append(
                ArticleSearchResult(
                    article_no=article_no or "(unknown)",
                    title=title,
                    content=content,
                    score=score,
                    snippet=_make_snippet(searchable, body.query),
                )
            )

        scored.sort(key=lambda r: (-r.score, r.article_no))
        total_count = len(scored)
        results = scored[: body.top_k]
        source = "law.go.kr"

        # Cache into DB (best-effort)
        try:
            await _cache_law_detail_to_db(db, detail)
            await db.commit()
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass

    # 3) If both DB and law.go.kr are unavailable/unconfigured
    if need_remote_fallback and not settings.law_api_key and db_error is None and law_name_kr is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "NotFound",
                "message": f"law_id '{law_id}'에 해당하는 법령을 찾을 수 없습니다.",
                "details": {
                    "hint": "DB에 적재되어 있지 않다면 scripts/collect_laws.py로 먼저 적재하거나 LAW_API_KEY를 설정하세요."
                },
            },
        )

    if need_remote_fallback and not settings.law_api_key and db_error is not None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ServiceUnavailable",
                "message": "PostgreSQL에 연결할 수 없고 LAW_API_KEY도 설정되어 있지 않습니다.",
                "details": {"cause": str(db_error)},
            },
        )

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    logger.info(
        "POST /api/v1/law/%s/articles/search q=%r results=%d source=%s (%.1fms)",
        law_id,
        body.query,
        len(results),
        source,
        elapsed_ms,
    )

    return ArticleSearchResponse(
        law_id=law_id,
        law_name_kr=law_name_kr,
        results=results,
        total_count=total_count,
        search_time_ms=elapsed_ms,
    )

def main() -> None:
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
