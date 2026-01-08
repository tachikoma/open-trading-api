#!/usr/bin/env python3
"""
Test all symbols in Config.WATCH_LIST using MA_Crossover.calculate_ma/get_signal.
Run: `uv run test_watchlist.py` from trading_bot/ (or project root via uv run trading_bot/test_watchlist.py)
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
logger = logging.getLogger("test_watchlist")


def main():
    try:
        Config.validate()
    except Exception as e:
        logger.error(f"Config validation failed: {e}")
        return 2

    broker = KISBroker(env_mode=Config.ENV_MODE)
    strategy = MovingAverageCrossover(broker)

    symbols = Config.WATCH_LIST
    total = len(symbols)
    failures = []

    for i, s in enumerate(symbols, start=1):
        logger.info(f"[{i}/{total}] Testing {s}...")
        try:
            ma = strategy.calculate_ma(s)
            logger.info(f"{s} calculate_ma: {ma}")
            sig = strategy.get_signal(s)
            logger.info(f"{s} get_signal: {sig}")
            if ma is None:
                failures.append((s, 'MA_NONE'))
        except Exception as e:
            logger.error(f"{s} test failed: {e}")
            failures.append((s, str(e)))

    if failures:
        logger.warning(f"{len(failures)}/{total} symbols failed")
        for s, reason in failures:
            logger.warning(f"FAILED: {s} -> {reason}")
        return 1

    logger.info("ALL_WATCHLIST_OK")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
