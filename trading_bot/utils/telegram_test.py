#!/usr/bin/env python3
"""텔레그램 알림 유틸리티의 간단한 테스트 스크립트 (uv run용).

사용법:
  # 프로젝트 루트에서
  uv run trading_bot/utils/telegram_test.py

이 스크립트는 `Config`를 읽고 `TELEGRAM_ENABLED`가 활성화된 경우 테스트 메시지를 전송합니다.
결과를 출력합니다.
"""
import sys
from pathlib import Path

# Ensure project root on path when run directly
# this file is inside trading_bot/utils -> project root is three levels up from file
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.config import Config
from trading_bot.utils.telegram import send_telegram_message


def main():
  print(f"텔레그램 테스트 (enabled={Config.TELEGRAM_ENABLED})")
  text = f"[Test] trading_bot at {PROJECT_ROOT.name} — env={Config.ENV_MODE}"
  ok = send_telegram_message(text)
  print("전송됨:", ok)


if __name__ == '__main__':
    main()
