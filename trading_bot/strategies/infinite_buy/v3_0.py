from .base import InfiniteBuyBase
import math
from typing import Any, Dict, List


class InfiniteBuyV3_0(InfiniteBuyBase):
    """InfiniteBuy v3.0 스켈레톤 구현 (한국어 설명).

    v3.0은 종목별 목표 퍼센트 맵핑이나 추가 파라미터를 지원할 수 있습니다.
    이 클래스는 베이스 클래스와 호환되는 인터페이스를 제공합니다.
    """

    def __init__(self, config: Dict[str, Any], broker: Any = None):
        super().__init__(config, broker)

    def compute_T(self, cum_buy_amt: float) -> float:
        # 기본 규칙: one_shot_amount로 나눈 값을 소수점 둘째 자리에서 올림
        one_shot = float(self.config.get("one_shot_amount", 1000.0))
        T = (cum_buy_amt) / one_shot if one_shot else 0.0
        return math.ceil(T * 100) / 100.0

    def compute_star_percent(self, T: float, symbol: str) -> float:
        # 예시: 구성(config)에서 종목별 base와 factor를 가져와 계산
        mapping = self.config.get("target_percent_map", {})
        factor_map = self.config.get("v3_factor_map", {})
        base = float(mapping.get(symbol, 10.0))
        factor = float(factor_map.get(symbol, 0.5))
        return max(0.0, base - factor * T)

    def decide_buy(self, date, quote) -> List[Dict[str, Any]]:
        # 간단한 스텁: v2.2와 유사하되 종목별 매개변수(map)를 허용
        total_amount = float(self.config.get("total_amount", 0.0))
        price = float(quote.get("price") if isinstance(quote, dict) and quote.get("price") is not None else 0.0)
        symbol = quote.get("symbol") if isinstance(quote, dict) else None
        if total_amount <= 0 or price <= 0:
            return []
        per_split = self.quota(total_amount)
        amount = self.ceil2(per_split)
        qty = amount / price
        return [{"type": "buy", "symbol": symbol, "price": price, "amount": amount, "quantity": qty}]

    def decide_sell(self, position, market_price) -> List[Dict[str, Any]]:
        # v3.0의 매도 규칙은 향후 상세 구현
        return []
