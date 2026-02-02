"""
수수료 및 세금 계산 유틸

함수:
- calculate_fees_and_taxes(price, qty, side, commission_rate=None, commission_min=None, trade_tax_rate=None)
  -> dict: {commission, tax, total_fees, gross_amount, net_amount}

설정은 `trading_bot.config.Config`의 값을 기본으로 사용합니다.
"""
from typing import Dict
from trading_bot.config import Config


def calculate_fees_and_taxes(price: int, qty: int, side: str = "buy",
                             commission_rate: float = None, commission_min: int = None,
                             trade_tax_rate: float = None) -> Dict:
    """주문 가격/수량 기준으로 수수료와 세금을 계산합니다.

    Args:
        price: 체결 단가(정수)
        qty: 체결 수량
        side: 'buy' 또는 'sell' (매도에만 거래세 적용)
        commission_rate: 수수료율(편도). 지정하지 않으면 `Config.COMMISSION_RATE` 사용
        commission_min: 최소수수료(원). 지정하지 않으면 `Config.COMMISSION_MIN` 사용
        trade_tax_rate: 거래세율(매도시). 지정하지 않으면 `Config.TRADE_TAX_RATE` 사용

    Returns:
        dict: {
            'commission': int,
            'tax': int,
            'total_fees': int,
            'gross_amount': int,  # price * qty
            'net_amount': int     # 매수: -현금흐름, 매도: +현금흐름
        }
    """
    if commission_rate is None:
        commission_rate = Config.COMMISSION_RATE
    if commission_min is None:
        commission_min = Config.COMMISSION_MIN
    if trade_tax_rate is None:
        trade_tax_rate = Config.TRADE_TAX_RATE

    gross = int(price) * int(qty)

    # 수수료는 보통 매수/매도 모두 적용
    commission = int(round(gross * float(commission_rate)))
    if commission < int(commission_min):
        commission = int(commission_min)

    # 거래세는 국내주식의 경우 매도에만 적용
    tax = 0
    if str(side).lower() == "sell":
        tax = int(round(gross * float(trade_tax_rate)))

    total_fees = commission + tax

    if str(side).lower() == "buy":
        net = - (gross + total_fees)
    else:
        net = gross - total_fees

    return {
        "commission": commission,
        "tax": tax,
        "total_fees": total_fees,
        "gross_amount": gross,
        "net_amount": net,
    }
