import sys

if __name__ == "__main__":
    # 프로젝트 루트를 sys.path에 추가하여 `trading_bot` 패키지 임포트가 가능하게 함
    from pathlib import Path
    PROJECT_ROOT = Path(__file__).parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    # pytest를 trading_bot 폴더 기준으로 실행
    import pytest
    sys.exit(pytest.main(["-q", "trading_bot/tests/test_token_refresh.py"]))
