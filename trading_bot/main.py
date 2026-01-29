"""
자동매매 봇 메인 실행 파일

이 파일을 직접 실행하지 마세요!
프로젝트 루트의 run_bot.py를 사용하세요:

    cd /path/to/open-trading-api
    uv run run_bot.py
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.config import Config
from trading_bot.broker import KISBroker
from trading_bot.strategies.registry import load_enabled_strategies
from trading_bot.scheduler import SimpleScheduler
from trading_bot.utils.logger import setup_logger


def main():
    """메인 함수"""
    # 설정 검증
    Config.validate()
    
    # 로거 설정
    logger = setup_logger("Main", Config.LOG_DIR, Config.LOG_LEVEL)
    
    logger.info("=" * 70)
    logger.info("KIS 자동매매 봇 시작")
    logger.info("=" * 70)
    logger.info(f"환경 모드: {Config.ENV_MODE}")
    logger.info(f"거래 활성화: {Config.TRADING_ENABLED}")
    logger.info(f"스케줄 간격: {Config.SCHEDULE_INTERVAL_MINUTES}분")
    logger.info(f"감시 종목: {Config.WATCH_LIST}")
    logger.info("=" * 70)
    
    try:
        # KIS Broker 초기화
        logger.info("KIS Broker 초기화 중...")
        broker = KISBroker(env_mode=Config.ENV_MODE)
        
        # 전략 초기화 (동적 레지스트리 사용)
        logger.info("전략 초기화 중...")
        strategies = load_enabled_strategies(Config.STRATEGIES_ENABLED, broker)
        
        # 스케줄러 초기화
        logger.info("스케줄러 초기화 중...")
        scheduler = SimpleScheduler(broker=broker, strategies=strategies)
        
        # 스케줄러 시작
        logger.info("스케줄러 시작...")
        logger.info("=" * 70)
        
        # schedule 라이브러리 사용 (설치 필요)
        # scheduler.start()
        
        # 또는 단순 time.sleep 방식 (라이브러리 불필요)
        scheduler.start_simple()
        
    except KeyboardInterrupt:
        logger.info("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"오류 발생: {e}", exc_info=True)
    finally:
        logger.info("=" * 70)
        logger.info("KIS 자동매매 봇 종료")
        logger.info("=" * 70)


if __name__ == "__main__":
    main()
