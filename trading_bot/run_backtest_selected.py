#!/usr/bin/env python3
"""
CSV에 적힌 종목 리스트로 `run_backtest.main()`을 호출해 백테스트를 실행합니다.

Usage:
  uv run trading_bot/run_backtest_selected.py <csv-path> [--start YYYYMMDD] [--end YYYYMMDD]

If no dates provided, defaults are used inside `run_backtest`.
"""
import sys
from pathlib import Path
import pandas as pd

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: uv run trading_bot/run_backtest_selected.py <csv-path> [--start YYYYMMDD] [--end YYYYMMDD]')
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f'CSV not found: {csv_path}')
        sys.exit(1)

    # 읽을 때 심볼을 문자열로 취급해 선행 0이 보존되도록 처리
    df = pd.read_csv(csv_path, dtype={
        'symbol': str
    })
    if 'symbol' not in df.columns:
        print('CSV missing `symbol` column')
        sys.exit(1)

    # 보수적으로 심볼을 6자리로 zero-pad (예: '3230' -> '003230')
    symbols = df['symbol'].astype(str).apply(lambda s: s.zfill(6)).tolist()

    # Build argv for run_backtest
    argv = ['run_backtest.py', '--source', 'fdr', '--symbols'] + symbols
    # Pass optional start/end from caller
    if '--start' in sys.argv:
        i = sys.argv.index('--start')
        if i + 1 < len(sys.argv):
            argv += ['--start', sys.argv[i+1]]
    if '--end' in sys.argv:
        i = sys.argv.index('--end')
        if i + 1 < len(sys.argv):
            argv += ['--end', sys.argv[i+1]]

    # Call the existing run_backtest main()
    import sys
    from pathlib import Path

    # Ensure project root is on sys.path (same logic as run_backtest.py)
    PROJECT_ROOT = Path(__file__).parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    import trading_bot.run_backtest as rb

    old_argv = sys.argv
    try:
        sys.argv = argv
        rb.main()
    finally:
        sys.argv = old_argv
