#!/usr/bin/env python3
"""
ADX/ATR 그리드 탐색: kospi_kosdaq 유니버스에 대해 여러 ADX와 ATR% 범위를 스크리닝합니다.

Usage (project root):
  uv run trading_bot/tools/adx_atr_grid.py

출력:
  - 각 조합별 선택 CSV: trading_bot/backtest_results/ma_crossover_adxatr_{target}_{ts}_{tag}_minavg{min}.csv
  - 요약 CSV: trading_bot/backtest_results/ma_crossover_adxatr_grid_{target}_{ts}.csv
"""
from pathlib import Path
from datetime import datetime
import itertools
import time

# 프로젝트 루트를 sys.path에 자동 추가하는 uv 실행 컨벤션을 따릅니다
import sys
from pathlib import Path as _P
PROJECT_ROOT = _P(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.config import Config
from trading_bot.backtest.data_source import BacktestDataSource
from trading_bot.utils.universe import resolve_universe_symbols
from trading_bot.utils.ma_screening import ScreeningConfig, screen_historical_data
import pandas as pd


def main():
    Config.validate()
    target = 'kospi_kosdaq'
    start = '20170101'
    end = '20241231'
    min_avg = 0
    adx_values = [20, 25, 30, 35]
    atr_pairs = [(1.5, 4.0), (2.0, 5.0), (3.0, 6.0)]
    out_dir = Path(__file__).parent.parent / 'backtest_results'
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    print(f"유니버스 타깃: {target}")
    uni = resolve_universe_symbols(target=target, default_symbols=list(Config.WATCH_LIST), cache_dir=Config.UNIVERSE_CACHE_DIR, refresh_daily=Config.UNIVERSE_REFRESH_DAILY, max_symbols=Config.UNIVERSE_MAX_SYMBOLS)
    symbols = uni.symbols
    print(f"유니버스 심볼수: {len(symbols)}")

    print("FinanceDataReader에서 히스토리 데이터 로드(한 번만)")
    historical_data = BacktestDataSource.load_from_fdr(symbols, start, end)
    print(f"로드된 심볼 수: {len(historical_data)}")

    rows = []

    for adx, (atr_min, atr_max) in itertools.product(adx_values, atr_pairs):
        print(f"\n--- adx={adx} atr={atr_min}-{atr_max} ---")
        cfg = ScreeningConfig(min_avg_value=float(min_avg), adx_threshold=adx, trend_ma_period=Config.MA_SCREENING_TREND_MA_PERIOD, atr_pct_min=atr_min, atr_pct_max=atr_max, top_n=Config.MA_SCREENING_TOP_N)
        selected, selected_df = screen_historical_data(historical_data=historical_data, cfg=cfg, reference_start_date=None)
        sel_count = len(selected)
        top10 = selected[:10]
        tag = f"adx{adx}_atr{atr_min}-{atr_max}".replace('.', 'p')
        if selected_df is not None and not selected_df.empty:
            out_csv = out_dir / f"ma_crossover_adxatr_{target}_{ts}_{tag}_minavg{min_avg}.csv"
            selected_df.to_csv(out_csv, index=False, encoding='utf-8-sig')
            print(f"CSV 저장: {out_csv} ({len(selected_df)} rows)")
        else:
            out_csv = None

        rows.append({
            'adx': adx,
            'atr_min': atr_min,
            'atr_max': atr_max,
            'selected_count': sel_count,
            'top10': ';'.join(top10),
            'selected_csv': out_csv.name if out_csv else ''
        })

        time.sleep(0.1)

    summary_df = pd.DataFrame(rows).sort_values(['adx','atr_min'])
    summary_csv = out_dir / f"ma_crossover_adxatr_grid_{target}_{ts}.csv"
    summary_df.to_csv(summary_csv, index=False, encoding='utf-8-sig')
    print(f"\n그리드 요약 저장: {summary_csv}")
    print(summary_df.to_string(index=False))


if __name__ == '__main__':
    raise SystemExit(main())
