"""
이동평균선 교차 전략

단순이동평균(SMA) 골든크로스/데드크로스 기반 매매 전략
"""
import pandas as pd
from typing import Optional

from trading_bot.strategies.base_strategy import BaseStrategy
from trading_bot.broker import KISBroker
from trading_bot.config import Config
from trading_bot.utils.symbols import format_symbol
from trading_bot.utils.fees import calculate_fees_and_taxes
from trading_bot.utils.risk import calculate_pnl_pct, should_force_stop_loss
from trading_bot.utils.ma_screening import ScreeningConfig, screen_symbols_with_broker
from trading_bot.utils.universe import resolve_universe_symbols


class MovingAverageCrossover(BaseStrategy):
    """
    이동평균 교차 전략
    
    - 골든크로스(단기이평 > 장기이평): 매수 시그널
    - 데드크로스(단기이평 < 장기이평): 매도 시그널
    """
    
    def __init__(self, broker: KISBroker, 
                 short_period: int = None, 
                 long_period: int = None):
        """
        Args:
            broker: KISBroker 인스턴스
            short_period: 단기 이동평균 기간 (기본값: Config.MA_SHORT_PERIOD)
            long_period: 장기 이동평균 기간 (기본값: Config.MA_LONG_PERIOD)
        """
        super().__init__(broker, "MA_Crossover")
        
        self.short_period = short_period or Config.MA_SHORT_PERIOD
        self.long_period = long_period or Config.MA_LONG_PERIOD
        
        # 이전 시그널 상태 저장 (골든크로스/데드크로스 감지용)
        self.prev_signals = {}
        
        self.logger.info(f"이동평균 설정: 단기={self.short_period}일, 장기={self.long_period}일")
    
    def analyze_data(self, symbol: str, data, debug: bool = False):
        """
        과거 데이터 분석 (백테스트용)
        
        Args:
            symbol: 종목코드
            data: 과거 데이터 DataFrame
            debug: 디버그 정보 출력 여부
            
        Returns:
            {'action': 'buy'|'sell'|'hold', 'reason': str, 'debug': dict} 또는 None
        """
        import pandas as pd
        
        if data is None or len(data) < self.long_period:
            if debug:
                self.logger.debug(f"[{format_symbol(symbol)}] 데이터 부족: {len(data) if data is not None else 0}/{self.long_period}")
            return None
        
        # 가격 데이터 추출
        if 'stck_clpr' in data.columns:
            prices = data['stck_clpr'].astype(float)
        elif 'close' in data.columns:
            prices = data['close'].astype(float)
        else:
            return None
        
        # 이동평균 계산
        short_ma = prices.rolling(window=self.short_period).mean()
        long_ma = prices.rolling(window=self.long_period).mean()
        
        # 현재 값
        current_short = short_ma.iloc[-1]
        current_long = long_ma.iloc[-1]
        current_price = prices.iloc[-1]
        
        # 이전 값 (교차 감지용)
        if len(short_ma) < 2:
            return None
        prev_short = short_ma.iloc[-2]
        prev_long = long_ma.iloc[-2]
        
        # 디버그 정보
        debug_info = {
            'price': current_price,
            'short_ma': current_short,
            'long_ma': current_long,
            'prev_short_ma': prev_short,
            'prev_long_ma': prev_long,
            'short_above_long': current_short > current_long,
            'prev_short_above_long': prev_short > prev_long
        }
        
        # 골든크로스 감지 (이전: 단기 <= 장기, 현재: 단기 > 장기)
        if prev_short <= prev_long and current_short > current_long:
            result = {
                'action': 'buy',
                'reason': f'골든크로스 (단기MA: {current_short:.0f}, 장기MA: {current_long:.0f})',
                'debug': debug_info
            }
            if debug:
                self.logger.info(f"[{format_symbol(symbol)}] {result['reason']}")
            return result
        
        # 데드크로스 감지 (이전: 단기 >= 장기, 현재: 단기 < 장기)
        elif prev_short >= prev_long and current_short < current_long:
            result = {
                'action': 'sell',
                'reason': f'데드크로스 (단기MA: {current_short:.0f}, 장기MA: {current_long:.0f})',
                'debug': debug_info
            }
            if debug:
                self.logger.info(f"[{format_symbol(symbol)}] {result['reason']}")
            return result
        
        # 시그널 없음
        if debug:
            status = "상승세" if current_short > current_long else "하락세"
            self.logger.debug(f"[{format_symbol(symbol)}] 시그널 없음 - {status} (단기: {current_short:.0f}, 장기: {current_long:.0f})")
        
        return None
    
    def calculate_ma(self, symbol: str) -> Optional[tuple]:
        """
        이동평균 계산
        
        Args:
            symbol: 종목코드
        
        Returns:
            (단기이평, 장기이평, 현재가, 이전_단기이평, 이전_장기이평) 또는 None
        """
        try:
            # 1) 기본: 일별 시세 조회 (최근 30거래일 제한)
            df = self.broker.get_daily_price(symbol, period="D")

            # 2) 조회 결과가 없으면 기간 조회로 대체 시도 (더 넓은 범위)
            if df is None or (hasattr(df, 'empty') and df.empty):
                from datetime import datetime, timedelta
                end_date = datetime.now().strftime("%Y%m%d")
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
                df = self.broker.get_period_price(symbol, start_date, end_date, period="D")

            # 3) 여전히 데이터가 없으면 경고
            if df is None or (hasattr(df, 'empty') and df.empty):
                self.logger.warning(f"[{format_symbol(symbol)}] 시세 데이터 없음")
                return None

            # 4) 종가 컬럼 식별 (여러 API 반환 형식에 대응)
            close_col = None
            preferred = ['stck_clpr', 'close', 'clpr', 'prpr', 'adj_prc', 'adj_close', 'price', 'last']
            for c in preferred:
                if c in df.columns:
                    close_col = c
                    break

            if close_col is None:
                # 숫자형 컬럼 중 이름에 pr/cl/close/price 포함되는 컬럼 우선 선택
                for c in df.columns:
                    lc = c.lower()
                    if ('pr' in lc or 'cl' in lc or 'close' in lc or 'price' in lc) and pd.api.types.is_numeric_dtype(df[c]):
                        close_col = c
                        break

            if close_col is None:
                # 마지막 수단: 숫자형 컬럼 중 첫번째
                for c in df.columns:
                    if pd.api.types.is_numeric_dtype(df[c]):
                        close_col = c
                        break

            if close_col is None:
                self.logger.error(f"[{format_symbol(symbol)}] 종가 컬럼 없음: columns={list(df.columns)}")
                return None

            # 종가를 숫자로 변환
            df.loc[:, 'close'] = pd.to_numeric(df[close_col], errors='coerce')

            # 날짜 컬럼이 있으면 오름차순(과거->최신)으로 정렬, 없으면 역순으로 만들어 과거->최신 보장
            date_col = None
            for c in df.columns:
                lc = c.lower()
                if 'date' in lc or 'bsop' in lc or 'trd' in lc:
                    date_col = c
                    break
            if date_col is not None:
                df = df.sort_values(by=date_col).reset_index(drop=True)
            else:
                df = df.iloc[::-1].reset_index(drop=True)

            # 이동평균 계산 (이제 최신이 마지막 행)
            df.loc[:, 'ma_short'] = df['close'].rolling(window=self.short_period).mean()
            df.loc[:, 'ma_long'] = df['close'].rolling(window=self.long_period).mean()

            # 충분한 데이터가 있어야 최신값과 이전값의 MA가 계산된다
            # rolling(window=N) 첫 유효값은 index N-1 -> 최신과 이전값 둘 다 존재하려면 N+1개 이상
            if len(df) < (self.long_period + 1):
                self.logger.warning(f"[{format_symbol(symbol)}] 이동평균 계산에 필요한 데이터 부족 ({len(df)}/{self.long_period + 1})")
                return None

            latest = df.iloc[-1]
            prev = df.iloc[-2]  # 이전 데이터

            ma_short = latest['ma_short']
            ma_long = latest['ma_long']
            current_price = latest['close']
            prev_ma_short = prev['ma_short']
            prev_ma_long = prev['ma_long']

            if pd.isna(ma_short) or pd.isna(ma_long) or pd.isna(prev_ma_short) or pd.isna(prev_ma_long):
                self.logger.warning(f"[{format_symbol(symbol)}] 이동평균 계산 불가 (데이터 부족)")
                return None

            return ma_short, ma_long, current_price, prev_ma_short, prev_ma_long

        except Exception as e:
            self.logger.error(f"[{format_symbol(symbol)}] 이동평균 계산 중 오류: {e}")
            return None
    
    def get_signal(self, symbol: str) -> Optional[str]:
        """
        매매 시그널 판단 (백테스트 로직과 동일한 교차 감지)
        
        Args:
            symbol: 종목코드
        
        Returns:
            'BUY', 'SELL', 'HOLD' 또는 None
        """
        result = self.calculate_ma(symbol)
        if result is None:
            return None
        
        ma_short, ma_long, current_price, prev_ma_short, prev_ma_long = result
        
        signal = None
        reason = ""
        
        # 골든크로스 감지 (이전: 단기 <= 장기, 현재: 단기 > 장기)
        # ※ 백테스트 analyze_data()와 동일한 로직
        if prev_ma_short <= prev_ma_long and ma_short > ma_long:
            signal = 'BUY'
            reason = f"골든크로스 (단기MA: {ma_short:.0f}, 장기MA: {ma_long:.0f})"
            self.prev_signals[symbol] = 'golden'
            
        # 데드크로스 감지 (이전: 단기 >= 장기, 현재: 단기 < 장기)
        # ※ 백테스트 analyze_data()와 동일한 로직
        elif prev_ma_short >= prev_ma_long and ma_short < ma_long:
            signal = 'SELL'
            reason = f"데드크로스 (단기MA: {ma_short:.0f}, 장기MA: {ma_long:.0f})"
            self.prev_signals[symbol] = 'dead'
        else:
            # 시그널 없음 (교차하지 않음)
            signal = 'HOLD'
            status = "상승세" if ma_short > ma_long else "하락세"
            reason = f"{status} 유지 (단기={ma_short:.0f}, 장기={ma_long:.0f})"
            # 현재 상태 저장 (다음 체크를 위해)
            if ma_short > ma_long:
                self.prev_signals[symbol] = 'golden'
            else:
                self.prev_signals[symbol] = 'dead'
        
        self.log_signal(symbol, signal, reason)
        return signal
    
    def execute(self):
        """전략 실행"""
        self.logger.info("=" * 50)
        self.logger.info("이동평균 교차 전략 실행")
        self.logger.info("=" * 50)

        try:
            universe_result = resolve_universe_symbols(
                target=Config.UNIVERSE_TARGET,
                default_symbols=list(Config.WATCH_LIST),
                cache_dir=Config.UNIVERSE_CACHE_DIR,
                refresh_daily=Config.UNIVERSE_REFRESH_DAILY,
                max_symbols=Config.UNIVERSE_MAX_SYMBOLS,
                logger=self.logger,
            )
            target_symbols = universe_result.symbols
            if universe_result.csv_path:
                self.logger.info(
                    f"유니버스 적용: target={universe_result.target}, "
                    f"symbols={len(target_symbols)}, file={universe_result.csv_path}"
                )
            else:
                self.logger.info(f"유니버스 적용: target={universe_result.target}, symbols={len(target_symbols)}")
        except Exception as e:
            self.logger.error(f"유니버스 생성 실패: {e} - WATCH_LIST로 대체")
            target_symbols = list(Config.WATCH_LIST)

        if not target_symbols:
            self.logger.warning("유니버스 종목이 비어 있어 전략 실행을 건너뜁니다.")
            return

        if Config.MA_SCREENING_ENABLED:
            try:
                screening_cfg = ScreeningConfig(
                    min_avg_value=Config.MA_SCREENING_MIN_AVG_VALUE,
                    adx_threshold=Config.MA_SCREENING_ADX_THRESHOLD,
                    trend_ma_period=Config.MA_SCREENING_TREND_MA_PERIOD,
                    atr_pct_min=Config.MA_SCREENING_ATR_PCT_MIN,
                    atr_pct_max=Config.MA_SCREENING_ATR_PCT_MAX,
                    top_n=Config.MA_SCREENING_TOP_N,
                )
                selected, selected_df = screen_symbols_with_broker(
                    symbols=target_symbols,
                    broker=self.broker,
                    cfg=screening_cfg,
                )
                if selected:
                    target_symbols = selected
                    self.logger.info(
                        f"유니버스 스크리닝 적용: {len(target_symbols)}개 선정 "
                        f"(기준: 거래대금20>={screening_cfg.min_avg_value:,.0f}, "
                        f"ADX>={screening_cfg.adx_threshold}, "
                        f"Close>MA{screening_cfg.trend_ma_period}, "
                        f"ATR%={screening_cfg.atr_pct_min}~{screening_cfg.atr_pct_max})"
                    )
                    self.logger.info(f"선정 종목: {target_symbols}")
                else:
                    self.logger.warning("유니버스 스크리닝 통과 종목 없음 - 기존 WATCH_LIST 사용")
                if selected_df is not None and not selected_df.empty:
                    self.logger.debug(f"스크리닝 결과(상위):\n{selected_df.head(10).to_string(index=False)}")
            except Exception as e:
                self.logger.error(f"유니버스 스크리닝 중 오류: {e} - 기존 WATCH_LIST 사용")
        
        # 감시 종목 순회
        for symbol in target_symbols:
            try:
                if self._check_and_execute_stop_loss(symbol):
                    continue

                signal = self.get_signal(symbol)
                
                if signal is None:
                    continue
                
                # 매수 시그널
                if signal == 'BUY':
                    self._execute_buy(symbol)
                
                # 매도 시그널
                elif signal == 'SELL':
                    self._execute_sell(symbol)
                
            except Exception as e:
                self.logger.error(f"[{format_symbol(symbol)}] 전략 실행 중 오류: {e}")
        
        self.logger.info("전략 실행 완료")

    @staticmethod
    def _safe_to_float(value) -> Optional[float]:
        """문자/숫자 혼합 값을 안전하게 float로 변환합니다."""
        if value is None:
            return None
        try:
            return float(str(value).replace(",", "").strip())
        except Exception:
            return None

    def _extract_avg_buy_price(self, holding_row: pd.Series) -> Optional[float]:
        """잔고 행에서 평균매수가를 추출합니다."""
        avg_price_keys = [
            "pchs_avg_pric",
            "pchs_avg_pric_amt",
            "avg_unpr",
            "pchs_unpr",
            "avg_buy_price",
        ]
        for key in avg_price_keys:
            if key in holding_row:
                avg_price = self._safe_to_float(holding_row.get(key))
                if avg_price is not None and avg_price > 0:
                    return avg_price
        return None

    def _check_and_execute_stop_loss(self, symbol: str) -> bool:
        """손절 조건 충족 시 강제 매도를 실행하고 True를 반환합니다."""
        try:
            holdings_df, _ = self.broker.get_balance()
            if holdings_df is None or holdings_df.empty or 'pdno' not in holdings_df.columns:
                return False

            holding = holdings_df[holdings_df['pdno'] == symbol]
            if holding.empty:
                return False

            qty = int(self._safe_to_float(holding.iloc[0].get('hldg_qty')) or 0)
            if qty <= 0:
                return False

            avg_price = self._extract_avg_buy_price(holding.iloc[0])
            if avg_price is None:
                self.logger.warning(
                    f"[{format_symbol(symbol)}] 평균매수가 컬럼을 찾지 못해 손절 체크를 스킵합니다. "
                    f"컬럼={list(holding.columns)}"
                )
                return False

            price_df = self.broker.get_current_price(symbol)
            if price_df is None or price_df.empty:
                return False

            current_price = self._safe_to_float(price_df.iloc[0].get('stck_prpr'))
            if current_price is None or current_price <= 0:
                return False

            pnl_pct = calculate_pnl_pct(current_price=current_price, avg_buy_price=avg_price)
            if pnl_pct is None:
                return False

            if should_force_stop_loss(
                current_price=current_price,
                avg_buy_price=avg_price,
                stop_loss_percent=Config.STOP_LOSS_PERCENT,
            ):
                self.logger.warning(
                    f"[{format_symbol(symbol)}] STOP_LOSS 강제매도 트리거: 현재가={current_price:.0f}, "
                    f"평균매수가={avg_price:.0f}, 손익률={pnl_pct:.2f}% "
                    f"(기준=-{Config.STOP_LOSS_PERCENT:.2f}%)"
                )
                self._execute_sell(symbol)
                return True

            return False
        except Exception as e:
            self.logger.error(f"[{format_symbol(symbol)}] 손절 체크 중 오류: {e}")
            return False
    
    def _execute_buy(self, symbol: str):
        """
        매수 실행
        
        Args:
            symbol: 종목코드
        """
        try:
            # 현재가 조회
            price_df = self.broker.get_current_price(symbol)
            if price_df is None or price_df.empty:
                self.logger.warning(f"[{format_symbol(symbol)}] 현재가 조회 실패")
                return
            
            current_price = int(price_df.iloc[0]['stck_prpr'])
            
            # 매수가능 금액 조회 (종목 및 현재가 기준)
            available_cash = self.broker.get_buyable_cash(symbol, current_price)
            if available_cash is None or available_cash == 0:
                self.logger.warning(f"[{format_symbol(symbol)}] 매수 가능 금액 없음")
                return
            
            # 포지션 크기 계산 (설정된 최대 금액과 가용 현금 중 작은 값)
            invest_amount = min(Config.MAX_POSITION_SIZE, available_cash)
            
            # 매수 수량 계산: 수수료(및 최소수수료)를 고려하여 실제로 투자 가능한 수량으로 보정
            qty = invest_amount // current_price

            # 조정 루프: 수량이 0이거나 수수료 포함 금액이 투자금액을 초과하면 수량 감소
            while qty > 0:
                est = calculate_fees_and_taxes(current_price, qty, side="buy")
                gross_plus_fee = est['gross_amount'] + est['total_fees']
                if gross_plus_fee <= invest_amount:
                    break
                qty -= 1

            if qty == 0:
                self.logger.warning(f"[{format_symbol(symbol)}] 매수 수량 0 (금액 및 수수료 고려 시 부족)")
                return
            
            # 호가 단위 조정 (broker에서도 자동 조정되지만, 로깅 명확성을 위해 미리 보여줌)
            adjusted_price = self.broker._adjust_price_to_tick_unit(current_price, env_mode=self.broker.env_mode)
            
            # 호가 단위가 조정된 경우, 수수료 재계산
            if adjusted_price != current_price:
                self.logger.debug(f"[{format_symbol(symbol)}] 호가 단위 조정: {current_price} → {adjusted_price}")
                est_adjusted = calculate_fees_and_taxes(adjusted_price, qty, side="buy")
                gross_adjusted = est_adjusted['gross_amount'] + est_adjusted['total_fees']
                if gross_adjusted > invest_amount:
                    self.logger.warning(f"[{format_symbol(symbol)}] 호가 조정 후 수수료 초과 - 수량 재조정 필요")
                    # 조정된 가격 기준으로 수량 재계산
                    qty = invest_amount // adjusted_price
                    while qty > 0:
                        est = calculate_fees_and_taxes(adjusted_price, qty, side="buy")
                        if est['gross_amount'] + est['total_fees'] <= invest_amount:
                            break
                        qty -= 1
                    if qty == 0:
                        self.logger.warning(f"[{format_symbol(symbol)}] 수량 재조정 후에도 0 (부족)")
                        return
            
            # 매수 주문 (조정된 가격 사용)
            self.logger.info(f"[{format_symbol(symbol)}] 매수 시도: 가격={adjusted_price}, 수량={qty}")
            result = self.broker.buy(symbol, qty, adjusted_price, order_type="00")
            
            if result and result.get('success'):
                fees_info = result.get('fees') or calculate_fees_and_taxes(current_price, qty, side="buy")
                self.logger.info(f"[{format_symbol(symbol)}] 매수 성공 - 수수료: {fees_info['commission']}, 세금: {fees_info['tax']}, 순투자금액: {-fees_info['net_amount']}")
            else:
                # result가 None 이거나 dict가 아닐 수 있으므로 안전하게 메시지 추출
                message = result.get('message') if isinstance(result, dict) and result.get('message') is not None else str(result)
                self.logger.error(f"[{format_symbol(symbol)}] 매수 실패: {message}")

        except Exception as e:
            self.logger.error(f"[{format_symbol(symbol)}] 매수 실행 중 오류: {e}")
    
    def _execute_sell(self, symbol: str):
        """
        매도 실행
        
        Args:
            symbol: 종목코드
        """
        try:
            # 보유 잔고 조회
            holdings_df, _ = self.broker.get_balance()
            
            if holdings_df is None or holdings_df.empty:
                self.logger.info(f"[{format_symbol(symbol)}] 보유 종목 없음")
                return
            
            # 해당 종목 보유 확인
            holding = holdings_df[holdings_df['pdno'] == symbol]
            
            if holding.empty:
                self.logger.info(f"[{format_symbol(symbol)}] 보유하지 않은 종목")
                return
            
            qty = int(holding.iloc[0]['hldg_qty'])
            
            if qty == 0:
                self.logger.info(f"[{format_symbol(symbol)}] 보유 수량 0")
                return
            
            # 현재가 조회
            price_df = self.broker.get_current_price(symbol)
            if price_df is None or price_df.empty:
                self.logger.warning(f"[{format_symbol(symbol)}] 현재가 조회 실패")
                return
            
            current_price = int(price_df.iloc[0]['stck_prpr'])
            
            # 호가 단위 조정 (broker에서도 자동 조정되지만, 로깅 명확성을 위해 미리 보여줌)
            adjusted_price = self.broker._adjust_price_to_tick_unit(current_price, env_mode=self.broker.env_mode)
            
            if adjusted_price != current_price:
                self.logger.debug(f"[{format_symbol(symbol)}] 호가 단위 조정: {current_price} → {adjusted_price}")
            
            # 매도 주문 (조정된 가격 사용)
            self.logger.info(f"[{format_symbol(symbol)}] 매도 시도: 가격={adjusted_price}, 수량={qty}")
            result = self.broker.sell(symbol, qty, adjusted_price, order_type="00")
            
            if result and result.get('success'):
                fees_info = result.get('fees') or calculate_fees_and_taxes(current_price, qty, side="sell")
                self.logger.info(f"[{format_symbol(symbol)}] 매도 성공 - 수수료: {fees_info['commission']}, 세금: {fees_info['tax']}, 순회수익: {fees_info['net_amount']}")
            else:
                # result가 None 이거나 dict가 아닐 수 있으므로 안전하게 메시지 추출
                message = result.get('message') if isinstance(result, dict) and result.get('message') is not None else str(result)
                self.logger.error(f"[{format_symbol(symbol)}] 매도 실패: {message}")
                
        except Exception as e:
            self.logger.error(f"[{format_symbol(symbol)}] 매도 실행 중 오류: {e}")
