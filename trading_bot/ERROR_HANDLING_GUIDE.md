# KIS API 오류 처리 가이드

## 개요

KIS API 사용 시 발생할 수 있는 다양한 오류 유형과 적절한 처리 방법을 정리합니다.

## 오류 분류

### 1. 재시도해서는 안 되는 오류 (Non-Retryable Errors)

이러한 오류는 **비즈니스 로직 문제**이므로 재시도해도 해결되지 않습니다.

#### 1.1 장운영시간 오류

**오류 메시지:**
```
장운영시간이 아닙니다.(단,주간거래시간이면 전용화면 주문가능, 주문시간 외 불가)
```

**발생 원인:**
- 해외 주식 시장이 마감된 시간에 주문 시도
- 국내 주식 시장 개장 전/후 주문 시도

**처리 방법:**
- ❌ 재시도하지 않음
- ✅ 사용자에게 시장 마감 알림
- ✅ 다음 장 개장 시간까지 대기
- ✅ 전략 로직에서 시장 시간 체크 추가

**코드 예시:**
```python
# trading_bot/utils/market_hours.py 참고
from trading_bot.utils.market_hours import is_market_open

if not is_market_open(market="US"):
    logger.warning("미국 시장 마감: 주문 보류")
    return None

# 또는 시장 개장 시간 대기
next_open = get_next_market_open(market="US")
logger.info(f"다음 개장 시간: {next_open}")
```

#### 1.2 호가단위 오류

**오류 메시지:**
```
호가 단위에 맞지 않습니다
호가단위 오류
```

**발생 원인:**
- 주문 가격이 해당 가격대의 호가 단위를 위반
- 예: 1,500원 종목에 1,502원 주문 (호가단위 5원 위반)

**처리 방법:**
- ❌ 재시도하지 않음
- ✅ 가격을 호가 단위에 맞춰 조정
- ✅ 조정된 가격으로 재주문

**코드 예시:**
```python
# 자동 조정 기능 사용 (kis_broker.py에 구현됨)
adjusted_price = broker._adjust_price_to_tick_unit(price, env_mode="demo")
result = broker.buy(symbol, qty, adjusted_price)
```

**호가 단위 규칙 (한국거래소 기준):**
| 가격대 | 호가 단위 |
|--------|----------|
| 1,000원 미만 | 1원 |
| 1,000 ~ 5,000원 | 5원 |
| 5,000 ~ 10,000원 | 10원 |
| 10,000 ~ 50,000원 | 50원 |
| 50,000 ~ 100,000원 | 100원 |
| 100,000 ~ 500,000원 | 500원 |
| 500,000원 이상 | 1,000원 |

#### 1.3 잔고 부족 오류

**오류 메시지:**
```
매수가능금액 부족
잔고 부족
주문가능금액 초과
```

**발생 원인:**
- 계좌 잔고보다 큰 금액 주문
- 증거금 부족

**처리 방법:**
- ❌ 재시도하지 않음
- ✅ 주문 금액 조정
- ✅ 가용 잔고 확인 후 재주문

**코드 예시:**
```python
# 매수 가능 금액 조회
buyable_cash = broker.get_buyable_cash(symbol, price)
max_qty = buyable_cash // price

# 금액 조정
if qty * price > buyable_cash:
    qty = max_qty
    logger.warning(f"잔고 부족: 수량 조정 {qty}주")
```

#### 1.4 주문 수량 오류

**오류 메시지:**
```
보유수량 부족
매도 가능 수량 초과
최소 주문 수량 미달
```

**발생 원인:**
- 보유하지 않은 종목 매도
- 최소 주문 단위 미달

**처리 방법:**
- ❌ 재시도하지 않음
- ✅ 보유 수량 확인
- ✅ 주문 수량 조정

#### 1.5 종목 거래 정지

**오류 메시지:**
```
거래정지 종목
매매거래정지
```

**발생 원인:**
- 해당 종목이 거래 정지 상태
- 상한가/하한가로 호가 없음

**처리 방법:**
- ❌ 재시도하지 않음
- ✅ 거래 재개 대기
- ✅ 대체 종목으로 전환

### 2. 재시도 가능한 오류 (Retryable Errors)

#### 2.1 Rate Limit 오류

**오류 코드:**
```
EGW00201
초당 거래건수를 초과하였습니다
```

**발생 원인:**
- API 호출 빈도 제한 초과
- 초당 거래 건수 제한 초과

**처리 방법:**
- ✅ 자동 재시도 (지연 후)
- ✅ 백오프(backoff) 전략 사용
- ✅ 호출 간격 조정

**재시도 로직:**
```python
# kis_broker.py에서 자동 처리됨
result = broker._call_with_retry(
    api_function,
    max_retries=3,
    delay_sec=0.5,
    check_result=broker._check_retry_on_empty_or_rate_limit
)
```

#### 2.2 토큰 만료 오류

**오류 코드:**
```
EGW00123
접근토큰이 만료되었습니다
```

**발생 원인:**
- API 인증 토큰 만료 (하루 1회 갱신 필요)

**처리 방법:**
- ✅ 자동 토큰 재발급
- ✅ 재시도

**코드:**
```python
# kis_broker.py에서 자동 처리됨
# 토큰 만료 감지 시 자동 재발급 후 재시도
```

#### 2.3 일시적 네트워크 오류

**오류:**
- Connection timeout
- HTTP 500/502/503 오류

**처리 방법:**
- ✅ 몇 초 대기 후 재시도
- ✅ 최대 재시도 횟수 제한

### 3. KIS API 오류 코드 참고

| 오류 코드 | 의미 | 재시도 여부 |
|----------|------|------------|
| EGW00123 | 토큰 만료 | ✅ 재시도 (토큰 재발급 후) |
| EGW00201 | Rate Limit | ✅ 재시도 (지연 후) |
| 장운영시간 | 시장 마감 | ❌ 재시도 안 함 |
| 호가단위 | 가격 오류 | ❌ 재시도 안 함 (가격 조정 필요) |
| 잔고부족 | 자금 부족 | ❌ 재시도 안 함 (금액 조정 필요) |

## 구현 세부사항

### kis_broker.py의 오류 처리

#### _check_retry_on_empty_or_rate_limit 메서드

이 메서드는 API 응답을 분석하여 재시도 여부를 판단합니다:

```python
def _check_retry_on_empty_or_rate_limit(self, result, exception) -> bool:
    """재시도 판정기
    
    재시도하는 경우:
    - Rate Limit 오류 (EGW00201, 초당 거래건수 초과)
    - 빈 결과 (단, 재시도하면 안 되는 오류 제외)
    
    재시도하지 않는 경우:
    - 호가단위 오류
    - 장운영시간 오류
    - 잔고 부족 오류
    """
```

#### error_payload 전파

API 오류 발생 시 오류 메시지가 DataFrame의 `attrs['error_payload']`에 저장됩니다:

```python
# 오류 확인 예시
df = broker.buy(symbol, qty, price)
if df.empty:
    error_payload = df.attrs.get("error_payload")
    if error_payload:
        error_msg = str(error_payload)
        if "장운영시간" in error_msg:
            logger.error("시장 마감: 주문 불가")
```

## 모범 사례 (Best Practices)

### 1. 시장 시간 체크

주문 전에 시장 개장 여부를 확인:

```python
from trading_bot.utils.market_hours import is_market_open

# 해외 주식
if not is_market_open(market="US"):
    logger.warning("미국 시장 마감")
    return None

# 국내 주식
if not is_market_open(market="KR"):
    logger.warning("국내 시장 마감")
    return None
```

### 2. 호가 단위 사전 검증

주문 전에 가격을 호가 단위에 맞춤:

```python
# 가격 조정
adjusted_price = broker._adjust_price_to_tick_unit(price, env_mode="demo")

# 또는 검증만 수행
is_valid, error_msg = broker._validate_price_tick_unit(price, env_mode="demo")
if not is_valid:
    logger.warning(error_msg)
```

### 3. 잔고 사전 확인

주문 전에 가용 잔고 확인:

```python
buyable_cash = broker.get_buyable_cash(symbol, price)
if qty * price > buyable_cash:
    logger.warning(f"잔고 부족: 필요={qty * price:,}원, 가용={buyable_cash:,}원")
    qty = buyable_cash // price  # 수량 조정
```

### 4. 오류 로깅 및 모니터링

오류 발생 시 충분한 정보 로깅:

```python
try:
    result = broker.buy(symbol, qty, price)
except Exception as e:
    logger.error(
        f"주문 실패: symbol={symbol}, qty={qty}, price={price}, error={e}",
        extra={"symbol": symbol, "qty": qty, "price": price}
    )
    # 텔레그램 알림
    send_telegram_message(f"⚠️ 주문 실패: {symbol}\n오류: {e}")
```

### 5. 재시도 정책 커스터마이징

특정 API 호출에 대해 재시도 정책 조정:

```python
# Rate Limit만 재시도 (빈 결과는 무시)
result = broker._call_with_retry(
    api_function,
    max_retries=5,
    delay_sec=1.0,
    check_result=broker._check_retry_on_rate_limit_only
)

# 커스텀 재시도 로직
def my_check_result(result, exception):
    if exception and "special_error" in str(exception):
        return True  # 재시도
    return False  # 재시도하지 않음

result = broker._call_with_retry(
    api_function,
    check_result=my_check_result
)
```

## 문제 해결 (Troubleshooting)

### "장운영시간이 아닙니다" 오류가 계속 재시도됨

**증상:**
```
2026-02-06 14:22:59 - KISBroker - INFO - API error (unknown status) - body (truncated): 장운영시간이 아닙니다.
2026-02-06 14:23:00 - KISBroker - WARNING - check_result 요청으로 재시도합니다. (시도 2/3)
```

**원인:**
- 장운영시간 오류 감지 로직이 없음
- 빈 결과만 보고 무조건 재시도

**해결:**
- ✅ 수정됨: [kis_broker.py](broker/kis_broker.py)의 `_check_retry_on_empty_or_rate_limit` 메서드에 장운영시간 체크 추가

### ENV_MODE 변경 후 인증 실패

**증상:**
```
토큰 인증 실패
```

**원인:**
- 이전 모드(real/demo)의 토큰이 캐시되어 있음

**해결:**
```bash
# 토큰 삭제
rm ~/KIS/config/KIS$(date +%Y%m%d)

# 봇 재시작
cd trading_bot
uv run run_bot.py
```

자세한 내용은 [ENV_MODE_GUIDE.md](ENV_MODE_GUIDE.md) 참고

## 관련 문서

- [ENV_MODE_GUIDE.md](ENV_MODE_GUIDE.md) - 환경 모드 설정
- [TICK_UNIT_GUIDE.md](TICK_UNIT_GUIDE.md) - 호가 단위 가이드
- [broker/kis_broker.py](broker/kis_broker.py) - 브로커 구현
- [utils/market_hours.py](utils/market_hours.py) - 시장 시간 유틸리티

## 요약

### 재시도하지 않아야 하는 오류
- ❌ 장운영시간 오류
- ❌ 호가단위 오류
- ❌ 잔고 부족 오류
- ❌ 수량 오류
- ❌ 거래 정지 종목

### 재시도 가능한 오류
- ✅ Rate Limit (EGW00201)
- ✅ 토큰 만료 (EGW00123)
- ✅ 일시적 네트워크 오류
- ✅ HTTP 500대 서버 오류

### 모범 사례
1. 주문 전 시장 시간 체크
2. 가격 호가 단위 사전 검증
3. 잔고 사전 확인
4. 충분한 오류 로깅
5. 텔레그램 알림으로 모니터링
