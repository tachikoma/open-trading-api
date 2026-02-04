# InfiniteBuy 무한매수 전략 설정 예시

## 파일 위치
```
trading_bot/config.py (주 설정)
trading_bot/strategies/infinite_buy/config_demo.yaml (모의투자)
trading_bot/strategies/infinite_buy/config_real.yaml (실전투자)
```

## 설정 항목 설명

### 1. 기본 설정 (config.py)

```python
# 환경 모드: "demo" 또는 "real"
ENV_MODE = "demo"  # 모의투자 또는 실전투자

# 전략 선택
STRATEGY = "infinite_buy"
STRATEGY_VERSION = "v2.2"  # v2.2 또는 v3.0
```

### 2. 모의투자 설정 (Demo Mode)

**특징:**
- 지정가(00) 주문만 가능
- 시간대별로 자동 재주문 (Pre/Regular/After)
- 최대 3회/일 실행 가능

**설정 예시:**
```yaml
# config.yaml (모의투자)
strategy:
  name: infinite_buy
  version: v2.2
  env_mode: demo
  symbols:
    "AAPL":
      exchange: NAS         # 나스닥
      total_amount: 1000    # 총 투자금액 ($)
      splits: 10            # 분할 횟수
      min_price: 150        # 최소 매입가
      max_price: 200        # 최대 매입가
    "MSFT":
      exchange: NAS
      total_amount: 1500
      splits: 15
  ovrs_excg_cd: NASD        # 거래소: NASD(나스닥), NYSE(뉴욕), AMEX(아멕스)
  tr_crcy_cd: USD           # 통화: USD
```

**모의투자 시간대별 특징:**
```
Pre-market  (04:00~09:30): 지정가 -2% 조정 (체결 확률 ↑)
Regular     (09:30~16:00): 지정가 그대로
After-hours (16:00~20:00): 지정가 +2% 조정 (체결 확률 ↑)
```

### 3. 실전투자 설정 (Real Mode)

**특징:**
- LOO/LOC/MOO/MOC 지원
- 하루 1회만 실행 (자동 실행)
- 시간대별 주문 유형 자동 선택

**설정 예시:**
```yaml
# config.yaml (실전투자)
strategy:
  name: infinite_buy
  version: v2.2
  env_mode: real          # ⚠️ 실전투자 (자본손실 위험)
  symbols:
    "AAPL":
      exchange: NAS       # 나스닥
      total_amount: 5000  # 총 투자금액 ($)
      splits: 20          # 분할 횟수
      min_price: 150
      max_price: 200
      limit_price: 155    # LOC/LOO 가격 (매입 예상가)
    "MSFT":
      exchange: NAS
      total_amount: 5000
      splits: 20
      limit_price: 380
  ovrs_excg_cd: NASD
  tr_crcy_cd: USD
```

**실전투자 시간대별 주문 유형:**
```
Pre-market  (04:00~09:30): 
  - Buy:  LOO (32) - 장개시 지정가 (지정 가격 이하)
  - Sell: MOO (31) - 장개시 시장가

Regular     (09:30~16:00):
  - Buy/Sell: LIMIT (00) - 일반 지정가

After-hours (16:00~20:00):
  - Buy:  LOC (34) - 장마감 지정가 (지정 가격 이하)
  - Sell: MOC (33) - 장마감 시장가
```

### 4. 주문 유형 코드

| 코드 | 이름 | 설명 | 사용 시간대 |
|------|------|------|-----------|
| 00 | 지정가 | LIMIT | 모든 시간대 (모의/실전) |
| 31 | MOO | 장개시 시장가 | Pre-market (실전 매도) |
| 32 | LOO | 장개시 지정가 | Pre-market (실전 매수) |
| 33 | MOC | 장마감 시장가 | After-hours (실전 매도) |
| 34 | LOC | 장마감 지정가 | After-hours (실전 매수) |

### 5. 환경별 실행 제약

#### 모의투자 (Demo)
```
[하루 1개 심볼 기준]

Pre-market 04:00~09:30
↓ (1회 실행 가능)
Regular 09:30~16:00
↓ (다시 실행 가능)
After-hours 16:00~20:00
↓ (다시 실행 가능)

Total: 최대 3회/일
```

**state 추적 예시:**
```python
state = {
    "last_exec_phase_2024-01-15_pre_market": "2024-01-15T07:30:00",
    "last_exec_phase_2024-01-15_regular": "2024-01-15T12:30:00",
    "last_exec_phase_2024-01-15_after_hours": "2024-01-15T17:30:00",
}
```

#### 실전투자 (Real)
```
[하루 1개 심볼 기준]

Pre/Regular/After 중 아무 때나 1회 실행
↓ (자동 실행)
하루는 더 이상 실행 안 함 (LOC/MOC 자동 체결 대기)

Total: 1회/일
```

**state 추적 예시:**
```python
state = {
    "last_execution_date": "2024-01-15",  # 오늘 실행함
}
```

## 실행 명령어

### 모의투자 실행
```bash
cd trading_bot

# config.py에서 ENV_MODE = "demo"로 설정 후
uv run run_bot.py

# 또는 환경 변수로 지정
ENV_MODE=demo uv run run_bot.py
```

### 실전투자 실행
```bash
cd trading_bot

# ⚠️ config.py에서 ENV_MODE = "real"로 설정 후 실행
# 반드시 확인 후 실행!
ENV_MODE=real uv run run_bot.py
```

### 백테스트 (모의투자 사용)
```bash
cd trading_bot

# FDR 데이터 사용
uv run run_backtest.py --source fdr --start 20230101 --end 20240101

# 외부 DB 사용
uv run run_backtest.py --source db --db-path backtest_data.db
```

## 설정 변경 시 체크리스트

### ENV_MODE 변경 시 (demo ↔ real)

**⚠️ 중요: 토큰 삭제 필수**

KIS API는 서버 구분(prod/vps)이 토큰 파일명에 없어서 ENV_MODE 변경 시 이전 모드 토큰이 재사용됩니다.

```bash
# 1. 현재 토큰 삭제
rm ~/KIS/config/KIS$(date +%Y%m%d)

# 2. config.py에서 ENV_MODE 변경
# ENV_MODE = "real"  # "demo"에서 변경

# 3. 봇 재시작 (새 토큰 자동 발급)
uv run run_bot.py
```

### 심볼 추가 시

```yaml
# symbols 섹션에 새 심볼 추가
symbols:
  "AAPL":
    exchange: NAS
    total_amount: 1000
    splits: 10
  "TSLA":              # ← 새 심볼 추가
    exchange: NAS
    total_amount: 2000
    splits: 20
```

## 문제 해결

### "시장이 폐장 중" 메시지

**원인:** US/Eastern 시간대로 시장이 닫혀있음 (20:00~04:00)

**확인:**
```python
from trading_bot.utils.market_time import get_us_market_time, get_market_phase
us_time = get_us_market_time()
print(f"현재 US 시간: {us_time}")
print(f"시장 단계: {get_market_phase(us_time)}")
```

**해결:**
- 미국 시간으로 04:00 이후에 실행
- Pre-market 이상 시간대에서 실행

### 모의투자에서 주문이 체결되지 않음

**원인:** 모의투자는 지정가 주문이 자동 체결되지 않음

**해결:**
- 매수: 현재가보다 높은 가격 설정 (또는 -2% 가격 조정 자동 적용)
- 매도: 현재가보다 낮은 가격 설정 (또는 +2% 가격 조정 자동 적용)
- 시간대별로 재주문되면 다음 기회에 체결 가능

### 실전투자에서 1일 1회 제약

**확인:**
```python
from datetime import datetime
import pytz

state = strategy.state
print(f"마지막 실행 날짜: {state.get('last_execution_date')}")

today = datetime.now(pytz.timezone('US/Eastern')).strftime("%Y-%m-%d")
print(f"오늘: {today}")
```

**해결:**
- 내일 같은 시간에 다시 실행하면 재설정
- 또는 `state["last_execution_date"]` 수동 삭제

## 추가 자료

- [market_time.py](../utils/market_time.py) - 시간대 판정 유틸
- [order_manager.py](../broker/order_manager.py) - 주문 변환 로직
- [impl_demo.py](./impl_demo.py) - 모의투자 구현
- [impl_real.py](./impl_real.py) - 실전투자 구현
- [ENV_MODE_GUIDE.md](../ENV_MODE_GUIDE.md) - 환경 모드 상세 가이드
