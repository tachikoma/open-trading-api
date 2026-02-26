#!/usr/bin/env python3
"""손실 매도 제한 임계값 그리드 백테스트 실행 스크립트.

사용 예시:
    cd trading_bot
    uv run backtest/grid_loss_sell_test.py --thresholds 0,3,5,8 --start 20170101 --end 20241231
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class GridResult:
    threshold_pct: float
    return_pct: float
    mdd_pct: float
    ret_over_mdd: float
    trade_rows: int
    sell_count: int
    win_rate_pct: float
    profit_factor: float
    trades_file: str
    equity_file: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="손실 매도 제한 임계값 그리드 백테스트")
    parser.add_argument("--thresholds", type=str, default="0,3,5,8", help="임계값 목록(%%, 쉼표 구분)")
    parser.add_argument("--start", type=str, default="20170101", help="시작일 YYYYMMDD")
    parser.add_argument("--end", type=str, default="20241231", help="종료일 YYYYMMDD")
    parser.add_argument("--source", type=str, default="fdr", choices=["fdr", "api", "db"], help="데이터 소스")
    parser.add_argument("--log-level", type=str, default="INFO", help="실행 로그 레벨")
    return parser.parse_args()


def parse_thresholds(raw: str) -> list[float]:
    items = [item.strip() for item in raw.split(",") if item.strip()]
    values = [float(item) for item in items]
    if not values:
        raise ValueError("thresholds 값이 비어 있습니다.")
    return values


def run_single(trading_bot_dir: Path, threshold: float, start: str, end: str, source: str, log_level: str) -> GridResult:
    env = os.environ.copy()
    env["LOSS_SELL_BLOCK_ENABLED"] = "1"
    env["LOSS_SELL_BLOCK_THRESHOLD_PERCENT"] = str(threshold)
    env["LOG_LEVEL"] = log_level

    cmd = [
        "uv",
        "run",
        "run_backtest.py",
        "--source",
        source,
        "--start",
        start,
        "--end",
        end,
    ]

    result = subprocess.run(cmd, cwd=trading_bot_dir, env=env, text=True, capture_output=True)
    output = (result.stdout or "") + "\n" + (result.stderr or "")

    if result.returncode != 0:
        raise RuntimeError(f"임계값 {threshold}% 실행 실패 (exit={result.returncode})\n{output[-4000:]}")

    m_ret = re.search(r"총 수익률:\s*([\d\.-]+)%", output)
    m_trade = re.search(r"거래 내역 저장:\s*(.*ma_crossover_fdr_trades_\d{8}_\d{6}\.csv)", output)
    m_equity = re.search(r"자산 곡선 저장:\s*(.*ma_crossover_fdr_equity_\d{8}_\d{6}\.csv)", output)

    if not (m_ret and m_trade and m_equity):
        raise RuntimeError(f"임계값 {threshold}% 실행 결과 파싱 실패\n{output[-4000:]}")

    return_pct = float(m_ret.group(1))
    trades_path = Path(m_trade.group(1).strip())
    equity_path = Path(m_equity.group(1).strip())

    trades_df = pd.read_csv(trades_path)
    sells_df = trades_df[trades_df["action"] == "sell"].copy()
    wins_df = sells_df[sells_df["profit"] > 0]
    losses_df = sells_df[sells_df["profit"] < 0]

    equity_df = pd.read_csv(equity_path)
    peak = equity_df["equity"].cummax()
    drawdown = equity_df["equity"] / peak - 1
    mdd_pct = float(drawdown.min() * 100)

    win_rate_pct = float(len(wins_df) / len(sells_df) * 100) if len(sells_df) else 0.0
    profit_factor = float(wins_df["profit"].sum() / (-losses_df["profit"].sum())) if len(losses_df) else float("inf")

    return GridResult(
        threshold_pct=threshold,
        return_pct=return_pct,
        mdd_pct=mdd_pct,
        ret_over_mdd=return_pct / abs(mdd_pct) if mdd_pct != 0 else float("inf"),
        trade_rows=int(len(trades_df)),
        sell_count=int(len(sells_df)),
        win_rate_pct=win_rate_pct,
        profit_factor=profit_factor,
        trades_file=trades_path.name,
        equity_file=equity_path.name,
    )


def main() -> None:
    args = parse_args()
    thresholds = parse_thresholds(args.thresholds)

    trading_bot_dir = Path(__file__).resolve().parents[1]
    rows: list[GridResult] = []

    print("손실 매도 제한 그리드 테스트 시작")
    print(f"임계값: {thresholds}")
    print(f"기간: {args.start} ~ {args.end}")
    print()

    for threshold in thresholds:
        print(f"[RUN] threshold={threshold}%")
        row = run_single(
            trading_bot_dir=trading_bot_dir,
            threshold=threshold,
            start=args.start,
            end=args.end,
            source=args.source,
            log_level=args.log_level,
        )
        rows.append(row)
        print(f"  -> return={row.return_pct:.2f}%, mdd={row.mdd_pct:.2f}%, score={row.ret_over_mdd:.3f}")

    summary_df = pd.DataFrame([r.__dict__ for r in rows])
    summary_df = summary_df.sort_values("threshold_pct")

    print("\n=== SUMMARY ===")
    print(summary_df.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))

    best = summary_df.sort_values("ret_over_mdd", ascending=False).iloc[0]
    print("\n=== BEST_BY_BALANCE (return/|mdd| 최대) ===")
    print(best.to_string())


if __name__ == "__main__":
    main()
