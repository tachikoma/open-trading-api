# ✅ KIS 자동매매 봇 구현 완료

## 🎯 구현 내용

### 완료된 작업
1. ✅ **폴더 구조 생성** (방안 3 기반)
   - trading_bot/ 메인 디렉토리
   - broker/ (KIS API 래퍼)
   - strategies/ (전략 모듈)
   - utils/ (유틸리티)
   - logs/ (로그 저장)

2. ✅ **KIS Broker 래퍼 구현**
   - examples_user/ 코드를 import하여 래핑
   - 간단한 인터페이스 제공
   - 자동 인증 처리

3. ✅ **전략 시스템 구현**
   - BaseStrategy 추상 클래스
   - MovingAverageCrossover 예시 전략
   - 쉬운 확장 구조

4. ✅ **스케줄러 구현**
   - 5분 간격 자동 실행
   - 장 운영 시간 체크
   - schedule 라이브러리 선택적 사용

5. ✅ **설정 관리**
   - config.py 중앙 집중식 설정
   - 환경 모드 분리 (demo/real)
   - 안전장치 (TRADING_ENABLED)

6. ✅ **로깅 시스템**
   - 모듈별 분리된 로그
   - 일별 로그 파일 저장
   - 디버깅 편의성

7. ✅ **문서화**
   - README.md (전체 가이드)
   - QUICKSTART.md (빠른 시작)
   - 코드 주석

## 📁 최종 파일 구조

```
open-trading-api/
├── run_bot.py                          # 👈 메인 실행 파일
├── kis_devlp.yaml                      # KIS API 설정 (~/KIS/config/)
├── pyproject.toml
├── requirements.txt
├── examples_user/                       # KIS 원본 코드 (유지)
│   ├── kis_auth.py
│   └── domestic_stock/
│       ├── domestic_stock_functions.py
│       └── domestic_stock_functions_ws.py
└── trading_bot/                         # 👈 새로 만든 자동매매 봇
    ├── __init__.py
    ├── main.py                          # 봇 메인 로직
    ├── config.py                        # 설정 파일
    ├── scheduler.py                     # 스케줄러
    ├── README.md                        # 상세 문서
    ├── QUICKSTART.md                    # 빠른 시작
    ├── broker/
    │   ├── __init__.py
    │   └── kis_broker.py               # KIS API 래퍼
    ├── strategies/
    │   ├── __init__.py
    │   ├── base_strategy.py            # 전략 베이스 클래스
    │   └── ma_crossover.py             # 이동평균 교차 전략
    ├── utils/
    │   ├── __init__.py
    │   └── logger.py                   # 로깅 유틸
    └── logs/                           # 로그 파일들
        ├── Main_20260105.log
        ├── KISBroker_20260105.log
        ├── Scheduler_20260105.log
        └── Strategy.MA_Crossover_20260105.log
```

## 🚀 실행 방법

### 기본 실행 (uv 필수)
```bash
# 프로젝트 루트에서
cd /path/to/open-trading-api

# uv로 실행 (의존성 자동 관리)
uv run run_bot.py
```

> **⚠️ 중요**: 이 프로젝트는 `uv` 기반입니다.
> `python run_bot.py`는 의존성 오류가 발생합니다.

### 실행 성공 확인
로그에서 다음과 같은 메시지 확인:
```
2026-01-05 22:03:50 - Main - INFO - KIS 자동매매 봇 시작
2026-01-05 22:03:50 - Main - INFO - 환경 모드: demo
2026-01-05 22:03:50 - Main - INFO - 거래 활성화: False
2026-01-05 22:03:50 - KISBroker - INFO - KISBroker 초기화 완료 (모드: demo)
2026-01-05 22:03:50 - Scheduler - INFO - 스케줄러 시작 (간격: 5분)
```

## ⚙️ 주요 설정

### trading_bot/config.py
```python
ENV_MODE = "demo"                    # demo: 모의투자, real: 실전
TRADING_ENABLED = False              # False: 로그만, True: 실제 주문
SCHEDULE_INTERVAL_MINUTES = 5        # 5분마다 전략 실행

WATCH_LIST = [                       # 감시 종목
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035720",  # 카카오
    "035420",  # NAVER
]

MAX_POSITION_SIZE = 1000000          # 최대 1백만원 투자
MA_SHORT_PERIOD = 5                  # 5일 이동평균
MA_LONG_PERIOD = 20                  # 20일 이동평균
```

### ~/KIS/config/kis_devlp.yaml
```yaml
paper_app: "모의투자_앱키"
paper_sec: "모의투자_시크릿"
my_acct: "12345678"
my_prod: "01"
# ... (나머지 설정)
```

## 🔍 동작 원리

### 1. 초기화
1. KIS API 인증 (`ka.auth()`)
2. Broker 초기화 (계좌 정보 로드)
3. 전략 초기화 (이동평균 설정)
4. 스케줄러 시작

### 2. 전략 실행 (5분마다)
1. 장 운영 시간 체크
2. 감시 종목 순회:
   - 일별 시세 조회
   - 이동평균 계산
   - 시그널 판단 (BUY/SELL/HOLD)
3. 시그널 발생 시:
   - BUY: 현재가 조회 → 매수 가능 금액 확인 → 주문
   - SELL: 보유 잔고 확인 → 매도 주문

### 3. 로깅
- 모든 동작을 일별 로그 파일에 기록
- 시그널, 주문, 오류 등 추적 가능

## 📊 현재 상태

### ✅ 정상 동작 확인
- [x] 프로젝트 루트에서 `uv run run_bot.py` 실행 가능
- [x] KIS API 인증 성공
- [x] 스케줄러 정상 시작
- [x] 로그 파일 생성
- [x] 장 운영 시간 체크 동작

### 🔒 안전 설정
- [x] `TRADING_ENABLED = False` (실제 주문 비활성화)
- [x] `ENV_MODE = "demo"` (모의투자 서버)
- [x] 로그로 모든 동작 추적 가능

## 🎓 사용 예시

### 시나리오 1: 안전하게 테스트
```python
# config.py
ENV_MODE = "demo"
TRADING_ENABLED = False

# 실행 결과: 로그에만 기록, 주문 없음
# [DRY RUN] 매수 주문: 005930, 수량: 10, 가격: 85000
```

### 시나리오 2: 모의투자로 실전 연습
```python
# config.py
ENV_MODE = "demo"
TRADING_ENABLED = True

# 실행 결과: 모의투자 서버에 실제 주문
# [005930] 매수 성공
```

### 시나리오 3: 실전 투자 (주의!)
```python
# config.py
ENV_MODE = "real"
TRADING_ENABLED = True

# 실행 결과: 실제 계좌로 주문 실행!!!
```

## 🔧 문제 해결

### ImportError 발생
**문제**: `ImportError: attempted relative import beyond top-level package`
**해결**: 프로젝트 루트에서 `run_bot.py` 실행 (trading_bot/ 안에서 실행 X)

### KIS 인증 실패
**문제**: `AttributeError: module 'kis_auth' has no attribute 'trenv'`
**해결**: `ka.auth()` 먼저 호출 필요 → 이미 kis_broker.py에 구현됨

### schedule 모듈 없음
**문제**: `ModuleNotFoundError: No module named 'schedule'`
**해결**: scheduler.py가 자동으로 fallback → 문제 없음

## 📈 다음 단계 (방안 1로 진화)

### 추가 가능 기능
- [ ] 리스크 관리자 (손절/익절 자동화)
- [ ] 포트폴리오 관리 (여러 종목 동시 관리)
- [ ] WebSocket 실시간 시세 연동
- [ ] 백테스팅 엔진
- [ ] 텔레그램 알림
- [ ] 성과 분석 대시보드

### 전략 추가
```python
# trading_bot/strategies/my_strategy.py
from trading_bot.strategies.base_strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def execute(self):
        # 나만의 전략 구현
        pass

# main.py에 추가
strategies = [
    MovingAverageCrossover(broker),
    MyStrategy(broker),  # 새 전략
]
```

## 📚 참고 자료
- [KIS Open API 문서](https://apiportal.koreainvestment.com)
- [GitHub 예제](https://github.com/koreainvestment/open-trading-api)
- trading_bot/README.md
- trading_bot/QUICKSTART.md

## ⚠️ 주의사항
1. **반드시 테스트 먼저**: TRADING_ENABLED=False로 충분히 테스트
2. **리스크 관리**: MAX_POSITION_SIZE 적절히 설정
3. **모니터링**: 로그를 주기적으로 확인
4. **API 제한**: 과도한 호출 주의
5. **네트워크**: 안정적인 인터넷 필요

---

**구현 완료일**: 2026-01-05  
**버전**: 0.1.0 (방안 3 기반)  
**다음 목표**: 방안 1로 진화 (이벤트 기반 아키텍처)
