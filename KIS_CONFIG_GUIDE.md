# KIS 설정 파일 위치 안내

## 📁 설정 파일 경로

### 실제 사용 경로
KIS API 인증은 다음 경로의 설정 파일을 사용합니다:
```
~/KIS/config/kis_devlp.yaml
```

이 경로는 `examples_user/kis_auth.py`에 하드코딩되어 있습니다.

### 템플릿 파일
프로젝트 루트의 `kis_devlp.yaml`은 **예시/템플릿 파일**입니다.

## 🚀 설정 파일 생성 방법

### 1. 디렉토리 생성
```bash
mkdir -p ~/KIS/config
```

### 2. 템플릿 복사
```bash
# 프로젝트 루트에서
cp kis_devlp.yaml ~/KIS/config/
```

### 3. 설정 파일 수정
```bash
# 편집기로 열기
vi ~/KIS/config/kis_devlp.yaml
# 또는
code ~/KIS/config/kis_devlp.yaml
# 또는
nano ~/KIS/config/kis_devlp.yaml
```

### 4. API 키 입력
- 실전투자 앱키/시크릿키
- 모의투자 앱키/시크릿키
- 계좌번호 및 상품코드

## 📝 설정 파일 구조

```yaml
# 실전투자 (Production)
my_app: "실전투자_앱키"
my_sec: "실전투자_시크릿"

# 모의투자 (Virtual)
paper_app: "모의투자_앱키"
paper_sec: "모의투자_시크릿"

# 계좌 정보
my_acct: "12345678"  # 계좌번호 8자리
my_prod: "01"        # 상품코드 2자리 (01:주식, 03:선물옵션 등)
my_htsid: "HTS_ID"

# 서버 URL (수정 불필요)
prod: "https://openapi.koreainvestment.com:9443"      # 실전투자 서버
vps: "https://openapivts.koreainvestment.com:29443"   # 모의투자 서버
ops: "ws://ops.koreainvestment.com:21000"             # 실전 웹소켓
vops: "ws://ops.koreainvestment.com:31000"            # 모의 웹소켓
```

## ⚠️ 주의사항

1. **보안**: 설정 파일에는 민감한 정보(API 키)가 포함되므로 Git에 커밋하지 마세요
   - 이미 `.gitignore`에 등록되어 있습니다
   
2. **경로 고정**: `~/KIS/config/kis_devlp.yaml` 경로는 KIS 예제 코드에 하드코딩되어 있어 변경할 수 없습니다

3. **템플릿 파일**: 프로젝트 루트의 `kis_devlp.yaml`은 참고용이며, 실제로는 사용되지 않습니다

## 🔍 확인 방법

설정 파일이 올바르게 생성되었는지 확인:
```bash
# 파일 존재 확인
ls -la ~/KIS/config/kis_devlp.yaml

# 파일 내용 확인 (민감정보 주의!)
cat ~/KIS/config/kis_devlp.yaml
```

## 💡 자동매매 봇 사용자

자동매매 봇(`trading_bot/`)을 사용하는 경우:
- `~/KIS/config/kis_devlp.yaml` 파일이 반드시 필요합니다
- `trading_bot/config.py`에서는 ENV_MODE만 설정하면 됩니다
- 자세한 내용은 [trading_bot/README.md](trading_bot/README.md)를 참고하세요

## 🆘 문제 해결

### "FileNotFoundError: kis_devlp.yaml"
**원인**: `~/KIS/config/kis_devlp.yaml` 파일이 없습니다

**해결**:
```bash
mkdir -p ~/KIS/config
cp kis_devlp.yaml ~/KIS/config/
vi ~/KIS/config/kis_devlp.yaml  # API 키 입력
```

### "Authentication failed"
**원인**: API 키가 잘못되었거나 만료되었습니다

**해결**:
1. [한국투자증권 Open API 포털](https://apiportal.koreainvestment.com)에서 API 키 확인
2. `~/KIS/config/kis_devlp.yaml`에 올바른 키 입력
3. 실전/모의 구분이 맞는지 확인

### 경로를 변경하고 싶은 경우
`examples_user/kis_auth.py` 파일을 수정해야 하지만, **권장하지 않습니다**:
- KIS에서 제공한 원본 코드 유지 권장
- 업데이트 시 충돌 가능성
- 표준 경로를 사용하는 것이 다른 사용자와 협업에 유리
