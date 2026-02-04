"""
InfiniteBuy 모의투자(Demo) 전용 실행 로직

모의투자는 지정가(LIMIT)만 가능하므로:
- Pre-market(04:00), Regular(09:30), After-hours(16:00)에 각각 재주문
- 시간대별로 가격 조정하여 체결 확률 높임
- 날짜별 각 시간대마다 1회만 실행 (중복 방지)
"""
from typing import Any, Dict, List
from datetime import datetime
import pytz
from trading_bot.utils.market_time import get_us_market_time, get_market_phase


class InfiniteBuyDemoImpl:
    """모의투자 실행 구현"""
    
    def __init__(self, strategy):
        """
        Args:
            strategy: InfiniteBuyBase 인스턴스
        """
        self.strategy = strategy
        self.broker = strategy.broker
        self.logger = strategy.logger
        self.config = strategy.config
    
    def should_execute_today(self) -> tuple:
        """
        오늘 현재 시간대에 실행 가능한지 확인
        
        Returns:
            (실행 가능 여부, 현재 시간대, 마지막 실행 시간대)
        """
        us_time = get_us_market_time()
        current_phase = get_market_phase(us_time)
        date_str = us_time.strftime("%Y-%m-%d")
        
        # 시간대별 실행 기록 확인
        phase_exec_key = f"last_exec_phase_{date_str}"
        last_exec_phase = self.strategy.state.get(phase_exec_key)
        
        # 같은 시간대에 이미 실행했으면 스킵
        if last_exec_phase == current_phase:
            self.logger.info(f"모의투자: {current_phase} 단계에서 이미 실행됨 (스킵)")
            return False, current_phase, last_exec_phase
        
        return True, current_phase, last_exec_phase
    
    def execute(self) -> bool:
        """
        모의투자 실행
        
        Returns:
            실행 성공 여부
        """
        try:
            self.logger.info("=" * 60)
            self.logger.info("[모의투자 무한매수] 실행 시작")
            self.logger.info("=" * 60)
            
            # 실행 가능한지 확인
            should_exec, current_phase, last_phase = self.should_execute_today()
            if not should_exec:
                return False
            
            us_time = get_us_market_time()
            date_str = us_time.strftime("%Y-%m-%d")
            
            # symbols 결정
            symbols = self.config.get('symbols') or self.config.get('watch_list') or []
            if not symbols:
                self.logger.info("심볼이 설정되지 않음 — 실행을 건너뜁니다.")
                return False
            
            self.logger.info(f"현재 시간대: {current_phase} ({us_time.strftime('%H:%M:%S')})")
            self.logger.info(f"대상 심볼: {list(symbols.keys()) if isinstance(symbols, dict) else symbols}")
            
            intents: List[Dict[str, Any]] = []
            
            # ===== 매수 의도 수집 =====
            for sym in (symbols.keys() if isinstance(symbols, dict) else symbols):
                try:
                    price_df = None
                    if self.broker is not None:
                        if hasattr(self.broker, 'get_current_price_overseas'):
                            cfg = self.strategy.cfg_for(sym)
                            exch = cfg.get('exchange', 'NAS')
                            price_df = self.broker.get_current_price_overseas(sym, exch=exch)
                        elif hasattr(self.broker, 'get_current_price'):
                            price_df = self.broker.get_current_price(sym)
                    
                    price = self.strategy._extract_price_from_df(price_df)
                    if price <= 0:
                        self.logger.debug(f"{sym}: 현재가 없음 또는 0, 스킵")
                        continue
                    
                    quote = {'symbol': sym, 'price': price}
                    buy_intents = self.strategy.decide_buy(date_str, quote) or []
                    if isinstance(buy_intents, dict):
                        buy_intents = [buy_intents]
                    intents.extend(buy_intents)
                    
                except Exception as e:
                    self.logger.error(f"{sym}: 매수 의도 생성 중 오류: {e}")
            
            # ===== 매도 의도 수집 =====
            try:
                if self.broker is not None and hasattr(self.broker, 'get_balance_overseas'):
                    ovrs_excg_cd = self.config.get('ovrs_excg_cd', 'NASD')
                    tr_crcy_cd = self.config.get('tr_crcy_cd', 'USD')
                    holdings_df, _ = self.broker.get_balance_overseas(ovrs_excg_cd=ovrs_excg_cd, tr_crcy_cd=tr_crcy_cd)
                    
                    if holdings_df is not None:
                        try:
                            import pandas as _pd
                            if isinstance(holdings_df, _pd.DataFrame) and not holdings_df.empty:
                                for _, row in holdings_df.iterrows():
                                    try:
                                        pos = {
                                            'symbol': row.get('ovrs_pdno') or row.get('pdno') or row.get('symbol'),
                                            'quantity': float(row.get('ord_psbl_qty') or row.get('hldg_qty') or 0),
                                            'avg_price': float(row.get('pchs_avg_pric') or row.get('avg_prc') or 0),
                                            'cum_buy_amt': float(self.strategy.get_cum_buy(row.get('ovrs_pdno') or row.get('pdno'))),
                                        }
                                        market_price = None
                                        try:
                                            market_price = float(row.get('now_pric2') or row.get('last') or None)
                                        except Exception:
                                            market_price = None
                                        
                                        sell_intents = self.strategy.decide_sell(pos, market_price) or []
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
                return False
            
            # ===== 주문 변환 (지정가로) 및 실행 =====
            try:
                # OrderManager를 통해 주문 변환
                from trading_bot.broker.order_manager import OrderManager
                order_manager = OrderManager(env_mode="demo", logger=self.logger)
                transformed_intents = order_manager.transform_intents(intents, us_time)
                
                self.logger.info(f"주문 변환: {len(intents)}개 → {len(transformed_intents)}개")
                for idx, intent in enumerate(transformed_intents, 1):
                    order_type_name = order_manager.get_order_type_name(intent.get('order_type', '00'))
                    self.logger.info(f"  [{idx}] {intent.get('type')} {intent.get('symbol')} "
                                   f"수량:{intent.get('quantity')} 가격:{intent.get('price')} "
                                   f"주문:{order_type_name}")
                
                # 실행
                results = self.broker.execute_intents(transformed_intents, strategy=self.strategy, simulate_only=False)
                self.logger.info(f"의도 실행 결과: {len(results)}개")
                
                # 현재 시간대를 실행 완료로 표시
                phase_exec_key = f"last_exec_phase_{date_str}"
                self.strategy.state[phase_exec_key] = current_phase
                self.logger.info(f"모의투자 {current_phase} 단계 실행 완료로 표시")
                
                return True
                
            except Exception as e:
                self.logger.error(f"실행 중 오류: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"execute() 오류: {e}")
            return False
        finally:
            self.logger.info(f"[모의투자 무한매수] 실행 종료")
