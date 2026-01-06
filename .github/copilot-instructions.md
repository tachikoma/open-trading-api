# Copilot Instructions for KIS Trading Bot Project

## 🎯 프로젝트 개요

이 저장소는 **두 개의 독립적인 프로젝트**가 공존합니다:

1. **KIS Open API 샘플 코드** (루트 레벨): 한국투자증권 제공 예시 (`examples_llm/`, `examples_user/`)
2. **자동매매 봇** (`trading_bot/` 폴더): KIS API를 활용한 커스텀 트레이딩 봇

### 핵심 아키텍처 원칙

- **격리**: KIS 제공 코드(루트)와 커스텀 봇 코드(`trading_bot/`)는 완전히 분리
- **단방향 의존성**: `trading_bot/`만 KIS 예시 코드를 import (역방향 금지)
- **보호**: KIS 원본 파일(`examples_llm/`, `examples_user/`, 루트 `README.md`)은 절대 수정 금지
- **예외**: `pyproject.toml`은 trading_bot 의존성 추가 시 수정 가능 (KIS 샘플은 의존성 최소화로 영향 없음)

```
open-trading-api/
├── examples_llm/           # LLM용 단일 API 기능 예제 (KIS 제공, 수정 금지 ❌)
├── examples_user/          # 사용자용 통합 API 예제 (KIS 제공, 수정 금지 ❌)
└── trading_bot/            # 자동매매 봇 (모든 커스텀 코드 ✅)
    └── broker/kis_broker.py  # examples_user를 래핑하여 전략 모듈에 제공
```

## 프로젝트 환경

### 🔧 빌드 시스템: UV 기반
이 프로젝트는 **`uv` 패키지 매니저**를 사용합니다.

- **의존성 관리**: `pyproject.toml`
- **실행 방법**: `uv run <script>`
- **Python 직접 실행 불가**: `python run_bot.py` ❌

### ⚠️ 중요: 실행 명령어

#### ✅ 올바른 실행 방법
```bash
# trading_bot 폴더에서 실행
cd trading_bot

# 메인 봇 실행
uv run run_bot.py

# 백테스트 실행
uv run run_backtest.py --source fdr

# 또는 프로젝트 루트에서 실행 (경로 포함)
uv run trading_bot/run_bot.py
uv run trading_bot/run_backtest.py --source fdr
```

#### ❌ 잘못된 실행 방법
```bash
# 이렇게 하면 의존성 오류 발생!
python run_bot.py          # ModuleNotFoundError
python3 run_bot.py         # ModuleNotFoundError
./run_bot.py               # 작동 안 함
```

**이유**: `uv run`은 자동으로 가상환경과 의존성을 관리하지만, 
직접 `python` 실행은 시스템 Python을 사용하여 필요한 패키지가 없을 수 있음.

## 📝 문서 작성 가이드라인

### 📁 파일 배치 원칙

1. **README.md (루트)**
   - KIS 원본 유지, 절대 수정 금지
   - trading_bot 관련 내용 추가 금지
   
2. **TRADING_BOT.md (루트)**
   - 자동매매 봇 소개 및 링크 모음
   - trading_bot/ 문서들로 연결
   
3. **trading_bot/README.md**
   - 자동매매 봇 상세 문서
   - 설치, 실행, 설정 방법

4. **trading_bot/backtest/*.md**
   - 백테스트 관련 상세 가이드
   - 경로는 모두 상대경로 사용 (trading_bot 폴더 기준)

### 실행 명령어 작성 시

#### trading_bot 폴더 기준으로 작성 (권장)

**좋은 예:**
```markdown
### 실행 방법

\`\`\`bash
# trading_bot 폴더에서
cd trading_bot
uv run run_backtest.py --source fdr --start 20220101

# 또는 프로젝트 루트에서
uv run trading_bot/run_backtest.py --source fdr --start 20220101
\`\`\`
```

**나쁜 예:**
```markdown
# 실행
python run_bot.py  # ❌ uv 없이는 작동 안 함!
```

### 설치 가이드 작성 시

```markdown
## 설치

### 방법 1: uv 사용 (권장)
\`\`\`bash
# uv가 없으면 먼저 설치
curl -LsSf https://astral.sh/uv/install.sh | sh

# trading_bot 폴더로 이동
cd trading_bot

# 프로젝트 실행 (의존성 자동 설치)
uv run run_bot.py
\`\`\`

### 방법 2: pip 사용
\`\`\`bash
# 의존성 수동 설치
pip install -r requirements.txt

# trading_bot 폴더로 이동
cd trading_bot

# 실행
python run_bot.py
\`\`\`
```

## 💻 코드 작성 가이드라인

### KIS API 인증 시스템

**중요**: KIS API는 특정 위치의 설정 파일을 사용합니다:
- **설정 파일 위치**: `~/KIS/config/kis_devlp.yaml` (사용자 홈 디렉토리)
- **프로젝트 루트의 kis_devlp.yaml**: 템플릿/예시일 뿐, 실제로 사용되지 않음
- **인증 모듈**: `examples_llm/kis_auth.py` 또는 `examples_user/kis_auth.py`

```python
# kis_auth.py가 읽는 설정 파일 경로
config_root = os.path.join(os.path.expanduser("~"), "KIS", "config")
# ~/KIS/config/kis_devlp.yaml
```

### 환경 모드 변환 (real/demo ↔ prod/vps)

**사용자 용어**와 **KIS API 내부 파라미터**가 다릅니다:

| 사용자 설정 | KIS API 파라미터 | 의미 |
|------------|-----------------|------|
| `real` | `prod` | 실전투자 서버 |
| `demo` | `vps` | 모의투자 서버 |

```python
# Config.ENV_MODE: "real" or "demo" (사용자 친화적)
# kis_auth.auth(svr): "prod" or "vps" (KIS API 내부)

# 변환 로직 (kis_broker.py 참고)
svr = "prod" if config.ENV_MODE == "real" else "vps"
ka.auth(svr=svr)
```

**⚠️ 중요: ENV_MODE 변경 시 토큰 삭제 필수**

KIS API는 토큰을 날짜별로 저장하지만 서버 구분(prod/vps)이 파일명에 없어서, 
ENV_MODE 변경 시 **이전 모드의 토큰이 재사용**되어 인증 실패할 수 있습니다.

```bash
# ENV_MODE 변경 시 반드시 실행
rm ~/KIS/config/KIS$(date +%Y%m%d)  # 오늘 토큰 삭제

# 전체 절차
# 1. 토큰 삭제
# 2. config.py에서 ENV_MODE 변경
# 3. 봇 재시작 (새 토큰 자동 발급)
```

자세한 내용은 [trading_bot/ENV_MODE_GUIDE.md](trading_bot/ENV_MODE_GUIDE.md) 참고

### Import 경로

이 프로젝트는 **절대 import** 방식을 사용합니다:

```python
# ✅ 올바른 방식
from trading_bot.config import Config
from trading_bot.broker import KISBroker
from trading_bot.strategies import MovingAverageCrossover

# ❌ 잘못된 방식 (relative import)
from .config import Config          # ImportError 발생!
from ..broker import KISBroker      # ImportError 발생!
```

**이유**: 
- 프로젝트 루트에서 `uv run`으로 실행
- 패키지를 top-level에서 import
- Relative import는 패키지 내부에서만 동작

### sys.path 설정

**trading_bot 폴더 내 실행 스크립트 패턴:**

```python
#!/usr/bin/env python3
"""
trading_bot 폴더 내 실행 스크립트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (trading_bot의 상위)
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# trading_bot 패키지 import
from trading_bot.config import Config
from trading_bot.main import main

if __name__ == "__main__":
    main()
```

**주의사항:**
- `Path(__file__).parent.parent` - trading_bot에서 프로젝트 루트로
- 절대 import 사용: `from trading_bot.xxx`

## 📐 코딩 컨벤션 (KIS 샘플 코드)

### 명명 규칙 (docs/convention.md 기반)
- **모듈/변수/함수**: `snake_case`
- **클래스**: `PascalCase`
- **상수**: `UPPER_SNAKE_CASE`
- **축약어 금지**: 널리 알려진 것(URL, ID) 외에는 명확한 전체 이름 사용

### Docstring 작성 (Google/Sphinx/NumPy 스타일)
```python
def get_current_price(symbol: str) -> Optional[pd.DataFrame]:
    """
    현재가 조회
    
    Args:
        symbol: 종목코드 (예: "005930")
    
    Returns:
        현재가 정보 DataFrame. 실패 시 None.
    
    Example:
        >>> df = broker.get_current_price("005930")
        >>> print(df['stck_prpr'])  # 현재가 출력
    """
```

### 주석 원칙
- **"왜"를 설명**: 코드는 "무엇"을 하는지 보여주고, 주석은 "왜" 그렇게 했는지 설명
- **자연어 문장**: LLM이 이해하기 쉽도록 완전한 문장 형태 사용
- **TODO/FIXME 태그**: 개선 필요한 부분 명시
- **코드 변경 시 주석도 함께 업데이트**

### 모듈화 원칙
- **단일 책임**: 함수/클래스는 하나의 명확한 기능만 가짐
- **직관적 코드**: 복잡한 디자인 패턴보다 명확한 구조 선호
- **장황해도 명확한 코드**: 한 줄 마법보다 여러 줄이라도 읽기 쉬운 코드

## 🏗️ 프로젝트 구조 규칙

### 핵심 원칙: KIS 코드 보호 + trading_bot 격리

**⚠️ 중요:**
- **KIS 제공 코드 수정 금지**: `examples_llm/`, `examples_user/`, `README.md`
- **모든 커스텀 코드는 `trading_bot/` 폴더 안에만 배치**
- **루트 README.md 수정 금지**: KIS가 업데이트할 수 있으므로 원본 유지

### KIS 샘플 코드 구조 이해

#### examples_llm/ (LLM용 기능 단위 샘플)
- **목적**: LLM이 단일 API 기능을 쉽게 탐색하고 학습
- **구조**: 각 API마다 독립된 폴더 + 2개 파일
  ```
  examples_llm/domestic_stock/inquire_price/
  ├── inquire_price.py         # 한 줄로 API 호출하는 함수
  └── chk_inquire_price.py     # 테스트 실행 파일
  ```
- **명명 규칙**: REST API URL 경로를 기반으로 함
  - URL: `/uapi/domestic-stock/v1/quotations/inquire-price`
  - 폴더명: `domestic_stock/inquire_price`

#### examples_user/ (사용자용 통합 샘플)
- **목적**: 실제 투자/자동매매 구현에 활용
- **구조**: 카테고리(상품)별로 모든 기능 통합
  ```
  examples_user/domestic_stock/
  ├── domestic_stock_functions.py      # 모든 REST API 함수 모음
  ├── domestic_stock_examples.py       # 사용 예제
  ├── domestic_stock_functions_ws.py   # WebSocket 함수 모음
  └── domestic_stock_examples_ws.py    # WebSocket 예제
  ```

#### trading_bot/broker/ (KIS API 래퍼)
- **목적**: `examples_user`의 함수들을 전략 모듈이 사용하기 쉽게 래핑
- **패턴**: `kis_broker.py`가 `domestic_stock_functions.py`를 import하여 재구성
- **예시**:
  ```python
  # trading_bot/broker/kis_broker.py
  from domestic_stock import domestic_stock_functions as dsf
  
  class KISBroker:
      def get_current_price(self, symbol):
          return dsf.inquire_price(symbol, ...)
  ```

### 디렉토리 구조
```
open-trading-api/           # 프로젝트 루트
├── README.md               # KIS 원본 (수정 금지 ❌)
├── TRADING_BOT.md          # 자동매매 봇 안내 (별도 파일)
├── pyproject.toml          # uv 설정 파일
├── examples_llm/           # KIS 제공 (수정 금지 ❌)
├── examples_user/          # KIS 제공 (수정 금지 ❌)
└── trading_bot/            # 자동매매 봇 (모든 커스텀 코드)
    ├── run_bot.py          # 봇 실행 스크립트
    ├── run_backtest.py     # 백테스트 실행 스크립트
    ├── create_external_db.py
    ├── backtest_results/   # 백테스트 결과 저장
    ├── main.py
    ├── config.py
    ├── broker/
    ├── strategies/
    ├── backtest/
    │   ├── QUICKSTART.md
    │   ├── DATA_SOURCES.md
    │   └── DB_GUIDE.md
    └── utils/
```

### 실행 위치 및 방법

**✅ 권장: trading_bot 폴더에서 실행**
```bash
cd trading_bot
uv run run_bot.py
uv run run_backtest.py --source fdr
uv run create_external_db.py
```

**대안: 프로젝트 루트에서 실행**
```bash
cd open-trading-api
uv run trading_bot/run_bot.py
uv run trading_bot/run_backtest.py --source fdr
```

## 🔍 디버깅 가이드

### ModuleNotFoundError 발생 시

**증상:**
```
ModuleNotFoundError: No module named 'pandas'
ModuleNotFoundError: No module named 'trading_bot'
```

**해결:**
1. `python` 대신 `uv run` 사용
2. 프로젝트 루트에서 실행하는지 확인
3. `pyproject.toml`에 의존성이 있는지 확인

### ImportError: attempted relative import 발생 시

**증상:**
```
ImportError: attempted relative import beyond top-level package
```

**해결:**
1. Relative import(`from .module`) → 절대 import(`from trading_bot.module`)로 변경
2. 프로젝트 루트에서 실행
3. `sys.path`에 프로젝트 루트 추가

## 📦 의존성 관리

### 새 패키지 추가 시

**trading_bot에 필요한 패키지는 pyproject.toml에 추가 가능:**

```bash
# 1. pyproject.toml의 [project.dependencies]에 추가
# 예: "matplotlib>=3.8.0", "finance-datareader>=0.9.50"

# 2. uv sync로 설치
cd /path/to/open-trading-api
uv sync
```

**일시적 테스트용으로만 설치:**
```bash
# pyproject.toml 수정 없이 임시 설치 (권장하지 않음)
uv pip install <package-name>
```

**참고**: KIS 샘플 코드는 최소 의존성만 사용하므로, trading_bot용 패키지 추가가 영향을 주지 않습니다.

### requirements.txt 업데이트

```bash
# pyproject.toml 기준으로 requirements.txt 생성
uv pip freeze > requirements.txt
```



## 📋 체크리스트: 새 기능 추가 시

- [ ] 코드는 `trading_bot/` 폴더 안에만 작성
- [ ] 절대 import 사용 (`from trading_bot.xxx`)
- [ ] 문서에 `uv run` 명령어로 작성
- [ ] trading_bot 폴더 기준 경로 사용
- [ ] 새 패키지 필요 시 `pyproject.toml`에 추가 후 `uv sync`
- [ ] 결과 파일은 `trading_bot/backtest_results/`에 저장
- [ ] KIS 샘플 코드(`examples_llm/`, `examples_user/`) 및 루트 `README.md` 수정하지 않음
- [ ] 문서 업데이트 시 `TRADING_BOT.md` 또는 `trading_bot/` 하위 문서만 수정

## 🚫 하지 말아야 할 것

1. **KIS 제공 파일 수정 금지**
   - `examples_llm/`, `examples_user/` - 절대 수정 금지
   - `README.md` (루트) - KIS가 업데이트할 수 있으므로 수정 금지
   - 커스텀 코드는 반드시 `trading_bot/` 안에 작성
   - **예외**: `pyproject.toml`은 trading_bot 의존성 추가 시 수정 가능

2. **문서에서 `python <script>` 단독으로 제시하지 않기**
   - 항상 `uv run`을 권장 방법으로 제시
   - pip 방식은 대안으로만 제시

3. **Relative import 사용하지 않기**
   - `from .module` ❌
   - `from trading_bot.module` ✅

4. **실행 스크립트를 trading_bot 밖에 배치하지 않기**
   - `run_*.py` 파일은 모두 `trading_bot/` 안에 위치
   - 결과 파일도 `trading_bot/backtest_results/`에 저장

5. **의존성을 pip로 직접 설치하지 않기 (uv 프로젝트에서)**
   - `pip install` ❌
   - `uv pip install` ✅

## 📂 파일 및 경로 관리

### 결과 파일 저장 위치

```python
# ✅ 올바른 경로 (trading_bot 기준 상대경로)
output_dir = Path(__file__).parent / "backtest_results"

# ❌ 잘못된 경로 (프로젝트 루트 기준)
output_dir = PROJECT_ROOT / "backtest_results"
```

### .gitignore 설정

```ignore
# 백테스트 결과 (차트, CSV 등)
trading_bot/backtest_results/

# 백테스트 DB (외부 생성)
trading_bot/backtest_data.db
```

### DB 파일 경로

```bash
# ✅ trading_bot 폴더에서 실행 시
uv run run_backtest.py --source db --db-path backtest_data.db

# ✅ 프로젝트 루트에서 실행 시
uv run trading_bot/run_backtest.py --source db --db-path trading_bot/backtest_data.db
```

## 🎯 요약

### 핵심 원칙
1. **KIS 파일 보호**: `examples_llm/`, `examples_user/`, 루트 `README.md` 수정 금지
2. **trading_bot 격리**: 모든 커스텀 코드는 `trading_bot/` 폴더에만
3. **실행은 항상 `uv run`**
4. **Import는 항상 절대 경로**
5. **문서는 uv 기준으로 작성**
6. **경로는 trading_bot 폴더 기준**

### 빠른 참조
```bash
# trading_bot 폴더로 이동
cd trading_bot

# 봇 실행
uv run run_bot.py

# 백테스트 실행
uv run run_backtest.py --source fdr

# 패키지 설치
uv pip install <package>

# 의존성 동기화
uv sync
```

### 프로젝트 구조 요약
```
open-trading-api/
├── README.md               # KIS 원본 (수정 금지 ❌)
├── TRADING_BOT.md          # 자동매매 봇 안내 문서
├── examples_llm/           # KIS 제공 (수정 금지 ❌)
├── examples_user/          # KIS 제공 (수정 금지 ❌)
└── trading_bot/            # 자동매매 봇 (모든 커스텀 코드 ✅)
    ├── run_bot.py          # 실행: cd trading_bot && uv run run_bot.py
    ├── run_backtest.py     # 실행: cd trading_bot && uv run run_backtest.py
    ├── backtest_results/   # 결과 저장
    ├── README.md           # 봇 상세 문서
    └── backtest/
        ├── QUICKSTART.md
        ├── DATA_SOURCES.md
        └── DB_GUIDE.md
```

---

**이 가이드라인을 따르면 사용자에게 정확하고 동작하는 명령어를 제공할 수 있습니다.**
