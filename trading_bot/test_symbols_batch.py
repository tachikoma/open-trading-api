#!/usr/bin/env python3
"""
Batch test multiple symbols against MA_Crossover calculate_ma and get_signal.
Run from trading_bot/: `uv run test_symbols_batch.py`
"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import logging
from trading_bot.config import Config
from trading_bot.broker.kis_broker import KISBroker
from trading_bot.strategies.ma_crossover import MovingAverageCrossover

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_symbols_batch")

SYMBOLS = ["032640", "035720", "005930", "086520"]


def main():
    try:
        Config.validate()
    except Exception as e:
        logger.error(f"Config validation failed: {e}")
        return

    broker = KISBroker(env_mode=Config.ENV_MODE)
    strategy = MovingAverageCrossover(broker)

    all_ok = True
    for s in SYMBOLS:
        logger.info(f"Testing {s}...")
        try:
            ma = strategy.calculate_ma(s)
            logger.info(f"{s} calculate_ma: {ma}")
            sig = strategy.get_signal(s)
            logger.info(f"{s} get_signal: {sig}")
        except Exception as e:
            logger.error(f"{s} test failed: {e}")
            all_ok = False

    if all_ok:
        logger.info("ALL_SYMBOLS_OK")
    else:
        logger.warning("SOME_SYMBOLS_FAILED")

if __name__ == '__main__':
    main()
