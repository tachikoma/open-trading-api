# 환경별(Demo/Real) 무한매수 전략 구현 완료 보고서

## 📋 작업 완료 내용

### ✅ 완료된 작업

1. **kis_broker.py** - 해외 잔고 조회 기능 추가
   - `get_balance_overseas(ovrs_excg_cd, tr_crcy_cd)` 메서드 추가
   - 해외 주식 보유 현황 조회 (거래소별, 통화별)

2. **base.py** - 환경별 분기 로직 추가
   - `execute()` 메서드 수정: 모의/실전 환경에 따라 impl 클래스 선택
   - 공통 로직 제거 (impl 클래스로 이동)

3. **market_time.py** (유틸) - US 시장 시간대 관리
   ```python
   get_us_market_time()           # 현재 US/Eastern 시간
   get_market_phase()             # pre_market|regular|after_hours|closed
   is_weekday()                   # 월-금 확인
   get_next_market_phase_time()   # 다음 시간대 예상 시간
   ```

4. **order_manager.py** (유틸) - 환경별 주문 변환
   ```python
   OrderManager(env_mode, logger)
   transform_intents(intents, us_time)  # 환경에 맞게 주문 변환
   ```
   - Demo: 모든 주문을 지정가(00)로, ±2% 가격 조정
   - Real: 시간대별 주문 유형 선택 (LOO/LOC/MOO/MOC)

5. **impl_demo.py** - 모의투자 구현
   ```python
   InfiniteBuyDemoImpl(strategy)
   execute()  # 시간대별 재주문 (Pre/Regular/After)
   ```
   - 특징: Pre/Regular/After 시간대마다 독립적으로 1회씩 실행 가능
   - 상태: `last_exec_phase_{date}_{phase}` 추적
   - 최대 3회/일 실행 가능

6. **impl_real.py** - 실전투자 구현
   ```python
   InfiniteBuyRealImpl(strategy)
   execute()  # 하루 1회만 실행
   ```
   - 특징: 하루 1회만 실행 (LOC/MOC 자동 체결 대기)
   - 상태: `last_execution_date` 추적
   - 시간대별 주문 유형 자동 선택

## 🏗️ 아키텍처

```
InfiniteBuyBase.execute()
│
├─ env_mode == "demo"
│  └─> InfiniteBuyDemoImpl.execute()
│      ├─> 시간대 확인 (Pre/Regular/After)
│      ├─> 매수/매도 의도 수집
│      ├─> OrderManager.transform_intents() → 지정가로 변환
│      └─> broker.execute_intents()
│
└─ env_mode == "real"
   └─> InfiniteBuyRealImpl.execute()
       ├─> 하루 실행 여부 확인
       ├─> 매수/매도 의도 수집
       ├─> OrderManager.transform_intents() → LOC/MOC 선택
       └─> broker.execute_intents()
```

### 데이터 흐름

```
decide_buy()/decide_sell()
    ↓
intents (list of dicts)
    ↓
OrderManager.transform_intents()
    ├─ Demo: 지정가(00) + 가격 조정
    └─ Real: 시간대별 주문 유형 선택
    ↓
transformed_intents
    ↓
broker.execute_intents()
    ↓
주문 실행 결과
```

## 🔄 실행 흐름

### 모의투자 (Demo)

```
[09:00] Pre-market 시작
  ↓
base.execute() 호출
  ↓ broker.env_mode = "demo"
InfiniteBuyDemoImpl 인스턴스 생성
  ↓
should_execute_today()
  ↓ last_exec_phase_2024-01-15_pre_market = None
  ↓ Pre-market 아직 실행 안 함 → True
  ↓
매수/매도 의도 수집
  ↓
OrderManager.transform_intents()
  ↓ 모든 주문 → 지정가(00)
  ↓ 매수가: -2% 조정 (체결 확률 ↑)
  ↓
broker.execute_intents()
  ↓
state["last_exec_phase_2024-01-15_pre_market"] = now

[12:00] Regular 시작
  ↓
base.execute() 호출
  ↓
should_execute_today()
  ↓ last_exec_phase_2024-01-15_regular = None
  ↓ Regular 아직 실행 안 함 → True
  ↓
[위와 동일]

[17:00] After-hours 시작
  ↓
[위와 동일]

[20:00] 폐장
  ↓
base.execute() 호출
  ↓
should_execute_today()
  ↓ 시장 폐장 → False
  ↓
실행 스킵
```

### 실전투자 (Real)

```
[09:00] Pre-market 시작
  ↓
base.execute() 호출
  ↓ broker.env_mode = "real"
InfiniteBuyRealImpl 인스턴스 생성
  ↓
should_execute_today()
  ↓ last_execution_date != 오늘
  ↓ 시장 개장 중
  ↓ True
  ↓
매수/매도 의도 수집
  ↓
OrderManager.transform_intents()
  ↓ Pre-market 시간대 감지
  ↓ 매수: LOO(32) 선택
  ↓ 매도: MOO(31) 선택
  ↓
broker.execute_intents()
  ↓
state["last_execution_date"] = "2024-01-15"

[12:00] Regular 시작
  ↓
base.execute() 호출
  ↓
should_execute_today()
  ↓ last_execution_date == 오늘
  ↓ False
  ↓
실행 스킵 (이미 오늘 실행함)

[17:00] After-hours 시작
  ↓
[실행 스킵]
```

## 📊 주문 유형 매핑표

### 모의투자 (Demo)

| 시간대 | 의도 유형 | 변환 후 | 가격 조정 | 비고 |
|-------|---------|--------|---------|------|
| Pre | Buy | 지정가(00) | -2% | 체결 확률 ↑ |
| Pre | Sell | 지정가(00) | +2% | 체결 확률 ↑ |
| Regular | Buy | 지정가(00) | 조정 없음 | 현재가 기준 |
| Regular | Sell | 지정가(00) | 조정 없음 | 현재가 기준 |
| After | Buy | 지정가(00) | -2% | 체결 확률 ↑ |
| After | Sell | 지정가(00) | +2% | 체결 확률 ↑ |

### 실전투자 (Real)

| 시간대 | 의도 유형 | 변환 후 | 비고 |
|-------|---------|--------|------|
| Pre | Buy | LOO(32) | 장개시 지정가 |
| Pre | Sell | MOO(31) | 장개시 시장가 |
| Regular | Buy | LIMIT(00) | 일반 지정가 |
| Regular | Sell | LIMIT(00) | 일반 지정가 |
| After | Buy | LOC(34) | 장마감 지정가 |
| After | Sell | MOC(33) | 장마감 시장가 |

## 🔧 설정 예시

### config.py

```python
# 환경 모드 선택
ENV_MODE = "demo"  # "real"로 변경하려면 토큰 삭제 필수

# 전략 설정
STRATEGY_VERSION = "v2.2"

# 전략별 설정 (trading_bot/config.yaml 참고)
WATCH_LIST = {
    "AAPL": {
        "exchange": "NAS",
        "total_amount": 1000,
        "splits": 10,
    },
    "MSFT": {
        "exchange": "NAS",
        "total_amount": 1500,
        "splits": 15,
    },
}
```

### trading_bot/config.yaml

```yaml
strategy:
  name: infinite_buy
  version: v2.2
  env_mode: demo  # "real"로 변경 가능

symbols:
  AAPL:
    exchange: NAS
    total_amount: 1000
    splits: 10
    min_price: 150
    max_price: 200
  MSFT:
    exchange: NAS
    total_amount: 1500
    splits: 15

ovrs_excg_cd: NASD
tr_crcy_cd: USD
```

## 🚀 실행 방법

### 모의투자 실행

```bash
cd trading_bot

# config.py에서 ENV_MODE = "demo" 확인
uv run run_bot.py

# 또는 직접 지정
ENV_MODE=demo uv run run_bot.py
```

### 실전투자 실행

```bash
cd trading_bot

# ⚠️ 중요: 사전 체크
# 1. ~/KIS/config/kis_devlp.yaml 확인 (실전 API 키)
# 2. config.py에서 ENV_MODE = "real" 확인
# 3. 심볼 설정 확인
# 4. 금액 설정 확인

# 5. 토큰 삭제 (환경 변경 시)
rm ~/KIS/config/KIS$(date +%Y%m%d)

# 6. 실행
ENV_MODE=real uv run run_bot.py
```

### 테스트

```bash
cd trading_bot

# 드라이 런 (실제 주문 안 함)
uv run test_dry_run.py

# 백테스트 (모의투자 로직 검증)
uv run run_backtest.py --source fdr --start 20230101
```

## 📝 상태 추적 상세

### 모의투자 상태

```python
state = {
    "cum_buy_AAPL": 5000,  # AAPL 누적 매수액
    "cum_buy_MSFT": 7500,  # MSFT 누적 매수액
    
    # 시간대별 실행 기록
    "last_exec_phase_2024-01-15_pre_market": "2024-01-15T07:30:00+00:00",
    "last_exec_phase_2024-01-15_regular": "2024-01-15T12:30:00+00:00",
    "last_exec_phase_2024-01-15_after_hours": "2024-01-15T17:30:00+00:00",
}

# 다음날은 새로운 레코드 생성
state = {
    ...,
    "last_exec_phase_2024-01-16_pre_market": "2024-01-16T07:30:00+00:00",
    ...
}
```

### 실전투자 상태

```python
state = {
    "cum_buy_AAPL": 5000,
    "cum_buy_MSFT": 7500,
    
    # 일일 실행 기록
    "last_execution_date": "2024-01-15",  # 오늘 실행함
}

# 다음날은 초기화 (또는 새로운 날짜)
state = {
    ...,
    "last_execution_date": "2024-01-16",  # 다음날 실행
    ...
}
```

## ⚠️ 주요 주의사항

### 1. ENV_MODE 변경 시 토큰 삭제

```bash
# 필수: 매번 환경 변경 전 토큰 삭제
rm ~/KIS/config/KIS$(date +%Y%m%d)

# 그 후 env_mode 변경
# ENV_MODE = "real"  ← 변경
uv run run_bot.py    # 새 토큰 자동 발급
```

**이유:** KIS API는 환경별 구분이 토큰 파일명에 없어서 이전 토큰이 재사용되면 인증 실패

### 2. 실전투자(Real) 시 1회/일 제약

- 하루에 1번만 실행됨
- 이유: LOC/MOC 자동 체결 대기
- 다음날 같은 시간에 다시 실행 가능
- 수동 리셋: `state["last_execution_date"]` 삭제

### 3. 모의투자(Demo) 시간대별 재주문

- Pre/Regular/After 각각 독립적으로 실행
- 같은 시간대에서는 중복 실행 불가
- 상태: `last_exec_phase_{date}_{phase}` 기반 추적

### 4. 시장 시간 확인

```python
from trading_bot.utils.market_time import get_us_market_time, get_market_phase

us_time = get_us_market_time()
phase = get_market_phase(us_time)

print(f"현재 US 시간: {us_time}")
print(f"시장 단계: {phase}")  # pre_market|regular|after_hours|closed
```

## 📁 파일 구조

```
trading_bot/
├── strategies/infinite_buy/
│   ├── base.py               # 공통 베이스 클래스
│   ├── impl_demo.py          # 모의투자 구현 ← NEW
│   ├── impl_real.py          # 실전투자 구현 ← NEW
│   ├── v2_2.py               # v2.2 전략 (decide_buy/sell)
│   ├── ENV_SPECIFIC_SETUP.md # 환경별 설정 가이드 ← NEW
│   └── ...
├── broker/
│   ├── kis_broker.py         # KIS 브로커 (수정됨)
│   └── order_manager.py      # 주문 변환 로직 ← NEW
├── utils/
│   └── market_time.py        # 시장 시간 유틸 ← NEW
└── ...
```

## ✅ 테스트 체크리스트

### 모의투자 테스트

- [ ] Pre-market 시간에 실행 → 지정가 주문 생성
- [ ] Regular 시간에 재실행 → 중복 실행 안 함 (다른 시간대이므로 가능)
- [ ] After-hours 시간에 재실행 → 3회 총 실행 완료
- [ ] 상태 추적 확인 → `last_exec_phase_*` 3개 레코드 생성
- [ ] 가격 조정 확인 → Pre/After에서 ±2% 조정됨
- [ ] 지정가 변환 확인 → 모든 주문이 00 타입으로 변환됨

### 실전투자 테스트

- [ ] 첫 실행 → 주문 실행 성공, 상태 기록
- [ ] 같은 날 재실행 → 스킵 ("이미 실행됨" 메시지)
- [ ] 다음날 실행 → 다시 실행 가능
- [ ] 주문 유형 확인 → 시간대별로 LOO/LOC/MOO/MOC 적용
- [ ] 상태 추적 확인 → `last_execution_date` = 오늘 날짜

## 📚 참고 자료

- [ENV_MODE_GUIDE.md](../ENV_MODE_GUIDE.md) - 환경 모드 상세 설명
- [ENV_SPECIFIC_SETUP.md](./ENV_SPECIFIC_SETUP.md) - 환경별 설정 가이드
- [market_time.py](../../utils/market_time.py) - 시장 시간 유틸 상세
- [order_manager.py](../../broker/order_manager.py) - 주문 변환 로직 상세
- [impl_demo.py](./impl_demo.py) - 모의투자 구현 상세
- [impl_real.py](./impl_real.py) - 실전투자 구현 상세

---

**작성일:** 2024-01-15  
**상태:** ✅ 완료  
**다음 단계:** 통합 테스트 및 실제 환경 검증
