#!/usr/bin/env python3
"""
KIS 자동매매 봇 실행 스크립트

이 프로젝트는 uv 기반이므로 반드시 다음과 같이 실행하세요:

trading_bot 폴더에서:
    cd trading_bot
    uv run run_bot.py

또는 프로젝트 루트에서 (경로 포함):
    uv run trading_bot/run_bot.py

주의: 다음 명령어는 의존성 오류가 발생할 수 있습니다:
    python run_bot.py   # ❌ ModuleNotFoundError
    python3 run_bot.py  # ❌ ModuleNotFoundError

pip로 의존성을 수동 설치한 경우에만 python 직접 실행 가능:
    cd trading_bot
    pip install -r requirements.txt
    python run_bot.py

예시: `STRATEGIES_CONFIG_TEMPLATE` 사용

`trading_bot/config.py`에 `STRATEGIES_CONFIG_TEMPLATE`을 선언해 두면
이 스크립트는 실행 시 자동으로 `Config.STRATEGIES_ENABLED`에
`STRATEGIES_CONFIG_TEMPLATE`을 대입하여 메인에서 해당 템플릿으로 전략을 로드합니다.

즉, 프로젝트 설정에 아래와 같은 템플릿이 있으면:

    STRATEGIES_CONFIG_TEMPLATE = [
        {"name": "ma_crossover", "config": {"symbols": ["005930"], "short_period": 5}},
        {"name": "infinite_buy", "config": {"version": "v2.2", "total_amount": 1000000}},
    ]

이 스크립트를 `uv run run_bot.py`로 실행하면 템플릿이 자동으로 적용되어
`ma_crossover` 및 `infinite_buy`가 해당 `config`로 초기화됩니다.

원하지 않을 경우 `STRATEGIES_CONFIG_TEMPLATE`을 비우거나 제거하면
기존의 `STRATEGIES_ENABLED` 리스트가 사용됩니다.
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Config 템플릿이 있으면 이를 STRATEGIES_ENABLED에 적용합니다.
try:
    from trading_bot.config import Config
    if hasattr(Config, "STRATEGIES_CONFIG_TEMPLATE") and isinstance(Config.STRATEGIES_CONFIG_TEMPLATE, list) and len(Config.STRATEGIES_CONFIG_TEMPLATE) > 0:
        # STRATEGIES_CONFIG_TEMPLATE을 STRATEGIES_ENABLED로 대체하여 main이 템플릿을 사용하도록 함
        Config.STRATEGIES_ENABLED = Config.STRATEGIES_CONFIG_TEMPLATE
        print("Info: Using Config.STRATEGIES_CONFIG_TEMPLATE as STRATEGIES_ENABLED")
except Exception:
    # 예외 시 무시 (의존성 문제로 임포트 실패 가능)
    pass

# trading_bot.main 실행
from trading_bot.main import main

if __name__ == "__main__":
    main()
