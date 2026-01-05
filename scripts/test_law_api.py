"""
Test script for law.go.kr API collector
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config.settings import settings
from src.pipeline.collectors.law_collector import search_law
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def main():
    """Test law collector"""

    if not settings.law_api_key:
        print("❌ LAW_API_KEY가 설정되어 있지 않습니다.")
        print("   - .env.example → .env로 복사한 후 LAW_API_KEY를 설정하세요.")
        print("   - 예: LAW_API_KEY=your_law_api_key")
        return
    
    print("=" * 80)
    print("Law Search Service - API Test")
    print("=" * 80)
    print()
    
    # Test 1: Single query
    print("Test 1: 단일 검색어 테스트")
    print("-" * 80)
    query1 = "개인정보 보호"
    print(f"검색어: {query1}")
    print()
    
    results1 = await search_law(query1, top_k=5)
    
    if results1:
        print(f"✅ {len(results1)}개의 법령을 찾았습니다:")
        for i, law in enumerate(results1, 1):
            print(f"\n{i}. {law['법령명한글']}")
            print(f"   - 소관부처: {law['소관부처명']}")
            print(f"   - 시행일자: {law['시행일자']}")
            print(f"   - 법령약칭명: {law['법령약칭명']}")
            print(f"   - 상세링크: {law['법령상세링크']}")
    else:
        print("❌ 검색 결과가 없습니다.")
    
    print()
    print("=" * 80)
    print()
    
    # Test 2: Multiple queries
    print("Test 2: 복수 검색어 테스트")
    print("-" * 80)
    query2 = "개인정보 보호법, 저작권법, 근로기준법"
    print(f"검색어: {query2}")
    print()
    
    results2 = await search_law(query2, top_k=10)
    
    if results2:
        print(f"✅ {len(results2)}개의 법령을 찾았습니다:")
        for i, law in enumerate(results2, 1):
            print(f"\n{i}. [{law['검색어']}] {law['법령명한글']}")
            print(f"   - 소관부처: {law['소관부처명']}")
            print(f"   - 시행일자: {law['시행일자']}")
    else:
        print("❌ 검색 결과가 없습니다.")
    
    print()
    print("=" * 80)
    print()
    
    # Test 3: Edge case - empty query
    print("Test 3: 빈 검색어 테스트")
    print("-" * 80)
    query3 = ""
    print(f"검색어: '{query3}'")
    print()
    
    results3 = await search_law(query3)
    print(f"결과: {len(results3)}개 (예상: 0개)")
    
    print()
    print("=" * 80)
    print("테스트 완료!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
