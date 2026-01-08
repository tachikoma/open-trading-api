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
    from trading_bot.config import Config
except Exception as e:
    print("IMPORT_ERROR", e)
    traceback.print_exc()
    raise

print("Config.TRADING_ENABLED:", Config.TRADING_ENABLED)

try:
    broker = KISBroker(env_mode="demo")
    print("Broker initialized")

    print('\n== get_balance ==')
    bal = broker.get_balance()
    print('get_balance =>', type(bal), bal if isinstance(bal, tuple) else bal)

    print('\n== get_buyable_cash ==')
    buy_cash = broker.get_buyable_cash()
    print('get_buyable_cash =>', buy_cash)

    print('\n== get_current_price(005930) ==')
    price_df = broker.get_current_price("005930")
    print('get_current_price => type:', type(price_df))
    try:
        print(price_df.head())
    except Exception:
        print(price_df)

    print('\n== buy (dry-run) ==')
    buy_res = broker.buy("005930", qty=1, price=0, order_type="01")
    print('buy =>', buy_res)

    print('\n== sell (dry-run) ==')
    sell_res = broker.sell("005930", qty=1, price=0, order_type="01")
    print('sell =>', sell_res)

    print('\n== cancel_order (dry-run) ==')
    cancel_res = broker.cancel_order(order_no="TEST123", qty=0, symbol="005930", order_type="01")
    print('cancel_order =>', cancel_res)

except Exception as e:
    print("RUNTIME_ERROR", e)
    traceback.print_exc()
