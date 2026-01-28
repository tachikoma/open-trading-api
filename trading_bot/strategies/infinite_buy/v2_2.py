"""v2.2 implementation of InfiniteBuy rules (ceil2, default splits=40)."""
from .base import InfiniteBuyBase
import math
from typing import Any, Dict, List

class InfiniteBuyV22(InfiniteBuyBase):
    def compute_T(self, cum_buy_amt: float) -> float:
        one_shot = float(self.config.get("one_shot_amount", 1000.0))
        T = (cum_buy_amt) / one_shot if one_shot else 0.0
        return math.ceil(T * 100) / 100.0

    def compute_star_percent(self, T: float, symbol: str) -> float:
        return max(0.0, 10.0 - T / 2.0)

    def decide_buy(self, date, quote) -> List[Dict[str, Any]]:
        # TODO: implement full order composition based on v2.2 rules
        return []

    def decide_sell(self, position, market_price) -> List[Dict[str, Any]]:
        # TODO: implement sell logic (daily 1/4 at star%, 3/4 at +10%)
        return []
