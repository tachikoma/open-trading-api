# KIS 자동매매 봇

한국투자증권(KIS) Open API를 활용한 주식 자동매매 프로그램

## 📁 프로젝트 구조

```
trading_bot/
├── main.py                    # 메인 실행 파일 (또는 프로젝트 루트의 run_bot.py 사용)
├── config.py                  # 설정 파일
├── scheduler.py               # 스케줄러
├── broker/                    # KIS API 래퍼
│   ├── __init__.py
│   └── kis_broker.py         # KIS Broker 클래스
├── strategies/                # 트레이딩 전략
│   ├── __init__.py
│   ├── base_strategy.py      # 전략 베이스 클래스
│   └── ma_crossover.py       # 이동평균 교차 전략
├── utils/                     # 유틸리티
│   ├── __init__.py
│   └── logger.py             # 로깅 유틸
└── logs/                      # 로그 파일 저장
```

## ✨ 주요 기능

### 1. KIS Broker 래퍼
- 기존 `examples_user/domestic_stock` 코드를 래핑
- 간단한 인터페이스 제공:
  - `get_current_price()`: 현재가 조회
  - `get_daily_price()`: 일별 시세 조회
  - `get_balance()`: 잔고 조회
  - `buy()`, `sell()`: 매수/매도 주문
  - `cancel_order()`: 주문 취소

### 2. 전략 시스템
- **BaseStrategy**: 모든 전략의 베이스 클래스
- **MovingAverageCrossover**: 이동평균 교차 전략
  - 골든크로스: 단기이평 > 장기이평 → 매수
  - 데드크로스: 단기이평 < 장기이평 → 매도

### 3. 스케줄러
- 정해진 시간 간격으로 전략 실행
- 장 운영 시간 체크 (평일 09:00~15:30)
- 두 가지 방식 지원:
  - `schedule` 라이브러리 방식 (선택사항)
  - 단순 `time.sleep` 방식 (기본값)

## 🚀 설치 및 실행

### 1. 필수 패키지 설치

이 프로젝트는 `uv` 또는 `pip`로 실행할 수 있습니다.

#### uv 사용 (권장)
```bash
# 프로젝트 루트에서 자동으로 의존성 설치 및 실행
cd /path/to/open-trading-api
uv run run_bot.py
```

#### pip 사용
```bash
# 의존성 설치
pip install -r requirements.txt
# 또는
pip install pandas pyyaml requests pycryptodome websockets

# 실행
python run_bot.py
```

### 2. 설정 파일 확인

`kis_devlp.yaml` 파일에 KIS API 인증 정보가 있어야 합니다.
기본 경로: `~/KIS/config/kis_devlp.yaml`

```yaml
# 실전투자
my_app: "실전투자_앱키"
my_sec: "실전투자_시크릿"

# 모의투자
paper_app: "모의투자_앱키"
paper_sec: "모의투자_시크릿"

# 계좌 정보
my_acct: "계좌번호8자리"
my_prod: "상품코드２자리"  # 01: 주식, 03: 선물옵션 등
my_htsid: "HTS_ID"

# 서버 URL (KIS API 내부 사용, 수정 불필요)
prod: "https://openapi.koreainvestment.com:9443"      # 실전투자 서버
vps: "https://openapivts.koreainvestment.com:29443"  # 모의투자 서버
my_url: "https://openapivts.koreainvestment.com:29443"
my_url_ws: "ws://ops.koreainvestment.com:31000"
my_agent: "Mozilla/5.0"
```

### 3. 봇 설정 조정

[trading_bot/config.py](trading_bot/config.py) 파일에서 설정을 변경할 수 있습니다:

```python
# 환경 모드 (사용자 설정)
# "demo": 모의투자 (KIS API는 내부적으로 vps 서버 사용)
# "real": 실전투자 (KIS API는 내부적으로 prod 서버 사용)
ENV_MODE = "demo"

# 실제 거래 활성화 (False면 시뮬레이션만)
TRADING_ENABLED = False

# 스케줄 실행 간격 (분)
SCHEDULE_INTERVAL_MINUTES = 5

# 감시 종목 리스트
WATCH_LIST = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035720",  # 카카오
    "035420",  # NAVER
]

# 전략 파라미터
MA_SHORT_PERIOD = 5   # 단기 이동평균 (일)
MA_LONG_PERIOD = 20   # 장기 이동평균 (일)

# 리스크 관리
MAX_POSITION_SIZE = 1000000  # 최대 투자 금액 (원)
STOP_LOSS_PERCENT = 3.0      # 손절 비율 (%)
TAKE_PROFIT_PERCENT = 5.0    # 익절 비율 (%)
```

### 4. 실행 방법

#### ⚠️ 중요: 이 프로젝트는 `uv` 기반입니다

이 프로젝트는 `uv` 패키지 매니저를 사용하므로 **반드시 `uv run`으로 실행**해야 합니다.
`python run_bot.py` 명령어는 의존성 오류가 발생할 수 있습니다.

#### 방법 1: uv 사용 (권장)
```bash
# 프로젝트 루트에서
cd /path/to/open-trading-api

# uv로 실행 (의존성 자동 관리)
uv run run_bot.py
```

#### 방법 2: pip로 의존성 수동 설치 후 실행
```bash
# 의존성 먼저 설치
pip install -r requirements.txt

# 그 다음 실행 가능
python run_bot.py
# 또는
python3 run_bot.py
```

> **💡 Tip**: `uv`가 없다면 설치하세요:
> ```bash
> curl -LsSf https://astral.sh/uv/install.sh | sh
> ```

## ⚙️ 사용 방법

### 기본 실행
```bash
# 프로젝트 루트에서 실행
cd /path/to/open-trading-api
uv run run_bot.py
```

### 안전한 테스트 (실제 거래 비활성화)
1. `config.py`에서 `TRADING_ENABLED = False` 설정
2. `ENV_MODE = "demo"` 설정 (모의투자 서버 사용)
3. 봇 실행 시 시그널만 로깅하고 실제 주문은 하지 않음

### 실제 거래
1. `config.py`에서 `ENV_MODE = "real"` 설정
2. `TRADING_ENABLED = True` 설정
3. **주의**: 실제 계좌에서 거래가 발생합니다!

### 실행 확인
```bash
# 로그 파일 확인
tail -f trading_bot/logs/Main_$(date +%Y%m%d).log

# 또는 모든 로그 확인
tail -f trading_bot/logs/*.log
```

## 📊 로그 확인

로그는 `trading_bot/logs/` 디렉토리에 일별로 저장됩니다:

```
logs/
├── Main_20260105.log                      # 메인 프로세스 로그
├── KISBroker_20260105.log                # API 호출 로그
├── Scheduler_20260105.log                # 스케줄러 실행 로그
└── Strategy.MA_Crossover_20260105.log    # 전략 시그널 로그
```

### 로그 예시
```
2026-01-05 22:03:50 - Scheduler - INFO - 장 운영 시간이 아닙니다. 전략을 실행하지 않습니다.
2026-01-05 09:05:00 - Strategy.MA_Crossover - INFO - [005930] BUY - 골든크로스 (단기=85000, 장기=83000)
2026-01-05 09:05:01 - KISBroker - INFO - [005930] 매수 주문 완료: 가격=85000, 수량=11
```

## 🔧 커스터마이징

### 새로운 전략 추가

1. `strategies/` 폴더에 새 파일 생성
2. `BaseStrategy` 상속받아 구현

```python
from .base_strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def __init__(self, broker):
        super().__init__(broker, "MyStrategy")
    
    def execute(self):
        # 전략 로직 구현
        for symbol in Config.WATCH_LIST:
            # 시그널 판단
            signal = self.analyze(symbol)
            
            if signal == 'BUY':
                self._execute_buy(symbol)
            elif signal == 'SELL':
                self._execute_sell(symbol)
```

3. `main.py`에서 전략 추가

```python
from strategies import MyStrategy

strategies = [
    MovingAverageCrossover(broker),
    MyStrategy(broker),  # 새 전략 추가
]
```

### 스케줄 간격 변경

`config.py`에서 `SCHEDULE_INTERVAL_MINUTES` 값을 변경하거나,
`scheduler.py`에서 직접 스케줄 로직을 수정할 수 있습니다.

## ⚠️ 주의사항

1. **테스트 필수**: 실제 거래 전에 반드시 `demo` 모드와 `TRADING_ENABLED=False`로 충분히 테스트하세요.

2. **리스크 관리**: 
   - `MAX_POSITION_SIZE`를 적절히 설정하세요
   - 손절/익절 로직 구현을 권장합니다

3. **API 제한**: 
   - KIS API에는 호출 제한이 있을 수 있습니다
   - 과도한 빈도의 조회는 피하세요

4. **네트워크**: 
   - 안정적인 인터넷 연결이 필요합니다
   - 24시간 운영 시 개인 VPS 또는 클라우드 서버 사용을 권장합니다
   - (참고: KIS API의 vps는 모의투자 서버를 의미하며, 개인 서버 VPS와는 다릅니다)

5. **장 운영 시간**: 
   - 평일 09:00~15:30에만 거래됩니다
   - 점심시간(12:00~13:00)도 거래 가능합니다

## 🔄 업데이트 방법

KIS측에서 소스 업데이트 시:

1. 기존 `examples_user/` 폴더 업데이트
2. `trading_bot/` 폴더는 그대로 유지
3. 필요 시 `broker/kis_broker.py`만 수정

이렇게 하면 기존 전략과 설정은 그대로 사용 가능합니다.

## 📈 확장 계획 (방안 1로 진화)

현재는 방안 3 (간단한 스케줄러 기반)으로 구현되어 있으며,
추후 방안 1 (전략 기반 모듈형 구조)로 확장 가능합니다:

- [ ] 이벤트 기반 시스템 추가
- [ ] 포트폴리오 관리자 구현
- [ ] 리스크 관리자 구현
- [ ] 실시간 WebSocket 연동
- [ ] 백테스팅 엔진 추가
- [ ] 성과 분석 대시보드

## 📝 라이선스

이 프로젝트는 KIS Open API 샘플 코드를 기반으로 하며,
개인 투자 목적으로만 사용하시기 바랍니다.

## 🤝 기여

버그 리포트나 기능 제안은 이슈로 등록해주세요.

## ⚖️ 면책 조항

이 프로그램은 교육 및 연구 목적으로 제공됩니다.
실제 투자에 사용 시 발생하는 모든 손실에 대해 개발자는 책임을 지지 않습니다.
투자는 본인의 판단과 책임 하에 진행하시기 바랍니다.
