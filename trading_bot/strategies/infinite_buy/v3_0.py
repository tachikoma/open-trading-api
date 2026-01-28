"""v3.0 implementation (stub): different splits, star% formulas, quota mode changes.

Fill with concrete rules from v3.0 when ready.
"""
from .base import InfiniteBuyBase
import math
from typing import Any, Dict, List

class InfiniteBuyV30(InfiniteBuyBase):
    def compute_T(self, cum_buy_amt: float) -> float:
        one_shot = float(self.config.get("one_shot_amount", 1000.0))
        T = (cum_buy_amt) / one_shot if one_shot else 0.0
        return math.ceil(T * 100) / 100.0

    def compute_star_percent(self, T: float, symbol: str) -> float:
        # Example: use mapping from config; default tuning factors
        mapping = self.config.get("target_percent_map", {"TQQQ": 15.0, "SOXL": 20.0})
        factor_map = self.config.get("v3_factor_map", {"TQQQ": 1.5, "SOXL": 2.0})
        base = float(mapping.get(symbol, 10.0))
        factor = float(factor_map.get(symbol, 0.5))
        return max(0.0, base - factor * T)

    def decide_buy(self, date, quote) -> List[Dict[str, Any]]:
        # TODO: implement v3.0 buy composition
        return []

    def decide_sell(self, position, market_price) -> List[Dict[str, Any]]:
        # TODO: implement v3.0 sell rules (quota/MOC behavior)
        return []
