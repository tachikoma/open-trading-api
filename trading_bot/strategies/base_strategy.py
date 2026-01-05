"""
기본 전략 베이스 클래스

모든 전략은 이 클래스를 상속받아 구현합니다.
"""
from abc import ABC, abstractmethod
from typing import Optional

from trading_bot.broker import KISBroker
from trading_bot.config import Config
from trading_bot.utils.logger import setup_logger


class BaseStrategy(ABC):
    """
    전략 베이스 클래스
    
    모든 전략은 이 클래스를 상속받아 execute() 메서드를 구현해야 합니다.
    """
    
    def __init__(self, broker: KISBroker, name: Optional[str] = None):
        """
        Args:
            broker: KISBroker 인스턴스
            name: 전략 이름 (None이면 클래스명 사용)
        """
        self.broker = broker
        self.name = name or self.__class__.__name__
        self.logger = setup_logger(f"Strategy.{self.name}", Config.LOG_DIR, Config.LOG_LEVEL)
        
        self.logger.info(f"{self.name} 전략 초기화")
    
    @abstractmethod
    def execute(self):
        """
        전략 실행
        
        반드시 구현해야 하는 메서드
        """
        pass
    
    def log_signal(self, symbol: str, signal: str, reason: str):
        """
        시그널 로깅
        
        Args:
            symbol: 종목코드
            signal: 시그널 (BUY, SELL, HOLD)
            reason: 시그널 이유
        """
        self.logger.info(f"[{symbol}] {signal} - {reason}")
