# 백테스트 데이터 소스 가이드

백테스트를 위한 과거 시세 데이터를 가져오는 3가지 방법을 제공합니다.

---

## 📊 데이터 소스 비교

| 데이터 소스 | 기간 제한 | 속도 | 설치 | 추천 용도 |
|------------|---------|------|------|----------|
| **KIS API** | 최대 100거래일 | 느림 (API 호출) | 불필요 | 단기 백테스트 |
| **SQLite DB** | 사용자 정의 | 매우 빠름 | 직접 구축 | 오프라인, 커스텀 데이터 |
| **FinanceDataReader** | **무제한** (상장일~현재) | 보통 (인터넷) | `uv pip install` | **장기 백테스트 (권장)** |

---

## 1️⃣ KIS API 사용 (기본값)

### 특징
- 한국투자증권 Open Trading API 직접 호출
- 별도 설치 불필요
- **제한: 최대 100거래일** (약 3-4개월)

### 사용 방법
```python
from trading_bot.backtest.engine import BacktestEngine
from trading_bot.strategies.ma_crossover import MovingAverageCrossover

engine = BacktestEngine(initial_capital=10_000_000)
results = engine.run(
    strategy=MovingAverageCrossover(),
    symbols=["005930", "000660"],
    start_date="20240901",  # 최대 100거래일 전
    end_date="20241231"
    # db_path와 use_fdr를 지정하지 않으면 API 사용
)
```

### 실행 스크립트
```bash
# KIS API로 최근 100거래일 백테스트
uv run run_backtest.py
```

### 장점
- 공식 API, 신뢰할 수 있는 데이터
- 별도 설치나 설정 불필요
- KIS 실전/모의 투자와 동일한 데이터 소스

### 단점
- ❌ 100거래일 제한 (장기 백테스트 불가)
- ⚠️ API 호출 속도 느림
- ⚠️ 네트워크 필요

---

## 2️⃣ SQLite DB 사용 (오프라인)

### 특징
- 로컬 SQLite 데이터베이스 사용
- 사용자가 직접 데이터 수집/저장
- 기간 제한 없음 (DB에 저장된 만큼)

### DB 생성 방법

#### A. KIS API로 DB 생성 (최대 100거래일)
```bash
uv run create_backtest_db.py
```

생성되는 DB 구조:
```sql
CREATE TABLE stock_daily (
    symbol TEXT,           -- 종목코드
    date TEXT,             -- 날짜 (YYYYMMDD)
    open REAL,             -- 시가
    high REAL,             -- 고가
    low REAL,              -- 저가
    close REAL,            -- 종가
    volume INTEGER,        -- 거래량
    PRIMARY KEY (symbol, date)
);
```

#### B. 기존 DB 사용 (커스텀 형식)

**형식 1: 통합 테이블** (`stock_daily`)
```python
# 위의 stock_daily 테이블 형식
```

**형식 2: 종목별 테이블** (예: `005930`, `000660`)
```python
# 각 종목마다 별도 테이블
# 테이블명: 종목코드 (005930, 000660 등)
# 컬럼: index (date YYYYMMDD), open, high, low, close, volume
```

### 사용 방법
```python
from pathlib import Path
from trading_bot.backtest.engine import BacktestEngine
from trading_bot.strategies.ma_crossover import MovingAverageCrossover

engine = BacktestEngine(initial_capital=10_000_000)
results = engine.run(
    strategy=MovingAverageCrossover(),
    symbols=["005930", "000660"],
    start_date="20230101",
    end_date="20241231",
    db_path=Path("/path/to/backtest_data.db")  # DB 경로 지정
)
```

### 실행 스크립트
```bash
# DB 파일이 있으면 자동 사용
DB_PATH="/Users/durkjaeyun/Documents/Projects/investment/SystemTrading/backtest_data.db"

# run_backtest.py는 자동으로 DB를 찾음
uv run run_backtest.py
```

### 장점
- ✅ 매우 빠른 속도 (로컬 파일)
- ✅ 오프라인 사용 가능
- ✅ 커스텀 데이터 저장 가능
- ✅ 기간 제한 없음 (저장된 만큼)

### 단점
- ⚠️ 직접 데이터 수집/관리 필요
- ⚠️ 초기 구축 시간 소요

---

## 3️⃣ FinanceDataReader 사용 (권장 ⭐)

### 특징
- Python 라이브러리로 무료 금융 데이터 제공
- **무제한 기간** (종목 상장일부터 현재까지)
- 야후 파이낸스, 네이버 금융, KRX 등 통합

### 설치
```bash
uv pip install finance-datareader
```

### 지원 데이터
- 🇰🇷 한국 주식: KOSPI, KOSDAQ, KONEX
- 🇺🇸 미국 주식: NYSE, NASDAQ, AMEX
- 🌏 해외 주식: 중국, 일본, 홍콩, 유럽 등
- 📈 지수, ETF, 환율, 암호화폐 등

### 사용 방법
```python
from trading_bot.backtest.engine import BacktestEngine
from trading_bot.strategies.ma_crossover import MovingAverageCrossover

engine = BacktestEngine(initial_capital=10_000_000)
results = engine.run(
    strategy=MovingAverageCrossover(),
    symbols=["005930", "000660", "035720"],
    start_date="20220101",  # 무제한! (2년 전도 가능)
    end_date="20241231",
    use_fdr=True  # FinanceDataReader 사용
)
```

### 실행 스크립트
```bash
# FinanceDataReader로 2년치 백테스트
uv run run_backtest_fdr.py
```

### 데이터 소스
FinanceDataReader는 다음 소스에서 데이터를 수집합니다:

| 소스 | 설명 | 크롤링 여부 |
|------|------|------------|
| **네이버 금융** | 한국 주식 일봉 데이터 | API (비공식) |
| **야후 파이낸스** | 글로벌 주식/지수 | API (공개) |
| **KRX** | 한국거래소 공식 데이터 | API (공식) |

⚠️ **크롤링 vs API:**
- FinanceDataReader는 **API 방식** 사용 (불법 크롤링 아님)
- 네이버/야후는 비공식 API지만 사용 제한 없음
- KRX는 공식 API

### 장점
- ✅ **무제한 기간** (상장일~현재)
- ✅ 간단한 설치 (`uv pip install`)
- ✅ 다양한 데이터 소스 통합
- ✅ 한국 주식에 최적화
- ✅ 활발한 커뮤니티 및 업데이트

### 단점
- ⚠️ 인터넷 연결 필요
- ⚠️ API 호출 속도 (DB보다 느림)
- ⚠️ 비공식 API (네이버/야후)

---

## 📚 외부 데이터 소스 추가 설명

### Q. 크롤링인가? API인가?

#### ✅ API 방식 (권장)
- **FinanceDataReader**: 네이버/야후 비공식 API 사용
- **yfinance**: 야후 파이낸스 비공식 API
- **KRX API**: 한국거래소 공식 API

```python
# yfinance 예시 (FinanceDataReader 대신 사용 가능)
import yfinance as yf
data = yf.download("005930.KS", start="2020-01-01", end="2024-12-31")
```

#### ❌ 크롤링 방식 (비권장)
- **BeautifulSoup + requests**: HTML 파싱
- **Selenium**: 브라우저 자동화

크롤링은 다음 이유로 **권장하지 않습니다**:
1. 불법 소지 (이용약관 위반)
2. IP 차단 위험
3. 사이트 구조 변경 시 코드 수정 필요
4. 느린 속도

### Q. 야후 파이낸스 vs 네이버 금융?

| 특징 | 야후 파이낸스 | 네이버 금융 |
|------|-------------|-----------|
| 한국 주식 코드 | `005930.KS` (접미사 필요) | `005930` (6자리) |
| 데이터 품질 | 약간 부정확 (환율 반영) | 정확 (원화 기준) |
| 업데이트 속도 | 느림 (1시간 지연) | 빠름 (15분 이내) |
| 사용 편의성 | 글로벌 통합 | 한국 주식 전용 |

**결론**: 한국 주식은 **네이버 금융**이 더 정확하며, **FinanceDataReader가 자동으로 최적의 소스를 선택**합니다.

---

## 🚀 실전 사용 가이드

### 시나리오별 추천

#### 1. 단기 백테스트 (최근 1-3개월)
```bash
# KIS API 사용 (설치 불필요)
uv run run_backtest.py
```
- 빠른 검증용
- 별도 설정 불필요

#### 2. 장기 백테스트 (1-5년)
```bash
# FinanceDataReader 사용 (권장)
uv pip install finance-datareader
uv run run_backtest_fdr.py
```
- 전략 성능 평가
- 다양한 시장 상황 테스트

#### 3. 오프라인 백테스트
```bash
# SQLite DB 사용
# 1. DB 생성 (1회만)
uv run create_backtest_db.py

# 2. 백테스트 실행 (인터넷 불필요)
uv run run_backtest.py
```
- 반복 테스트 시 빠른 속도
- 커스텀 데이터 사용

---

## 🔧 고급 설정

### 데이터 소스 직접 제어

```python
from pathlib import Path
from trading_bot.backtest.data_source import BacktestDataSource

# 1. SQLite에서 로드
data = BacktestDataSource.load_from_sqlite(
    Path("/path/to/db.db"),
    symbols=["005930"],
    start_date="20230101",
    end_date="20241231"
)

# 2. KIS API에서 로드
from trading_bot.broker import KISBroker
broker = KISBroker(env_mode="demo")
data = BacktestDataSource.load_from_api(
    broker,
    symbols=["005930"],
    start_date="20240901",
    end_date="20241231"
)

# 3. FinanceDataReader에서 로드
data = BacktestDataSource.load_from_fdr(
    symbols=["005930", "000660"],
    start_date="20200101",
    end_date="20241231"
)

# data 형식: Dict[symbol, pd.DataFrame]
print(data["005930"].head())
```

---

## 📖 참고 자료

### FinanceDataReader
- GitHub: https://github.com/FinanceData/FinanceDataReader
- 문서: https://financedata.github.io/posts/finance-data-reader-users-guide.html
- 설치: `pip install finance-datareader`

### yfinance (야후 파이낸스)
- GitHub: https://github.com/ranaroussi/yfinance
- 문서: https://pypi.org/project/yfinance/
- 설치: `pip install yfinance`

### KRX 공식 API
- 홈페이지: http://data.krx.co.kr
- 가입 후 API 키 발급 필요
- 복잡한 인증 절차

---

## 💡 요약

| 상황 | 추천 데이터 소스 |
|------|----------------|
| 처음 백테스트 | **KIS API** (설치 불필요) |
| 장기 백테스트 (1년+) | **FinanceDataReader** ⭐ |
| 오프라인 반복 테스트 | **SQLite DB** |
| 커스텀 데이터 | **SQLite DB** |

**일반적으로 FinanceDataReader를 권장합니다!**
- 무제한 기간
- 간단한 설치
- 한국 주식 최적화
