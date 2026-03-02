#!/usr/bin/env python3
"""
선택 리스트에 포함되었으나 백테스트에서 거래가 발생하지 않은 심볼들 진단 스크립트

결과: `trading_bot/backtest_results/diagnose_selection_missing_<ts>.csv`

검사 항목:
 - insufficient_history: 히스토리 길이 부족
 - no_signal: 기간 내 MA 골든크로스 신호 없음
 - quantity_zero: 매수시 수량 계산 결과 0 (주가 > Config.MAX_ORDER_AMOUNT)
 - data_missing: 데이터 로드 실패 또는 결측 다수

사용법:
 uv run trading_bot/tools/diagnose_selection_missing.py
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


def load_selection(path: Path):
    df = pd.read_csv(path, dtype=str)
    return df


def diagnose(symbols, start_date: str, end_date: str, short_period=Config.MA_SHORT_PERIOD, long_period=Config.MA_LONG_PERIOD):
    results = []

    # BacktestDataSource.load_from_fdr expects list of symbols
    for sym in symbols:
        rec = {
            'symbol': sym,
            'len_history': 0,
            'insufficient_history': False,
            'data_missing': False,
            'has_signal': False,
            'signal_dates': '',
            'quantity_zero_on_signal': False,
            'primary_reason': '',
        }

        try:
            data_map = BacktestDataSource.load_from_fdr([sym], start_date, end_date)
        except Exception as e:
            data_map = None

        if not data_map or sym not in data_map or data_map[sym] is None or data_map[sym].empty:
            rec['data_missing'] = True
            rec['primary_reason'] = 'data_missing'
            results.append(rec)
            continue

        df = data_map[sym].copy()

        # 표준화된 종가 컬럼 찾기
        close_col = None
        for c in ['stck_clpr', 'close', 'clpr', 'prpr', 'adj_prc', 'adj_close', 'price', 'last']:
            if c in df.columns:
                close_col = c
                break
        if close_col is None:
            for c in df.columns:
                if pd.api.types.is_numeric_dtype(df[c]):
                    close_col = c
                    break

        if close_col is None:
            rec['data_missing'] = True
            rec['primary_reason'] = 'data_missing'
            results.append(rec)
            continue

        df['close'] = pd.to_numeric(df[close_col], errors='coerce')
        df = df.dropna(subset=['close']).reset_index(drop=True)
        rec['len_history'] = len(df)

        # 엔진 최소 기간 검사 (engine에서 long_period 기준으로 필터링)
        if len(df) < long_period:
            rec['insufficient_history'] = True
            rec['primary_reason'] = 'insufficient_history'
            results.append(rec)
            continue

        # 이동평균 계산 및 골든크로스(신호) 탐지
        df['ma_short'] = df['close'].rolling(window=short_period).mean()
        df['ma_long'] = df['close'].rolling(window=long_period).mean()

        signal_dates = []
        # 교차 감지: prev_short <= prev_long and cur_short > cur_long
        for i in range(long_period, len(df)):
            prev_short = df.loc[i-1, 'ma_short']
            prev_long = df.loc[i-1, 'ma_long']
            cur_short = df.loc[i, 'ma_short']
            cur_long = df.loc[i, 'ma_long']
            if pd.isna(prev_short) or pd.isna(prev_long) or pd.isna(cur_short) or pd.isna(cur_long):
                continue
            if prev_short <= prev_long and cur_short > cur_long:
                # signal at index i
                # 날짜 컬럼 찾기
                date_col = None
                for c in df.columns:
                    if 'date' in c.lower() or 'bsop' in c.lower() or 'trd' in c.lower():
                        date_col = c
                        break
                if date_col is not None:
                    dt = df.loc[i, date_col]
                else:
                    dt = i
                signal_dates.append(str(dt))

        if signal_dates:
            rec['has_signal'] = True
            rec['signal_dates'] = ';'.join(signal_dates)

            # 가격 기준 quantity==0 여부 (엔진 로직 상 1회 최대 주문금액 제한)
            try:
                # 가격을 첫 신호일 종가로 확인
                first_idx = df.index[df.apply(lambda r: str(r.get('date')) == signal_dates[0] if 'date' in df.columns else False, axis=1)]
                if len(first_idx) > 0:
                    price_at_signal = float(df.loc[first_idx[0], 'close'])
                else:
                    # fallback: use price at index long_period
                    price_at_signal = float(df.loc[long_period, 'close'])
            except Exception:
                price_at_signal = float(df.loc[long_period, 'close'])

            max_order = Config.MAX_ORDER_AMOUNT
            if price_at_signal > max_order:
                rec['quantity_zero_on_signal'] = True
                if not rec['primary_reason']:
                    rec['primary_reason'] = 'quantity_zero'

        else:
            rec['has_signal'] = False
            if not rec['primary_reason']:
                rec['primary_reason'] = 'no_signal'

        # 최종 primary_reason 보정
        if not rec['primary_reason']:
            if rec['data_missing']:
                rec['primary_reason'] = 'data_missing'
            elif rec['insufficient_history']:
                rec['primary_reason'] = 'insufficient_history'
            elif rec['has_signal'] and rec['quantity_zero_on_signal']:
                rec['primary_reason'] = 'quantity_zero'
            elif not rec['has_signal']:
                rec['primary_reason'] = 'no_signal'
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

    sel_df = load_selection(selection_path)
    symbols = sel_df['symbol'].astype(str).str.strip().tolist()

    # trades 파일에서 실제 거래된 심볼 추출 (optional) - 포함하면 미체결 목록으로 한정
    trades_path = repo_root / 'trading_bot' / 'backtest_results' / 'ma_crossover_fdr_trades_20260302_152901.csv'
    traded = set()
    if trades_path.exists():
        td = pd.read_csv(trades_path, dtype=str)
        traded = set(td['symbol'].astype(str).str.strip().unique().tolist())

    missing = [s for s in symbols if s not in traded]
    print(f'선택 심볼 총 {len(symbols)}개, 미체결(거래없음) {len(missing)}개')

    # 진단 대상 기간 (백테스트 기간과 동일하게 설정)
    start_date = '20170101'
    end_date = '20241231'

    results = diagnose(missing, start_date, end_date)
    out_df = pd.DataFrame(results)
    out_path = repo_root / 'trading_bot' / 'backtest_results' / f'diagnose_selection_missing_{now}.csv'
    out_df.to_csv(out_path, index=False)
    print('진단 완료 ->', out_path)
    summary = out_df['primary_reason'].value_counts().to_dict()
    print('요약:', json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
