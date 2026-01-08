#!/usr/bin/env python3
import sys
from pathlib import Path
import traceback

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "examples_user"))
sys.path.insert(0, str(PROJECT_ROOT / "examples_llm"))

try:
    from trading_bot.broker.kis_broker import KISBroker
except Exception as e:
    print("IMPORT_ERROR", e)
    traceback.print_exc()
    raise

try:
    broker = KISBroker(env_mode="demo")
    print("Broker initialized")

    # 현재가 조회
    price_df = broker.get_current_price("005930")
    print("get_current_price => type:", type(price_df))
    try:
        print(price_df.head())
    except Exception:
        print(price_df)

    # 현재가 기준으로 매수 가능 현금 조회 (종목 코드와 가격 전달)
    current_price = 0
    if price_df is not None and not getattr(price_df, 'empty', False):
        try:
            current_price = int(price_df.iloc[0]['stck_prpr'])
        except Exception:
            for col in ['close', 'stck_clpr', 'clpr', 'prpr', 'last']:
                if col in price_df.columns:
                    try:
                        current_price = int(price_df.iloc[0][col])
                        break
                    except Exception:
                        continue

    buy_cash = broker.get_buyable_cash("005930", current_price)
    print("get_buyable_cash =>", buy_cash)
except Exception as e:
    print("RUNTIME_ERROR", e)
    traceback.print_exc()
