import sys
from pathlib import Path

# 테스트 실행 시 `trading_bot` 패키지를 찾을 수 있도록 프로젝트 루트를 sys.path에 추가합니다.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
