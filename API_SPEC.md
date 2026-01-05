# Law Search Service - API 명세서

## 📋 개요

Law Search Service의 REST API 명세서입니다. 모든 엔드포인트는 `/api/v1` prefix를 사용합니다.

**Base URL**: `https://api.klaro.dev/law-search` (예정)

---

## 🔐 인증

### Klaro Hub 내부 서비스
- 루트 API Gateway를 통한 gRPC 인증
- 테넌트 컨텍스트 자동 주입

### 외부 API (추후)
- API Key 방식: `X-API-Key: your_api_key`
- Rate Limiting 적용

---

## 📡 엔드포인트

### 1. 법령 검색

#### `POST /api/v1/law/search`

법령을 검색합니다. 키워드 검색, 의미 기반 검색, 하이브리드 검색을 지원합니다.

**Request Body**:
```json
{
  "query": "개인정보 보호",
  "search_type": "hybrid",
  "top_k": 20,
  "filters": {
    "department": ["행정안전부"],
    "law_type": ["법률"],
    "status": ["시행중"],
    "enforce_date_from": "20200101",
    "enforce_date_to": "20241231"
  },
  "include_articles": false,
  "rerank": false
}
```

**Parameters**:
| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `query` | string | ✅ | - | 검색어 |
| `search_type` | enum | ❌ | `"hybrid"` | `"lexical"` \| `"semantic"` \| `"hybrid"` |
| `top_k` | integer | ❌ | 20 | 반환할 결과 개수 (1-100) |
| `filters` | object | ❌ | `{}` | 필터 조건 |
| `filters.department` | string[] | ❌ | - | 소관부처명 필터 |
| `filters.law_type` | string[] | ❌ | - | 법령 유형 필터 |
| `filters.status` | string[] | ❌ | - | 시행 상태 필터 |
| `filters.enforce_date_from` | string | ❌ | - | 시행일자 시작 (YYYYMMDD) |
| `filters.enforce_date_to` | string | ❌ | - | 시행일자 종료 (YYYYMMDD) |
| `include_articles` | boolean | ❌ | `false` | 조문 포함 여부 |
| `rerank` | boolean | ❌ | `false` | 재순위화 사용 여부 (추후) |

**Response** (200 OK):
```json
{
  "results": [
    {
      "law_id": "001234",
      "law_name_kr": "개인정보 보호법",
      "law_abbr": "개인정보법",
      "department": "행정안전부",
      "law_type": "법률",
      "status": "시행중",
      "enforce_date": "20200805",
      "promulgate_date": "20110930",
      "score": 0.945,
      "snippet": "개인정보의 처리 및 보호에 관한 사항을 정함으로써...",
      "detail_link": "https://www.law.go.kr/법령/개인정보보호법",
      "matched_articles": null
    },
    {
      "law_id": "005678",
      "law_name_kr": "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
      "law_abbr": "정보통신망법",
      "department": "과학기술정보통신부",
      "law_type": "법률",
      "status": "시행중",
      "enforce_date": "20200610",
      "promulgate_date": "20010116",
      "score": 0.823,
      "snippet": "정보통신망의 이용을 촉진하고 정보통신서비스를...",
      "detail_link": "https://www.law.go.kr/법령/정보통신망이용촉진및정보보호등에관한법률",
      "matched_articles": null
    }
  ],
  "total_count": 12,
  "search_time_ms": 124.5,
  "search_metadata": {
    "search_type": "hybrid",
    "lexical_count": 8,
    "semantic_count": 15,
    "cache_hit": false
  }
}
```

**Error Responses**:
- `400 Bad Request`: 잘못된 요청 파라미터
  ```json
  {
    "error": "ValidationError",
    "message": "query는 필수 항목입니다.",
    "details": {
      "field": "query",
      "constraint": "required"
    }
  }
  ```
- `500 Internal Server Error`: 서버 오류

---

### 2. 법령 상세 조회

#### `GET /api/v1/law/{law_id}`

특정 법령의 상세 정보를 조회합니다.

**Path Parameters**:
| 필드 | 타입 | 설명 |
|------|------|------|
| `law_id` | string | 법령 ID |

**Query Parameters**:
| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `include_articles` | boolean | ❌ | `true` | 조문 포함 여부 |
| `include_full_text` | boolean | ❌ | `false` | 전문 포함 여부 |

**Request**:
```http
GET /api/v1/law/001234?include_articles=true&include_full_text=false
```

**Response** (200 OK):
```json
{
  "law_id": "001234",
  "law_serial": "12345678",
  "law_name_kr": "개인정보 보호법",
  "law_abbr": "개인정보법",
  "department": "행정안전부",
  "law_type": "법률",
  "status": "시행중",
  "enforce_date": "20200805",
  "promulgate_date": "20110930",
  "detail_link": "https://www.law.go.kr/법령/개인정보보호법",
  "full_text": null,
  "articles": [
    {
      "article_no": "제1조",
      "title": "목적",
      "content": "이 법은 개인정보의 처리 및 보호에 관한 사항을 정함으로써 개인의 자유와 권리를 보호하고, 나아가 개인의 존엄과 가치를 구현함을 목적으로 한다.",
      "vector_id": "art_001234_001"
    },
    {
      "article_no": "제2조",
      "title": "정의",
      "content": "이 법에서 사용하는 용어의 뜻은 다음과 같다.\n1. \"개인정보\"란 살아 있는 개인에 관한 정보로서...",
      "vector_id": "art_001234_002"
    }
  ],
  "article_count": 75,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-12-01T14:22:00Z"
}
```

**Error Responses**:
- `404 Not Found`: 법령을 찾을 수 없음
  ```json
  {
    "error": "NotFound",
    "message": "law_id '999999'에 해당하는 법령을 찾을 수 없습니다."
  }
  ```

---

### 3. 조문 검색

#### `POST /api/v1/law/{law_id}/articles/search`

특정 법령 내에서 조문을 검색합니다.

**Path Parameters**:
| 필드 | 타입 | 설명 |
|------|------|------|
| `law_id` | string | 법령 ID |

**Request Body**:
```json
{
  "query": "개인정보 수집",
  "search_type": "semantic",
  "top_k": 10
}
```

**Response** (200 OK):
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
  "total_count": 8,
  "search_time_ms": 78.3
}
```

---

### 4. 법령 목록 조회

#### `GET /api/v1/law`

법령 목록을 조회합니다. (페이지네이션 지원)

**Query Parameters**:
| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `page` | integer | ❌ | 1 | 페이지 번호 |
| `page_size` | integer | ❌ | 50 | 페이지 크기 (1-100) |
| `department` | string | ❌ | - | 소관부처 필터 |
| `law_type` | string | ❌ | - | 법령 유형 필터 |
| `status` | string | ❌ | `"시행중"` | 시행 상태 필터 |
| `sort_by` | string | ❌ | `"enforce_date"` | 정렬 기준 (`enforce_date` \| `law_name_kr` \| `updated_at`) |
| `sort_order` | string | ❌ | `"desc"` | 정렬 순서 (`asc` \| `desc`) |

**Request**:
```http
GET /api/v1/law?page=1&page_size=20&department=행정안전부&sort_by=enforce_date&sort_order=desc
```

**Response** (200 OK):
```json
{
  "items": [
    {
      "law_id": "001234",
      "law_name_kr": "개인정보 보호법",
      "law_abbr": "개인정보법",
      "department": "행정안전부",
      "law_type": "법률",
      "status": "시행중",
      "enforce_date": "20200805",
      "detail_link": "https://www.law.go.kr/법령/개인정보보호법"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 156,
    "total_pages": 8
  }
}
```

---

### 5. 법령 통계

#### `GET /api/v1/law/stats`

법령 데이터베이스의 통계 정보를 조회합니다.

**Response** (200 OK):
```json
{
  "total_laws": 12453,
  "total_articles": 345678,
  "by_department": {
    "행정안전부": 234,
    "과학기술정보통신부": 189,
    "법무부": 156
  },
  "by_law_type": {
    "법률": 1234,
    "대통령령": 2345,
    "총리령": 456,
    "부령": 8418
  },
  "by_status": {
    "시행중": 11234,
    "폐지": 1219
  },
  "last_updated": "2024-12-18T02:30:00Z"
}
```

---

### 6. 헬스 체크

#### `GET /api/v1/health`

서비스 상태를 확인합니다.

**Response** (200 OK):
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-12-18T09:00:00Z",
  "checks": {
    "database": "healthy",
    "qdrant": "healthy",
    "redis": "healthy",
    "minio": "healthy"
  }
}
```

---

## 🚨 에러 코드

| HTTP 코드 | 에러 타입 | 설명 |
|-----------|----------|------|
| 400 | `ValidationError` | 요청 파라미터 검증 실패 |
| 401 | `Unauthorized` | 인증 실패 |
| 403 | `Forbidden` | 권한 없음 |
| 404 | `NotFound` | 리소스를 찾을 수 없음 |
| 429 | `RateLimitExceeded` | Rate Limit 초과 |
| 500 | `InternalServerError` | 서버 내부 오류 |
| 503 | `ServiceUnavailable` | 서비스 일시 중단 (유지보수) |

**에러 응답 형식**:
```json
{
  "error": "ValidationError",
  "message": "검색어는 1자 이상이어야 합니다.",
  "details": {
    "field": "query",
    "constraint": "minLength",
    "value": ""
  },
  "timestamp": "2024-12-18T09:00:00Z",
  "request_id": "req_abc123xyz"
}
```

---

## 📊 Rate Limiting

| 사용자 유형 | 제한 |
|-------------|------|
| 내부 서비스 (Klaro Hub) | 무제한 |
| 외부 API (Free Tier) | 100 req/min, 10,000 req/day |
| 외부 API (Pro Tier) | 1,000 req/min, 100,000 req/day |

**Rate Limit 헤더**:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1642512000
```

---

## 🔄 버저닝

API 버전은 URL 경로에 포함됩니다 (`/api/v1`).

**마이그레이션 정책**:
- 새로운 필드 추가: 하위 호환성 유지
- 기존 필드 제거/변경: 새 버전 (`/api/v2`) 릴리스
- Deprecated API는 6개월간 유지 후 제거

---

## 📝 사용 예시

### Python
```python
import httpx
import asyncio

async def search_laws(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.klaro.dev/law-search/api/v1/law/search",
            json={
                "query": query,
                "search_type": "hybrid",
                "top_k": 10
            },
            headers={
                "Content-Type": "application/json"
            }
        )
        return response.json()

# 실행
result = asyncio.run(search_laws("개인정보 보호"))
print(result["results"][0]["law_name_kr"])
```

### JavaScript (Node.js)
```javascript
const axios = require('axios');

async function searchLaws(query) {
  const response = await axios.post(
    'https://api.klaro.dev/law-search/api/v1/law/search',
    {
      query: query,
      search_type: 'hybrid',
      top_k: 10
    }
  );
  return response.data;
}

searchLaws('개인정보 보호').then(result => {
  console.log(result.results[0].law_name_kr);
});
```

### cURL
```bash
curl -X POST "https://api.klaro.dev/law-search/api/v1/law/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "개인정보 보호",
    "search_type": "hybrid",
    "top_k": 10
  }'
```

---

## 🔒 보안 고려사항

1. **HTTPS 필수**: 모든 요청은 HTTPS를 통해서만 허용
2. **API Key 보호**: API Key는 환경 변수로 관리, 코드에 하드코딩 금지
3. **Input Validation**: 모든 입력값은 서버에서 재검증
4. **SQL Injection 방지**: 파라미터화된 쿼리 사용
5. **Rate Limiting**: 과도한 요청 차단

---

## 📚 추가 리소스

- [MCP 도구 명세](./mcp_tools_spec.md)
- [데이터 스키마](./database_schema.md)
- [배포 가이드](./deployment_guide.md)
