from abc import ABC, abstractmethod
from typing import Any, Dict, List
import math


class InfiniteBuyBase(ABC):
    """InfiniteBuy 전략의 공통 베이스 클래스와 헬퍼.

    기본값:
    - `base_currency`: USD
    - `splits`: 40
    - T 반올림 규칙: 소수점 둘째 자리에서 올림(ceil2)

    이 클래스는 전략 구현이 따라야 할 추상 메서드 인터페이스와
    공용 유틸리티(예: `ceil2`, `quota`)를 제공합니다.
    """

    def __init__(self, config: Dict[str, Any], broker: Any = None):
        # 전략 설정(config)과 브로커 참조를 보관
        self.config = config or {}
        self.broker = broker
        self.version = str(self.config.get("version", "v2.2"))
        self.base_currency = self.config.get("base_currency", "USD")
        self.splits = int(self.config.get("splits", 40))
        # 전략 상태 저장소 (누적 매수금 등 사용자 정의 상태 보관)
        self.state: Dict[str, Any] = {}

    @staticmethod
    def ceil2(value: float) -> float:
        """소수점 둘째 자리에서 올림: ceil(value * 100) / 100

        v2.2 규칙에서 T의 반올림에 사용되는 헬퍼입니다.
        """
        return math.ceil(float(value) * 100.0) / 100.0

    def quota(self, total_amount: float) -> float:
        """전체 투자금액을 `splits`로 나눈 분할당 금액을 반환합니다."""
        if self.splits <= 0:
            raise ValueError("splits must be > 0")
        return float(total_amount) / float(self.splits)

    @abstractmethod
    def compute_T(self, cum_buy_amt: float) -> float:
        """누적 매수금액(`cum_buy_amt`)으로부터 T를 계산합니다.

        반환값은 버전별 규칙(예: 반올림)을 적용한 실수형입니다.
        """
        raise NotImplementedError

    @abstractmethod
    def compute_star_percent(self, T: float, symbol: str) -> float:
        """T와 종목(symbol)을 받아 목표 `star%`를 계산합니다."""
        raise NotImplementedError

    @abstractmethod
    def decide_buy(self, date, quote) -> List[Dict[str, Any]]:
        """매수 의도 리스트를 반환합니다. 각 의도는 주문 실행에 필요한 키를 포함합니다."""
        raise NotImplementedError

    @abstractmethod
    def decide_sell(self, position, market_price) -> List[Dict[str, Any]]:
        """매도 의도 리스트를 반환합니다."""
        raise NotImplementedError

    def record_trade(self, trade: Dict[str, Any]) -> None:
        """전략 내부의 거래 기록을 저장합니다 (백테스트/로그용)."""
        self.state.setdefault("trades", []).append(trade)

    # ==================== 하루 1회 실행 제약 헬퍼 ====================
    def _can_execute_T_today(self, T: float, date_str: str) -> bool:
        """주어진 T에 대해 `date_str`(YYYY-MM-DD 혹은 유사 문자열) 날짜에 이미 실행했는지 검사합니다.

        - 상태 키 `last_exec_by_T`는 {str(T): date_str} 형태로 저장됩니다.
        - 같은 날짜에 재실행을 허용하지 않습니다.
        """
        last_map = self.state.setdefault("last_exec_by_T", {})
        key = str(T)
        last = last_map.get(key)
        return last != date_str

    def _mark_executed_T(self, T: float, date_str: str) -> None:
        """주어진 T에 대해 `date_str`로 실행 표식을 남깁니다."""
        last_map = self.state.setdefault("last_exec_by_T", {})
        last_map[str(T)] = date_str

    def get_state(self) -> Dict[str, Any]:
        """전략의 내부 상태(state) 딕셔너리를 반환합니다."""
        return self.state
