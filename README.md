# Law Search Service

대한민국 국가법령정보센터(law.go.kr)의 법령 데이터를 자체 DB화하여 검색 가능하게 하는 **독립형 도메인 서비스**

## 📋 프로젝트 개요

- **목표**: law.go.kr 법령 데이터를 자체 DB화하여 검색 가능하도록 하고, 다양한 서비스에 법령 정보 제공
- **주요 기능**:
  - 법령 데이터 수집 및 자동 업데이트
  - Hybrid Search (Lexical + Semantic)
  - REST API 제공
  - MCP 인터페이스 (LLM Agent용)

## 🏗️ 아키텍처

- **Data Pipeline**: law.go.kr API → PostgreSQL + Qdrant
- **Search Engine**: Hybrid Search (PostgreSQL FTS + Qdrant Vector Search)
- **Interface**: REST API + MCP Server
- **Storage**: PostgreSQL (메타데이터), Qdrant (벡터), Redis (캐시)

상세 아키텍처는 [law-search-service-architecture.puml](./law-search-service-architecture.puml) 참고

## 🚀 빠른 시작

### 사전 요구사항

- Python 3.11+
- PostgreSQL 15+
- Redis (선택, 캐시용)
- Qdrant (선택, 벡터 검색용)

### 설치

```bash
# 저장소 클론
git clone https://github.com/Klaro-Works/law-search-service.git
cd law-search-service

# 가상 환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 필요한 값 입력
```

### 환경 설정

`.env` 파일에서 다음 항목을 설정하세요:

```bash
# OpenAI API (임베딩 생성용, 추후 구현)
OPENAI_API_KEY=your_openai_api_key

# Law.go.kr API
LAW_API_KEY=your_law_api_key

# Qdrant (선택, 벡터 검색용)
QDRANT_URL=https://qdrant.choistory.co.kr
QDRANT_API_KEY=your_qdrant_api_key

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=law_search
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Redis (선택, 캐시용)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Vector Store 설정 (file_system, qdrant, in_memory)
VECTOR_STORE_TYPE=file_system
VECTOR_STORE_FS_PATH=./vector_data

# Cache 설정 (redis, in_memory)
CACHE_TYPE=in_memory
```

### 데이터베이스 초기화

```bash
# PostgreSQL 테이블 생성 (DB는 미리 생성되어 있어야 합니다)
python3 scripts/init_db.py

# PostgreSQL FTS 인덱스 추가 (선택, 성능 최적화)
python3 scripts/add_fts_indexes.py

# law.go.kr API 연결 테스트 (선택)
python3 scripts/test_law_api.py

# 초기 법령 데이터 수집/적재 (예: 검색어 기반)
python3 scripts/collect_laws.py --query "개인정보 보호법, 저작권법" --top-k 20
```

### 서버 실행

```bash
# REST API 서버
python3 -m src.main

# MCP 서버 (stdio transport)
python3 -m src.mcp.server
```

## 📡 API 사용

### REST API

```bash
# 법령 검색
curl -X POST "http://localhost:8000/api/v1/law/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "개인정보 보호",
    "search_type": "hybrid",
    "top_k": 10
  }'

# 법령 상세 조회
curl "http://localhost:8000/api/v1/law/{law_id}?include_articles=true"

# 법령 목록 조회
curl "http://localhost:8000/api/v1/law?page=1&page_size=20"

# 통계 조회
curl "http://localhost:8000/api/v1/law/stats"
```

상세 API 명세는 [API_SPEC.md](./API_SPEC.md) 참고

### MCP Tools

MCP 클라이언트에서 다음 도구를 사용할 수 있습니다:

- `search_law`: 법령 검색
- `get_law_detail`: 법령 상세 조회
- `search_article`: 조문 검색

상세 MCP 명세는 [MCP_TOOLS_SPEC.md](./MCP_TOOLS_SPEC.md) 참고

## 🛠️ 개발

### 프로젝트 구조

```
law-search-service/
├── src/
│   ├── api/              # REST API (main.py)
│   ├── mcp/              # MCP Server
│   ├── pipeline/         # 데이터 수집/처리
│   │   └── collectors/   # law.go.kr API 연동
│   ├── core/             # 공통 서비스
│   │   ├── vector_store.py       # 벡터 저장소 추상화
│   │   ├── in_memory_store.py    # 인메모리 벡터 스토어
│   │   ├── file_system_store.py  # 파일시스템 벡터 스토어
│   │   ├── qdrant_store.py       # Qdrant 벡터 스토어
│   │   ├── cache.py              # 캐시 추상화
│   │   ├── redis_cache.py        # Redis 캐시
│   │   ├── in_memory_cache.py    # 인메모리 캐시
│   │   └── scheduler.py          # 자동 수집 스케줄러
│   ├── repository/       # 데이터 접근
│   │   ├── db.py                 # DB 세션 팩토리
│   │   └── fts_queries.py       # FTS 쿼리
│   ├── models/           # 데이터 모델
│   ├── config/           # 설정
│   └── utils/            # 유틸리티
├── scripts/              # 스크립트
│   ├── init_db.py               # DB 스키마 초기화
│   ├── add_fts_indexes.py       # FTS 인덱스 추가
│   ├── collect_laws.py          # 법령 수집
│   └── test_law_api.py          # API 테스트
├── tests/                # 테스트
├── AGENTS.md            # AI 코딩 에이전트 가이드라인
├── API_SPEC.md          # REST API 명세서
├── MCP_TOOLS_SPEC.md    # MCP 도구 명세서
└── requirements.txt
```

### 테스트

```bash
# 전체 테스트
pytest

# 특정 테스트
pytest tests/unit/test_law_collector.py

# 커버리지
pytest --cov=src tests/
```

### Linting/포맷팅

```bash
# 코드 포맷팅
black src/ tests/

# 린팅 체크
ruff check src/ tests/

# 타입 체크
mypy src/
```

## 🔄 작업 흐름

### 법령 검색

```
1. 사용자 → API 요청 (query)
2. PostgreSQL FTS 검색
   ↓ 실패 시
3. law.go.kr API 호출 (Fallback)
4. 결과를 PostgreSQL에 캐싱
5. 응답 반환
```

### 자동 수집

```
1. APScheduler가 설정된 크론 표현식에 따라 트리거
2. 인기 검색어로 법령 검색
3. 상세 정보 수집 (조문 포함)
4. DB에 적재
```

## 📚 문서

- [구현 계획서](./architecture_proposal.md)
- [API 명세서](./API_SPEC.md)
- [MCP Tools 명세서](./MCP_TOOLS_SPEC.md)
- [아키텍처 다이어그램](./law-search-service-architecture.puml)
- [AI 코딩 가이드라인](./AGENTS.md)

## 📄 라이선스

MIT License

## 👥 팀

Klaro Works - [GitHub](https://github.com/Klaro-Works)

## 🔗 관련 프로젝트

- [rag-agent](https://github.com/Klaro-Works/rag-agent)
- [data-process-service](https://github.com/Klaro-Works/data-process-service)

---

## TODO

### 현재 진행 중
- [ ] PostgreSQL FTS 인덱스 설치 및 테스트 (`textsearch_korean` 확장 필요)
- [ ] 파일시스템 벡터 스토어 테스트
- [ ] 캐시 시스템 통합

### 곧 진행 예정
- [ ] OpenAI 임베딩 서비스 구현
- [ ] 법령/조문 벡터 적재 파이프라인 구축
- [ ] Hybrid Search 통합 (FTS + Vector)
- [ ] 스케줄러 기능 완성 및 테스트
- [ ] MCP 서버에 벡터 검색 도구 추가

### 향후 계획
- [ ] Qdrant 실제 벡터 DB 연동
- [ ] Reranking 모델 (Cohere) 연동
- [ ] 법률별 주제 태깅 시스템
- [ ] 관련 법령 추천 기능
- [ ] 판례 데이터 통합
- [ ] AI 기반 조문 해설
