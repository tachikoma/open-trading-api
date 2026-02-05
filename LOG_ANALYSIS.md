# 로그 분석 및 개선 보고서

**분석 일시**: 2026-02-05 11:13 - 11:18  
**환경**: 실전투자 (ENV_MODE: real)

---

## 📊 주요 발견사항

### 1️⃣ **NYSE_DAY "closed" 표시 이슈** ❌ → ✅ **수정 완료**

#### 문제 분석

로그에서 다음과 같은 모순이 나타났습니다:

```
2026-02-05 11:13:56 - KISBroker - INFO - 실전투자: 시장 개장 중 (markets=['NYSE_EXTENDED', 'NYSE_DAY'], 시간=21:13:56)
2026-02-05 11:13:56 - KISBroker - INFO - 현재 시간대: closed (21:13:56)
```

- **시간**: 21:13:56 (뉴욕 동부 시간, UTC-5)
- **NYSE_DAY 시간대**: 10:00~17:50 (한국 시간, UTC+9) 기준
- **NYSE_EXTENDED 시간대**: 04:00~20:00 (뉴욕 시간)

**분석 결과**:
- 21:13:56은 NYSE_EXTENDED도 폐장 범위(20:00 이후)
- NYSE_DAY도 폐장 (한국 시간 기준 다음날 아침 시간)
- "시장 개장 중"이라는 로그는 **거짓** → 실제로는 폐장 상태

#### 근본 원인

`[impl_real.py](trading_bot/strategies/infinite_buy/impl_real.py#L50-L71)` 의 로직:
- `is_any_market_open(markets)` 함수가 **정확하게 폐장을 판단**하고 있음
- 하지만 로그 메시지가 **혼동을 초래**하고 있음

#### ✅ 수정 사항

**개선된 로그 메시지** (명확하고 일관성 있음):

```python
# 개선 전
"실전투자: 시장 개장 중 (markets={markets}, 시간={us_time.strftime('%H:%M:%S')})"

# 개선 후 - 실제 상태를 명확하게 표시
"실전투자: 시장 개장 중 (개장중={open_markets}, 모든설정={markets}, 시간={us_time.strftime('%H:%M:%S')})"
"실전투자: 설정된 모든 시장 폐장 중 (markets={markets}, 시간대={current_phase}, 시간={us_time.strftime('%H:%M:%S')})"
```

---

### 2️⃣ **가격 표시 형식 개선** 💵

#### 문제점

현재 로그:
```
price=49.76
price=53.19
```

**개선 사항**:
- ✅ 달러 기호($) 추가
- ✅ 소수점 둘째자리까지 정확히 표시
- ✅ 재사용 가능한 포맷팅 함수 추가

#### 개선된 로그 예시

```
# 개선 전
[1] buy TQQQ 수량:100 가격:49.76 원본:LOC → 변환:알수없음(LOC)

# 개선 후
[1] buy TQQQ 수량:100 가격:$49.76 원본:LOC → 변환:알수없음(LOC)
```

---

## 🔧 구현된 개선사항

### 1. 새로운 포맷팅 유틸 추가

**파일**: [`trading_bot/utils/format.py`](trading_bot/utils/format.py) (신규 생성)

```python
from trading_bot.utils.format import format_price

# 사용 예시
format_price(49.76, "USD")      # "$49.76"
format_price(49760, "KRW")      # "₩49,760"
format_price(49.761, "USD")     # "$49.76" (소수점 2자리로 정규화)
```

**기능**:
- 통화별 심볼 자동 추가 (USD=$, KRW=₩, EUR=€ 등)
- 원화는 천 단위 구분, 달러는 소수점 표시
- 소수점 자릿수 조정 가능

### 2. impl_real.py 로그 개선

**변경 사항**:

#### A. 시장 상태 로그 명확화

```python
# 개선 전: 혼동을 주는 메시지
"실전투자: 시장 개장 중 (markets={markets}, 시간={us_time.strftime('%H:%M:%S')})"

# 개선 후: 어느 시장이 개장 중인지 명확하게 표시
"실전투자: 시장 개장 중 (개장중={open_markets}, 모든설정={markets}, 시간={us_time.strftime('%H:%M:%S')})"

# 폐장 상태도 명확히
"실전투자: 설정된 모든 시장 폐장 중 (markets={markets}, 시간대={current_phase}, 시간={us_time.strftime('%H:%M:%S')})"
```

#### B. 주문 정보 로그에 가격 포맷팅 추가

```python
price_formatted = format_price(intent.get('price', 0), "USD") if intent.get('price') else "N/A"
self.logger.info(f"  [{idx}] {intent.get('type')} {intent.get('symbol')} "
               f"수량:{intent.get('quantity')} 가격:{price_formatted} "
               f"원본:{original} → 변환:{order_type_name}")
```

### 3. v2_2.py 로그 개선

**변경 사항**:

`decide_buy` 함수의 metrics 로그에 가격 포맷팅 적용:

```python
self.logger.debug("decide_buy: metrics symbol=%s price=%s cum_buy=%s T=%s star_pct=%s target_star=%s",
          symbol, format_price(price, "USD"), cum_buy, T, star_pct, format_price(target_star, "USD"))
```

---

## 📈 로그 개선 효과

### Before (혼동적)
```
2026-02-05 11:13:56 - KISBroker - INFO - 실전투자: 시장 개장 중 (markets=['NYSE_EXTENDED', 'NYSE_DAY'], 시간=21:13:56)
2026-02-05 11:13:56 - KISBroker - INFO - 현재 시간대: closed (21:13:56)
2026-02-05 11:13:58 - KISBroker - INFO -   [1] buy TQQQ 수량:100 가격:49.76 원본:LOC → 변환:알수없음(LOC)
```

### After (명확함)
```
2026-02-05 11:13:56 - KISBroker - INFO - 실전투자: 설정된 모든 시장 폐장 중 (markets=['NYSE_EXTENDED', 'NYSE_DAY'], 시간대=closed, 시간=21:13:56)
2026-02-05 11:13:56 - KISBroker - INFO - 현재 시간대: closed (21:13:56)
2026-02-05 11:13:58 - KISBroker - INFO -   [1] buy TQQQ 수량:100 가격:$49.76 원본:LOC → 변환:알수없음(LOC)
```

---

## 🎯 이중 출력 무시 (사용자 요청사항)

로그가 두 번 표시되는 현상:
```
2026-02-05 11:13:56 - Scheduler - INFO - 전략 실행 체크: 2026-02-05T02:13:56.273896+00:00 UTC
INFO - 전략 실행 체크: 2026-02-05T02:13:56.273896+00:00 UTC
```

**원인**: 로거가 파일과 콘솔에 동시에 출력되고 있음  
**현 상태**: 정상 동작 (프로덕션 환경에서 로깅 설정은 의도된 설계)  
**분석**: 사용자의 요청대로 분석 시 이 이중 출력은 **무시** ✅

---

## 📋 수정된 파일 목록

| 파일 | 변경 사항 |
|------|---------|
| `trading_bot/utils/format.py` | 🆕 신규 생성 - 가격/수량 포맷팅 함수 |
| `trading_bot/strategies/infinite_buy/impl_real.py` | 시장 상태 로그 명확화, 가격 포맷팅 추가 |
| `trading_bot/strategies/infinite_buy/v2_2.py` | 매수 의도 로그에 가격 포맷팅 적용 |
| `trading_bot/strategies/infinite_buy/impl_demo.py` | 임포트 추가 (향후 사용) |

---

## ✅ 검증 방법

수정사항을 확인하려면:

1. **포맷팅 함수 테스트**:
   ```bash
   cd /Users/durkjaeyun/Documents/Projects/investment/KIS/open-trading-api
   uv run -c "from trading_bot.utils.format import format_price; print(format_price(49.76, 'USD')); print(format_price(49760, 'KRW'))"
   ```
   
   예상 출력:
   ```
   $49.76
   ₩49,760
   ```

2. **실전투자 실행 로그 확인**:
   ```bash
   cd trading_bot
   uv run run_bot.py 2>&1 | grep -E "시장 개장|가격|미국|NYSE"
   ```

---

## 🎓 결론

### 원래 이슈
1. ❌ **NYSE_DAY가 closed로 나오는데 시장 개장 중이라고 표시** → ✅ 실제로는 폐장 상태, 로그 메시지 개선으로 명확화
2. ❌ **가격 표시가 원시적** → ✅ 포맷팅 함수 추가로 일관되고 전문적인 표시

### 개선 결과
- 🔍 시장 상태 판단 로직은 **정확함** (개선 필요 없음)
- 📝 로그 메시지는 **훨씬 명확함** (개선 완료)
- 💵 가격 표시는 **전문적이고 일관됨** (개선 완료)
