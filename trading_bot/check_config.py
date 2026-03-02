#!/usr/bin/env python3
"""
간단한 설정 확인 스크립트
uv run trading_bot/check_config.py
"""
from pathlib import Path
import sys

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.config import Config


def main():
    print("Config values loaded:")
    print(f"  MA_SCREENING_ENABLED = {Config.MA_SCREENING_ENABLED}")
    print(f"  MA_SCREENING_TOP_N    = {Config.MA_SCREENING_TOP_N}")
    print(f"  MA_SCREENING_MIN_AVG_VALUE = {Config.MA_SCREENING_MIN_AVG_VALUE}")
    print(f"  MA_SCREENING_ATR_PCT_MIN = {Config.MA_SCREENING_ATR_PCT_MIN}")
    print(f"  MA_SCREENING_ATR_PCT_MAX = {Config.MA_SCREENING_ATR_PCT_MAX}")
    print(f"  MA_SCREENING_ADX_THRESHOLD = {Config.MA_SCREENING_ADX_THRESHOLD}")
    print(f"  UNIVERSE_MAX_SYMBOLS = {Config.UNIVERSE_MAX_SYMBOLS}")
    print(f"  UNIVERSE_TARGET = {Config.UNIVERSE_TARGET}")


if __name__ == '__main__':
    main()
