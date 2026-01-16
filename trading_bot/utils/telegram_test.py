#!/usr/bin/env python3
"""Simple uv-run test for Telegram notifier.

Usage:
  # from project root
  uv run trading_bot/utils/telegram_test.py

This script reads `Config` and attempts to send a test message when
`TELEGRAM_ENABLED=1`. It prints the result.
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
    print(f"Testing Telegram (enabled={Config.TELEGRAM_ENABLED})")
    text = f"[Test] trading_bot at {PROJECT_ROOT.name} — env={Config.ENV_MODE}"
    ok = send_telegram_message(text)
    print("Sent:" , ok)


if __name__ == '__main__':
    main()
