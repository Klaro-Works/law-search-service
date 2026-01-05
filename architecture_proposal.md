# 아키텍처 제언: 법령 검색 기능의 서비스화 전략

## 1. 📋 Executive Summary
사용자님의 고민인 **"법령 검색(Law MCP)을 별도 서비스(`law-pipeline` or `law-mcp`)로 분리하는 것"**에 대해 Klaro Hub 전체 아키텍처 관점에서 검토한 결과, **강력히 추천(Highly Recommended)** 합니다.

단순히 RAG 챗봇의 부가 기능이 아니라, **Klaro 플랫폼의 핵심 공통 서비스(Core Shared Service)** 로 격상시켜야 합니다. 이는 기술적 확장성뿐만 아니라 비즈니스 모델(BM) 다각화에도 유리합니다.

---

## 2. 🏗️ 아키텍처 분석

### AS-IS: Monolithic Plugin
- **구조**: RAG Chatbot 내부에 `search_law` 도구 함수로 존재 (외부 API 단순 호출).
- **문제점**:
  - **재사용 불가**: '민원 처리 봇', '계약서 검토 봇' 등 다른 서비스에서 법령 검색을 쓰려면 코드를 복사해야 함.
  - **데이터 자산화 어려움**: 외부 API(국가법령센터 등)에 전적으로 의존하며, 우리만의 고품질 법령 데이터베이스(임베딩된 판례 등)를 구축하기 어려움.

### TO-BE: Law MCP Service (Microservice)
- **구조**: 독립적인 `Law MCP Server` 구축 (Python/FastAPI or Go).
- **데이터 흐름**:
  1. **수집/가공 (ETL)**: 국가법령정보센터, 판례 등을 수집하여 전처리 및 임베딩 → 전용 Qdrant Collection 적재 (기존 `Document Pipeline` 패턴 활용).
  2. **서빙 (Serving)**: 표준 MCP 프로토콜 또는 REST API (`/v1/search/law`)로 검색 기능 제공.
- **연동**: RAG Chatbot은 MCP Client로서 이 서비스에 연결만 하면 됨.

---

## 3. 💼 비즈니스 모델(BM) 관점의 이점

### 1) 플랫폼 내부 효율성 (Cost Saver)
Klaro Hub에 있는 다양한 도메인 서비스들이 법령 정보를 공통으로 필요로 할 가능성이 높습니다.
- **RAG Chatbot**: "임대차 보호법 알려줘"
- **계약서 검토 서비스**: "이 조항이 근로기준법 위반인가?"
- **자동 민원 분류**: "이 민원은 도로교통법 소관인가?"

이 모든 서비스가 `Law MCP Service` 하나를 공유함으로써 중복 개발을 막고 데이터 품질을 일원화할 수 있습니다.

### 2) 새로운 수익원 창출 (Revenue Maker)
독립 서비스로 잘 만들어두면, 내부 사용을 넘어 **외부 판매**가 가능해집니다.
- **API 판매 (SaaS)**: `LawSearch API`를 기업들에게 제공 (예: SearchAPI.io의 법률 버전).
- **특화 봇 OEM**: 법무법인, 지자체 등에 '법령 검색 엔진'만 따로 떼어서 납품 가능.

---

## 4. 🚀 구현 로드맵 제안

### Phase 1: 독립형 MCP 서버 구축 (현재 단계)
- **목표**: RAG 챗봇에서 떼어내어 독립 실행 가능한 MCP 서버로 개발.
- **기술**: `mcp-python-sdk`, `FastAPI`, `Qdrant`.
- **검증**: RAG 챗봇 설정(`config`)에서 MCP 연결 정보만 입력하면 작동하도록 구현.

### Phase 2: 데이터 파이프라인 고도화
- **목표**: 단순 API 검색을 넘어, 판례/법령 데이터를 주기적으로 크롤링하여 자체 Vector DB 구축.
- **가치**: 외부 API보다 더 정확하고 빠른 'Semantic Search(의미 검색)' 제공 가능.

### Phase 3: 플랫폼 공통 서비스화
- **목표**: Klaro Hub의 `Shared Resources` 영역으로 이동 및 gRPC/REST 연동.
- **확장**: 다른 서비스(계약 검토 등)에 API 제공.

---

## 5. 💡 결론
**"웹 검색은 간단하게 두더라도, 법령 검색은 따로 빼자"**는 판단은 매우 정확합니다. 웹 검색은 Commodity(범용재)지만, **법령 데이터는 Asset(자산)** 이 될 수 있기 때문입니다.


---

## 6. 🧩 MCP 서비스 구성 전략: 도메인 중심의 접근

사용자님의 질문("MCP마다 서비스를 만들까, 하나에 다 넣을까, 도메인 서비스에 붙일까?")에 대한 분석 결과, **"Domain Service + MCP Interface"** 방식이 가장 적합합니다.

### 🔍 옵션 비교

| 방식 | 설명 | 장점 | 단점 | 추천 대상 |
| :--- | :--- | :--- | :--- | :--- |
| **Option A: 1 MCP = 1 Service** | 모든 툴(날씨, 검색, 계산기...)을 각각 별도 서버로 띄움 | 완벽한 격리 | 관리 포인트 폭증 (DevOps 지옥) | 사용하지 않음 |
| **Option B: Monolithic MCP** | 하나의 `Utility MCP Server`에 잡다한 기능(웹검색, 날씨 등)을 모두 모음 | 배포/관리 편함 | 도메인 경계가 모호해짐, 덩치가 커짐 | **Simple Tools** (웹 검색, 계산기, 단위변환) |
| **Option C: Domain + MCP (✅)** | **독립된 도메인 서비스(`Law Service`)가 MCP 프로토콜도 지원** | 도메인, DB 응집도가 높음. 재사용성 최상 | 초기 개발 공수 | **Core Service** (법령, 계약, 인사 등 핵심 비즈니스) |

### 💡 Klaro Hub 전략: Hybrid Approach

1.  **Generic MCP Server (Option B)**
    *   **역할**: 도메인/DB가 필요 없는 단순 유틸리티 모음.
    *   **포함**: Web Search, Calculator, Time, Weather.
    *   **위치**: `Integration Hub` 내부 또는 별도 경량 컨테이너.

2.  **Domain Service w/ MCP (Option C)**
    *   **역할**: Klaro Hub의 핵심 비즈니스 로직 및 데이터 보유.
    *   **포함**: **Law Service**, **Contract Service**.
    *   **구현**: `Law Service`는 REST API도 제공하고, 동시에 MCP Server로서도 동작하여 LLM이 직접 도구로 쓸 수 있게 함.
    *   **이점**: "Law 서비스를 만든다"는 관점이므로, 챗봇뿐만 아니라 일반 웹앱에서도 API로 쓸 수 있어 활용도가 극대화됨.

### 🚀 최종 제안
**"법령 검색은 `Law Pipeline Service`라는 정식 도메인 서비스로 만들고, 그 서비스가 MCP 인터페이스를 제공하도록 하십시오."**
(단순히 MCP를 위해 서비스를 만드는 게 아니라, 서비스를 만들고 MCP라는 문을 하나 더 여는 개념입니다.)

