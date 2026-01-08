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

    buy_cash = broker.get_buyable_cash()
    print("get_buyable_cash =>", buy_cash)

    price_df = broker.get_current_price("005930")
    print("get_current_price => type:", type(price_df))
    try:
        print(price_df.head())
    except Exception:
        print(price_df)
except Exception as e:
    print("RUNTIME_ERROR", e)
    traceback.print_exc()
