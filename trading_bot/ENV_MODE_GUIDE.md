# 실전/모의 투자 환경 설정 가이드

## 📌 용어 정리

이 프로젝트에서는 실전/모의 투자 구분을 위해 다음과 같은 용어를 사용합니다:

### 사용자 관점 (설정 파일)
- **`real`**: 실전투자 (실제 돈이 거래됨)
- **`demo`**: 모의투자 (가상 계좌, 실제 돈 사용 안 함)

### KIS API 내부 (자동 변환)
- **`prod`**: 실전투자 서버 (Production)
- **`vps`**: 모의투자 서버 (Virtual Private Server)

> **중요**: 사용자는 `real`/`demo`만 사용하면 됩니다. 
> `prod`/`vps`는 KIS API 내부적으로 자동 변환되어 사용됩니다.

## 🔄 변환 흐름

```
사용자 설정          →    KIS 인증          →    KIS API 호출
-----------------------------------------------------------------
real (실전투자)     →    prod 서버         →    env_dv="real"
demo (모의투자)     →    vps 서버          →    env_dv="demo"
```

## ⚙️ 설정 방법

### 0. KIS 설정 파일 위치 (중요!)

**KIS API는 다음 경로의 설정 파일을 사용합니다:**
```
~/KIS/config/kis_devlp.yaml
```

**프로젝트 루트의 `kis_devlp.yaml`은 예시/템플릿 파일입니다.**

실제 사용을 위해서는 반드시 `~/KIS/config/kis_devlp.yaml`을 생성해야 합니다:

```bash
# 디렉토리 생성
mkdir -p ~/KIS/config

# 템플릿 복사 (프로젝트 루트에서)
cp kis_devlp.yaml ~/KIS/config/

# 설정 파일 수정
vi ~/KIS/config/kis_devlp.yaml
```

### 1. config.py 설정
```python
# trading_bot/config.py

# 모의투자 (개발/테스트용)
ENV_MODE = "demo"

# 실전투자 (주의!)
# ENV_MODE = "real"
```

### 2. kis_devlp.yaml 설정
```yaml
# ~/KIS/config/kis_devlp.yaml

# 실전투자 앱키
my_app: "실전투자_앱키"
my_sec: "실전투자_시크릿"

# 모의투자 앱키
paper_app: "모의투자_앱키"
paper_sec: "모의투자_시크릿"

# 계좌 정보
my_acct: "12345678"
my_prod: "01"  # 01: 주식, 03: 선물옵션 등

# 서버 URL (KIS API 내부 사용, 수정 불필요)
prod: "https://openapi.koreainvestment.com:9443"      # 실전투자 서버
vps: "https://openapivts.koreainvestment.com:29443"  # 모의투자 서버
```

## 💻 코드 내부 동작

### 인증 시 (KISBroker._init_auth)
```python
# 사용자 설정값을 KIS 서버 파라미터로 변환
svr = "prod" if self.env_mode == "real" else "vps"

# 해당 서버로 인증
ka.auth(svr=svr)  # prod 또는 vps 서버에 인증
```

### API 호출 시
```python
# API 함수는 "real"/"demo"를 받도록 설계됨
dsf.inquire_price(
    env_dv=self.env_mode,  # "real" 또는 "demo" 전달
    ...
)

dsf.order_cash(
    env_dv=self.env_mode,  # "real" 또는 "demo" 전달
    ...
)
```

## 🎯 사용 예시

### 안전한 테스트 (권장)
```python
# config.py
ENV_MODE = "demo"           # 모의투자 서버
TRADING_ENABLED = False     # 주문 실행 안 함 (로깅만)
```
- 실제 주문이 전혀 실행되지 않음
- API 호출만 테스트
- 가장 안전한 방식

### 모의투자
```python
# config.py
ENV_MODE = "demo"           # 모의투자 서버
TRADING_ENABLED = True      # 주문 실행
```
- 모의투자 계좌에서 주문 실행
- 실제 돈 사용 안 함
- 전략 테스트에 적합

### 실전투자 (⚠️ 주의)
```python
# config.py
ENV_MODE = "real"           # 실전투자 서버
TRADING_ENABLED = True      # 주문 실행
```
- **실제 계좌로 주문 실행**
- **실제 돈이 거래됨**
- 충분한 테스트 후에만 사용!

## 🚫 주의사항

### ❌ 하지 말아야 할 것
```python
# 잘못된 예시
ENV_MODE = "prod"   # ❌ "prod"는 사용 안 함
ENV_MODE = "vps"    # ❌ "vps"는 사용 안 함
```

### ✅ 올바른 사용
```python
# 올바른 예시
ENV_MODE = "real"   # ✅ 실전투자
ENV_MODE = "demo"   # ✅ 모의투자
```

## 🔍 확인 방법

### 로그에서 확인
```bash
# trading_bot 폴더에서
cd trading_bot
tail -f logs/Main_*.log

# 또는 프로젝트 루트에서
tail -f trading_bot/logs/Main_*.log
```

다음과 같은 메시지로 환경 확인:
```
2026-01-06 10:00:00 - Main - INFO - 환경 모드: demo
2026-01-06 10:00:00 - KISBroker - INFO - 계좌 정보 로드 완료: 12345678-01 (서버: vps)
```

### 서버 확인
- `서버: prod` → 실전투자 서버 사용 중
- `서버: vps` → 모의투자 서버 사용 중

## 📚 참고

### KIS API 문서 용어
- **실전투자**: Production 환경, prod 서버
- **모의투자**: Virtual 환경, vps 서버

### 우리 프로젝트 용어
- **실전투자**: `real` (사용자 친화적)
- **모의투자**: `demo` (사용자 친화적)

### TR ID 구분
KIS API는 TR ID로 실전/모의를 구분합니다:
- 실전투자: `TTTC00XXX` 형식
- 모의투자: `VTTC00XXX` 형식 (앞글자가 V)

domestic_stock_functions.py에서 `env_dv` 파라미터를 통해 자동으로 올바른 TR ID를 선택합니다.

## ✅ 체크리스트

실전투자 전환 전 확인사항:

- [ ] 모의투자(`demo`)에서 충분히 테스트 완료
- [ ] `TRADING_ENABLED=False`로 시뮬레이션 테스트 완료
- [ ] kis_devlp.yaml에 실전투자 앱키 설정 확인
- [ ] 계좌번호와 상품코드 확인
- [ ] 손절/익절 로직 구현 확인
- [ ] MAX_POSITION_SIZE 적절히 설정
- [ ] 로그 모니터링 준비
- [ ] 긴급 종료 방법 숙지 (`pkill -f run_bot.py`)

---

**마지막 경고**: `ENV_MODE = "real"`로 설정하면 실제 계좌에서 거래가 발생합니다. 
충분한 테스트 없이 실전투자 모드를 사용하지 마세요!
