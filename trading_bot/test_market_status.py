#!/usr/bin/env python3
"""
시장 상태 테스트 스크립트

market_time.py의 새로운 함수들을 테스트합니다.
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.utils.market_time import (
    get_us_market_time,
    get_market_phase,
    get_market_status,
    get_markets_status_summary,
    is_market_session_open,
)


def test_market_status():
    """시장 상태 테스트"""
    print("=" * 70)
    print("시장 상태 테스트")
    print("=" * 70)
    
    # 현재 시간
    us_time = get_us_market_time()
    print(f"\n📅 현재 시간 (미국 동부): {us_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"📅 현재 시간대: {get_market_phase(us_time)}")
    
    # 테스트할 시장들
    markets = ["NYSE", "NYSE_EXTENDED", "NYSE_DAY", "NASDAQ"]
    
    print("\n" + "=" * 70)
    print("개별 시장 상태")
    print("=" * 70)
    
    for market in markets:
        is_open = is_market_session_open(market)
        status = get_market_status(market)
        status_emoji = "✅" if is_open else "❌"
        print(f"{status_emoji} {market:20s} → {status:15s} (개장={is_open})")
    
    # 복합 시장 상태
    print("\n" + "=" * 70)
    print("복합 시장 상태 (NYSE_EXTENDED + NYSE_DAY)")
    print("=" * 70)
    
    test_markets = ["NYSE_EXTENDED", "NYSE_DAY"]
    summary = get_markets_status_summary(test_markets)
    
    print(f"\n📊 전체 요약:")
    print(f"  - 하나라도 개장: {summary['any_open']}")
    print(f"  - 모두 개장: {summary['all_open']}")
    print(f"  - 개장 중인 시장: {summary['open_markets']}")
    print(f"  - 폐장 중인 시장: {summary['closed_markets']}")
    
    print(f"\n📋 각 시장 상세:")
    for market, status in summary['markets'].items():
        emoji = "✅" if status in ('open', 'day_trading') else "❌"
        print(f"  {emoji} {market}: {status}")
    
    # 로그 형식 예시
    print("\n" + "=" * 70)
    print("로그 형식 예시 (impl_real.py에서 사용)")
    print("=" * 70)
    
    if summary['any_open']:
        open_detail = ', '.join([f"{m}={summary['markets'][m]}" for m in summary['open_markets']])
        closed_detail = ', '.join(summary['closed_markets']) if summary['closed_markets'] else '없음'
        print(f"\n✅ 실전투자: 시장 개장 중")
        print(f"   (개장중=[{open_detail}], 폐장=[{closed_detail}], 시간={us_time.strftime('%H:%M:%S')})")
    else:
        markets_detail = ', '.join([f"{m}={summary['markets'][m]}" for m in test_markets])
        print(f"\n❌ 실전투자: 설정된 모든 시장 폐장 중")
        print(f"   (시장상태=[{markets_detail}], 시간대={get_market_phase(us_time)}, 시간={us_time.strftime('%H:%M:%S')})")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    try:
        test_market_status()
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
