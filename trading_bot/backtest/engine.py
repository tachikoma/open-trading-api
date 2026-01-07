"""
백테스트 엔진

과거 데이터를 사용하여 전략을 시뮬레이션하고 성과를 평가합니다.
"""
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.broker.kis_broker import KISBroker
from trading_bot.strategies.base_strategy import BaseStrategy
from trading_bot.backtest.metrics import PerformanceMetrics
from trading_bot.utils.logger import setup_logger
from trading_bot.config import Config


class BacktestEngine:
    """
    백테스트 엔진 클래스
    
    과거 데이터로 전략을 시뮬레이션하고 성과를 분석합니다.
    """
    
    def __init__(self, 
                 initial_capital: float = 10000000,
                 commission_rate: float = 0.00015,  # 0.015% (편도)
                 slippage_rate: float = 0.001):      # 0.1% 슬리피지
        """
        Args:
            initial_capital: 초기 자본금
            commission_rate: 수수료율 (편도)
            slippage_rate: 슬리피지율
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        
        self.logger = setup_logger("Backtest", Config.LOG_DIR, Config.LOG_LEVEL)
        
        # 백테스트 상태
        self.cash = initial_capital
        self.positions = {}  # {symbol: {'qty': int, 'avg_price': float}}
        self.equity_curve = []
        self.trades = []
        self.daily_equity = {}
        
    def calculate_commission(self, price: float, quantity: int) -> float:
        """
        수수료 계산
        
        Args:
            price: 가격
            quantity: 수량
            
        Returns:
            수수료
        """
        return price * quantity * self.commission_rate
    
    def calculate_slippage(self, price: float, is_buy: bool) -> float:
        """
        슬리피지 적용 가격 계산
        
        Args:
            price: 원래 가격
            is_buy: 매수 여부
            
        Returns:
            슬리피지 적용된 가격
        """
        if is_buy:
            return price * (1 + self.slippage_rate)
        else:
            return price * (1 - self.slippage_rate)
    
    def execute_trade(self, symbol: str, action: str, price: float, 
                     quantity: int, date: str) -> bool:
        """
        거래 실행
        
        Args:
            symbol: 종목코드
            action: 'buy' 또는 'sell'
            price: 가격
            quantity: 수량
            date: 거래일
            
        Returns:
            거래 성공 여부
        """
        # 슬리피지 적용
        actual_price = self.calculate_slippage(price, action == 'buy')
        
        # 수수료 계산
        commission = self.calculate_commission(actual_price, quantity)
        
        if action == 'buy':
            total_cost = actual_price * quantity + commission
            
            if total_cost > self.cash:
                self.logger.warning(f"[{date}] 자금 부족: 필요 {total_cost:,.0f}원, 보유 {self.cash:,.0f}원")
                return False
            
            # 매수 실행
            self.cash -= total_cost
            
            if symbol not in self.positions:
                self.positions[symbol] = {'qty': 0, 'avg_price': 0}
            
            # 평균 단가 계산
            old_qty = self.positions[symbol]['qty']
            old_avg = self.positions[symbol]['avg_price']
            new_qty = old_qty + quantity
            new_avg = ((old_avg * old_qty) + (actual_price * quantity)) / new_qty
            
            self.positions[symbol]['qty'] = new_qty
            self.positions[symbol]['avg_price'] = new_avg
            
            self.logger.info(f"[{date}] 매수: {symbol} {quantity}주 @ {actual_price:,.0f}원 (수수료: {commission:,.0f}원)")
            
        elif action == 'sell':
            if symbol not in self.positions or self.positions[symbol]['qty'] < quantity:
                self.logger.warning(f"[{date}] 보유 수량 부족: {symbol}")
                return False
            
            # 매도 실행
            total_revenue = actual_price * quantity - commission
            self.cash += total_revenue
            
            # 포지션 업데이트
            avg_price = self.positions[symbol]['avg_price']
            self.positions[symbol]['qty'] -= quantity
            
            # 손익 계산
            profit = (actual_price - avg_price) * quantity - commission * 2  # 매수/매도 수수료
            profit_pct = ((actual_price - avg_price) / avg_price) * 100
            
            # 거래 기록
            trade_record = {
                'date': date,
                'symbol': symbol,
                'action': 'sell',
                'quantity': quantity,
                'price': actual_price,
                'avg_buy_price': avg_price,
                'profit': profit,
                'profit_pct': profit_pct,
                'commission': commission * 2
            }
            self.trades.append(trade_record)
            
            self.logger.info(f"[{date}] 매도: {symbol} {quantity}주 @ {actual_price:,.0f}원 "
                           f"(손익: {profit:,.0f}원, {profit_pct:.2f}%)")
            
            # 포지션 정리
            if self.positions[symbol]['qty'] == 0:
                del self.positions[symbol]
        
        return True
    
    def calculate_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """
        현재 포트폴리오 가치 계산
        
        Args:
            current_prices: {종목코드: 현재가} 딕셔너리
            
        Returns:
            총 자산 가치
        """
        position_value = sum(
            self.positions[symbol]['qty'] * current_prices.get(symbol, 0)
            for symbol in self.positions
        )
        return self.cash + position_value
    
    def run(self, 
            strategy: BaseStrategy,
            symbols: List[str],
            start_date: str,
            end_date: str,
            broker: Optional[KISBroker] = None,
            db_path: Optional[Path] = None,
            use_fdr: bool = False,
            data_start_date: Optional[str] = None) -> dict:
        """
        백테스트 실행
        
        Args:
            strategy: 전략 객체
            symbols: 종목코드 리스트
            start_date: 백테스트 시작일 (YYYYMMDD) - 실제 거래 시작일
            end_date: 종료일 (YYYYMMDD)
            broker: KISBroker 인스턴스 (없으면 새로 생성)
            db_path: SQLite DB 파일 경로 (있으면 DB 사용)
            use_fdr: FinanceDataReader 사용 여부 (True면 FDR 사용)
            data_start_date: 데이터 로드 시작일 (YYYYMMDD, 워밍업 기간 포함)
                           - 없으면 start_date 사용
                           - 이동평균 등 지표 계산을 위해 start_date보다 이전부터 데이터 로드
            
        Returns:
            백테스트 결과 딕셔너리
        """
        # 워밍업 기간 포함된 데이터 로드 시작일 사용
        actual_data_start = data_start_date if data_start_date else start_date
        
        self.logger.info(f"백테스트 기간: {start_date} ~ {end_date}")
        if data_start_date:
            self.logger.info(f"데이터 로드 기간: {data_start_date} ~ {end_date} (워밍업 포함)")
        self.logger.info(f"초기 자본금: {self.initial_capital:,.0f}원")
        self.logger.info(f"대상 종목: {', '.join(symbols)}")
        
        # 데이터 소스 결정
        from trading_bot.backtest.data_source import BacktestDataSource
        
        if use_fdr:
            # FinanceDataReader에서 데이터 로드
            self.logger.info("FinanceDataReader에서 데이터 로드")
            historical_data = BacktestDataSource.load_from_fdr(
                symbols, actual_data_start, end_date
            )
        elif db_path and Path(db_path).exists():
            # SQLite DB에서 데이터 로드
            self.logger.info(f"DB 파일에서 데이터 로드: {db_path}")
            historical_data = BacktestDataSource.load_from_sqlite(
                Path(db_path), symbols, actual_data_start, end_date
            )
        else:
            # KIS API에서 데이터 로드 (최대 100건)
            self.logger.info("KIS API에서 데이터 로드 (최대 100건)")
            if broker is None:
                broker = KISBroker(env_mode="demo")
            
            historical_data = BacktestDataSource.load_from_api(
                broker, symbols, actual_data_start, end_date
            )
        
        if not historical_data:
            self.logger.error("사용 가능한 데이터가 없습니다")
            return {
                'metrics': {},
                'equity_curve': [],
                'trades': [],
                'final_positions': {},
                'final_cash': self.initial_capital
            }
        
        # 각 종목 데이터 건수 로깅
        for symbol, df in historical_data.items():
            self.logger.info(f"{symbol} 데이터: {len(df)}일")
            
            # 워밍업 기간 충뵡0성 검증
            min_period = getattr(strategy, 'long_period', 20)
            if len(df) < min_period:
                self.logger.warning(f"{symbol} 데이터 부족: {len(df)}일 < {min_period}일 (필요)")
                self.logger.warning(f"  ➜ {symbol} 종목은 백테스트에서 제외됩니다.")
        
        # 충뵡0한 데이터가 있는 종목만 필터링
        min_period = getattr(strategy, 'long_period', 20)
        valid_data = {sym: df for sym, df in historical_data.items() if len(df) >= min_period}
        
        if not valid_data:
            self.logger.error(f"모든 종목의 데이터가 부족합니다 (최소 {min_period}일 필요)")
            self.logger.error(f"해결: --start 날짜를 더 늦게 설정하거나, 더 오래된 데이터를 사용하세요.")
            return {
                'metrics': {},
                'equity_curve': [],
                'trades': [],
                'final_positions': {},
                'final_cash': self.initial_capital
            }
        
        if len(valid_data) < len(historical_data):
            excluded = set(historical_data.keys()) - set(valid_data.keys())
            self.logger.warning(f"데이터 부족으로 제외된 종목: {', '.join(excluded)}")
        
        historical_data = valid_data
        
        # 모든 거래일 수집 (합집합)
        all_dates = set()
        for df in historical_data.values():
            all_dates.update(df['date'].tolist())
        all_dates = sorted(list(all_dates))
        
        if not all_dates:
            self.logger.error("거래일 데이터가 없습니다")
            return {
                'metrics': {},
                'equity_curve': [],
                'trades': [],
                'final_positions': {},
                'final_cash': self.initial_capital
            }
        
        # 실제 백테스트 기간 필터링 (워밍업 기간 제외)
        start_dt = datetime.strptime(start_date, "%Y%m%d")
        backtest_dates = [d for d in all_dates if d >= start_dt]
        
        self.logger.info(f"전체 데이터 기간: {len(all_dates)}일")
        self.logger.info(f"백테스트 거래일: {len(backtest_dates)}일 (워밍업 제외)")
        
        # 시그널 통계
        signal_stats = {'buy': 0, 'sell': 0, 'none': 0, 'data_insufficient': 0}
        
        # 날짜별 시뮬레이션 (워밍업 기간 이후만)
        for idx, date in enumerate(backtest_dates):
            date_str = date.strftime('%Y%m%d')
            
            # 해당 날짜의 가격 정보 수집
            current_prices = {}
            for symbol, df in historical_data.items():
                day_data = df[df['date'] == date]
                if not day_data.empty:
                    current_prices[symbol] = float(day_data.iloc[0]['stck_clpr'])
            
            # 진행상황 로깅 (10% 단위)
            if idx % max(1, len(backtest_dates) // 10) == 0:
                progress = (idx / len(backtest_dates)) * 100
                self.logger.info(f"진행: {progress:.0f}% ({idx}/{len(backtest_dates)}일) - 거래: {len(self.trades)}건, 보유: {len([p for p in self.positions.values() if p['qty'] > 0])}종목")
            
            # 각 종목에 대해 전략 실행
            for symbol in symbols:
                if symbol not in current_prices:
                    continue
                
                # 해당 종목의 과거 데이터 전달
                symbol_data = historical_data[symbol]
                symbol_data_until_now = symbol_data[symbol_data['date'] <= date]
                
                # 전략에 필요한 최소 데이터 확인
                min_period = getattr(strategy, 'long_period', 20)
                if len(symbol_data_until_now) < min_period:
                    signal_stats['data_insufficient'] += 1
                    continue  # 데이터 부족
                
                # 전략 시그널 생성 (첫 10일과 마지막 10일은 디버그 모드)
                debug_mode = idx < 10 or idx >= len(backtest_dates) - 10
                signal = strategy.analyze_data(symbol, symbol_data_until_now, debug=debug_mode)
                
                if signal is None:
                    signal_stats['none'] += 1
                    continue
                
                # 시그널 통계
                if signal['action'] == 'buy':
                    signal_stats['buy'] += 1
                elif signal['action'] == 'sell':
                    signal_stats['sell'] += 1
                
                # 거래 실행
                action = signal['action']
                price = current_prices[symbol]
                
                if action == 'buy':
                    # 가용 자금의 일정 비율로 매수
                    max_investment = min(self.cash * 0.3, Config.MAX_ORDER_AMOUNT)
                    quantity = int(max_investment / price)
                    
                    if quantity > 0:
                        self.execute_trade(symbol, 'buy', price, quantity, date_str)
                
                elif action == 'sell':
                    # 보유 중이면 전량 매도
                    if symbol in self.positions:
                        quantity = self.positions[symbol]['qty']
                        self.execute_trade(symbol, 'sell', price, quantity, date_str)
            
            # 일별 자산 가치 기록
            portfolio_value = self.calculate_portfolio_value(current_prices)
            holdings_count = len([s for s, p in self.positions.items() if p['qty'] > 0])
            self.daily_equity[date_str] = portfolio_value
            self.equity_curve.append({
                'date': date_str,
                'equity': portfolio_value,
                'cash': self.cash,
                'position_value': portfolio_value - self.cash,
                'holdings_count': holdings_count  # 보유 종목 수 추가
            })
        
        # 성과 계산
        equity_series = pd.Series([e['equity'] for e in self.equity_curve])
        metrics = PerformanceMetrics.calculate_all_metrics(
            equity_series, 
            self.trades,
            all_dates[0].strftime('%Y-%m-%d'),
            all_dates[-1].strftime('%Y-%m-%d')
        )
        
        # 시그널 통계 출력
        total_checks = sum(signal_stats.values())
        self.logger.info("\n=== 시그널 통계 ===")
        self.logger.info(f"총 체크: {total_checks}회")
        self.logger.info(f"  매수 시그널: {signal_stats['buy']}회 ({signal_stats['buy']/max(1,total_checks)*100:.1f}%)")
        self.logger.info(f"  매도 시그널: {signal_stats['sell']}회 ({signal_stats['sell']/max(1,total_checks)*100:.1f}%)")
        self.logger.info(f"  시그널 없음: {signal_stats['none']}회 ({signal_stats['none']/max(1,total_checks)*100:.1f}%)")
        self.logger.info(f"  데이터 부족: {signal_stats['data_insufficient']}회 ({signal_stats['data_insufficient']/max(1,total_checks)*100:.1f}%)")
        
        self.logger.info("\n백테스트 완료")
        self.logger.info(f"최종 자산: {metrics['final_capital']:,.0f}원")
        self.logger.info(f"총 수익률: {metrics['total_return_pct']:.2f}%")
        self.logger.info(f"MDD: {metrics['mdd_pct']:.2f}%")
        self.logger.info(f"총 거래: {metrics['total_trades']}회")
        
        return {
            'metrics': metrics,
            'equity_curve': self.equity_curve,
            'trades': self.trades,
            'final_positions': self.positions.copy(),
            'final_cash': self.cash
        }
