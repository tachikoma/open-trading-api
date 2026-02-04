"""
환경별(모의투자/실전투자) 주문 관리 클래스

모의투자(demo): 지정가(LIMIT)만 가능 → 시간대별 재주문
실전투자(real): LOC/MOC 등 사용 → 1회 주문 후 자동 실행
"""
import math
from typing import List, Dict, Any
from trading_bot.utils.logger import setup_logger
from trading_bot.utils.market_time import (
    get_market_phase, is_pre_market, is_regular_hours, is_after_hours
)
from datetime import datetime
import pytz


class OrderManager:
    """환경별 주문 전략 관리"""
    
    def __init__(self, env_mode: str = "demo", logger=None):
        """
        Args:
            env_mode: 'real' (실전투자) 또는 'demo' (모의투자)
            logger: 로거 (없으면 생성)
        """
        self.env_mode = env_mode
        self.logger = logger or setup_logger("OrderManager")
    
    def transform_intents(self, intents: List[Dict[str, Any]], us_time: datetime = None) -> List[Dict[str, Any]]:
        """
        주문 의도를 환경에 맞게 변환
        
        Args:
            intents: 변환할 주문 의도 리스트
            us_time: 미국 동부 시간 (None이면 현재 시간)
        
        Returns:
            변환된 주문 의도 리스트
        """
        if not intents:
            return []
        
        if self.env_mode == "demo":
            return self._transform_demo_intents(intents, us_time)
        else:
            return self._transform_real_intents(intents, us_time)
    
    def _transform_demo_intents(self, intents: List[Dict[str, Any]], us_time: datetime = None) -> List[Dict[str, Any]]:
        """모의투자: 모든 주문을 지정가(LIMIT)로 변환"""
        if us_time is None:
            us_time = datetime.now(pytz.timezone('US/Eastern'))
        
        phase = get_market_phase(us_time)
        modified = []
        
        for intent in intents:
            intent_copy = dict(intent)
            
            # 모든 주문을 지정가로 변환
            intent_copy['order_type'] = '00'  # 지정가
            intent_copy['original_order_type'] = intent.get('order_type', 'LIMIT')
            intent_copy['env_mode'] = 'demo'
            intent_copy['market_phase'] = phase
            
            # 시간대별로 가격 조정 (체결 확률 높이기 위함)
            if is_pre_market(us_time):
                # Pre-market: 매수는 약간 낮춤, 매도는 약간 높임
                if intent.get('type') == 'buy':
                    intent_copy['price'] = self._adjust_price_down(intent_copy.get('price', 0))
                elif intent.get('type') == 'sell':
                    intent_copy['price'] = self._adjust_price_up(intent_copy.get('price', 0))
                intent_copy['note'] = f"{intent_copy.get('note', '')} [demo:pre_market_limit]"
            
            elif is_after_hours(us_time):
                # After-hours: 매수는 약간 낮춤, 매도는 약간 높임
                if intent.get('type') == 'buy':
                    intent_copy['price'] = self._adjust_price_down(intent_copy.get('price', 0))
                elif intent.get('type') == 'sell':
                    intent_copy['price'] = self._adjust_price_up(intent_copy.get('price', 0))
                intent_copy['note'] = f"{intent_copy.get('note', '')} [demo:after_hours_limit]"
            
            else:
                # Regular: 원본 가격 유지
                intent_copy['note'] = f"{intent_copy.get('note', '')} [demo:regular_limit]"
            
            modified.append(intent_copy)
            self.logger.debug(f"Demo 변환: {intent.get('type')} {intent.get('symbol')} - "
                            f"원본:{intent.get('order_type')} → 변환:LIMIT")
        
        return modified
    
    def _transform_real_intents(self, intents: List[Dict[str, Any]], us_time: datetime = None) -> List[Dict[str, Any]]:
        """실전투자: 시간대에 맞는 주문 유형 적용"""
        if us_time is None:
            us_time = datetime.now(pytz.timezone('US/Eastern'))
        
        phase = get_market_phase(us_time)
        modified = []
        
        for intent in intents:
            intent_copy = dict(intent)
            intent_copy['env_mode'] = 'real'
            intent_copy['market_phase'] = phase
            
            intent_type = intent.get('type')
            original_order_type = intent.get('order_type', 'LIMIT')
            
            if is_pre_market(us_time):
                # Pre-market: LOO(장개시지정가) 또는 MOO(장개시시장가)
                if intent_type == 'buy':
                    intent_copy['order_type'] = '32'  # LOO(장개시지정가)
                    intent_copy['note'] = f"{intent_copy.get('note', '')} [real:LOO_pre_market]"
                elif intent_type == 'sell':
                    intent_copy['order_type'] = '31'  # MOO(장개시시장가)
                    intent_copy['note'] = f"{intent_copy.get('note', '')} [real:MOO_pre_market]"
            
            elif is_after_hours(us_time):
                # After-hours: LOC(장마감지정가) 또는 MOC(장마감시장가)
                if intent_type == 'buy':
                    intent_copy['order_type'] = '34'  # LOC(장마감지정가)
                    intent_copy['note'] = f"{intent_copy.get('note', '')} [real:LOC_after_hours]"
                elif intent_type == 'sell':
                    intent_copy['order_type'] = '33'  # MOC(장마감시장가)
                    intent_copy['note'] = f"{intent_copy.get('note', '')} [real:MOC_after_hours]"
            
            else:
                # Regular: 원본 주문 유형 유지
                intent_copy['note'] = f"{intent_copy.get('note', '')} [real:regular_hours]"
            
            modified.append(intent_copy)
            self.logger.debug(f"Real 변환: {intent_type} {intent.get('symbol')} - "
                            f"원본:{original_order_type} → 변환:{intent_copy.get('order_type')} ({phase})")
        
        return modified
    
    @staticmethod
    def _adjust_price_down(price: float, percent: float = 2.0) -> float:
        """
        가격을 아래로 조정 (매수 주문 체결 확률 높임)
        
        Args:
            price: 원본 가격
            percent: 하락 비율 (%)
        
        Returns:
            조정된 가격
        """
        if price <= 0:
            return price
        adjusted = price * (1.0 - percent / 100.0)
        return round(adjusted, 2)
    
    @staticmethod
    def _adjust_price_up(price: float, percent: float = 2.0) -> float:
        """
        가격을 위로 조정 (매도 주문 체결 확률 높임)
        
        Args:
            price: 원본 가격
            percent: 상승 비율 (%)
        
        Returns:
            조정된 가격
        """
        if price <= 0:
            return price
        adjusted = price * (1.0 + percent / 100.0)
        return round(adjusted, 2)
    
    def should_reorder(self, current_phase: str, last_exec_phase: str = None) -> bool:
        """
        재주문 여부 결정
        
        모의투자: 시간대 변경 시 재주문
        실전투자: 재주문 불필요 (LOC/MOC는 자동 실행)
        
        Args:
            current_phase: 현재 시장 단계
            last_exec_phase: 마지막 실행 단계
        
        Returns:
            재주문 여부
        """
        if self.env_mode == "demo":
            # 모의투자: 다른 시간대이면 재주문
            return last_exec_phase is None or last_exec_phase != current_phase
        else:
            # 실전투자: 재주문 불필요
            return False
    
    def get_order_type_name(self, order_type: str) -> str:
        """주문 유형 코드를 한글 이름으로 변환"""
        order_type_map = {
            '00': '지정가',
            '31': 'MOO(장개시시장가)',
            '32': 'LOO(장개시지정가)',
            '33': 'MOC(장마감시장가)',
            '34': 'LOC(장마감지정가)',
        }
        return order_type_map.get(order_type, f'알수없음({order_type})')
