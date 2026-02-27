"""
MA 교차 전략용 유니버스 스크리닝 유틸리티.

실거래/백테스트에서 동일한 필터를 재사용합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd


@dataclass
class ScreeningConfig:
    min_avg_value: float = 10_000_000_000
    adx_threshold: float = 25.0
    trend_ma_period: int = 60
    atr_pct_min: float = 1.5
    atr_pct_max: float = 8.0
    top_n: int = 20


def to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")


def pick_col(df: pd.DataFrame, candidates: list[str], must_numeric: bool = True) -> Optional[str]:
    for candidate in candidates:
        if candidate in df.columns:
            if not must_numeric:
                return candidate
            converted = to_float(df[candidate])
            if converted.notna().sum() > 0:
                return candidate

    if must_numeric:
        for col in df.columns:
            lc = col.lower()
            if any(keyword in lc for keyword in ["close", "clpr", "high", "low", "open", "volume", "vol"]):
                converted = to_float(df[col])
                if converted.notna().sum() > 0:
                    return col
    return None


def normalize_ohlcv(raw: pd.DataFrame) -> Optional[pd.DataFrame]:
    if raw is None or raw.empty:
        return None

    date_col = pick_col(raw, ["stck_bsop_date", "xymd", "date"], must_numeric=False)
    open_col = pick_col(raw, ["stck_oprc", "open"])
    high_col = pick_col(raw, ["stck_hgpr", "high"])
    low_col = pick_col(raw, ["stck_lwpr", "low"])
    close_col = pick_col(raw, ["stck_clpr", "close", "stck_prpr", "prpr"])
    volume_col = pick_col(raw, ["acml_vol", "cntg_vol", "volume", "vol"])

    required = [open_col, high_col, low_col, close_col, volume_col]
    if any(col is None for col in required):
        return None

    df = pd.DataFrame(
        {
            "open": to_float(raw[open_col]),
            "high": to_float(raw[high_col]),
            "low": to_float(raw[low_col]),
            "close": to_float(raw[close_col]),
            "volume": to_float(raw[volume_col]),
        }
    )

    if date_col is not None:
        dates = pd.to_datetime(raw[date_col].astype(str), errors="coerce")
        df["date"] = dates
        df = df.sort_values("date").reset_index(drop=True)
    else:
        df = df.iloc[::-1].reset_index(drop=True)

    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    if df.empty:
        return None
    return df


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    tr1 = (high - low).abs()
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = true_range.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr

    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, pd.NA)) * 100
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = (high - low).abs()
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def score_ohlcv(df: pd.DataFrame, cfg: ScreeningConfig) -> Optional[dict]:
    min_needed = max(30, cfg.trend_ma_period + 2)
    if df is None or len(df) < min_needed:
        return None

    work = df.copy()
    work["trading_value"] = work["close"] * work["volume"]

    avg_trading_value_20 = float(work["trading_value"].rolling(20).mean().iloc[-1])
    adx = float(compute_adx(work, period=14).iloc[-1])
    atr = float(compute_atr(work, period=14).iloc[-1])
    close = float(work["close"].iloc[-1])
    ma_trend = float(work["close"].rolling(cfg.trend_ma_period).mean().iloc[-1])
    atr_pct = (atr / close) * 100 if close > 0 else 0.0

    pass_liquidity = avg_trading_value_20 >= cfg.min_avg_value
    pass_adx = adx >= cfg.adx_threshold
    pass_trend = close > ma_trend
    pass_volatility = cfg.atr_pct_min <= atr_pct <= cfg.atr_pct_max
    passed = pass_liquidity and pass_adx and pass_trend and pass_volatility

    return {
        "close": close,
        "avg_trading_value_20": avg_trading_value_20,
        "adx": adx,
        "atr": atr,
        "atr_pct": atr_pct,
        "ma_trend": ma_trend,
        "pass_liquidity": pass_liquidity,
        "pass_adx": pass_adx,
        "pass_trend": pass_trend,
        "pass_volatility": pass_volatility,
        "passed": passed,
    }


def screen_symbols_with_broker(
    symbols: Iterable[str],
    broker,
    cfg: ScreeningConfig,
    lookback_days: int = 370,
) -> Tuple[list[str], pd.DataFrame]:
    rows = []
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y%m%d")

    for symbol in symbols:
        raw = broker.get_period_price(symbol, start_date=start_date, end_date=end_date, period="D")
        ohlcv = normalize_ohlcv(raw)
        score = score_ohlcv(ohlcv, cfg)
        if score is None:
            continue
        score["symbol"] = symbol
        rows.append(score)

    if not rows:
        return [], pd.DataFrame()

    df = pd.DataFrame(rows)
    selected_df = df[df["passed"]].sort_values(["avg_trading_value_20", "adx"], ascending=[False, False])
    selected = selected_df["symbol"].head(cfg.top_n).tolist()
    return selected, selected_df


def screen_historical_data(
    historical_data: Dict[str, pd.DataFrame],
    cfg: ScreeningConfig,
    reference_start_date: Optional[str] = None,
) -> Tuple[list[str], pd.DataFrame]:
    """
    백테스트용 스크리닝.

    reference_start_date가 주어지면 해당 날짜 이전 데이터만 사용하여
    종목을 선별해 look-ahead bias를 방지합니다.
    """
    rows = []
    ref_dt = None
    if reference_start_date:
        ref_dt = datetime.strptime(reference_start_date, "%Y%m%d")

    for symbol, raw in historical_data.items():
        ohlcv = normalize_ohlcv(raw)
        if ohlcv is None:
            continue

        eval_df = ohlcv
        if ref_dt is not None and "date" in ohlcv.columns:
            eval_df = ohlcv[ohlcv["date"] < pd.Timestamp(ref_dt)]

        score = score_ohlcv(eval_df, cfg)
        if score is None:
            continue
        score["symbol"] = symbol
        rows.append(score)

    if not rows:
        return [], pd.DataFrame()

    df = pd.DataFrame(rows)
    selected_df = df[df["passed"]].sort_values(["avg_trading_value_20", "adx"], ascending=[False, False])
    selected = selected_df["symbol"].head(cfg.top_n).tolist()
    return selected, selected_df
