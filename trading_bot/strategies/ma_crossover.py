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
    
    def analyze_data(self, symbol: str, data):
        """
        과거 데이터 분석 (백테스트용)
        
        Args:
            symbol: 종목코드
            data: 과거 데이터 DataFrame
            
        Returns:
            {'action': 'buy'|'sell'|'hold', 'reason': str} 또는 None
        """
        import pandas as pd
        
        if data is None or len(data) < self.long_period:
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
        
        # 이전 값 (교차 감지용)
        if len(short_ma) < 2:
            return None
        prev_short = short_ma.iloc[-2]
        prev_long = long_ma.iloc[-2]
        
        # 골든크로스 감지
        if prev_short <= prev_long and current_short > current_long:
            return {
                'action': 'buy',
                'reason': f'골든크로스 (단기MA: {current_short:.0f}, 장기MA: {current_long:.0f})'
            }
        
        # 데드크로스 감지
        elif prev_short >= prev_long and current_short < current_long:
            return {
                'action': 'sell',
                'reason': f'데드크로스 (단기MA: {current_short:.0f}, 장기MA: {current_long:.0f})'
            }
        
        return None
    
    def calculate_ma(self, symbol: str) -> Optional[tuple]:
        """
        이동평균 계산
        
        Args:
            symbol: 종목코드
        
        Returns:
            (단기이평, 장기이평, 현재가) 또는 None
        """
        try:
            # 일별 시세 조회 (장기 이평 계산을 위해 넉넉하게)
            df = self.broker.get_daily_price(symbol, period="D")
            
            if df is None or df.empty:
                self.logger.warning(f"[{symbol}] 시세 데이터 없음")
                return None
            
            # 종가 컬럼 확인
            if 'stck_clpr' not in df.columns:
                self.logger.error(f"[{symbol}] 종가 컬럼 없음")
                return None
            
            # 종가를 숫자로 변환
            df['close'] = pd.to_numeric(df['stck_clpr'], errors='coerce')
            
            # 이동평균 계산
            df['ma_short'] = df['close'].rolling(window=self.short_period).mean()
            df['ma_long'] = df['close'].rolling(window=self.long_period).mean()
            
            # 최신 데이터
            latest = df.iloc[0]  # domestic_stock_functions는 최신날짜가 첫 행
            
            ma_short = latest['ma_short']
            ma_long = latest['ma_long']
            current_price = latest['close']
            
            if pd.isna(ma_short) or pd.isna(ma_long):
                self.logger.warning(f"[{symbol}] 이동평균 계산 불가 (데이터 부족)")
                return None
            
            return ma_short, ma_long, current_price
            
        except Exception as e:
            self.logger.error(f"[{symbol}] 이동평균 계산 중 오류: {e}")
            return None
    
    def get_signal(self, symbol: str) -> Optional[str]:
        """
        매매 시그널 판단
        
        Args:
            symbol: 종목코드
        
        Returns:
            'BUY', 'SELL', 'HOLD' 또는 None
        """
        result = self.calculate_ma(symbol)
        if result is None:
            return None
        
        ma_short, ma_long, current_price = result
        
        # 현재 크로스 상태
        is_golden = ma_short > ma_long  # 골든크로스 (매수)
        is_dead = ma_short < ma_long    # 데드크로스 (매도)
        
        # 이전 상태와 비교
        prev_state = self.prev_signals.get(symbol, None)
        
        signal = None
        reason = ""
        
        if is_golden and prev_state != 'golden':
            # 골든크로스 발생
            signal = 'BUY'
            reason = f"골든크로스 (단기={ma_short:.0f}, 장기={ma_long:.0f})"
            self.prev_signals[symbol] = 'golden'
            
        elif is_dead and prev_state != 'dead':
            # 데드크로스 발생
            signal = 'SELL'
            reason = f"데드크로스 (단기={ma_short:.0f}, 장기={ma_long:.0f})"
            self.prev_signals[symbol] = 'dead'
        else:
            signal = 'HOLD'
            reason = f"유지 (단기={ma_short:.0f}, 장기={ma_long:.0f}, 현재가={current_price:.0f})"
        
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
