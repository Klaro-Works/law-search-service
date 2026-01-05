"""
Law.go.kr API collector - 제공하신 코드 기반
"""
import asyncio
from typing import Any, List, Optional
from urllib.parse import quote, urljoin

import httpx
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


# 한글 초성 변환 (기존 코드)
HANGUL_JAMO = [
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ",
    "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
]

INITIAL_GANA_MAP = [
    "ga", "kka", "na", "da", "tta", "ra", "ma", "ba", "ppa",
    "sa", "ssa", "a", "ja", "jja", "cha", "ka", "ta", "pa", "ha",
]


def get_gana_value(query: str) -> Optional[str]:
    """
    검색어의 첫 글자 초성을 가나다 코드로 변환
    """
    if not isinstance(query, str):
        return None

    trimmed = query.strip()
    if not trimmed:
        return None

    first_char = trimmed[0]
    code = ord(first_char)

    # 한글 음절 (가 ~ 힣)
    if 0xAC00 <= code <= 0xD7A3:
        initial_index = (code - 0xAC00) // 588
        return INITIAL_GANA_MAP[initial_index] if initial_index < len(INITIAL_GANA_MAP) else None

    # 한글 자모 (ㄱ ~ ㅎ)
    if first_char in HANGUL_JAMO:
        jamo_index = HANGUL_JAMO.index(first_char)
        return INITIAL_GANA_MAP[jamo_index] if jamo_index < len(INITIAL_GANA_MAP) else None

    return None


def to_query_list(query: str) -> List[str]:
    """
    쉼표로 구분된 검색어를 리스트로 변환
    """
    if not isinstance(query, str):
        return []

    return [part.strip() for part in query.split(",") if part.strip()]


async def fetch_law_for_query(
    query: str,
    query_display: int = 10
) -> List[dict]:
    """
    law.go.kr API를 호출하여 법령 검색
    
    Args:
        query: 검색어
        query_display: 결과 개수
    
    Returns:
        법령 정보 리스트
    """
    base_url = "https://www.law.go.kr"  # Use original working URL
    search_url = f"{base_url}/DRF/lawSearch.do?target=eflaw"

    params = {
        "OC": settings.law_api_key,
        "type": "JSON",
        "nw": "3",
        "display": query_display,
        "query": query,
    }

    # 가나다 초성 추가
    gana = get_gana_value(query)
    if gana:
        params["gana"] = gana

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(search_url, params=params)
            response.raise_for_status()
            
            # Debug: print response text
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response text: {response.text[:500]}")  # First 500 chars
            
            try:
                data = response.json()
            except Exception as json_err:
                logger.error(f"JSON parsing error for query '{query}': {json_err}")
                logger.error(f"Response text: {response.text}")
                return []

        # 에러 페이지 체크
        if isinstance(data, str):
            logger.error(f"API returned error page for query: {query}")
            return []

        # 결과 파싱
        raw_law_list = data.get("LawSearch", {}).get("law", [])
        
        # 단일 결과인 경우 리스트로 변환
        if isinstance(raw_law_list, dict):
            raw_law_list = [raw_law_list]
        elif not isinstance(raw_law_list, list):
            raw_law_list = []

        # 결과 정제
        refined_law_list = []
        for law in raw_law_list:
            if not law or not isinstance(law, dict):
                continue
            
            # 빈 객체 필터링
            if not any(law.values()):
                continue

            refined_law = {
                "법령명한글": law.get("법령명한글", ""),
                "소관부처명": law.get("소관부처명", ""),
                "시행일자": law.get("시행일자", ""),
                "공포일자": law.get("공포일자", ""),
                "법령약칭명": law.get("법령약칭명", ""),
                "법령상세링크": _build_detail_link(base_url, law),
                "법령일련번호": law.get("법령일련번호", ""),
                "법령ID": law.get("법령ID", ""),
                "현행연혁코드": law.get("현행연혁코드", ""),
            }
            refined_law_list.append(refined_law)

        logger.info(f"Fetched {len(refined_law_list)} laws for query: {query}")
        return refined_law_list

    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching laws for query '{query}': {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching laws for query '{query}': {e}")
        return []


def _build_detail_link(base_url: str, law: dict) -> str:
    """
    법령 상세 링크 생성
    """
    law_name = law.get("법령약칭명") or law.get("법령명한글", "")
    if not law_name:
        return ""
    
    # law.go.kr detail pages accept encoded law name path segments.
    return f"{base_url}/법령/{quote(str(law_name))}"


def _ensure_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _extract_law_service_root(data: Any) -> dict:
    """
    lawService.do 응답은 target마다 구조가 다를 수 있어, 가능한 루트 dict를 최대한 안전하게 추출합니다.
    """
    if not isinstance(data, dict):
        return {}

    # Some responses may wrap the payload.
    for key in ("LawService", "lawService", "법령", "law"):
        candidate = data.get(key)
        if isinstance(candidate, dict):
            return candidate

    # Many targets return the payload as a flat dict already.
    return data


def _flatten_article_content(article: dict) -> str:
    """
    조문(조/항/호 등) 계층 구조를 사람이 읽을 수 있는 텍스트로 평탄화합니다.
    """
    if not isinstance(article, dict):
        return ""

    parts: list[str] = []

    # Base article text
    base_text = (
        article.get("조문내용")
        or article.get("조내용")
        or article.get("내용")
        or article.get("조문내용_한글")
    )
    if isinstance(base_text, str) and base_text.strip():
        parts.append(base_text.strip())

    # Paragraph-level items (항)
    para_list = _ensure_list(article.get("항") or article.get("항목") or article.get("항목목록"))
    for para in para_list:
        if not isinstance(para, dict):
            continue
        para_no = para.get("항번호") or para.get("항") or ""
        para_text = para.get("항내용") or para.get("내용") or ""
        line = " ".join([str(para_no).strip(), str(para_text).strip()]).strip()
        if line:
            parts.append(line)

        # Sub-items (호)
        ho_list = _ensure_list(para.get("호") or para.get("호목록"))
        for ho in ho_list:
            if not isinstance(ho, dict):
                continue
            ho_no = ho.get("호번호") or ho.get("호") or ""
            ho_text = ho.get("호내용") or ho.get("내용") or ""
            ho_line = " ".join([str(ho_no).strip(), str(ho_text).strip()]).strip()
            if ho_line:
                parts.append(ho_line)

    return "\n".join([p for p in parts if p])


def _normalize_law_articles(root: dict, law_id: str) -> list[dict]:
    """
    lawService.do 응답의 조문 목록을 API용 표준 형태로 변환합니다.
    """
    articles_raw = (
        root.get("조문")
        or root.get("조문목록")
        or root.get("조문리스트")
        or root.get("조문내용")
        or []
    )

    # Sometimes 조문목록 아래에 조문 키가 한 번 더 존재할 수 있음
    if isinstance(articles_raw, dict):
        if "조문" in articles_raw:
            articles_raw = articles_raw.get("조문")

    normalized: list[dict] = []
    for idx, art in enumerate(_ensure_list(articles_raw), start=1):
        if not isinstance(art, dict):
            continue

        article_no = (
            art.get("조번호")
            or art.get("조문번호")
            or art.get("조문번호_한글")
            or art.get("조문")
            or ""
        )
        title = art.get("조제목") or art.get("조문제목") or art.get("제목") or ""
        content = _flatten_article_content(art)

        # Skip empty entries
        if not (str(article_no).strip() or str(title).strip() or str(content).strip()):
            continue

        normalized.append(
            {
                "article_no": str(article_no).strip(),
                "title": str(title).strip() or None,
                "content": str(content).strip(),
                # Vector ids do not exist until we build Qdrant pipeline.
                "vector_id": f"art_{law_id}_{idx:03d}",
            }
        )

    return normalized


async def search_law(query: str, top_k: int = 20) -> List[dict]:
    """
    법령 검색 API (복수 검색어 지원)
    
    Args:
        query: 검색어 (쉼표로 구분 가능)
        top_k: 전체 반환할 최대 개수
    
    Returns:
        검색어별 법령 정보 리스트
    """
    query_list = to_query_list(query)

    if not query_list:
        logger.warning("Empty query provided")
        return []

    # 검색어당 할당할 개수
    per_query = max(1, top_k // len(query_list))
    
    # 병렬로 모든 검색어 처리
    tasks = [fetch_law_for_query(q, per_query) for q in query_list]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # 결과 취합
    aggregated = []
    for query_str, result in zip(query_list, results_list):
        if isinstance(result, Exception):
            logger.error(f"Error fetching laws for query '{query_str}': {result}")
            continue
        
        for law in result:
            law_with_query = {"검색어": query_str, **law}
            aggregated.append(law_with_query)

    logger.info(f"Total {len(aggregated)} laws found for queries: {query_list}")
    return aggregated[:top_k]  # top_k로 제한


# 동기 버전 (테스트용)
def search_law_sync(query: str, top_k: int = 20) -> List[dict]:
    """동기 버전 - 테스트용"""
    return asyncio.run(search_law(query, top_k))


async def fetch_law_detail(
    law_id: str,
    include_articles: bool = True,
    include_full_text: bool = False,
) -> dict:
    """
    law.go.kr API(lawService.do)를 호출하여 특정 법령의 상세(조문 포함)를 조회합니다.

    Note:
      - 현재 서비스는 DB/Qdrant 이전 단계이므로, 원격 API 응답을 그대로 가공해 반환합니다.
      - include_full_text는 전문 필드가 없으면 조문을 합쳐 생성합니다.
    """
    if not isinstance(law_id, str) or not law_id.strip():
        return {}

    base_url = "https://www.law.go.kr"
    service_url = f"{base_url}/DRF/lawService.do"

    params = {
        "OC": settings.law_api_key,
        "target": "law",
        "ID": law_id.strip(),
        "type": "JSON",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(service_url, params=params)
            response.raise_for_status()

            logger.debug(f"Law detail response status: {response.status_code}")
            logger.debug(f"Law detail response text: {response.text[:500]}")

            try:
                data = response.json()
            except Exception as json_err:
                logger.error(f"JSON parsing error for law_id '{law_id}': {json_err}")
                logger.error(f"Response text: {response.text}")
                return {}

        if isinstance(data, str):
            logger.error(f"API returned error page for law_id: {law_id}")
            return {}

        root = _extract_law_service_root(data)

        law_name = root.get("법령명한글") or root.get("법령명") or root.get("법령명_한글") or ""
        law_abbr = root.get("법령약칭명") or root.get("약칭") or ""
        department = root.get("소관부처명") or root.get("부처명") or ""
        law_type = root.get("법종구분") or root.get("법종구분명") or root.get("법종구분_한글") or ""
        status = root.get("현행여부") or root.get("현행연혁코드") or root.get("현행연혁") or ""
        enforce_date = root.get("시행일자") or ""
        promulgate_date = root.get("공포일자") or ""
        law_serial = root.get("법령일련번호") or root.get("MST") or root.get("법령마스터번호") or ""

        detail_link = ""
        if law_name:
            detail_link = f"{base_url}/법령/{quote(str(law_name))}"

        articles: list[dict] = []
        if include_articles:
            articles = _normalize_law_articles(root, law_id.strip())

        full_text: Optional[str] = None
        if include_full_text:
            # Prefer a dedicated "전문" field if it exists; otherwise compose from articles.
            full_text_candidate = root.get("전문") or root.get("전문내용") or root.get("법령전문")
            if isinstance(full_text_candidate, str) and full_text_candidate.strip():
                full_text = full_text_candidate.strip()
            elif articles:
                chunks = []
                for art in articles:
                    header = " ".join([art.get("article_no") or "", art.get("title") or ""]).strip()
                    body = art.get("content") or ""
                    chunks.append("\n".join([p for p in (header, body) if p]).strip())
                full_text = "\n\n".join([c for c in chunks if c]).strip() or None

        normalized = {
            "law_id": law_id.strip(),
            "law_serial": str(law_serial).strip() or None,
            "law_name_kr": str(law_name).strip() or law_id.strip(),
            "law_abbr": str(law_abbr).strip() or None,
            "department": str(department).strip() or None,
            "law_type": str(law_type).strip() or None,
            "status": str(status).strip() or None,
            "enforce_date": str(enforce_date).strip() or None,
            "promulgate_date": str(promulgate_date).strip() or None,
            "detail_link": detail_link or None,
            "full_text": full_text,
            "articles": articles if include_articles else None,
            "article_count": len(articles) if include_articles else 0,
        }

        logger.info(f"Fetched law detail for law_id={law_id} articles={len(articles)}")
        return normalized

    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching law detail for law_id '{law_id}': {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error fetching law detail for law_id '{law_id}': {e}")
        return {}
