"""
이동평균선 교차 전략

단순이동평균(SMA) 골든크로스/데드크로스 기반 매매 전략
"""
import pandas as pd
from typing import Optional

from trading_bot.strategies.base_strategy import BaseStrategy
from trading_bot.broker import KISBroker
from trading_bot.config import Config


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
                self.logger.debug(f"[{symbol}] 데이터 부족: {len(data) if data is not None else 0}/{self.long_period}")
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
                self.logger.info(f"[{symbol}] {result['reason']}")
            return result
        
        # 데드크로스 감지 (이전: 단기 >= 장기, 현재: 단기 < 장기)
        elif prev_short >= prev_long and current_short < current_long:
            result = {
                'action': 'sell',
                'reason': f'데드크로스 (단기MA: {current_short:.0f}, 장기MA: {current_long:.0f})',
                'debug': debug_info
            }
            if debug:
                self.logger.info(f"[{symbol}] {result['reason']}")
            return result
        
        # 시그널 없음
        if debug:
            status = "상승세" if current_short > current_long else "하락세"
            self.logger.debug(f"[{symbol}] 시그널 없음 - {status} (단기: {current_short:.0f}, 장기: {current_long:.0f})")
        
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
                self.logger.warning(f"[{symbol}] 시세 데이터 없음")
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
                self.logger.error(f"[{symbol}] 종가 컬럼 없음: columns={list(df.columns)}")
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
                self.logger.warning(f"[{symbol}] 이동평균 계산에 필요한 데이터 부족 ({len(df)}/{self.long_period + 1})")
                return None

            latest = df.iloc[-1]
            prev = df.iloc[-2]  # 이전 데이터

            ma_short = latest['ma_short']
            ma_long = latest['ma_long']
            current_price = latest['close']
            prev_ma_short = prev['ma_short']
            prev_ma_long = prev['ma_long']

            if pd.isna(ma_short) or pd.isna(ma_long) or pd.isna(prev_ma_short) or pd.isna(prev_ma_long):
                self.logger.warning(f"[{symbol}] 이동평균 계산 불가 (데이터 부족)")
                return None

            return ma_short, ma_long, current_price, prev_ma_short, prev_ma_long

        except Exception as e:
            self.logger.error(f"[{symbol}] 이동평균 계산 중 오류: {e}")
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
        
        # 감시 종목 순회
        for symbol in Config.WATCH_LIST:
            try:
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
                self.logger.error(f"[{symbol}] 전략 실행 중 오류: {e}")
        
        self.logger.info("전략 실행 완료")
    
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
                self.logger.warning(f"[{symbol}] 현재가 조회 실패")
                return
            
            current_price = int(price_df.iloc[0]['stck_prpr'])
            
            # 매수가능 금액 조회
            available_cash = self.broker.get_buyable_cash()
            if available_cash is None or available_cash == 0:
                self.logger.warning(f"[{symbol}] 매수 가능 금액 없음")
                return
            
            # 포지션 크기 계산 (설정된 최대 금액과 가용 현금 중 작은 값)
            invest_amount = min(Config.MAX_POSITION_SIZE, available_cash)
            
            # 매수 수량 계산
            qty = invest_amount // current_price
            
            if qty == 0:
                self.logger.warning(f"[{symbol}] 매수 수량 0 (금액 부족)")
                return
            
            # 매수 주문
            self.logger.info(f"[{symbol}] 매수 시도: 가격={current_price}, 수량={qty}")
            result = self.broker.buy(symbol, qty, current_price, order_type="00")
            
            if result and result.get('success'):
                self.logger.info(f"[{symbol}] 매수 성공")
            else:
                self.logger.error(f"[{symbol}] 매수 실패: {result.get('message')}")
                
        except Exception as e:
            self.logger.error(f"[{symbol}] 매수 실행 중 오류: {e}")
    
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
                self.logger.info(f"[{symbol}] 보유 종목 없음")
                return
            
            # 해당 종목 보유 확인
            holding = holdings_df[holdings_df['pdno'] == symbol]
            
            if holding.empty:
                self.logger.info(f"[{symbol}] 보유하지 않은 종목")
                return
            
            qty = int(holding.iloc[0]['hldg_qty'])
            
            if qty == 0:
                self.logger.info(f"[{symbol}] 보유 수량 0")
                return
            
            # 현재가 조회
            price_df = self.broker.get_current_price(symbol)
            if price_df is None or price_df.empty:
                self.logger.warning(f"[{symbol}] 현재가 조회 실패")
                return
            
            current_price = int(price_df.iloc[0]['stck_prpr'])
            
            # 매도 주문
            self.logger.info(f"[{symbol}] 매도 시도: 가격={current_price}, 수량={qty}")
            result = self.broker.sell(symbol, qty, current_price, order_type="00")
            
            if result and result.get('success'):
                self.logger.info(f"[{symbol}] 매도 성공")
            else:
                self.logger.error(f"[{symbol}] 매도 실패: {result.get('message')}")
                
        except Exception as e:
            self.logger.error(f"[{symbol}] 매도 실행 중 오류: {e}")
