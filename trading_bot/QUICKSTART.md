# KIS 자동매매 봇 빠른 시작 가이드

## 🚀 5분만에 시작하기

### 1단계: 프로젝트 다운로드
```bash
git clone <repository-url>
cd open-trading-api
```

### 2단계: KIS API 설정
`~/KIS/config/kis_devlp.yaml` 파일 생성 및 설정:

```yaml
# 모의투자 (테스트용)
paper_app: "모의투자_앱키"
paper_sec: "모의투자_시크릿키"

# 계좌 정보
my_acct: "12345678"  # 계좌번호 8자리
my_prod: "01"        # 상품코드 2자리
my_htsid: "your_hts_id"

# 서버 URL (KIS API 내부 사용, 그대로 사용)
vps: "https://openapivts.koreainvestment.com:29443"  # 모의투자 서버
prod: "https://openapi.koreainvestment.com:9443"     # 실전투자 서버
my_url: "https://openapivts.koreainvestment.com:29443"
my_url_ws: "ws://ops.koreainvestment.com:31000"
my_agent: "Mozilla/5.0"
```

> **💡 KIS 앱키 발급 방법**
> 1. [한국투자증권 홈페이지](https://www.koreainvestment.com) 접속
> 2. Open API 신청 (모의투자/실전투자)
> 3. 앱키/시크릿키 발급받기

### 3단계: 봇 설정 (선택사항)
`trading_bot/config.py`에서 원하는 설정 변경:

```python
# 감시 종목 변경
WATCH_LIST = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
]

# 거래 비활성화 (테스트용)
TRADING_ENABLED = False
```

### 4단계: 실행!
```bash
# 프로젝트 루트에서
cd /path/to/open-trading-api

# uv로 실행 (권장 - 의존성 자동 관리)
uv run run_bot.py
```

> **⚠️ 주의**: `python run_bot.py`는 의존성 오류가 발생할 수 있습니다.
> 이 프로젝트는 `uv` 기반이므로 `uv run`을 사용하세요.

### 5단계: 로그 확인
```bash
# 실시간 로그 모니터링
tail -f trading_bot/logs/Main_$(date +%Y%m%d).log
```

## 📝 주요 명령어

### 실행
```bash
# 기본 실행 (항상 프로젝트 루트에서)
cd /path/to/open-trading-api
uv run run_bot.py

# 백그라운드 실행 (nohup)
nohup uv run run_bot.py > bot.log 2>&1 &

# 백그라운드 실행 (screen)
screen -S trading_bot
cd /path/to/open-trading-api
uv run run_bot.py
# Ctrl+A, D로 detach
```

> **💡 Tip**: 항상 프로젝트 루트(`open-trading-api/`)에서 실행하세요.

### 로그 확인
```bash
# 전체 로그
tail -f trading_bot/logs/*.log

# 메인 로그만
tail -f trading_bot/logs/Main_*.log

# 전략 시그널만
tail -f trading_bot/logs/Strategy*.log

# 최근 100줄
tail -100 trading_bot/logs/Main_*.log
```

### 프로세스 관리
```bash
# 실행 중인 봇 찾기
ps aux | grep run_bot.py

# 종료
pkill -f run_bot.py

# 또는 Ctrl+C (포그라운드 실행 시)
```

## ⚙️ 모드별 설정

### 테스트 모드 (안전)
```python
# config.py
ENV_MODE = "demo"           # 모의투자 서버 (KIS API는 내부적으로 vps 서버 사용)
TRADING_ENABLED = False     # 주문 비활성화 (로깅만)
```
- 실제 주문 없음
- API 호출만 테스트
- 안전하게 전략 검증 가능

### 모의투자 모드
```python
# config.py
ENV_MODE = "demo"           # 모의투자 서버 (KIS API는 내부적으로 vps 서버 사용)
TRADING_ENABLED = True      # 주문 활성화
```
- 모의투자 서버에서 주문 실행
- 실제 돈은 사용 안 함
- 전략 실전 테스트

### 실전투자 모드 (주의!)
```python
# config.py
ENV_MODE = "real"           # 실전투자 서버 (KIS API는 내부적으로 prod 서버 사용)
TRADING_ENABLED = True      # 주문 활성화
```
- **실제 계좌로 주문 실행**
- **실제 돈이 거래됨**
- 충분한 테스트 후에만 사용!

## 🔧 문제 해결

### "python run_bot.py" 실행 시 오류
**증상**: `ModuleNotFoundError: No module named 'pandas'`

**해결**: 이 프로젝트는 `uv` 기반입니다. `uv run`을 사용하세요.
```bash
# ❌ 이렇게 실행하면 오류 발생
python run_bot.py

# ✅ 올바른 실행 방법
uv run run_bot.py
```

### uv가 설치되지 않은 경우
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 또는 pip로 의존성 수동 설치
pip install -r requirements.txt
python run_bot.py
```

### ImportError 발생 시
```bash
# 의존성 재설치 (uv 사용)
uv sync

# 또는 pip 사용
pip install -r requirements.txt --force-reinstall
```

### KIS 인증 오류
1. `~/KIS/config/kis_devlp.yaml` 파일 경로 확인
2. 앱키/시크릿키 정확성 확인
3. 계좌번호/상품코드 확인

### 장 운영 시간 외 실행
- 평일 09:00~15:30만 전략 실행
- 시간 외에는 대기 상태
- 로그에서 확인 가능:
  ```
  장 운영 시간이 아닙니다. 전략을 실행하지 않습니다.
  ```

### 로그 파일 없음
```bash
# 로그 디렉토리 생성
mkdir -p trading_bot/logs

# 권한 확인
chmod 755 trading_bot/logs
```

## 📚 더 알아보기

- [상세 README](README.md) - 전체 기능 설명
- [KIS Open API 문서](https://apiportal.koreainvestment.com)
- [GitHub 예제 코드](https://github.com/koreainvestment/open-trading-api)

## ⚠️ 주의사항

1. **테스트 필수**: 실전 전에 반드시 모의투자로 충분히 테스트
2. **리스크 관리**: `MAX_POSITION_SIZE` 적절히 설정
3. **API 제한**: 과도한 호출 주의
4. **네트워크**: 안정적인 연결 필요
5. **모니터링**: 로그를 주기적으로 확인

## 💡 팁

- 24시간 운영 시 개인 VPS(가상 서버) 또는 클라우드 서버 사용 권장
  - 참고: KIS API의 'vps'는 모의투자 서버를 의미하며, 개인 서버 VPS와는 다릅니다
- 로그 디스크 용량 정기 체크
- 전략 파라미터는 백테스팅 후 조정
- 손절/익절 로직 반드시 구현
