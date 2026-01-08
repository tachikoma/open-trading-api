#!/usr/bin/env python3
"""
Simple live test: query MA and signal for a single symbol using KIS API
Run from project root: `cd trading_bot && uv run test_symbol.py`
"""
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path when running from trading_bot/
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.config import Config
from trading_bot.broker.kis_broker import KISBroker
from trading_bot.strategies.ma_crossover import MovingAverageCrossover

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_symbol")

def main(symbol: str = "086520"):
    try:
        Config.validate()
    except Exception as e:
        logger.error(f"Config validation failed: {e}")
        return

    broker = KISBroker(env_mode=Config.ENV_MODE)
    strategy = MovingAverageCrossover(broker)

    logger.info(f"Testing symbol: {symbol} (env={Config.ENV_MODE})")

    # 상세 MA 값
    ma = strategy.calculate_ma(symbol)
    logger.info(f"calculate_ma result: {ma}")

    # 간단 시그널
    signal = strategy.get_signal(symbol)
    logger.info(f"get_signal result: {signal}")

if __name__ == '__main__':
    main()
