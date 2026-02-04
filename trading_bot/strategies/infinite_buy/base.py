from abc import ABC, abstractmethod
from typing import Any, Dict, List
import math
from datetime import datetime
import pytz

from trading_bot.broker.kis_broker import KISBroker
from trading_bot.config import Config
from trading_bot.utils.logger import setup_logger


class InfiniteBuyBase(ABC):
    """InfiniteBuy 전략의 공통 베이스 클래스와 헬퍼.

    기본값:
    - `base_currency`: USD
    - T 반올림 규칙: 소수점 둘째 자리에서 올림(ceil2)

    필수 설정 (symbols 하위):
    - `total_amount`: 종목별 총 투자금액
    - `splits`: 종목별 분할 횟수
    - `exchange`: 거래소 코드 (예: NAS, AMS)

    이 클래스는 전략 구현이 따라야 할 추상 메서드 인터페이스와
    공용 유틸리티(예: `ceil2`, `quota`)를 제공합니다.
    """

    def __init__(self, config: Dict[str, Any], broker: KISBroker = None):
        # 전략 설정(config)과 브로커 참조를 보관
        self.config = config or {}
        self.broker = broker
        self.version = str(self.config.get("version", "v2.2"))
        self.base_currency = self.config.get("base_currency", "USD")
        # 전략 상태 저장소 (누적 매수금 등 사용자 정의 상태 보관)
        self.state: Dict[str, Any] = {}
        # 로거: broker가 로거를 제공하면 재사용, 아니면 기본 로거 생성
        try:
            self.logger = getattr(self.broker, "logger") if self.broker is not None and hasattr(self.broker, "logger") else setup_logger(f"Strategy.{self.__class__.__name__}", Config.LOG_DIR, Config.LOG_LEVEL)
        except Exception:
            self.logger = setup_logger(f"Strategy.{self.__class__.__name__}", Config.LOG_DIR, Config.LOG_LEVEL)

    def cfg_for(self, symbol: str) -> Dict[str, Any]:
        """주어진 `symbol`에 대해 symbols 설정을 반환합니다.

        사용 예:
            cfg = self.cfg_for(symbol)
            total_amount = float(cfg.get("total_amount", 0.0))
            splits = int(cfg.get("splits", 40))
        """
        base = dict(self.config) if isinstance(self.config, dict) else {}
        symbols_map = base.get("symbols") or {}
        
        if isinstance(symbols_map, dict) and symbol in symbols_map:
            symbol_cfg = symbols_map.get(symbol, {}) or {}
            # symbol 설정에 base_currency와 version도 포함
            result = {"base_currency": self.base_currency, "version": self.version}
            result.update(symbol_cfg)
            return result
        
        # symbols에 없으면 빈 dict 반환 (더 이상 전역 설정을 폴백하지 않음)
        return {"base_currency": self.base_currency, "version": self.version}

    @staticmethod
    def ceil2(value: float) -> float:
        """소수점 둘째 자리에서 올림: ceil(value * 100) / 100

        v2.2 규칙에서 T의 반올림에 사용되는 헬퍼입니다.
        """
        return math.ceil(float(value) * 100.0) / 100.0

    def quota(self, total_amount: float, splits: int) -> float:
        """전체 투자금액을 `splits`로 나눈 분할당 금액을 반환합니다.
        
        Args:
            total_amount: 전체 투자금액
            splits: 분할 횟수 (심볼별 설정에서 가져옴)
        """
        if splits <= 0:
            raise ValueError("splits must be > 0")
        return float(total_amount) / float(splits)

    @abstractmethod
    def compute_T(self, cum_buy_amt: float, symbol: str = None) -> float:
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

    # ==================== 누적 매수 금액 관리 (심볼별) ====================
    def get_cum_buy(self, symbol: str = None) -> float:
        """심볼별 누적 매수금액을 반환합니다.

        - 심볼 지정 시 `state['cum_buy_amt_by_symbol'][symbol]`을 우선 조회
        - 존재하지 않으면 글로벌 `state['cum_buy_amt']`를 폴백으로 반환합니다.
        """
        try:
            if symbol:
                by_sym = self.state.setdefault("cum_buy_amt_by_symbol", {})
                return float(by_sym.get(symbol, float(self.state.get("cum_buy_amt", 0.0))))
        except Exception:
            pass
        return float(self.state.get("cum_buy_amt", 0.0))

    def add_cum_buy(self, symbol: str, amount: float) -> None:
        """심볼별 누적 매수금액에 `amount`를 더합니다.

        - 심볼별로 누적하고, 글로벌 `cum_buy_amt`도 보조적으로 유지하여
          기존 코드(테스트 등)가 글로벌 키를 참조하더라도 호환되도록 합니다.
        """
        try:
            amt = float(amount or 0.0)
        except Exception:
            amt = 0.0

        if symbol:
            by_sym = self.state.setdefault("cum_buy_amt_by_symbol", {})
            by_sym[symbol] = float(by_sym.get(symbol, 0.0)) + amt

        # global 누적값도 갱신(하위 호환성 유지)
        self.state["cum_buy_amt"] = float(self.state.get("cum_buy_amt", 0.0)) + amt

    def _extract_price_from_df(self, df) -> float:
        """DataFrame 형태의 현재가 응답에서 가격을 추출하는 유틸.

        여러 API 반환 포맷에 대응: 'stck_prpr', 'last', 'price', 'close', 'prpr' 등을 우선 사용합니다.
        """
        if df is None:
            return 0.0
        try:
            # pandas DataFrame-like
            import pandas as _pd
            if isinstance(df, _pd.DataFrame) and not df.empty:
                preferred = ['stck_prpr', 'last', 'price', 'close', 'prpr', 'clpr']
                for c in preferred:
                    if c in df.columns:
                        try:
                            return float(df.iloc[0][c])
                        except Exception:
                            continue
                # fallback: find first numeric column
                for c in df.columns:
                    if _pd.api.types.is_numeric_dtype(df[c]):
                        try:
                            return float(df.iloc[0][c])
                        except Exception:
                            continue
        except Exception:
            pass
        # not a dataframe or failed: try dict/list extraction
        try:
            if isinstance(df, dict):
                data = df.get('data') or df
                if isinstance(data, dict):
                    for k in ('price', 'last', 'exec_price', 'stck_prpr'):
                        if k in data:
                            return float(data.get(k) or 0.0)
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    for k in ('price', 'last', 'exec_price', 'stck_prpr'):
                        if k in data[0]:
                            return float(data[0].get(k) or 0.0)
        except Exception:
            pass
        return 0.0

    def execute(self):
        """실행 진입점: 환경별(모의투자/실전투자) 전략에 따라 실행

        - 모의투자(demo): 지정가만 가능 → 시간대별 재주문 (Pre/Regular/After 각각)
        - 실전투자(real): LOC/MOC 지원 → 하루 1회만 실행 (자동 실행)
        """
        try:
            # 환경 확인
            env_mode = self.broker.env_mode if self.broker else "demo"
            
            if env_mode == "demo":
                # 모의투자: 시간대별 재주문
                from trading_bot.strategies.infinite_buy.impl_demo import InfiniteBuyDemoImpl
                impl = InfiniteBuyDemoImpl(self)
                impl.execute()
            else:
                # 실전투자: 하루 1회만
                from trading_bot.strategies.infinite_buy.impl_real import InfiniteBuyRealImpl
                impl = InfiniteBuyRealImpl(self)
                impl.execute()
        
        except Exception as e:
            self.logger.error(f"execute() 오류: {e}")
