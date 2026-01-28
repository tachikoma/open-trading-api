"""
간단한 스케줄러

지정된 시간 간격으로 전략을 실행합니다.
"""
import time
from datetime import datetime, time as dt_time
from typing import List
import pytz

try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False

from trading_bot.config import Config
from trading_bot.broker import KISBroker
from trading_bot.utils.logger import setup_logger


class SimpleScheduler:
    """
    간단한 스케줄러
    
    정해진 시간 간격으로 전략을 실행합니다.
    """
    
    def __init__(self, broker: KISBroker, strategies: List):
        """
        Args:
            broker: KISBroker 인스턴스
            strategies: 실행할 전략 리스트
        """
        self.logger = setup_logger("Scheduler", Config.LOG_DIR, Config.LOG_LEVEL)
        self.broker = broker
        self.strategies = strategies
        self.is_running = False
        
        self.logger.info(f"스케줄러 초기화 완료 (전략 수: {len(strategies)})")
    
    def is_market_hours(self) -> bool:
        """
        장 운영 시간인지 확인
        
        Returns:
            장 운영 시간이면 True
        """
        # 한국 시간대 사용
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        
        # 주말 체크
        if now.weekday() >= 5:  # 토요일(5), 일요일(6)
            return False
        
        # 시간 체크 (09:00 ~ 15:30)
        current_time = now.time()
        market_open = dt_time(9, 0)
        market_close = dt_time(15, 30)
        
        return market_open <= current_time <= market_close
    
    def run_strategies(self):
        """전략 실행"""
        if not self.is_market_hours():
            self.logger.info("장 운영 시간이 아닙니다. 전략을 실행하지 않습니다.")
            return
        
        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)
        self.logger.info("=" * 50)
        self.logger.info(f"전략 실행 시작: {now_kst.strftime('%Y-%m-%d %H:%M:%S')} KST")
        self.logger.info("=" * 50)
        
        for strategy in self.strategies:
            try:
                self.logger.info(f"전략 실행: {strategy.__class__.__name__}")
                strategy.execute()
            except Exception as e:
                self.logger.error(f"전략 실행 중 오류 발생 ({strategy.__class__.__name__}): {e}")
        
        self.logger.info("=" * 50)
        self.logger.info("전략 실행 완료")
        self.logger.info("=" * 50)
    
    def start(self):
        """
        스케줄러 시작 (schedule 라이브러리 사용)
        """
        if not SCHEDULE_AVAILABLE:
            self.logger.warning("schedule 패키지가 설치되지 않았습니다. start_simple() 메서드를 사용합니다.")
            return self.start_simple()
        
        self.is_running = True
        self.logger.info(f"스케줄러 시작 (간격: {Config.SCHEDULE_INTERVAL_MINUTES}분)")
        
        # 스케줄 등록
        schedule.every(Config.SCHEDULE_INTERVAL_MINUTES).minutes.do(self.run_strategies)
        
        # 즉시 한 번 실행
        self.run_strategies()
        
        # 스케줄 루프
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("사용자에 의해 중단되었습니다.")
            self.stop()
    
    def start_simple(self):
        """
        스케줄러 시작 (단순 time.sleep 방식)
        
        schedule 라이브러리 없이 간단한 루프로 구현
        """
        self.is_running = True
        self.logger.info(f"스케줄러 시작 (간격: {Config.SCHEDULE_INTERVAL_MINUTES}분)")
        
        try:
            while self.is_running:
                self.run_strategies()
                
                # 다음 실행까지 대기
                wait_seconds = Config.SCHEDULE_INTERVAL_MINUTES * 60
                self.logger.info(f"{Config.SCHEDULE_INTERVAL_MINUTES}분 후 다음 실행...")
                time.sleep(wait_seconds)
        except KeyboardInterrupt:
            self.logger.info("사용자에 의해 중단되었습니다.")
            self.stop()
    
    def stop(self):
        """스케줄러 중지"""
        self.is_running = False
        self.logger.info("스케줄러 중지")
