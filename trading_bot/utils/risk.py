"""리스크 관리 유틸리티."""

from typing import Optional


def calculate_pnl_pct(current_price: float, avg_buy_price: float) -> Optional[float]:
    """현재가와 평균매수가로 손익률(%)을 계산합니다."""
    if avg_buy_price is None or avg_buy_price <= 0:
        return None
    return ((current_price - avg_buy_price) / avg_buy_price) * 100


def should_force_stop_loss(current_price: float, avg_buy_price: float, stop_loss_percent: float) -> bool:
    """고정 손절 조건 충족 여부를 반환합니다."""
    pnl_pct = calculate_pnl_pct(current_price=current_price, avg_buy_price=avg_buy_price)
    if pnl_pct is None:
        return False
    return pnl_pct <= -abs(float(stop_loss_percent))
