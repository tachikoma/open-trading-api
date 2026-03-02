#!/usr/bin/env python3
"""
MA 교차 전략용 종목 스크리너

4가지 기준으로 후보 종목을 선별합니다.
1) 유동성(20일 평균 거래대금)
2) 추세 강도(ADX)
3) 장기 추세(현재가 > 장기 MA)
4) 변동성(ATR 비율 범위)

실행 예시 (trading_bot 폴더 기준):
    uv run examples/ma_universe_screen.py --top-n 20

프로젝트 루트 기준:
    uv run trading_bot/examples/ma_universe_screen.py --top-n 20
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.config import Config
from trading_bot.broker.kis_broker import KISBroker
from trading_bot.broker.auth_utils import TokenRefreshError
from trading_bot.utils.ma_screening import ScreeningConfig, screen_symbols_with_broker, diagnose_symbols_with_broker


def _load_symbols(path: Optional[str]) -> list[str]:
    if not path:
        return list(Config.WATCH_LIST)

    file_path = Path(path)
    rows = [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines()]
    symbols = [row for row in rows if row and not row.startswith("#")]
    return symbols


def _format_money(value: float) -> str:
    return f"{value:,.0f}"


def run(
    symbols: list[str],
    env_mode: str,
    min_avg_value: float,
    adx_threshold: float,
    trend_ma_period: int,
    atr_pct_min: float,
    atr_pct_max: float,
    top_n: int,
    output_csv: Optional[str],
    debug_screen: bool,
) -> int:
    Config.validate()
    try:
        broker = KISBroker(env_mode=env_mode)
    except Exception as e:
        print(f"브로커 초기화 실패: {e}")
        print("확인 항목:")
        print("1) ~/KIS/config/kis_devlp.yaml 설정이 올바른지 확인")
        print(f"2) 현재 실행 모드(--env-mode): {env_mode}")
        print("   - 실전: my_app/my_sec")
        print("   - 모의: paper_app/paper_sec")
        print("3) 필요 시 --env-mode demo 로 재시도")
        return 1

    cfg = ScreeningConfig(
        min_avg_value=min_avg_value,
        adx_threshold=adx_threshold,
        trend_ma_period=trend_ma_period,
        atr_pct_min=atr_pct_min,
        atr_pct_max=atr_pct_max,
        top_n=top_n,
    )

    try:
        selected, passed_df = screen_symbols_with_broker(
            symbols=symbols,
            broker=broker,
            cfg=cfg,
        )
    except TokenRefreshError as e:
        print(f"토큰 재발급 실패로 스크리닝을 중단합니다: {e}")
        print("실전 모드라면 my_app/my_sec, 모의 모드라면 paper_app/paper_sec를 확인하세요.")
        return 1

    if passed_df is None or passed_df.empty:
        print("조건 계산 가능한 종목이 없습니다.")
        if debug_screen:
            diag_df = diagnose_symbols_with_broker(symbols=symbols, broker=broker, cfg=cfg)
            if diag_df is not None and not diag_df.empty:
                print("\n=== 디버그: 계산 불가 원인 ===")
                columns = [
                    "symbol",
                    "reason",
                    "raw_rows",
                    "rows_after_dropna",
                    "min_needed_rows",
                    "open_col",
                    "high_col",
                    "low_col",
                    "close_col",
                    "volume_col",
                    "missing_required",
                    "pass_liquidity",
                    "pass_adx",
                    "pass_trend",
                    "pass_volatility",
                ]
                available_cols = [col for col in columns if col in diag_df.columns]
                preview = diag_df[available_cols].copy()

                if "reason" in preview.columns:
                    unscorable = preview[preview["reason"] != "filtered_out"]
                    filtered = preview[preview["reason"] == "filtered_out"]

                    if not unscorable.empty:
                        print("\n[진짜 계산 불가]")
                        print(unscorable.sort_values(["reason", "symbol"]).to_string(index=False))
                    else:
                        print("\n[진짜 계산 불가]")
                        print("없음")

                    if not filtered.empty:
                        print("\n[조건 미통과(filtered_out)]")
                        print(filtered.sort_values(["symbol"]).to_string(index=False))
                else:
                    print(preview.to_string(index=False))
        return 1

    print("\n=== 스크리닝 요약 ===")
    print(f"최종 통과: {len(passed_df)}")

    preview = passed_df.head(top_n)
    if preview.empty:
        print("통과 종목이 없습니다.")
    else:
        print("\n=== 통과 상위 종목 ===")
        for _, row in preview.iterrows():
            print(
                f"{row['symbol']} | 거래대금20={_format_money(row['avg_trading_value_20'])} | "
                f"ADX={row['adx']:.2f} | ATR%={row['atr_pct']:.2f}% | "
                f"Close={row['close']:.0f} > MA{trend_ma_period}={row['ma_trend']:.0f}"
            )

    if output_csv:
        out_path = Path(output_csv)
    else:
        out_dir = Path(__file__).parent.parent / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"ma_screen_{now}.csv"

    passed_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\nCSV 저장: {out_path}")

    print("\nWATCH_LIST 반영용 예시:")
    print("WATCH_LIST = [")
    for symbol in selected:
        print(f'    "{symbol}",')
    print("]")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MA 교차 전략용 종목 스크리너")
    parser.add_argument("--env-mode", default=Config.ENV_MODE, choices=["real", "demo"], help="KIS 환경 모드")
    parser.add_argument(
        "--symbols-file",
        default="",
        help="종목코드 파일 경로(한 줄 1종목). 미지정 시 Config.WATCH_LIST 사용",
    )
    parser.add_argument(
        "--min-avg-value",
        type=float,
        default=10_000_000_000,
        help="20일 평균 거래대금 최소값(원). 기본 100억",
    )
    parser.add_argument("--adx-threshold", type=float, default=25.0, help="ADX 최소 기준")
    parser.add_argument(
        "--trend-ma-period",
        type=int,
        default=60,
        help="장기 추세 MA 기간 (기본 60, 데이터 충분 시 120/200 사용)",
    )
    parser.add_argument("--atr-pct-min", type=float, default=1.5, help="ATR%% 최소")
    parser.add_argument("--atr-pct-max", type=float, default=8.0, help="ATR%% 최대")
    parser.add_argument("--top-n", type=int, default=20, help="상위 출력 종목 수")
    parser.add_argument("--output-csv", default="", help="결과 CSV 저장 경로")
    parser.add_argument("--debug-screen", action="store_true", help="계산 불가 종목의 상세 원인 출력")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    symbols = _load_symbols(args.symbols_file)
    if not symbols:
        print("대상 종목이 없습니다.")
        return 1

    output_csv = args.output_csv or None

    return run(
        symbols=symbols,
        env_mode=args.env_mode,
        min_avg_value=args.min_avg_value,
        adx_threshold=args.adx_threshold,
        trend_ma_period=args.trend_ma_period,
        atr_pct_min=args.atr_pct_min,
        atr_pct_max=args.atr_pct_max,
        top_n=args.top_n,
        output_csv=output_csv,
        debug_screen=args.debug_screen,
    )


if __name__ == "__main__":
    raise SystemExit(main())
