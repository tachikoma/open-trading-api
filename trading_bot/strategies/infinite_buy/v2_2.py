from .base import InfiniteBuyBase
import math
from typing import Any, Dict, List


class InfiniteBuyV2_2(InfiniteBuyBase):
    """InfiniteBuy 전략의 v2.2 구현.

    설명:
        - `compute_T(cum_buy_amt)`: 누적 매수금액을 `one_shot_amount`로 나누어 T를 계산하고
          소수점 둘째 자리에서 올림합니다.
        - `compute_star_percent(T, symbol)`: T에 기반한 목표 `star%` 계산 (간단한 예제 규칙 적용).
        - `decide_buy(date, quote)`: 매수 의도 리스트를 반환합니다. 각 의도에는 목표 매도 가격(25%: star%, 75%: +10%)이 포함됩니다.
    """

    def __init__(self, config: Dict[str, Any], broker: Any = None):
        super().__init__(config, broker)

    def compute_T(self, cum_buy_amt: float) -> float:
        # 누적 매수금액을 기준으로 T를 계산하고 소수점 둘째 자리에서 올림
        one_shot = float(self.config.get("one_shot_amount", 1000.0))
        T = (cum_buy_amt) / one_shot if one_shot else 0.0
        return math.ceil(T * 100) / 100.0

    def compute_star_percent(self, T: float, symbol: str) -> float:
        # 간단한 예시 규칙: 기본 10%에서 T/2만큼 차감, 최솟값 0
        return max(0.0, 10.0 - T / 2.0)

    def decide_buy(self, date, quote) -> List[Dict[str, Any]]:
        # v2.2 매수 의도 생성 로직:
        # - 설정값 `total_amount`(전체 투자금)을 기준으로 한 분할(per_split)을 계산하고,
        #   `ceil2` 규칙으로 주문 금액을 결정합니다.
        # - 현재 누적 매수 금액으로부터 T를 계산하고 star%를 산출합니다.
        # - 반환되는 의도(intent)에는 두 개의 목표 매도가(25%는 star%, 75%는 +10%)가 포함됩니다.
        total_amount = float(self.config.get("total_amount", 0.0))
        if not isinstance(quote, dict):
            return []
        price = float(quote.get("price") or 0.0)
        symbol = quote.get("symbol")
        if total_amount <= 0 or price <= 0:
            return []

        cum_buy = float(self.state.get("cum_buy_amt", 0.0))
        per_split = self.quota(total_amount)
        amount = self.ceil2(per_split)
        qty = amount / price

        T = self.compute_T(cum_buy)
        star_pct = self.compute_star_percent(T, symbol)
        target_star = price * (1.0 + float(star_pct) / 100.0)
        target_plus10 = price * 1.10

        # 주문유형은 설정값으로 제어 가능 (기본 LOC 또는 config에서 지정)
        order_type = str(self.config.get("order_type", "LOC"))

        intent = {
            "type": "buy",
            "symbol": symbol,
            "price": price,
            "amount": amount,
            "quantity": qty,
            "T": T,
            "star_percent": star_pct,
            "order_type": order_type,
            "market": self.config.get("market", "overseas"),
            "ovrs_excg_cd": self.config.get("ovrs_excg_cd", None),
            "exec_date": date,
            "targets": [
                {"fraction": 0.25, "price": target_star},
                {"fraction": 0.75, "price": target_plus10},
            ],
        }
        return [intent]

    def decide_sell(self, position, market_price) -> List[Dict[str, Any]]:
        # v2.2 매도 규칙:
        # - 보유 수량의 25%를 star% 목표가에 매도 의도로 생성
        # - 나머지 75%를 평균단가 대비 +10% 목표가에 매도 의도로 생성
        # position에는 최소한 `symbol`, `quantity`, `avg_price`가 포함되어야 합니다.
        if not isinstance(position, dict):
            return []
        qty = float(position.get("quantity", 0.0))
        avg_price = float(position.get("avg_price", position.get("price", 0.0)))
        symbol = position.get("symbol")
        cum_buy = float(position.get("cum_buy_amt", self.state.get("cum_buy_amt", 0.0)))
        if qty <= 0 or avg_price <= 0:
            return []

        T = self.compute_T(cum_buy)
        star_pct = self.compute_star_percent(T, symbol)
        target_star = avg_price * (1.0 + float(star_pct) / 100.0)
        target_plus10 = avg_price * 1.10

        sell_qty1 = qty * 0.25
        sell_qty2 = qty - sell_qty1

        intents: List[Dict[str, Any]] = []
        if sell_qty1 > 0:
            intents.append({
                "type": "sell",
                "symbol": symbol,
                "price": target_star,
                "quantity": sell_qty1,
                "reason": "take_profit_star",
            })
        if sell_qty2 > 0:
            intents.append({
                "type": "sell",
                "symbol": symbol,
                "price": target_plus10,
                "quantity": sell_qty2,
                "reason": "take_profit_plus10",
            })
        return intents
