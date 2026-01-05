# Copilot Instructions for KIS Trading Bot Project

## 프로젝트 환경

### 🔧 빌드 시스템: UV 기반
이 프로젝트는 **`uv` 패키지 매니저**를 사용합니다.

- **의존성 관리**: `pyproject.toml`
- **실행 방법**: `uv run <script>`
- **Python 직접 실행 불가**: `python run_bot.py` ❌

### ⚠️ 중요: 실행 명령어

#### ✅ 올바른 실행 방법
```bash
# 메인 봇 실행
uv run run_bot.py

# 테스트 실행
uv run pytest

# 스크립트 실행
uv run python -m trading_bot.main
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

### 실행 명령어 작성 시

#### README, QUICKSTART, 주석 등 모든 문서에서:

**항상 `uv run`을 먼저 제시:**
```markdown
### 실행 방법

\`\`\`bash
# 권장 (uv 사용)
uv run run_bot.py

# 대안 (pip로 의존성을 직접 설치한 경우에만)
pip install -r requirements.txt
python run_bot.py
\`\`\`
```

**나쁜 예:**
```markdown
# 실행
python run_bot.py  # ❌ uv 없이는 작동 안 함!
```

**좋은 예:**
```markdown
# 실행
uv run run_bot.py  # ✅ 의존성 자동 관리
```

### 설치 가이드 작성 시

```markdown
## 설치

### 방법 1: uv 사용 (권장)
\`\`\`bash
# uv가 없으면 먼저 설치
curl -LsSf https://astral.sh/uv/install.sh | sh

# 프로젝트 실행 (의존성 자동 설치)
uv run run_bot.py
\`\`\`

### 방법 2: pip 사용
\`\`\`bash
# 의존성 수동 설치
pip install -r requirements.txt

# 실행
python run_bot.py
\`\`\`
```

## 💻 코드 작성 가이드라인

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

새로운 모듈을 만들 때 프로젝트 루트를 참조해야 하는 경우:

```python
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 이제 절대 import 가능
from trading_bot.config import Config
```

### 실행 스크립트 패턴

프로젝트 루트에 실행 스크립트를 만들 때:

```python
#!/usr/bin/env python3
"""
실행 스크립트 예시
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# trading_bot 패키지 import
from trading_bot.main import main

if __name__ == "__main__":
    main()
```

## 🏗️ 프로젝트 구조 규칙

### 디렉토리 구조
```
open-trading-api/           # 프로젝트 루트
├── pyproject.toml          # uv 설정 파일
├── run_bot.py              # 실행 진입점 (루트에 위치)
├── examples_user/          # KIS 원본 코드 (수정 금지)
└── trading_bot/            # 자동매매 봇 패키지
    ├── __init__.py         # 패키지 표시
    ├── main.py
    ├── config.py
    └── ...
```

### 실행 진입점 위치
- **프로젝트 루트에 위치**: `run_bot.py`, `run_test.py` 등
- **이유**: `uv run`이 프로젝트 루트에서 실행되므로
- **패키지 내부 실행 금지**: `trading_bot/` 안에서 `python main.py` 실행 안 됨

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

```bash
# pyproject.toml에 추가하지 말고, uv로 설치
uv pip install <package-name>

# 또는 pyproject.toml [project.dependencies]에 직접 추가 후
uv sync
```

### requirements.txt 업데이트

```bash
# pyproject.toml 기준으로 requirements.txt 생성
uv pip freeze > requirements.txt
```

## 🧪 테스트 실행

```bash
# ✅ 올바른 방식
uv run pytest
uv run pytest tests/test_broker.py
uv run python -m pytest

# ❌ 잘못된 방식
python -m pytest  # 의존성 없을 수 있음
```

## 📋 체크리스트: 새 기능 추가 시

- [ ] 절대 import 사용 (`from trading_bot.xxx`)
- [ ] 문서에 `uv run` 명령어로 작성
- [ ] 프로젝트 루트에서 실행 테스트
- [ ] 필요한 의존성이 `pyproject.toml`에 있는지 확인
- [ ] 주석에 실행 방법 명시 시 `uv run` 사용

## 🚫 하지 말아야 할 것

1. **문서에서 `python <script>` 단독으로 제시하지 않기**
   - 항상 `uv run`을 권장 방법으로 제시
   - pip 방식은 대안으로만 제시

2. **Relative import 사용하지 않기**
   - `from .module` ❌
   - `from trading_bot.module` ✅

3. **trading_bot/ 디렉토리 안에서 직접 실행하지 않기**
   - 항상 프로젝트 루트로 이동 후 실행

4. **의존성을 pip로 직접 설치하지 않기 (uv 프로젝트에서)**
   - `pip install` ❌
   - `uv pip install` ✅

## 🎯 요약

### 핵심 원칙
1. **실행은 항상 `uv run`**
2. **Import는 항상 절대 경로**
3. **문서는 uv 기준으로 작성**
4. **프로젝트 루트에서 실행**

### 빠른 참조
```bash
# 봇 실행
uv run run_bot.py

# 패키지 설치
uv pip install <package>

# 의존성 동기화
uv sync

# Python 스크립트 실행
uv run python <script.py>
```

---

**이 가이드라인을 따르면 사용자에게 정확하고 동작하는 명령어를 제공할 수 있습니다.**
