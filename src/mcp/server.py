"""src.mcp.server

MCP (Model Context Protocol) server for Law Search Service.

Current implementation:
- stdio transport
- Tools:
  - search_law
  - get_law_detail
  - search_article

NOTE
- This repo snapshot does not yet implement DB/Qdrant based hybrid search.
  Tools currently proxy to law.go.kr DRF endpoints.
"""

from __future__ import annotations

import json
import time
from typing import Any

import anyio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.stdio import stdio_server

from src.config.settings import settings
from src.pipeline.collectors.law_collector import fetch_law_detail, search_law
from src.utils.logger import get_logger

logger = get_logger(__name__)


SERVER_NAME = "law-search-mcp"


server = Server(
    SERVER_NAME,
    version=settings.service_version,
    instructions=(
        "Korean law search tools backed by law.go.kr. "
        "Use search_law to find relevant laws, then get_law_detail or search_article for article-level context."
    ),
)


@server.list_tools()
async def list_tools(_: types.ListToolsRequest | None) -> types.ListToolsResult:
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name="search_law",
                description=(
                    "법령 검색 도구. 법령명/키워드로 관련 법령 목록을 조회합니다. "
                    "현재 구현은 law.go.kr API 기반 lexical 검색입니다."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "검색어. 여러 법령을 검색하는 경우 쉼표(,)로 구분하세요.",
                        },
                        "search_type": {
                            "type": "string",
                            "enum": ["lexical", "semantic", "hybrid"],
                            "default": "hybrid",
                        },
                        "top_k": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "default": 10,
                        },
                        "department": {"type": "string"},
                        "law_type": {
                            "type": "string",
                            "enum": ["법률", "대통령령", "총리령", "부령"],
                        },
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="get_law_detail",
                description="법령 ID로 법령의 상세 정보(조문 포함)를 조회합니다.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "law_id": {"type": "string", "description": "법령 ID"},
                        "include_articles": {"type": "boolean", "default": True},
                        "include_full_text": {"type": "boolean", "default": False},
                    },
                    "required": ["law_id"],
                },
            ),
            types.Tool(
                name="search_article",
                description="특정 법령 내에서 조문을 검색합니다 (현재 lexical).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "law_id": {"type": "string", "description": "법령 ID"},
                        "query": {"type": "string", "description": "조문 내 검색어"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                    },
                    "required": ["law_id", "query"],
                },
            ),
        ]
    )


def _text_and_structured(payload: dict[str, Any]):
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return ([types.TextContent(type="text", text=text)], payload)


@server.call_tool()
async def call_tool(name: str, arguments: dict | None):
    args = arguments or {}

    if not settings.law_api_key:
        raise RuntimeError("LAW_API_KEY is not configured")

    if name == "search_law":
        query = str(args.get("query") or "").strip()
        top_k = int(args.get("top_k") or 10)

        started = time.perf_counter()
        results = await search_law(query, top_k=top_k)
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        payload = {
            "results": results,
            "total_count": len(results),
            "search_time_ms": elapsed_ms,
            "note": "현재는 law.go.kr 기반 lexical 검색만 제공됩니다.",
        }
        return _text_and_structured(payload)

    if name == "get_law_detail":
        law_id = str(args.get("law_id") or "").strip()
        include_articles = bool(args.get("include_articles", True))
        include_full_text = bool(args.get("include_full_text", False))

        started = time.perf_counter()
        detail = await fetch_law_detail(
            law_id=law_id,
            include_articles=include_articles,
            include_full_text=include_full_text,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        if not detail:
            raise ValueError(f"Law not found: {law_id}")

        payload = {
            **detail,
            "search_time_ms": elapsed_ms,
        }
        return _text_and_structured(payload)

    if name == "search_article":
        law_id = str(args.get("law_id") or "").strip()
        query = str(args.get("query") or "").strip()
        top_k = int(args.get("top_k") or 5)

        started = time.perf_counter()
        detail = await fetch_law_detail(
            law_id=law_id,
            include_articles=True,
            include_full_text=False,
        )
        if not detail:
            raise ValueError(f"Law not found: {law_id}")

        law_name_kr = detail.get("law_name_kr")
        articles = detail.get("articles") or []

        q_lower = query.lower()
        results: list[dict[str, Any]] = []
        for art in articles:
            if not isinstance(art, dict):
                continue
            article_no = str(art.get("article_no") or "").strip()
            title = art.get("title")
            content = str(art.get("content") or "").strip()
            haystack = " ".join([article_no, title or "", content]).strip()

            hay_lower = haystack.lower()
            if not q_lower or q_lower not in hay_lower:
                continue

            idx = hay_lower.find(q_lower)
            start = max(0, idx - 60)
            end = min(len(haystack), idx + len(query) + 60)
            snippet = haystack[start:end]
            snippet = snippet.replace(haystack[idx : idx + len(query)], f"<em>{query}</em>")
            if start > 0:
                snippet = "..." + snippet
            if end < len(haystack):
                snippet = snippet + "..."

            results.append(
                {
                    "article_no": article_no or "(unknown)",
                    "title": title,
                    "content": content,
                    "score": 1.0,
                    "snippet": snippet,
                }
            )

        results = results[:top_k]
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        payload = {
            "law_id": law_id,
            "law_name_kr": law_name_kr,
            "results": results,
            "total_count": len(results),
            "search_time_ms": elapsed_ms,
            "note": "현재는 단순 substring 기반 lexical 조문 검색만 제공됩니다.",
        }
        return _text_and_structured(payload)

    raise ValueError(f"Unknown tool: {name}")


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(
                notification_options=NotificationOptions(
                    prompts_changed=False,
                    resources_changed=False,
                    tools_changed=False,
                ),
                experimental_capabilities={},
            ),
        )


def main() -> None:
    anyio.run(_run)


if __name__ == "__main__":
    main()
