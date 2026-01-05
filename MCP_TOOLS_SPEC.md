# Law Search Service - MCP Tools 명세서

## 📋 개요

Law Search Service의 MCP (Model Context Protocol) 도구 명세서입니다. LLM Agent가 법령 검색 기능을 활용할 수 있도록 제공되는 도구들을 정의합니다.

**MCP Server 정보**:
- **서버 이름**: `law-search-mcp`
- **버전**: `1.0.0`
- **프로토콜**: MCP 1.0
- **전송**: stdio, SSE

---

## 🛠️ 제공 도구

### 1. search_law

법령을 검색하여 관련 법령 목록을 반환합니다.

#### Tool Definition

```json
{
  "name": "search_law",
  "description": "법령 검색 도구. 법령명, 키워드, 법률 용어로 관련 법령 목록을 조회합니다. 법령명 기준으로 검색하므로 검색어는 법령명에 포함될 가능성이 높은 키워드를 사용하세요.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "검색어. 법령명, 키워드, 법률 용어 등. 여러 법령을 검색하는 경우 쉼표(,)로 구분하세요. 예: '개인정보 보호법, 저작권법'"
      },
      "search_type": {
        "type": "string",
        "enum": ["lexical", "semantic", "hybrid"],
        "default": "hybrid",
        "description": "검색 방식. lexical: 키워드 일치, semantic: 의미 기반, hybrid: 혼합 (권장)"
      },
      "top_k": {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "default": 10,
        "description": "반환할 법령 개수 (1-50)"
      },
      "department": {
        "type": "string",
        "description": "소관부처명으로 필터링 (선택사항). 예: '행정안전부'"
      },
      "law_type": {
        "type": "string",
        "enum": ["법률", "대통령령", "총리령", "부령"],
        "description": "법령 유형으로 필터링 (선택사항)"
      }
    },
    "required": ["query"]
  }
}
```

#### 사용 시점

다음과 같은 상황에서 이 도구를 호출해야 합니다:

1. 사용자가 법령, 법률, 규정, 제도 등 법적 근거를 요구하는 경우
   - 예: "개인정보 보호 관련 법은 무엇인가요?"
   
2. RAG로 검색된 문서에서 특정 법령명이 언급되었으나 상세 정보가 부족한 경우
   - 예: 문서에 "개인정보 보호법에 따라..."라는 내용이 있지만 법령 전문이 필요한 경우

3. 정책, 사업, 지원제도 등의 법적 근거를 확인해야 하는 경우
   - 예: "청년 지원 정책의 법적 근거는?"

4. 사용자가 명시적으로 법령 검색을 요청하는 경우
   - 예: "저작권법 찾아줘"

#### Request Example

```json
{
  "query": "개인정보 보호",
  "search_type": "hybrid",
  "top_k": 5
}
```

#### Response Example

```json
{
  "results": [
    {
      "검색어": "개인정보 보호",
      "법령명한글": "개인정보 보호법",
      "소관부처명": "행정안전부",
      "시행일자": "20200805",
      "공포일자": "20110930",
      "법령약칭명": "개인정보법",
      "법령상세링크": "https://www.law.go.kr/법령/개인정보보호법",
      "법령일련번호": "12345678",
      "법령ID": "001234",
      "현행연혁코드": "시행",
      "score": 0.945
    },
    {
      "검색어": "개인정보 보호",
      "법령명한글": "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
      "소관부처명": "과학기술정보통신부",
      "시행일자": "20200610",
      "공포일자": "20010116",
      "법령약칭명": "정보통신망법",
      "법령상세링크": "https://www.law.go.kr/법령/정보통신망이용촉진및정보보호등에관한법률",
      "법령일련번호": "23456789",
      "법령ID": "005678",
      "현행연혁코드": "시행",
      "score": 0.823
    }
  ],
  "total_count": 12,
  "search_time_ms": 124.5
}
```

#### Agent 활용 예시

```python
# LLM Agent의 사고 과정
user_query = "개인정보 처리 시 주의사항은?"

# Agent: 개인정보 관련 법령을 검색해야겠다
result = await agent.call_tool(
    "search_law",
    {
        "query": "개인정보 보호",
        "search_type": "hybrid",
        "top_k": 3
    }
)

# Agent: 결과를 바탕으로 답변 생성
response = f"""
개인정보 처리 시 주의사항은 다음 법령에 근거합니다:

1. **{result['results'][0]['법령명한글']}** ({result['results'][0]['소관부처명']})
   - 시행일: {result['results'][0]['시행일자']}
   - 상세: {result['results'][0]['법령상세링크']}

주요 내용:
- 개인정보 수집 시 동의 필요
- 목적 외 사용 금지
- 안전성 확보 조치 의무
...
"""
```

---

### 2. get_law_detail

특정 법령의 상세 정보(조문 포함)를 조회합니다.

#### Tool Definition

```json
{
  "name": "get_law_detail",
  "description": "법령 ID로 법령의 상세 정보를 조회합니다. 조문 전체 또는 전문(全文)을 확인할 수 있습니다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "law_id": {
        "type": "string",
        "description": "법령 ID (search_law 도구의 결과에서 얻을 수 있음)"
      },
      "include_articles": {
        "type": "boolean",
        "default": true,
        "description": "조문 목록을 포함할지 여부"
      },
      "include_full_text": {
        "type": "boolean",
        "default": false,
        "description": "법령 전문을 포함할지 여부 (매우 긴 텍스트)"
      }
    },
    "required": ["law_id"]
  }
}
```

#### 사용 시점

1. `search_law`로 법령을 찾은 후, 특정 법령의 조문을 확인해야 할 때
2. 사용자가 "제N조의 내용은?"과 같이 구체적인 조문을 요구할 때
3. 법령 전문(全文)이 필요한 경우

#### Request Example

```json
{
  "law_id": "001234",
  "include_articles": true,
  "include_full_text": false
}
```

#### Response Example

```json
{
  "law_id": "001234",
  "law_name_kr": "개인정보 보호법",
  "law_abbr": "개인정보법",
  "department": "행정안전부",
  "enforce_date": "20200805",
  "articles": [
    {
      "article_no": "제1조",
      "title": "목적",
      "content": "이 법은 개인정보의 처리 및 보호에 관한 사항을 정함으로써 개인의 자유와 권리를 보호하고, 나아가 개인의 존엄과 가치를 구현함을 목적으로 한다."
    },
    {
      "article_no": "제2조",
      "title": "정의",
      "content": "이 법에서 사용하는 용어의 뜻은 다음과 같다.\n1. \"개인정보\"란 살아 있는 개인에 관한 정보로서..."
    }
  ],
  "article_count": 75
}
```

#### Agent 활용 예시

```python
# 1단계: 법령 검색
search_result = await agent.call_tool("search_law", {"query": "개인정보 보호법"})
law_id = search_result['results'][0]['법령ID']

# 2단계: 상세 조회
detail = await agent.call_tool("get_law_detail", {
    "law_id": law_id,
    "include_articles": True
})

# 3단계: 응답 생성
response = f"""
{detail['law_name_kr']}의 주요 조문은 다음과 같습니다:

{detail['articles'][0]['article_no']} ({detail['articles'][0]['title']})
{detail['articles'][0]['content']}
"""
```

---

### 3. search_article

특정 법령 내에서 조문을 검색합니다.

#### Tool Definition

```json
{
  "name": "search_article",
  "description": "특정 법령 내에서 키워드로 관련 조문을 검색합니다. 의미 기반 검색을 통해 관련성 높은 조문을 찾을 수 있습니다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "law_id": {
        "type": "string",
        "description": "법령 ID (search_law 결과에서 얻음)"
      },
      "query": {
        "type": "string",
        "description": "조문 내 검색어. 예: '개인정보 수집', '동의'"
      },
      "top_k": {
        "type": "integer",
        "minimum": 1,
        "maximum": 20,
        "default": 5,
        "description": "반환할 조문 개수"
      }
    },
    "required": ["law_id", "query"]
  }
}
```

#### 사용 시점

1. 특정 법령 내에서 특정 주제의 조문을 찾아야 할 때
   - 예: "개인정보 보호법에서 '수집'에 관한 조항은?"
2. 법령이 길어서 전체를 읽기 어려울 때
3. 의미 기반 검색으로 관련 조문을 빠르게 찾고 싶을 때

#### Request Example

```json
{
  "law_id": "001234",
  "query": "개인정보 수집",
  "top_k": 3
}
```

#### Response Example

```json
{
  "law_id": "001234",
  "law_name_kr": "개인정보 보호법",
  "results": [
    {
      "article_no": "제15조",
      "title": "개인정보의 수집·이용",
      "content": "개인정보처리자는 다음 각 호의 어느 하나에 해당하는 경우에는 개인정보를 수집할 수 있으며...",
      "score": 0.912,
      "snippet": "개인정보를 <em>수집</em>할 수 있으며..."
    },
    {
      "article_no": "제16조",
      "title": "개인정보의 수집 제한",
      "content": "개인정보처리자는 제15조제1항 각 호의 어느 하나에 해당하여 개인정보를 수집하는 경우...",
      "score": 0.887,
      "snippet": "<em>개인정보를 수집</em>하는 경우..."
    }
  ],
  "total_count": 8
}
```

#### Agent 활용 예시

```python
# 사용자: "개인정보 보호법에서 '수집'에 관한 조항 알려줘"

# 1단계: 법령 검색
search_result = await agent.call_tool("search_law", {"query": "개인정보 보호법"})
law_id = search_result['results'][0]['법령ID']

# 2단계: 조문 검색
article_result = await agent.call_tool("search_article", {
    "law_id": law_id,
    "query": "개인정보 수집"
})

# 3단계: 응답 생성
response = f"""
개인정보 보호법에서 '개인정보 수집'과 관련된 조문은 다음과 같습니다:

**{article_result['results'][0]['article_no']}** ({article_result['results'][0]['title']})
{article_result['results'][0]['content']}

**{article_result['results'][1]['article_no']}** ({article_result['results'][1]['title']})
{article_result['results'][1]['content']}
"""
```

---

## 🔄 워크플로우 예시

### 시나리오 1: 일반적인 법령 질문

**사용자**: "개인정보를 처리할 때 지켜야 할 법이 뭐야?"

```python
# Agent 실행 흐름
1. search_law(query="개인정보 보호")
   → "개인정보 보호법" 발견

2. get_law_detail(law_id="001234", include_articles=True)
   → 주요 조문 확인

3. 답변 생성
```

---

### 시나리오 2: 구체적인 조문 질문

**사용자**: "개인정보 보호법에서 '동의'에 관한 조항은?"

```python
# Agent 실행 흐름
1. search_law(query="개인정보 보호법")
   → law_id 획득

2. search_article(law_id="001234", query="동의")
   → 관련 조문 리스트 획득

3. 답변 생성 (조문 인용)
```

---

### 시나리오 3: 복잡한 법률 비교

**사용자**: "개인정보 보호법과 정보통신망법의 차이는?"

```python
# Agent 실행 흐름
1. search_law(query="개인정보 보호법, 정보통신망법")
   → 두 법령 모두 발견

2. get_law_detail(law_id="001234")  # 개인정보 보호법
3. get_law_detail(law_id="005678")  # 정보통신망법

4. 두 법령의 목적, 주요 조문을 비교하여 답변 생성
```

---

## 🧩 MCP Server 구현

### Python (mcp SDK)

```python
from mcp.server import Server
from mcp.types import Tool, TextContent
import json

app = Server("law-search-mcp")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_law",
            description="법령 검색 도구...",
            inputSchema={
                "type": "object",
                "properties": {...},
                "required": ["query"]
            }
        ),
        Tool(
            name="get_law_detail",
            description="법령 상세 조회...",
            inputSchema={...}
        ),
        Tool(
            name="search_article",
            description="조문 검색...",
            inputSchema={...}
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "search_law":
        # SearchService 호출
        results = await search_service.search(
            query=arguments["query"],
            search_type=arguments.get("search_type", "hybrid"),
            top_k=arguments.get("top_k", 10),
            filters={
                "department": arguments.get("department"),
                "law_type": arguments.get("law_type"),
            }
        )
        
        return [TextContent(
            type="text",
            text=json.dumps(results, ensure_ascii=False, indent=2)
        )]
    
    elif name == "get_law_detail":
        # LawService 호출
        detail = await law_service.get_detail(
            law_id=arguments["law_id"],
            include_articles=arguments.get("include_articles", True),
            include_full_text=arguments.get("include_full_text", False)
        )
        
        return [TextContent(
            type="text",
            text=json.dumps(detail, ensure_ascii=False, indent=2)
        )]
    
    elif name == "search_article":
        # ArticleSearchService 호출
        results = await article_search_service.search(
            law_id=arguments["law_id"],
            query=arguments["query"],
            top_k=arguments.get("top_k", 5)
        )
        
        return [TextContent(
            type="text",
            text=json.dumps(results, ensure_ascii=False, indent=2)
        )]
    
    else:
        raise ValueError(f"Unknown tool: {name}")
```

---

## 🔌 클라이언트 연동

### RAG Chatbot에서 MCP 도구 사용

```python
# RAG Chatbot의 config.json
{
  "chatbot_id": "legal_advisor",
  "mcp_tools": [
    {
      "type": "mcp_server",
      "server_name": "law-search-mcp",
      "transport": {
        "type": "stdio",
        "command": "python",
        "args": ["-m", "law_search_service.mcp.server"]
      },
      "tools": ["search_law", "get_law_detail", "search_article"]
    }
  ]
}
```

### Agno Agent에서 활용

```python
from agno import Agent
from agno.tools.mcp import MCPTool

# MCP 도구 연결
law_search_tool = MCPTool(
    server_name="law-search-mcp",
    tools=["search_law", "get_law_detail", "search_article"]
)

# Agent 생성
agent = Agent(
    name="Legal Advisor",
    model="gpt-4o",
    tools=[law_search_tool],
    instructions="""
    You are a legal advisor assistant.
    When users ask about Korean laws, use the law-search-mcp tools to find relevant laws and articles.
    Always cite the law name and article number when providing legal information.
    """
)

# 실행
response = await agent.arun("개인정보를 수집할 때 필요한 사항은?")
```

---

## 📊 성능 고려사항

### 캐싱
- 인기 검색어는 Redis에 캐싱 (TTL: 1시간)
- 법령 상세 정보는 캐싱 (TTL: 24시간, 법령 변경 시 무효화)

### Rate Limiting
- MCP 도구는 내부 서비스용이므로 Rate Limit 없음
- 외부 API 제공 시 적용

### 에러 처리
```json
{
  "error": "LawNotFound",
  "message": "law_id '999999'에 해당하는 법령을 찾을 수 없습니다.",
  "suggestions": [
    "search_law 도구로 먼저 법령을 검색해보세요."
  ]
}
```

---

## 🚀 향후 확장

### 추가 예정 도구

1. **search_case**: 판례 검색
2. **get_amendment_history**: 법령 개정 이력
3. **find_related_laws**: 관련 법령 찾기
4. **explain_article**: 조문 해설 (LLM 기반)

---

## 📚 참고 자료

- [MCP Protocol Specification](https://modelcontextprotocol.io/docs)
- [law.go.kr Open API 문서](https://www.law.go.kr/DRF/lawService.do?OC=yoo7477)
- [Klaro Hub Integration Hub](../integration-hub/README.md)
