# 테스트 스크립트: FinanceDataReader를 모킹하여 증분 캐시 병합 동작 검증
import sys, types
from pathlib import Path
import pandas as pd

import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# 모듈 임포트 대상
from trading_bot.backtest.data_source import BacktestDataSource
import trading_bot.backtest.data_source as ds_mod

# 가짜 FinanceDataReader 모듈 생성
def fake_DataReader(symbol, start, end):
    rng = pd.date_range(start, end, freq='B')
    df = pd.DataFrame(index=rng)
    df.index.name = 'Date'
    df['Open'] = 1
    df['High'] = 1
    df['Low'] = 1
    df['Close'] = 1
    df['Volume'] = 100
    return df

fake_mod = types.SimpleNamespace(DataReader=fake_DataReader)
sys.modules['FinanceDataReader'] = fake_mod

from trading_bot.config import Config

# 캐시 디렉토리 준비 (Config.FDR_CACHE_DIR 사용)
cache_dir = Config.FDR_CACHE_DIR
cache_dir.mkdir(parents=True, exist_ok=True)

symbol = 'AAA_TEST'
cache_file = cache_dir / f"{symbol}.parquet"

# 기존 캐시(부분 구간) 생성: 2020-01-06 ~ 2020-01-10 (영업일)
partial_rng = pd.date_range('2020-01-06', '2020-01-10', freq='B')
partial = pd.DataFrame({
    'date': partial_rng,
    'stck_oprc': 1,
    'stck_hgpr': 1,
    'stck_lwpr': 1,
    'stck_clpr': 1,
    'acml_vol': 100
})
partial['stck_bsop_date'] = partial['date'].dt.strftime('%Y%m%d')
partial.to_parquet(cache_file)

# 이제 load_from_fdr 호출: 요청 기간 2020-01-01 ~ 2020-01-31
res = BacktestDataSource.load_from_fdr([symbol], '20200101', '20200131')

print('\n=== 결과 요약 ===')
print('keys:', list(res.keys()))
if symbol in res:
    print('rows:', len(res[symbol]))
    print(res[symbol].head(3))

# 캐시 파일 검사
if cache_file.exists():
    cached = pd.read_parquet(cache_file)
    print('\n캐시 범위:', cached['date'].min(), '->', cached['date'].max())
    print('캐시 행 수:', len(cached))
else:
    print('캐시 파일이 존재하지 않습니다')
