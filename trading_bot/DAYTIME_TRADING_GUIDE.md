# 한국투자증권 API - 주간거래(Daytime Trading) 가이드

## 개요

한국투자증권 API는 **미국 주식 주간거래**를 위한 별도의 API를 제공합니다.
주간거래는 일반 정규장 거래와 **API 엔드포인트, TR_ID, 거래소 코드**가 모두 다릅니다.

## 주간거래(Daytime Trading)란?

### 거래 시간
- **주간거래 시간**: 미국 시간 10:00 ~ 16:00 (정규장 시간)
- **시차 고려**: 한국 시간으로는 야간/새벽 시간대
- **장운영시간 오류**: 주간거래 시간이 아닐 때 주문하면 "장운영시간이 아닙니다" 오류 발생

### 주간거래 vs 연장거래(Extended Hours)

| 구분 | 주간거래 (Daytime) | 연장거래 (Extended Hours) |
|------|-------------------|--------------------------|
| 시간 | 10:00 - 16:00 EST | 04:00-09:30, 16:00-20:00 EST |
| API | `daytime_order` | `order` |
| 유동성 | 높음 | 낮음 |
| 주문 유형 | 지정가만 | 다양 (LOO, LOC, MOO, MOC 등) |
| 거래소 코드 | NASD, NYSE, AMEX | 일반 코드와 동일 |

## API 비교

### 1. 일반 해외주식 주문 API

**API 정보:**
```python
# API 엔드포인트
API_URL = "/uapi/overseas-stock/v1/trading/order"

# TR ID
TTTT1002U  # 실전 매수
TTTT1006U  # 실전 매도
VTTT1002U  # 모의 매수
VTTT1006U  # 모의 매도
```

**거래소 코드:**
```python
ovrs_excg_cd = "NASD"  # 나스닥
ovrs_excg_cd = "NYSE"  # 뉴욕
ovrs_excg_cd = "AMEX"  # 아멕스
ovrs_excg_cd = "SEHK"  # 홍콩
ovrs_excg_cd = "SHAA"  # 중국 상해
ovrs_excg_cd = "SZAA"  # 중국 심천
ovrs_excg_cd = "TKSE"  # 일본
ovrs_excg_cd = "HASE"  # 베트남 하노이
ovrs_excg_cd = "VNSE"  # 베트남 호치민
```

**주문 유형:**
```python
# 미국 매수
"00"  # 지정가
"32"  # LOO (장개시지정가)
"34"  # LOC (장마감지정가)

# 미국 매도
"00"  # 지정가
"31"  # MOO (장개시시장가)
"32"  # LOO (장개시지정가)
"33"  # MOC (장마감시장가)
"34"  # LOC (장마감지정가)

# 모의투자는 00(지정가)만 가능
```

**사용 예시:**
```python
from overseas_stock import overseas_stock_functions as osf

# 일반 해외주식 주문
result = osf.order(
    cano=account,
    acnt_prdt_cd=product_code,
    ovrs_excg_cd="NASD",      # 나스닥
    pdno="AAPL",
    ord_qty="10",
    ovrs_ord_unpr="150.00",
    ord_dv="buy",
    ctac_tlno="",
    mgco_aptm_odno="",
    ord_svr_dvsn_cd="0",
    ord_dvsn="00",            # 지정가
    env_dv="real"
)
```

### 2. 주간거래 전용 API

**API 정보:**
```python
# API 엔드포인트 (다름!)
API_URL = "/uapi/overseas-stock/v1/trading/daytime-order"

# TR ID (다름!)
TTTS6036U  # 실전/모의 매수
TTTS6037U  # 실전/모의 매도
```

**거래소 코드 (동일):**
```python
ovrs_excg_cd = "NASD"  # 나스닥
ovrs_excg_cd = "NYSE"  # 뉴욕
ovrs_excg_cd = "AMEX"  # 아멕스
# 미국만 지원 (홍콩, 중국, 일본, 베트남 등 미지원)
```

**주문 유형 (제한적):**
```python
ord_dvsn = "00"  # 지정가만 가능!
# LOO, LOC, MOO, MOC 등 사용 불가
```

**사용 예시:**
```python
from overseas_stock import overseas_stock_functions as osf

# 주간거래 주문
result = osf.daytime_order(
    order_dv="buy",
    cano=account,
    acnt_prdt_cd=product_code,
    ovrs_excg_cd="NASD",      # 나스닥
    pdno="AAPL",
    ord_qty="10",
    ovrs_ord_unpr="150.00",
    ctac_tlno="",
    mgco_aptm_odno="",
    ord_svr_dvsn_cd="0",
    ord_dvsn="00"             # 지정가만 가능
)
```

### 3. 주간거래 정정/취소 API

**API 정보:**
```python
# API 엔드포인트
API_URL = "/uapi/overseas-stock/v1/trading/daytime-order-rvsecncl"

# 함수
osf.daytime_order_rvsecncl(
    cano=account,
    acnt_prdt_cd=product_code,
    ovrs_excg_cd="NASD",
    pdno="AAPL",
    orgn_odno="원주문번호",
    rvse_cncl_dvsn_cd="01",  # 01:정정, 02:취소
    ord_qty="10",
    ovrs_ord_unpr="150.00",
    ctac_tlno="",
    mgco_aptm_odno=""
)
```

## 주간거래 실시간 시세 조회

주간거래 시간대의 실시간 시세 조회는 **거래소 코드를 변경**해야 합니다.

### WebSocket 실시간 시세 (주간거래용)

**거래소 코드:**
```python
# 주간거래 실시간 시세 조회 시
"BAQ"  # 나스닥 (주간)
"BAY"  # 뉴욕 (주간)
"BAA"  # 아멕스 (주간)

# 일반 시세 조회
"NAS"  # 나스닥
"NYS"  # 뉴욕
"AMS"  # 아멕스
```

**사용 예시:**
```python
# WebSocket 실시간 시세 (주간거래)
# examples_user/overseas_stock/overseas_stock_functions_ws.py

# 주간거래 실시간 시세
tr_key = "BAQ"  # 나스닥 주간거래
```

### 분봉 차트 (주간거래용)

**API: `inquire_time_itemchartprice`**

```python
# 주간거래 분봉 조회 제한사항:
# - 최대 1일치만 조회 가능
# - 거래소 코드: BAY, BAQ, BAA

result = osf.inquire_time_itemchartprice(
    auth="",
    excd="BAQ",      # 나스닥 주간거래
    symb="AAPL",
    nmin="1",        # 1분봉
    pinc="1",
    next="",
    nrec="120",
    fill="0",
    keyb=""
)
```

**거래소 코드:**
| 시장 | 일반 | 주간거래 |
|------|------|---------|
| 뉴욕 | NYS | BAY |
| 나스닥 | NAS | BAQ |
| 아멕스 | AMS | BAA |
| 홍콩 | HKS | - |
| 상해 | SHS | - |
| 심천 | SZS | - |
| 호치민 | HSX | - |
| 하노이 | HNX | - |
| 도쿄 | TSE | - |

## 종목 정보 조회

### 주간거래 가능 여부 확인

**API: `search_info` (해외주식 상품기본정보)**

```python
result = osf.search_info(
    prdt_type_cd="512",  # 512: 나스닥, 513: 뉴욕, 529: 아멕스
    pdno="AAPL"
)

# 응답 필드
# - dtm_tr_psbl_yn: 주간거래가능여부 (Y/N)
```

**상품 유형 코드:**
```python
"512"  # 미국 나스닥
"513"  # 미국 뉴욕
"529"  # 미국 아멕스
"515"  # 일본
"501"  # 홍콩
"543"  # 홍콩 CNY
"558"  # 홍콩 USD
"507"  # 베트남 하노이
"508"  # 베트남 호치민
"551"  # 중국 상해A
"552"  # 중국 심천A
```

## 주요 차이점 요약

| 항목 | 일반 해외주식 주문 | 주간거래 주문 |
|------|------------------|-------------|
| **API 엔드포인트** | `/trading/order` | `/trading/daytime-order` |
| **TR ID (매수)** | TTTT1002U / VTTT1002U | TTTS6036U |
| **TR ID (매도)** | TTTT1006U / VTTT1006U | TTTS6037U |
| **지원 시장** | 미국, 홍콩, 중국, 일본, 베트남 | 미국만 (나스닥, 뉴욕, 아멕스) |
| **주문 유형** | 지정가, LOO, LOC, MOO, MOC | 지정가만 |
| **거래 시간** | 연장거래 포함 | 정규장만 (10:00-16:00 EST) |
| **거래소 코드** | NASD, NYSE, AMEX | NASD, NYSE, AMEX |
| **실시간 시세 코드** | NAS, NYS, AMS | BAQ, BAY, BAA |
| **분봉 조회** | 제한 없음 | 최대 1일치만 |

## KISBroker에 주간거래 지원 추가

### 현재 상태
- `buy_overseas()`: 일반 `order` API만 사용
- `sell_overseas()`: 일반 `order` API만 사용
- **주간거래 API 미지원**

### 개선 방안

#### 1. 주간거래 전용 메서드 추가

```python
# trading_bot/broker/kis_broker.py

def buy_overseas_daytime(
    self, 
    symbol: str, 
    qty: int, 
    price: float, 
    ovrs_excg_cd: str = None
) -> Optional[Dict]:
    """해외주식 주간거래 매수 주문
    
    Args:
        symbol: 해외 종목 코드 (예: AAPL)
        qty: 주문 수량
        price: 지정가 (주간거래는 지정가만 가능)
        ovrs_excg_cd: 거래소 코드 (NASD, NYSE, AMEX)
    
    Returns:
        주문 결과 dict
        
    Note:
        - 주간거래는 지정가 주문만 가능
        - 미국 시장만 지원 (NASD, NYSE, AMEX)
        - 거래 시간: 미국 시간 10:00-16:00
    """
    if not Config.TRADING_ENABLED:
        self.logger.warning(f"[DRY RUN] 주간거래 매수: {symbol}, qty={qty}, price=${price:.2f}")
        return {"success": False, "message": "TRADING_ENABLED=False"}
    
    try:
        ovrs_excg = ovrs_excg_cd or "NASD"
        
        # daytime_order 함수 import
        from overseas_stock import overseas_stock_functions as osf
        
        res = self._call_with_retry(
            osf.daytime_order,
            order_dv="buy",
            cano=self.account,
            acnt_prdt_cd=self.product_code,
            ovrs_excg_cd=ovrs_excg,
            pdno=symbol,
            ord_qty=str(qty),
            ovrs_ord_unpr=str(price),
            ctac_tlno="",
            mgco_aptm_odno="",
            ord_svr_dvsn_cd="0",
            ord_dvsn="00",  # 지정가만 가능
            check_result=self._check_retry_on_empty_or_rate_limit,
        )
        return {"success": True, "data": res}
    except Exception as e:
        self.logger.error(f"주간거래 매수 실패 ({symbol}): {e}")
        return {"success": False, "message": str(e)}

def sell_overseas_daytime(
    self, 
    symbol: str, 
    qty: int, 
    price: float, 
    ovrs_excg_cd: str = None
) -> Optional[Dict]:
    """해외주식 주간거래 매도 주문"""
    if not Config.TRADING_ENABLED:
        self.logger.warning(f"[DRY RUN] 주간거래 매도: {symbol}, qty={qty}, price=${price:.2f}")
        return {"success": False, "message": "TRADING_ENABLED=False"}
    
    try:
        ovrs_excg = ovrs_excg_cd or "NASD"
        from overseas_stock import overseas_stock_functions as osf
        
        res = self._call_with_retry(
            osf.daytime_order,
            order_dv="sell",
            cano=self.account,
            acnt_prdt_cd=self.product_code,
            ovrs_excg_cd=ovrs_excg,
            pdno=symbol,
            ord_qty=str(qty),
            ovrs_ord_unpr=str(price),
            ctac_tlno="",
            mgco_aptm_odno="",
            ord_svr_dvsn_cd="0",
            ord_dvsn="00",
            check_result=self._check_retry_on_empty_or_rate_limit,
        )
        return {"success": True, "data": res}
    except Exception as e:
        self.logger.error(f"주간거래 매도 실패 ({symbol}): {e}")
        return {"success": False, "message": str(e)}
```

#### 2. 자동 API 선택 로직

```python
def buy_overseas(
    self,
    symbol: str,
    qty: int,
    price: float,
    order_type: str = "LIMIT",
    ovrs_excg_cd: str = None,
    use_daytime_api: bool = None
) -> Optional[Dict]:
    """해외주식 매수 주문 (자동 API 선택)
    
    Args:
        use_daytime_api: True면 주간거래 API 사용, False면 일반 API 사용
                       None이면 현재 시간과 주문 유형으로 자동 결정
    """
    # 자동 API 선택
    if use_daytime_api is None:
        # 현재 시간이 주간거래 시간이고 지정가 주문이면 주간거래 API 사용
        from trading_bot.utils.market_hours import is_daytime_trading_hours
        if is_daytime_trading_hours(market="US") and order_type.upper() == "LIMIT":
            use_daytime_api = True
        else:
            use_daytime_api = False
    
    if use_daytime_api:
        # 주간거래는 지정가만 가능
        if order_type.upper() != "LIMIT":
            self.logger.warning(f"주간거래는 지정가만 가능: {order_type} → LIMIT")
            order_type = "LIMIT"
        return self.buy_overseas_daytime(symbol, qty, price, ovrs_excg_cd)
    else:
        # 기존 일반 API 사용
        ord_svr, ord_dvsn = self._map_overseas_ord_dvsn(order_type, side="buy")
        # ... 기존 로직
```

#### 3. 시간대 체크 유틸리티

```python
# trading_bot/utils/market_hours.py 추가

from datetime import datetime
import pytz

def is_daytime_trading_hours(market: str = "US") -> bool:
    """주간거래 시간인지 확인
    
    Args:
        market: "US" (미국만 지원)
    
    Returns:
        True: 주간거래 시간 (10:00-16:00 EST)
        False: 그 외 시간
    """
    if market != "US":
        return False
    
    # 미국 동부 시간
    est = pytz.timezone("US/Eastern")
    now_est = datetime.now(est)
    
    # 거래일 확인 (월~금)
    if now_est.weekday() >= 5:  # 토, 일
        return False
    
    # 시간 확인 (10:00-16:00 EST)
    hour = now_est.hour
    minute = now_est.minute
    
    if hour < 10:
        return False
    if hour >= 16:
        return False
    
    return True
```

## 모범 사례

### 1. 주간거래 시간대 체크

```python
from trading_bot.utils.market_hours import is_daytime_trading_hours, is_market_open

# 주간거래 시간인지 확인
if is_daytime_trading_hours(market="US"):
    # 주간거래 API 사용
    result = broker.buy_overseas_daytime(symbol, qty, price)
else:
    # 일반 API 사용 (연장거래 포함)
    result = broker.buy_overseas(symbol, qty, price, order_type="LIMIT")
```

### 2. 전략에서 주간거래 고려

```python
class MyStrategy(BaseStrategy):
    def decide_buy(self, data):
        # 주간거래 시간이면 지정가만 사용
        if is_daytime_trading_hours("US"):
            order_type = "LIMIT"  # 주간거래는 지정가만
        else:
            order_type = "LOC"    # 장마감 지정가
        
        return [{
            "type": "buy",
            "symbol": "AAPL",
            "amount": 1000.0,
            "price": 150.0,
            "order_type": order_type,
            "market": "overseas",
            "ovrs_excg_cd": "NASD"
        }]
```

### 3. 오류 처리 개선

```python
# 장운영시간 오류 발생 시 주간거래 안내
try:
    result = broker.buy_overseas(symbol, qty, price)
except Exception as e:
    if "장운영시간이 아닙니다" in str(e):
        # 주간거래 시간인지 체크
        if is_daytime_trading_hours("US"):
            logger.info("주간거래 API로 재시도")
            result = broker.buy_overseas_daytime(symbol, qty, price)
        else:
            logger.error("시장 마감: 거래 불가")
            result = None
```

## 제한사항

### 주간거래 API 제한
1. **미국 시장만 지원**: 나스닥, 뉴욕, 아멕스만 가능
2. **지정가 주문만**: LOO, LOC, MOO, MOC 등 사용 불가
3. **분봉 조회 제한**: 최대 1일치만 조회 가능
4. **거래 시간 제한**: 미국 시간 10:00-16:00만

### 일반 API 제한
1. **모의투자 제한**: 지정가(00)만 가능 (LOO, LOC 등 실전만 가능)
2. **시장별 제한**: 홍콩은 단주지정가(50) 추가 지원

## 관련 문서

- [ERROR_HANDLING_GUIDE.md](ERROR_HANDLING_GUIDE.md) - 오류 처리 가이드
- [examples_llm/overseas_stock/daytime_order/](../examples_llm/overseas_stock/daytime_order/) - 주간거래 예제
- [examples_user/overseas_stock/overseas_stock_functions.py](../examples_user/overseas_stock/overseas_stock_functions.py) - 함수 구현

## 요약

### 주간거래 사용 시기
- ✅ 미국 정규장 거래 시간 (10:00-16:00 EST)
- ✅ 지정가 주문만 필요한 경우
- ✅ 미국 주식만 거래 (나스닥, 뉴욕, 아멕스)

### 일반 API 사용 시기
- ✅ 연장거래 시간 (프리마켓, 애프터아워)
- ✅ LOO, LOC, MOO, MOC 등 특수 주문
- ✅ 홍콩, 중국, 일본, 베트남 등 다른 시장

### 핵심 차이
| 구분 | 일반 API | 주간거래 API |
|------|---------|------------|
| 엔드포인트 | `/trading/order` | `/trading/daytime-order` |
| 지원 시장 | 전세계 | 미국만 |
| 주문 유형 | 다양 | 지정가만 |
| 거래 시간 | 연장거래 포함 | 정규장만 |
