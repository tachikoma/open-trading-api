"""InfiniteBuy strategy base classes and helpers.

Common defaults:
- base_currency: USD
- splits: 40
- T rounding: ceil(value * 100) / 100 (ceil2)
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List

class InfiniteBuyBase(ABC):
    def __init__(self, config: Dict[str, Any], broker: Any = None):
        self.config = config or {}
        self.broker = broker
        self.version = self.config.get("version", "v2.2")
        self.base_currency = self.config.get("base_currency", "USD")
        self.splits = int(self.config.get("splits", 40))
        self.state: Dict[str, Any] = {}

    @abstractmethod
    def compute_T(self, cum_buy_amt: float) -> float:
        """Compute turn T from cumulative buy amount.
        Returns T as float (version-specific rounding applied).
        """
        raise NotImplementedError

    @abstractmethod
    def compute_star_percent(self, T: float, symbol: str) -> float:
        """Compute star percent given T and symbol.
        """
        raise NotImplementedError

    @abstractmethod
    def decide_buy(self, date, quote) -> List[Dict[str, Any]]:
        """Return list of order intents (dict with keys: price, qty, type).
        """
        raise NotImplementedError

    @abstractmethod
    def decide_sell(self, position, market_price) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def record_trade(self, trade: Dict[str, Any]) -> None:
        self.state.setdefault("trades", []).append(trade)

    def get_state(self) -> Dict[str, Any]:
        return self.state
