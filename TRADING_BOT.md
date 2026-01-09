# 자동매매 봇 (Trading Bot)

이 저장소에는 KIS Open API를 활용한 **자동매매 봇**이 `trading_bot/` 폴더에 포함되어 있습니다.

## 📁 위치

```
open-trading-api/
└── trading_bot/                # 자동매매 봇 프로젝트
    ├── run_bot.py              # 봇 실행 스크립트
    ├── run_backtest.py         # 백테스트 실행 스크립트
    ├── create_external_db.py   # 외부 DB 생성 도구
    ├── README.md               # 봇 상세 문서
    ├── QUICKSTART.md           # 빠른 시작 가이드
    ├── BACKTEST_GUIDE.md       # 백테스트 가이드
    ├── ENV_MODE_GUIDE.md       # 실전/모의 환경 설정
    ├── IMPLEMENTATION.md       # 구현 상세
    ├── backtest/               # 백테스트 엔진
    │   ├── QUICKSTART.md       # 백테스트 빠른 시작
    │   ├── DATA_SOURCES.md     # 데이터 소스 가이드
    │   └── DB_GUIDE.md         # 외부 DB 생성 가이드
    ├── broker/                 # KIS API 래퍼
    ├── strategies/             # 매매 전략
    └── utils/                  # 유틸리티
```

## 🚀 시작하기

자세한 사용법은 아래 문서를 참고하세요:

### 📖 주요 문서 (우선순위)

#### 1. 처음 시작하는 사용자

1. **[trading_bot/QUICKSTART.md](trading_bot/QUICKSTART.md)** - 5분만에 시작하기 ⭐
   - KIS API 설정 방법
   - 봇 실행 단계별 가이드
   - 주요 명령어 및 문제 해결

2. **[trading_bot/README.md](trading_bot/README.md)** - 자동매매 봇 전체 개요
   - 프로젝트 구조
   - 주요 기능 소개
   - 설치 및 실행 방법

#### 2. 백테스트 사용자

1. **[trading_bot/backtest/QUICKSTART.md](trading_bot/backtest/QUICKSTART.md)** - 백테스트 빠른 시작 ⭐
   - 3가지 데이터 소스 사용법 (api, db, fdr)
   - 실전 예시 명령어
   - 결과 해석 방법

2. **[trading_bot/BACKTEST_GUIDE.md](trading_bot/BACKTEST_GUIDE.md)** - 백테스트 종합 가이드
   - 백테스트 개념 설명
   - 설정 변경 방법
   - 성과 지표 해석
   - 고급 사용법

3. **[trading_bot/backtest/DATA_SOURCES.md](trading_bot/backtest/DATA_SOURCES.md)** - 데이터 소스 비교
   - KIS API vs 외부 DB vs FinanceDataReader
   - 각 소스의 장단점 및 제약사항
   - 성능 비교

4. **[trading_bot/backtest/DB_GUIDE.md](trading_bot/backtest/DB_GUIDE.md)** - 외부 DB 생성 가이드
   - SQLite DB 구조 (2가지 형식)
   - FinanceDataReader로 DB 생성
   - 커스텀 DB 생성 방법

#### 3. 고급 사용자

1. **[trading_bot/ENV_MODE_GUIDE.md](trading_bot/ENV_MODE_GUIDE.md)** - 실전/모의 환경 설정
   - real/demo 용어 설명
   - 환경 전환 방법
   - 안전 체크리스트

2. **[trading_bot/IMPLEMENTATION.md](trading_bot/IMPLEMENTATION.md)** - 구현 상세
   - 코드 구조 설명
   - 동작 원리
   - 다음 단계 개발 가이드

## ⚡ 빠른 실행

### 봇 실행
```bash
# trading_bot 폴더로 이동 (권장)
cd trading_bot

# 봇 실행
uv run run_bot.py

# 또는 프로젝트 루트에서
cd open-trading-api
uv run trading_bot/run_bot.py
```

### 백테스트 실행
```bash
# trading_bot 폴더에서
cd trading_bot

# FDR로 2년 백테스트 (권장 - 무료, 무제한)
uv run run_backtest.py --source fdr --start 20220101

# KIS API로 최근 100일 백테스트
uv run run_backtest.py --source api

# 외부 DB로 백테스트
uv run run_backtest.py --source db --db-path backtest_data.db

# 외부 DB 생성
uv run create_external_db.py
```

### 주요 옵션
```bash
--source {api|db|fdr}    # 데이터 소스 선택
--start YYYYMMDD         # 시작일
--end YYYYMMDD           # 종료일
--symbols 005930 000660  # 종목 코드
--capital 10000000       # 초기 자본금
--short-period 5         # 단기 이동평균
--long-period 20         # 장기 이동평균
```

## 📦 주요 기능

### 1. 자동매매 봇
- ✅ **KIS Broker 래퍼**: 간편한 API 호출 인터페이스
- ✅ **전략 시스템**: 이동평균 교차 전략 (확장 가능)
- ✅ **스케줄러**: 정해진 시간에 자동 실행
- ✅ **로깅**: 모든 거래 내역 기록
- ✅ **안전 모드**: 실전/모의 환경 분리

### 2. 백테스트 엔진
- ✅ **3가지 데이터 소스**: KIS API (100일) / 외부 DB (무제한) / FinanceDataReader (무제한)
- ✅ **성과 지표**: 총 수익률, MDD, 샤프비율, 승률, 손익비
- ✅ **시각화**: 자산 곡선 차트 자동 생성
- ✅ **CSV 출력**: 거래 내역, 일별 자산 곡선
- ✅ **통합 인터페이스**: 단일 명령어로 모든 소스 사용

### 3. 문서화
- ✅ **빠른 시작 가이드**: 5분만에 실행 가능
- ✅ **상세 문서**: 각 기능별 설명
- ✅ **문제 해결**: 자주 발생하는 오류 해결법
- ✅ **예시 코드**: 실전 사용 예시

## 💡 사용 시나리오

### 시나리오 1: 처음 시작하는 사용자
1. [trading_bot/QUICKSTART.md](trading_bot/QUICKSTART.md) 읽기
2. KIS API 설정 (~/KIS/config/kis_devlp.yaml)
3. `cd trading_bot && uv run run_bot.py` 실행
4. 로그 확인으로 동작 검증

### 시나리오 2: 백테스트만 하는 사용자
1. [trading_bot/backtest/QUICKSTART.md](trading_bot/backtest/QUICKSTART.md) 읽기
2. `cd trading_bot` 이동
3. `uv run run_backtest.py --source fdr --start 20220101` 실행
4. backtest_results/ 폴더에서 결과 확인

### 시나리오 3: 장기 백테스트 사용자
1. [trading_bot/backtest/DB_GUIDE.md](trading_bot/backtest/DB_GUIDE.md) 읽기
2. `uv run create_external_db.py`로 DB 생성
3. `uv run run_backtest.py --source db --db-path backtest_data.db --start 20140101` 실행
4. 5년~10년 장기 백테스트 수행

### 시나리오 4: 실전 투자 준비
1. [trading_bot/ENV_MODE_GUIDE.md](trading_bot/ENV_MODE_GUIDE.md) 읽기
2. 모의투자로 충분한 테스트 (`ENV_MODE = "demo"`)
3. 백테스트로 전략 검증
4. 체크리스트 확인 후 실전 전환 (`ENV_MODE = "real"`)

## ⚠️ 주의사항

### 프로젝트 독립성
- trading_bot은 **별도 프로젝트**이며, KIS 제공 샘플 코드(`examples_llm/`, `examples_user/`)와는 독립적입니다.
- KIS 제공 샘플 코드가 업데이트되어도 trading_bot에는 영향을 주지 않습니다.
- 모든 커스텀 코드는 `trading_bot/` 폴더 안에만 배치됩니다.

### 투자 책임
- 실제 투자는 본인 책임이며, 충분한 테스트 후 사용하시기 바랍니다.
- 반드시 모의투자로 충분히 검증한 후 실전 투자하세요.
- 손절/익절 로직을 반드시 구현하세요.

### 실행 환경
- 이 프로젝트는 **uv 기반**이므로 `uv run` 명령어를 사용하세요.
- `python run_bot.py` 직접 실행은 의존성 오류가 발생할 수 있습니다.
- trading_bot 폴더에서 실행하는 것을 권장합니다.

## 🔧 설정 파일 위치

### KIS API 설정 (중요!)
```
~/KIS/config/kis_devlp.yaml    # 실제 사용 설정 파일
```
- 프로젝트 루트의 `kis_devlp.yaml`은 **템플릿**입니다.
- 반드시 `~/KIS/config/` 경로에 설정 파일을 생성하세요.

### 봇 설정
```
trading_bot/config.py            # 봇 동작 설정
```
- 감시 종목, 전략 파라미터, 실전/모의 모드 등 설정

### 환경 변수 및 .env 파일

- 프로젝트는 `trading_bot/config.py`에서 **프로젝트 루트에 위치한 `.env` 파일**과 시스템 환경변수를 읽어 설정을 초기화합니다.
- 우선순위: 시스템 환경변수 > 프로젝트 루트의 `.env` > 코드 내 기본값

- 사용 가능한 주요 키:
   - `ENV_MODE`: "real" 또는 "demo" (실전/모의)
   - `TRADING_ENABLED`: 실제 주문 활성화 여부 (`true`/`false`, `1`/`0`, `yes`/`no` 허용)

- 파일 위치(프로젝트 루트):
   - `./.env`  (실제 사용 파일 — 민감정보 포함 시 절대 커밋 금지)
   - `./.env.sample` (커밋 가능한 샘플 파일 — 저장소에 포함되어 있습니다)

- 예시 `.env` (프로젝트 루트에 생성):

```
ENV_MODE=demo
TRADING_ENABLED=true
```

- `.env.sample` 파일을 복사하여 `.env`로 이름을 바꾼 후, 환경에 맞게 값을 수정하면 됩니다.
- `TRADING_ENABLED`는 문자열 파싱으로 허용되는 값들을 처리하므로 `true/false`, `1/0`, `yes/no` 형태로 설정하세요.

참고: `.env.sample`은 저장소에 커밋해도 안전한 예시 파일입니다. 실제 운영값(특히 API 키 등 민감정보)은 `.env`에 두고 커밋하지 마세요.

### 백테스트 결과
```
trading_bot/backtest_results/    # 백테스트 결과 저장 (.gitignore)
trading_bot/backtest_data.db     # 외부 DB 파일 (.gitignore)
```

### 로그
```
trading_bot/logs/                # 실행 로그 저장
```

## 🚀 다음 단계

### 1단계: 기본 실행
- [ ] [QUICKSTART.md](trading_bot/QUICKSTART.md) 읽고 봇 실행해보기
- [ ] 로그 확인하여 정상 동작 검증
- [ ] 모의투자 모드에서 충분히 테스트

### 2단계: 백테스트
- [ ] [backtest/QUICKSTART.md](trading_bot/backtest/QUICKSTART.md) 읽기
- [ ] FDR로 빠른 백테스트 실행
- [ ] 전략 파라미터 조정하며 최적화

### 3단계: 고급 사용
- [ ] 외부 DB 생성하여 장기 백테스트
- [ ] 커스텀 전략 개발
- [ ] 실전 투자 전 체크리스트 확인

## 🔗 관련 링크

- [KIS Open API 포털](https://apiportal.koreainvestment.com/)
- [프로젝트 최상단 README](README.md)
- [코딩 컨벤션](docs/convention.md)

---

**💡 더 자세한 내용은 [trading_bot/README.md](trading_bot/README.md)를 참고하세요.**
