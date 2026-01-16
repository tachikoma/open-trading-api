#!/usr/bin/env python3
"""간단한 로그 회전 테스트 스크립트

이 스크립트는 `trading_bot.utils.logger.setup_logger`로 로거를 초기화하고
짧은 메시지를 다수 출력하여 파일 회전 동작을 검증합니다.
"""
import os
import sys
import time
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (uv run으로 직접 실행할 때도 import 가능하도록)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.config import Config
from trading_bot.utils.logger import setup_logger


def main():
    # 설정 로드(이미 Config가 .env를 읽음)
    Config.validate()

    # 모듈 로거 설정
    logger = setup_logger("ForceRotateTest", Config.LOG_DIR, Config.LOG_LEVEL)

    # 대량 로그 출력
    for i in range(2000):
        logger.info(f"test-message {i} " + ("x" * 200))
        if i % 200 == 0:
            time.sleep(0.01)

    print("done")


if __name__ == "__main__":
    main()
