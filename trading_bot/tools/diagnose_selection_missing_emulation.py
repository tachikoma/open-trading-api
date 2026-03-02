#!/usr/bin/env python3
"""
선택 리스트 미체결 심볼에 대해 엔진 규칙을 모사해 빠르게 원인 비율을 추정합니다.

생성: `trading_bot/backtest_results/diagnose_selection_missing_emulation_<ts>.csv`

모사 항목:
 - 데이터/히스토리 부족
 - MA 신호 유무
 - 가격에 따른 수량 0 여부 (`Config.MAX_ORDER_AMOUNT`)
 - 스크리닝(평균거래대금, ATR%) 기준 미달

사용법:
 uv run trading_bot/tools/diagnose_selection_missing_emulation.py
"""
import sys
from pathlib import Path
from datetime import datetime
import json
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.config import Config
from trading_bot.backtest.data_source import BacktestDataSource


def compute_atr_pct(df, period=14):
    # df must have stck_hgpr, stck_lwpr, stck_clpr
    if not all(c in df.columns for c in ('stck_hgpr', 'stck_lwpr', 'stck_clpr')):
        return None
    high = pd.to_numeric(df['stck_hgpr'], errors='coerce')
    low = pd.to_numeric(df['stck_lwpr'], errors='coerce')
    close = pd.to_numeric(df['stck_clpr'], errors='coerce')
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    # ATR percent: latest ATR / latest close * 100
    try:
        atr_pct = (atr.iloc[-1] / close.iloc[-1]) * 100.0
        return float(atr_pct)
    except Exception:
        return None


def diagnose_emulation(symbols, start_date: str, end_date: str):
    results = []

    for sym in symbols:
        rec = {
            'symbol': sym,
            'len_history': 0,
            'data_missing': False,
            'has_signal': False,
            'quantity_zero_on_signal': False,
            'avg_turnover': None,
            'atr_pct': None,
            'passes_screening': True,
            'primary_reason': ''
        }

        try:
            data_map = BacktestDataSource.load_from_fdr([sym], start_date, end_date)
        except Exception:
            data_map = None

        if not data_map or sym not in data_map or data_map[sym] is None or data_map[sym].empty:
            rec['data_missing'] = True
            rec['primary_reason'] = 'data_missing'
            results.append(rec)
            continue

        df = data_map[sym].copy()
        # find close
        if 'stck_clpr' in df.columns:
            df['close'] = pd.to_numeric(df['stck_clpr'], errors='coerce')
        else:
            # fallback numeric column
            for c in df.columns:
                if pd.api.types.is_numeric_dtype(df[c]):
                    df['close'] = pd.to_numeric(df[c], errors='coerce')
                    break

        df = df.dropna(subset=['close']).reset_index(drop=True)
        rec['len_history'] = len(df)

        if len(df) < Config.MA_LONG_PERIOD:
            rec['primary_reason'] = 'insufficient_history'
            results.append(rec)
            continue

        # MA signals
        short = Config.MA_SHORT_PERIOD
        long = Config.MA_LONG_PERIOD
        df['ma_short'] = df['close'].rolling(window=short).mean()
        df['ma_long'] = df['close'].rolling(window=long).mean()

        signal_dates = []
        for i in range(long, len(df)):
            prev_short = df.loc[i-1, 'ma_short']
            prev_long = df.loc[i-1, 'ma_long']
            cur_short = df.loc[i, 'ma_short']
            cur_long = df.loc[i, 'ma_long']
            if pd.isna(prev_short) or pd.isna(prev_long) or pd.isna(cur_short) or pd.isna(cur_long):
                continue
            if prev_short <= prev_long and cur_short > cur_long:
                signal_dates.append(i)

        if signal_dates:
            rec['has_signal'] = True
            # price at first signal
            price_at_signal = float(df.loc[signal_dates[0], 'close'])
            if price_at_signal > Config.MAX_ORDER_AMOUNT:
                rec['quantity_zero_on_signal'] = True
                rec['primary_reason'] = 'quantity_zero'

        else:
            rec['has_signal'] = False
            rec['primary_reason'] = 'no_signal'

        # screening emulation: avg turnover, ATR%
        try:
            # average daily turnover over last N days (use trend period)
            trend_period = max(30, getattr(Config, 'MA_SCREENING_TREND_MA_PERIOD', 60))
            recent = df.tail(trend_period)
            if 'acml_vol' in recent.columns:
                vol = pd.to_numeric(recent['acml_vol'], errors='coerce').fillna(0)
            else:
                vol = pd.Series([0]*len(recent))
            avg_turnover = (recent['close'] * vol).mean()
            rec['avg_turnover'] = float(avg_turnover) if pd.notna(avg_turnover) else None
        except Exception:
            rec['avg_turnover'] = None

        rec['atr_pct'] = compute_atr_pct(df)

        # apply screening thresholds
        passes = True
        min_avg = getattr(Config, 'MA_SCREENING_MIN_AVG_VALUE', None)
        if min_avg and rec['avg_turnover'] is not None and rec['avg_turnover'] < float(min_avg):
            passes = False
            if not rec['primary_reason']:
                rec['primary_reason'] = 'screening_low_avg_turnover'

        atr_min = getattr(Config, 'MA_SCREENING_ATR_PCT_MIN', None)
        atr_max = getattr(Config, 'MA_SCREENING_ATR_PCT_MAX', None)
        if rec['atr_pct'] is not None and atr_min is not None and atr_max is not None:
            if rec['atr_pct'] < float(atr_min) or rec['atr_pct'] > float(atr_max):
                passes = False
                if not rec['primary_reason']:
                    rec['primary_reason'] = 'screening_atr_out_of_range'

        rec['passes_screening'] = passes

        # final primary reason default
        if not rec['primary_reason']:
            if rec['has_signal'] and rec['quantity_zero_on_signal']:
                rec['primary_reason'] = 'quantity_zero'
            elif not rec['has_signal']:
                rec['primary_reason'] = 'no_signal'
            elif not rec['passes_screening']:
                rec['primary_reason'] = 'screening_filtered'
            else:
                rec['primary_reason'] = 'other'

        results.append(rec)

    return results


def main():
    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    repo_root = PROJECT_ROOT
    selection_path = repo_root / 'trading_bot' / 'backtest_results' / 'ma_crossover_local_selected_kospi_kosdaq_20260302_152127.csv'

    if not selection_path.exists():
        print('선택 파일을 찾을 수 없습니다:', selection_path)
        return 1

    sel_df = pd.read_csv(selection_path, dtype=str)
    symbols = sel_df['symbol'].astype(str).str.strip().tolist()

    trades_path = repo_root / 'trading_bot' / 'backtest_results' / 'ma_crossover_fdr_trades_20260302_152901.csv'
    traded = set()
    if trades_path.exists():
        td = pd.read_csv(trades_path, dtype=str)
        traded = set(td['symbol'].astype(str).str.strip().unique().tolist())

    missing = [s for s in symbols if s not in traded]
    print(f'선택 심볼 총 {len(symbols)}개, 미체결(거래없음) {len(missing)}개')

    start_date = '20170101'
    end_date = '20241231'

    results = diagnose_emulation(missing, start_date, end_date)
    out_df = pd.DataFrame(results)
    out_path = repo_root / 'trading_bot' / 'backtest_results' / f'diagnose_selection_missing_emulation_{now}.csv'
    out_df.to_csv(out_path, index=False)
    print('모사 진단 완료 ->', out_path)
    summary = out_df['primary_reason'].value_counts().to_dict()
    print('요약:', json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
