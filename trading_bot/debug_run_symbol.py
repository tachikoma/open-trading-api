#!/usr/bin/env python3
"""
단일 종목 디버그 실행 스크립트

사용법:
    cd trading_bot
    uv run debug_run_symbol.py

주의: `Config.TRADING_ENABLED`가 기본으로 `False`이므로 실제 주문은 실행되지 않습니다.
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.config import Config
from trading_bot.broker import KISBroker
from trading_bot.strategies import MovingAverageCrossover
from trading_bot.utils.logger import setup_logger


def main():
    # 간단한 로거
    logger = setup_logger("DebugRun", Config.LOG_DIR, Config.LOG_LEVEL)

    # 디버그할 단일 종목으로 감시 리스트 교체
    Config.WATCH_LIST = ["267250"]
    logger.info(f"디버그 실행: 감시 목록={Config.WATCH_LIST}")

    # 브로커 및 전략 초기화
    broker = KISBroker(env_mode=Config.ENV_MODE)
    strat = MovingAverageCrossover(broker=broker,
                                   short_period=Config.MA_SHORT_PERIOD,
                                   long_period=Config.MA_LONG_PERIOD)

    # 단일 실행
    logger.info("단일 전략 실행 시작")
    strat.execute()
    logger.info("단일 전략 실행 완료")


if __name__ == "__main__":
    main()
