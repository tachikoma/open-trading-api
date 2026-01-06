#!/usr/bin/env python3
"""
KIS 자동매매 봇 실행 스크립트

이 프로젝트는 uv 기반이므로 반드시 다음과 같이 실행하세요:

프로젝트 루트에서:
    uv run run_bot.py

주의: 다음 명령어는 의존성 오류가 발생할 수 있습니다:
    python run_bot.py   # ❌ ModuleNotFoundError
    python3 run_bot.py  # ❌ ModuleNotFoundError

pip로 의존성을 수동 설치한 경우에만 python 직접 실행 가능:
    pip install -r requirements.txt
    python run_bot.py
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# trading_bot.main 실행
from trading_bot.main import main

if __name__ == "__main__":
    main()
