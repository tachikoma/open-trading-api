# 백테스트용 외부 데이터베이스 준비 가이드

백테스트 시스템에서 사용할 수 있는 SQLite 데이터베이스를 준비하는 방법을 설명합니다.

---

## 📋 DB 스키마 요구사항

### 지원하는 두 가지 형식

#### 형식 1: 통합 테이블 (권장)

하나의 `stock_daily` 테이블에 모든 종목 데이터 저장:

```sql
CREATE TABLE stock_daily (
    symbol TEXT NOT NULL,      -- 종목코드 (예: 005930)
    date TEXT NOT NULL,         -- 날짜 YYYYMMDD 형식
    open REAL,                  -- 시가
    high REAL,                  -- 고가
    low REAL,                   -- 저가
    close REAL,                 -- 종가
    volume INTEGER,             -- 거래량
    PRIMARY KEY (symbol, date)
);

CREATE INDEX idx_stock_daily_date ON stock_daily(date);
CREATE INDEX idx_stock_daily_symbol ON stock_daily(symbol);
```

**예시 데이터:**
```
symbol  | date     | open  | high  | low   | close | volume
--------|----------|-------|-------|-------|-------|--------
005930  | 20240101 | 75000 | 76000 | 74500 | 75500 | 1000000
005930  | 20240102 | 75500 | 76500 | 75000 | 76000 | 1200000
000660  | 20240101 | 125000| 127000| 124000| 126000| 500000
```

#### 형식 2: 종목별 테이블

각 종목마다 별도 테이블:

```sql
-- 테이블명: 종목코드 (예: 005930, 000660)
CREATE TABLE "005930" (
    "index" TEXT PRIMARY KEY,   -- 날짜 YYYYMMDD 형식
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER
);
```

**예시:**
- 테이블 `005930`: 삼성전자 데이터
- 테이블 `000660`: SK하이닉스 데이터
- 테이블 `035720`: 카카오 데이터

---

## 🛠️ DB 생성 방법

### 방법 1: FinanceDataReader 사용 (권장)

FinanceDataReader를 사용하여 한국 주식 데이터를 다운로드하고 DB에 저장:

```python
#!/usr/bin/env python3
"""
FinanceDataReader를 사용한 백테스트 DB 생성

설치: uv pip install finance-datareader
"""
import sqlite3
import FinanceDataReader as fdr
from datetime import datetime, timedelta

# DB 파일 생성 (trading_bot 하위에 저장 권장)
db_path = "backtest_data.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 테이블 생성 (형식 1: 통합 테이블)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_daily (
        symbol TEXT NOT NULL,
        date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        PRIMARY KEY (symbol, date)
    )
""")

# 인덱스 생성
cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_daily_date ON stock_daily(date)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_daily_symbol ON stock_daily(symbol)")

# 종목 리스트
symbols = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035720",  # 카카오
    "035420",  # NAVER
    "051910",  # LG화학
    "006400",  # 삼성SDI
]

# 데이터 다운로드 및 저장
start_date = "2020-01-01"  # 4년치 데이터
end_date = datetime.now().strftime("%Y-%m-%d")

for symbol in symbols:
    print(f"📥 {symbol} 다운로드 중...")
    
    try:
        # FinanceDataReader로 데이터 다운로드
        df = fdr.DataReader(symbol, start_date, end_date)
        
        # 데이터 변환
        df = df.reset_index()
        df['symbol'] = symbol
        df['date'] = df['Date'].dt.strftime('%Y%m%d')
        df = df.rename(columns={
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })
        
        # DB에 저장
        df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume']].to_sql(
            'stock_daily',
            conn,
            if_exists='append',
            index=False
        )
        
        print(f"✅ {symbol}: {len(df)}건 저장")
        
    except Exception as e:
        print(f"❌ {symbol} 다운로드 실패: {e}")

conn.commit()
conn.close()

print(f"\n✅ DB 생성 완료: {db_path}")
print(f"   종목 수: {len(symbols)}")
print(f"   기간: {start_date} ~ {end_date}")
```

**실행:**
```bash
uv pip install finance-datareader
uv run create_external_db.py
```

### 방법 2: yfinance 사용

야후 파이낸스에서 데이터 다운로드:

```python
import yfinance as yf
import sqlite3

symbols = ["005930.KS", "000660.KS"]  # .KS 접미사 필요
db_path = "backtest_data.db"

conn = sqlite3.connect(db_path)

for symbol_full in symbols:
    symbol = symbol_full.replace(".KS", "")
    print(f"📥 {symbol} 다운로드 중...")
    
    # yfinance로 데이터 다운로드
    df = yf.download(symbol_full, start="2020-01-01", end=datetime.now())
    
    # 데이터 변환
    df = df.reset_index()
    df['symbol'] = symbol
    df['date'] = df['Date'].dt.strftime('%Y%m%d')
    df = df.rename(columns={
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume'
    })
    
    # DB에 저장
    df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume']].to_sql(
        'stock_daily',
        conn,
        if_exists='append',
        index=False
    )

conn.close()
```

### 방법 3: 직접 API 호출

증권사 API나 다른 데이터 소스에서 직접 수집:

```python
import sqlite3
import requests

def fetch_stock_data(symbol, start_date, end_date):
    """
    사용자의 데이터 소스에서 주가 데이터 가져오기
    """
    # 여기에 실제 API 호출 로직 구현
    # 예: 키움, 이베스트, 네이버 금융 등
    pass

# DB에 저장
conn = sqlite3.connect("backtest_data.db")
cursor = conn.cursor()

# ... 데이터 수집 및 저장 로직
```

---

## 🔍 DB 검증

생성한 DB가 올바른 형식인지 확인:

```python
import sqlite3

db_path = "backtest_data.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 테이블 목록 확인
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"테이블 목록: {tables}")

# stock_daily 테이블 확인 (형식 1)
if ('stock_daily',) in tables:
    cursor.execute("SELECT COUNT(*) FROM stock_daily")
    total_rows = cursor.fetchone()[0]
    print(f"총 레코드 수: {total_rows}")
    
    cursor.execute("SELECT DISTINCT symbol FROM stock_daily")
    symbols = cursor.fetchall()
    print(f"종목 수: {len(symbols)}")
    print(f"종목 목록: {[s[0] for s in symbols]}")
    
    cursor.execute("SELECT MIN(date), MAX(date) FROM stock_daily")
    date_range = cursor.fetchone()
    print(f"데이터 기간: {date_range[0]} ~ {date_range[1]}")

# 종목별 테이블 확인 (형식 2)
else:
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
        count = cursor.fetchone()[0]
        print(f"{table_name}: {count}건")

conn.close()
```

---

## 💡 권장사항

### 1. 데이터 품질

- **무결성**: 결측치 없이 완전한 데이터
- **정확성**: 수정주가(액면분할, 배당 반영) 사용
- **일관성**: 모든 종목이 동일한 기간 커버

### 2. 성능 최적화

```sql
-- 인덱스 추가 (쿼리 속도 향상)
CREATE INDEX idx_stock_daily_date ON stock_daily(date);
CREATE INDEX idx_stock_daily_symbol ON stock_daily(symbol);
CREATE INDEX idx_stock_daily_symbol_date ON stock_daily(symbol, date);

-- VACUUM으로 DB 최적화
VACUUM;
```

### 3. 데이터 업데이트

정기적으로 최신 데이터 추가:

```python
# 마지막 날짜 확인
cursor.execute("SELECT MAX(date) FROM stock_daily WHERE symbol=?", (symbol,))
last_date = cursor.fetchone()[0]

# 그 이후 데이터만 추가
new_start_date = (datetime.strptime(last_date, '%Y%m%d') + timedelta(days=1)).strftime('%Y-%m-%d')
df = fdr.DataReader(symbol, new_start_date, datetime.now())
# ... 저장
```

---

## 📖 백테스트 실행

DB 준비 후 백테스트 실행:

```bash
# 외부 DB로 백테스트
uv run run_backtest.py --source db --db-path backtest_data.db --start 20230101 --end 20241231

# 종목 지정
uv run run_backtest.py --source db --db-path backtest_data.db --symbols 005930 000660 035720
```

---

## ⚠️ 주의사항

### Universe 불일치

외부 DB의 종목 리스트가 Config.WATCH_LIST와 다를 수 있습니다:

```python
# Config.WATCH_LIST
["005930", "000660", "035720", "035420"]

# DB에 있는 종목
["005930", "000660"]  # 035720, 035420 없음
```

**해결 방법:**
1. 백테스트 실행 시 `--symbols` 옵션으로 DB에 있는 종목만 지정
2. DB에 필요한 종목 데이터 추가

### 날짜 형식

- DB: `YYYYMMDD` 문자열 (예: "20240101")
- 날짜 정렬과 비교가 쉬움
- 시간 정보는 불필요 (일봉 데이터)

---

## 🔗 관련 문서

- [데이터 소스 가이드](DATA_SOURCES.md) - 세 가지 데이터 소스 비교
- [백테스트 가이드](QUICKSTART.md) - 백테스트 사용법
- [FinanceDataReader 문서](https://github.com/FinanceData/FinanceDataReader)

---

## 💬 FAQ

**Q: KIS API로 DB를 만들 수 있나요?**
A: 가능하지만 권장하지 않습니다. KIS API는 최대 100거래일만 제공하므로 장기 백테스트에 부적합합니다.

**Q: 어떤 데이터 소스가 가장 좋나요?**
A: 한국 주식은 **FinanceDataReader**를 권장합니다 (무료, 무제한, 정확).

**Q: DB 크기는 얼마나 되나요?**
A: 종목 10개 × 5년 × 250거래일 = 약 12,500건 → **약 1-2MB** (SQLite 압축 효율 좋음)

**Q: 실시간 데이터도 저장할 수 있나요?**
A: 이 DB는 백테스트용 일봉 데이터만 저장합니다. 실시간 데이터는 별도 시스템 필요.
