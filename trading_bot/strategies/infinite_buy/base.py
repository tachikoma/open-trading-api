from abc import ABC, abstractmethod
from typing import Any, Dict, List
import math
from datetime import datetime
import pytz

from trading_bot.config import Config
from trading_bot.utils.logger import setup_logger


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
        # 로거: broker가 로거를 제공하면 재사용, 아니면 기본 로거 생성
        try:
            self.logger = getattr(self.broker, "logger") if self.broker is not None and hasattr(self.broker, "logger") else setup_logger(f"Strategy.{self.__class__.__name__}", Config.LOG_DIR, Config.LOG_LEVEL)
        except Exception:
            self.logger = setup_logger(f"Strategy.{self.__class__.__name__}", Config.LOG_DIR, Config.LOG_LEVEL)

    def cfg_for(self, symbol: str) -> Dict[str, Any]:
        """주어진 `symbol`에 대해 전역 설정(self.config)과 `per_symbol` 오버라이드를 병합한 딕셔너리를 반환합니다.

        사용 예:
            cfg = self.cfg_for(symbol)
            total_amount = float(cfg.get("total_amount", 0.0))
        """
        base = dict(self.config) if isinstance(self.config, dict) else {}
        # 우선순위: symbol별 설정 맵 키 'symbols' -> legacy 'per_symbol' -> none
        symbols_map = base.get("symbols") or {}
        per_map = base.get("per_symbol") or {}
        overrides = {}
        try:
            if isinstance(symbols_map, dict) and symbol in symbols_map:
                overrides = symbols_map.get(symbol, {}) or {}
            elif isinstance(per_map, dict) and symbol in per_map:
                overrides = per_map.get(symbol, {}) or {}
        except Exception:
            overrides = {}
        merged = dict(base)
        merged.update(overrides or {})
        return merged

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
        """공통 실행 진입점: 현재가/잔고를 조회해 `decide_buy`/`decide_sell`로 의도를 생성하고
        `broker.execute_intents`로 전달하여 실행합니다.

        - symbols: self.config['symbols'] 우선, 없으면 전역 Config.WATCH_LIST 사용
        - 매수 의도는 `decide_buy(date, quote)` 호출로 생성
        - 매도 의도는 보유 포지션을 순회하며 `decide_sell(position, market_price)` 호출로 생성
        """
        try:
            self.logger.info("=" * 50)
            self.logger.info(f"{self.__class__.__name__} 실행 시작")
            self.logger.info("=" * 50)

            # symbols 결정: InfiniteBuy 전략은 미국(해외) 전용 전략이므로
            # 전역 `Config.WATCH_LIST`를 기본값으로 사용하지 않습니다.
            # 반드시 인스턴스 설정(self.config['symbols'] 또는 self.config['watch_list'])으로 지정하세요.
            symbols = self.config.get('symbols') or self.config.get('watch_list') or []
            if not symbols:
                self.logger.info("심볼이 설정되지 않음 — InfiniteBuy는 self.config['symbols']를 필요로 합니다. 실행을 건너뜁니다.")
                return

            date_str = datetime.now(pytz.timezone('Asia/Seoul')).strftime("%Y-%m-%d")

            intents: List[Dict[str, Any]] = []

            # 매수 의도 수집
            for sym in symbols:
                try:
                    price_df = None
                    if self.broker is not None and hasattr(self.broker, 'get_current_price'):
                        price_df = self.broker.get_current_price(sym)
                    price = self._extract_price_from_df(price_df)
                    if price <= 0:
                        self.logger.debug(f"{sym}: 현재가 없음 또는 0, 스킵")
                        continue
                    quote = {'symbol': sym, 'price': price}
                    buy_intents = self.decide_buy(date_str, quote) or []
                    if isinstance(buy_intents, dict):
                        buy_intents = [buy_intents]
                    intents.extend(buy_intents)
                except Exception as e:
                    self.logger.error(f"{sym}: 매수 의도 생성 중 오류: {e}")

            # 매도 의도 수집: 보유 포지션 기반
            try:
                if self.broker is not None and hasattr(self.broker, 'get_balance'):
                    holdings_df, _ = self.broker.get_balance()
                    if holdings_df is not None:
                        # iterate rows if DataFrame-like
                        try:
                            import pandas as _pd
                            if isinstance(holdings_df, _pd.DataFrame) and not holdings_df.empty:
                                for _, row in holdings_df.iterrows():
                                    try:
                                        pos = {
                                            'symbol': row.get('pdno') or row.get('symbol') or row.get('pd_no'),
                                            'quantity': float(row.get('hldg_qty') or row.get('quantity') or 0),
                                            'avg_price': float(row.get('avg_prc') or row.get('avg_price') or row.get('price') or 0),
                                            'cum_buy_amt': float(self.get_cum_buy(row.get('pdno') or row.get('symbol') or row.get('pd_no'))),
                                        }
                                        market_price = None
                                        try:
                                            market_price = float(row.get('last') or row.get('stck_prpr') or None)
                                        except Exception:
                                            market_price = None
                                        sell_intents = self.decide_sell(pos, market_price) or []
                                        if isinstance(sell_intents, dict):
                                            sell_intents = [sell_intents]
                                        intents.extend(sell_intents)
                                    except Exception:
                                        continue
                        except Exception:
                            pass
            except Exception:
                pass

            if not intents:
                self.logger.info("생성된 의도 없음 — 실행 종료")
                return

            # 실행 (브로커가 TRADING_ENABLED를 검사하므로 simulate_only=False)
            try:
                results = self.broker.execute_intents(intents, strategy=self, simulate_only=False)
                self.logger.info(f"의도 실행 결과 개수: {len(results)}")
            except Exception as e:
                self.logger.error(f"execute_intents 호출 중 오류: {e}")

        except Exception as e:
            self.logger.error(f"execute() 오류: {e}")
        finally:
            self.logger.info(f"{self.__class__.__name__} 실행 완료")
