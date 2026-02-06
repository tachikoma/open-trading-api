#!/usr/bin/env python3
"""
호가 단위(Tick Unit) 검증 테스트

국내 주식 가격대별 호가 단위 규칙 확인:
- 1,000원 미만: 1원
- 1,000 ~ 5,000원: 5원
- 5,000 ~ 10,000원: 10원
- 10,000 ~ 50,000원: 50원
- 50,000 ~ 100,000원: 100원
- 100,000 ~ 500,000원: 500원
- 500,000원 이상: 1,000원
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.broker.kis_broker import KISBroker


def test_tick_units():
    """호가 단위 테스트"""
    test_cases = [
        # (price, expected_tick_unit)
        (500, 1),           # 1,000원 미만: 1원
        (999, 1),           # 1,000원 미만: 1원
        (1_000, 5),         # 1,000 ~ 5,000원: 5원
        (2_500, 5),         # 1,000 ~ 5,000원: 5원
        (4_999, 5),         # 1,000 ~ 5,000원: 5원
        (5_000, 10),        # 5,000 ~ 10,000원: 10원
        (7_500, 10),        # 5,000 ~ 10,000원: 10원
        (9_999, 10),        # 5,000 ~ 10,000원: 10원
        (10_000, 50),       # 10,000 ~ 50,000원: 50원
        (25_000, 50),       # 10,000 ~ 50,000원: 50원
        (49_999, 50),       # 10,000 ~ 50,000원: 50원
        (50_000, 100),      # 50,000 ~ 100,000원: 100원
        (75_000, 100),      # 50,000 ~ 100,000원: 100원
        (99_999, 100),      # 50,000 ~ 100,000원: 100원
        (100_000, 500),     # 100,000 ~ 500,000원: 500원
        (218_250, 500),     # 100,000 ~ 500,000원: 500원 (셀트리온 사례)
        (250_000, 500),     # 100,000 ~ 500,000원: 500원
        (499_999, 500),     # 100,000 ~ 500,000원: 500원
        (500_000, 1_000),   # 500,000원 이상: 1,000원
        (750_000, 1_000),   # 500,000원 이상: 1,000원
    ]
    
    print("=" * 70)
    print("호가 단위(Tick Unit) 테스트")
    print("=" * 70)
    
    for price, expected_unit in test_cases:
        actual_unit = KISBroker._get_tick_unit(price)
        status = "✅" if actual_unit == expected_unit else "❌"
        print(f"{status} {price:>8,}원 → 호가 단위: {actual_unit:>5}원 (예상: {expected_unit:>5}원)")
        
        if actual_unit != expected_unit:
            print(f"   [오류] 호가 단위가 일치하지 않습니다!")


def test_price_validation():
    """가격 검증 테스트"""
    print("\n" + "=" * 70)
    print("가격 검증(Validation) 테스트")
    print("=" * 70)
    
    test_cases = [
        # (price, expected_valid, description)
        (218_250, False, "셀트리온: 218,250원은 500원 호가 단위 위반"),
        (218_000, True, "셀트리온: 218,000원은 500원 호가 단위 만족"),
        (218_500, True, "셀트리온: 218,500원은 500원 호가 단위 만족"),
        (10_050, True, "10,050원은 50원 호가 단위 만족 (10,050 ÷ 50 = 201)"),
        (10_075, False, "10,075원은 50원 호가 단위 위반"),
        (10_100, True, "10,100원은 50원 호가 단위 만족"),
        (0, True, "시장가(0)는 검증 대상 외"),
    ]
    
    for price, expected_valid, description in test_cases:
        is_valid, error_msg = KISBroker._validate_price_tick_unit(price)
        status = "✅" if is_valid == expected_valid else "❌"
        
        print(f"{status} {description}")
        if not is_valid:
            print(f"   → 오류: {error_msg}")


def test_price_adjustment():
    """가격 조정 테스트"""
    print("\n" + "=" * 70)
    print("가격 조정(Adjustment) 테스트")
    print("=" * 70)
    
    test_cases = [
        # (original_price, expected_adjusted)
        (218_250, 218_000),     # 500원 호가 단위로 내림
        (218_749, 218_500),     # 500원 호가 단위로 내림
        (10_075, 10_050),        # 50원 호가 단위로 내림
        (25_333, 25_300),        # 50원 호가 단위로 내림
        (100_250, 100_000),      # 100원 호가 단위로 내림
        (500_750, 500_000),      # 1,000원 호가 단위로 내림
        (500_000, 500_000),      # 이미 호가 단위에 맞음
        (0, 0),                  # 시장가
    ]
    
    for original, expected_adjusted in test_cases:
        adjusted = KISBroker._adjust_price_to_tick_unit(original)
        status = "✅" if adjusted == expected_adjusted else "❌"
        tick_unit = KISBroker._get_tick_unit(original)
        
        print(f"{status} {original:>8,}원 → {adjusted:>8,}원 (호가: {tick_unit}원)")
        
        if adjusted != expected_adjusted:
            print(f"   [오류] 예상 조정가: {expected_adjusted:,}원")


def test_celltrion_case():
    """셀트리온(068270) 실제 사례 테스트"""
    print("\n" + "=" * 70)
    print("셀트리온(068270) 사례 검증")
    print("=" * 70)
    
    symbol = "셀트리온(068270)"
    price = 218_250
    qty = 4
    
    print(f"종목: {symbol}")
    print(f"주문 시도 가격: {price:,}원")
    print(f"수량: {qty}주")
    print()
    
    # 호가 단위 확인
    tick_unit = KISBroker._get_tick_unit(price)
    print(f"해당 가격대 호가 단위: {tick_unit}원")
    
    # 검증
    is_valid, error_msg = KISBroker._validate_price_tick_unit(price)
    if not is_valid:
        print(f"❌ {error_msg}")
    else:
        print(f"✅ 유효한 가격")
    
    # 조정
    adjusted_price = KISBroker._adjust_price_to_tick_unit(price)
    print(f"\n조정된 가격 (내림): {adjusted_price:,}원")
    print(f"다음 가능한 가격 (올림): {adjusted_price + tick_unit:,}원")


if __name__ == "__main__":
    test_tick_units()
    test_price_validation()
    test_price_adjustment()
    test_celltrion_case()
    
    print("\n" + "=" * 70)
    print("✅ 모든 호가 단위 검증 테스트 완료!")
    print("=" * 70)
