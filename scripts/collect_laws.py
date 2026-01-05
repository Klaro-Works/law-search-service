"""Collect laws from law.go.kr and persist into PostgreSQL.

This is an MVP ingestion script.

Modes
- By query: use lawSearch.do to discover law IDs.
- By explicit law_id(s): fetch details directly.

Usage examples
  # 1) Collect by query (comma-separated queries supported)
  python3 scripts/collect_laws.py --query "개인정보 보호법, 저작권법" --top-k 20

  # 2) Collect explicit law IDs
  python3 scripts/collect_laws.py --law-id 001971 --law-id 009682

Prereqs
- .env contains LAW_API_KEY and POSTGRES_* values
- PostgreSQL database exists
- Run: python3 scripts/init_db.py
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.entities import Law, LawArticle
from src.pipeline.collectors.law_collector import fetch_law_detail, search_law


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect laws from law.go.kr into PostgreSQL")

    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--query", type=str, help="검색어(쉼표로 여러 개 가능)")
    src.add_argument(
        "--law-id",
        action="append",
        dest="law_ids",
        help="법령ID (여러 번 지정 가능)",
    )

    p.add_argument("--top-k", type=int, default=20, help="query 모드에서 수집할 법령 수")
    p.add_argument(
        "--no-articles",
        action="store_true",
        help="조문 저장을 건너뜁니다 (law 메타만 저장)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 저장하지 않고 수집 대상만 출력합니다",
    )

    return p.parse_args()


def _upsert_law(session: Session, detail: dict[str, Any]) -> None:
    law_id = str(detail.get("law_id") or "").strip()
    if not law_id:
        return

    stmt = (
        pg_insert(Law)
        .values(
            law_id=law_id,
            law_serial=detail.get("law_serial"),
            law_name_kr=str(detail.get("law_name_kr") or law_id),
            law_abbr=detail.get("law_abbr"),
            department=detail.get("department"),
            law_type=detail.get("law_type"),
            status=detail.get("status"),
            enforce_date=detail.get("enforce_date"),
            promulgate_date=detail.get("promulgate_date"),
            detail_link=detail.get("detail_link"),
            raw=detail,
        )
        .on_conflict_do_update(
            index_elements=[Law.law_id],
            set_={
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
            },
        )
    )

    session.execute(stmt)


def _replace_articles(session: Session, law_id: str, articles: list[dict[str, Any]]) -> None:
    session.execute(delete(LawArticle).where(LawArticle.law_id == law_id))

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
        session.execute(pg_insert(LawArticle), rows)


async def _collect_law_ids_by_query(query: str, top_k: int) -> list[str]:
    results = await search_law(query, top_k=top_k)
    ids: list[str] = []
    seen: set[str] = set()

    for r in results:
        law_id = str(r.get("법령ID") or "").strip()
        if not law_id or law_id in seen:
            continue
        seen.add(law_id)
        ids.append(law_id)

    return ids


async def main() -> None:
    args = _parse_args()

    if not settings.law_api_key:
        raise SystemExit("LAW_API_KEY is required. Set it in .env")

    if args.query:
        law_ids = await _collect_law_ids_by_query(args.query, args.top_k)
    else:
        law_ids = [str(x).strip() for x in (args.law_ids or []) if str(x).strip()]

    if not law_ids:
        print("No law_ids to collect")
        return

    print(f"Targets: {len(law_ids)} law(s)")
    for x in law_ids:
        print(f"- {x}")

    if args.dry_run:
        return

    # DB write
    from sqlalchemy import create_engine

    engine = create_engine(settings.postgres_url_sync)

    with Session(engine) as session:
        for i, law_id in enumerate(law_ids, start=1):
            print(f"[{i}/{len(law_ids)}] Fetching detail: {law_id}")
            detail = await fetch_law_detail(
                law_id=law_id,
                include_articles=not args.no_articles,
                include_full_text=False,
            )

            if not detail:
                print(f"  - skipped: not found or error")
                continue

            _upsert_law(session, detail)

            if not args.no_articles:
                articles = detail.get("articles") or []
                if isinstance(articles, list):
                    _replace_articles(session, law_id, articles)

            session.commit()
            print("  - saved")


if __name__ == "__main__":
    asyncio.run(main())
