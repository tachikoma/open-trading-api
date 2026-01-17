#!/usr/bin/env python3
"""
간단한 로거 핸들러 중복 테스트
"""
import sys
import logging
from pathlib import Path

# Ensure project root is on sys.path when run as a standalone test
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT.parent))

from trading_bot.utils.logger import setup_logger
from trading_bot.config import Config


def show(logger):
    print("Logger:", logger.name, "handlers:", len(logger.handlers))
    for i, h in enumerate(logger.handlers):
        print(i, type(h).__name__, getattr(h, "stream", None), getattr(h, "baseFilename", None))


if __name__ == "__main__":
    # 첫 호출
    logger1 = setup_logger("Scheduler", Config.LOG_DIR, Config.LOG_LEVEL)
    show(logger1)

    # 두 번째 호출(중복 추가 방지 확인)
    logger2 = setup_logger("Scheduler", Config.LOG_DIR, Config.LOG_LEVEL)
    show(logger2)

    # 루트 로거 상태
    root = logging.getLogger()
    print("Root handlers:", len(root.handlers))
    for i, h in enumerate(root.handlers):
        print(i, type(h).__name__, getattr(h, "stream", None), getattr(h, "baseFilename", None))

    print("Done")
