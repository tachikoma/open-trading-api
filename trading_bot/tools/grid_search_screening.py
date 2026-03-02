#!/usr/bin/env python3
"""
그리드 서치: `MA_SCREENING_MIN_AVG_VALUE` 후보값으로 유니버스 스크리닝을 실행합니다.

Usage (project root):
  uv run trading_bot/tools/grid_search_screening.py --min-avg-values 100000000,500000000,... \
      --universe-target kospi_kosdaq --start 20170101 --end 20241231 --top-n 100

출력:
  - 각 후보에 대해 `trading_bot/backtest_results/ma_crossover_tuned_selected_{target}_{ts}_{min}.csv`
  - 요약 CSV: `trading_bot/backtest_results/ma_crossover_tuned_gridsearch_{target}_{ts}.csv`
"""
import sys
from pathlib import Path
from datetime import datetime
import argparse
import time

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from trading_bot.config import Config
from trading_bot.backtest.data_source import BacktestDataSource
from trading_bot.utils.universe import resolve_universe_symbols
from trading_bot.utils.ma_screening import ScreeningConfig, screen_historical_data


def parse_args():
    p = argparse.ArgumentParser(description="Grid search for MA screening min avg trading value")
    p.add_argument("--min-avg-values", required=True, help="콤마 구분 숫자 목록(원 단위)")
    p.add_argument("--atr-min", type=float, default=Config.MA_SCREENING_ATR_PCT_MIN)
    p.add_argument("--atr-max", type=float, default=Config.MA_SCREENING_ATR_PCT_MAX)
    p.add_argument("--universe-target", type=str, default=Config.UNIVERSE_TARGET)
    p.add_argument("--top-n", type=int, default=Config.MA_SCREENING_TOP_N)
    p.add_argument("--start", type=str, default=None)
    p.add_argument("--end", type=str, default=None)
    p.add_argument("--output-dir", type=str, default=str(Path(__file__).parent.parent / "backtest_results"))
    p.add_argument("--dry-run", action="store_true", help="데이터 다운로드 없이 우선 종목수/설정만 확인")
    return p.parse_args()


def main():
    args = parse_args()
    Config.validate()

    min_values = [int(v.strip()) for v in args.min_avg_values.split(",") if v.strip()]
    atr_min = args.atr_min
    atr_max = args.atr_max
    target = args.universe_target
    top_n = args.top_n
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 시간범위 기본값: run_backtest와 동일 루틴 사용
    if args.end:
        end_date = args.end
    else:
        end_date = datetime.now().strftime("%Y%m%d")

    if args.start:
        start_date = args.start
    else:
        start_date = (datetime.now()).strftime("%Y%m%d")

    # 유니버스 해석
    print(f"유니버스 타깃: {target}")
    uni = resolve_universe_symbols(target=target, default_symbols=list(Config.WATCH_LIST), cache_dir=Config.UNIVERSE_CACHE_DIR, refresh_daily=Config.UNIVERSE_REFRESH_DAILY, max_symbols=Config.UNIVERSE_MAX_SYMBOLS)
    symbols = uni.symbols
    print(f"유니버스 심볼수: {len(symbols)} (예: {symbols[:5]})")

    # 데이터 로드 (한 번만) - FDR 사용
    historical_data = {}
    if args.dry_run:
        print("--dry-run: 데이터 다운로드 생략")
    else:
        print("FinanceDataReader에서 히스토리 데이터 로드(한 번만)")
        historical_data = BacktestDataSource.load_from_fdr(symbols, start_date, end_date)
        print(f"로드된 심볼 수: {len(historical_data)}")

    # 결과 컬렉션
    rows = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    for minv in min_values:
        print(f"\n--- 테스트: MA_SCREENING_MIN_AVG_VALUE={minv:,} ---")
        cfg = ScreeningConfig(min_avg_value=float(minv), adx_threshold=Config.MA_SCREENING_ADX_THRESHOLD, trend_ma_period=Config.MA_SCREENING_TREND_MA_PERIOD, atr_pct_min=atr_min, atr_pct_max=atr_max, top_n=top_n)

        if args.dry_run:
            # dry-run: skip scoring, just record the config
            selected = []
            selected_count = 0
            top10 = []
        else:
            # 백테스트용 참조일자를 넣지 않아 전체 사용 가능 데이터로 스코어링
            selected, selected_df = screen_historical_data(historical_data=historical_data, cfg=cfg, reference_start_date=None)
            selected_count = len(selected)
            top10 = selected[:10]

            # 저장: 선택된 상위 데이터프레임
            if selected_df is not None and not selected_df.empty:
                out_csv = out_dir / f"ma_crossover_tuned_selected_{target}_{ts}_{minv}.csv"
                selected_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
                print(f"CSV 저장: {out_csv} ({len(selected_df)} rows)")

        rows.append({
            "min_avg_value": minv,
            "selected_count": selected_count,
            "top10": ";".join(top10) if top10 else "",
        })

        # API 부담 완화
        time.sleep(0.1)

    summary_df = pd.DataFrame(rows).sort_values("min_avg_value")
    summary_csv = out_dir / f"ma_crossover_tuned_gridsearch_{target}_{ts}.csv"
    summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    print(f"\n그리드 요약 저장: {summary_csv}")
    print(summary_df.to_string(index=False))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
