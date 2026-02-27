#!/usr/bin/env python3
"""
국내주식 유니버스(후보군) 갱신 스크립트.

실행:
  cd trading_bot
  uv run run_update_universe.py --target kospi200_kosdaq150
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.config import Config
from trading_bot.utils.universe import resolve_universe_symbols


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="유니버스 캐시 갱신")
    parser.add_argument(
        "--target",
        type=str,
        default=Config.UNIVERSE_TARGET,
        help="watchlist/kospi/kosdaq/kospi_kosdaq/kospi200/kosdaq150/kospi200_kosdaq150",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=Config.UNIVERSE_MAX_SYMBOLS,
        help="최대 종목 수 제한 (0=무제한)",
    )
    parser.add_argument(
        "--no-daily-refresh",
        action="store_true",
        help="일자별 파일 대신 고정 파일 사용",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="캐시 파일이 있어도 강제로 재생성",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    result = resolve_universe_symbols(
        target=args.target,
        default_symbols=list(Config.WATCH_LIST),
        cache_dir=Config.UNIVERSE_CACHE_DIR,
        refresh_daily=not args.no_daily_refresh,
        max_symbols=args.max_symbols,
        force_refresh=args.force,
    )

    print("\n=== Universe Update ===")
    print(f"target: {result.target}")
    print(f"count : {len(result.symbols)}")
    if result.csv_path:
        print(f"file  : {result.csv_path}")
    else:
        print("file  : (watchlist 모드)")

    print("\n상위 20개 종목:")
    for symbol in result.symbols[:20]:
        print(symbol)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
