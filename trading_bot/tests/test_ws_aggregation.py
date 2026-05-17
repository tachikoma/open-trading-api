import pandas as pd
from types import SimpleNamespace

import pytest

import trading_bot.broker.kis_broker as kb_module
from trading_bot.broker.kis_broker import KISBroker


def test_ws_partial_fill_aggregates_and_notifies(monkeypatch):
    # Prepare minimal ka._cfg and TREnv for KISBroker init
    cfg = {
        "my_prod": "01",
        "paper_app": "paper_app_val",
        "paper_sec": "paper_sec_val",
        "my_paper_stock": "12345678",
    }
    monkeypatch.setattr(kb_module.ka, "_cfg", cfg, raising=False)
    monkeypatch.setattr(kb_module.ka, "getTREnv", lambda: SimpleNamespace(my_acct="12345678", my_prod="01", my_htsid="HTS1"))
    monkeypatch.setattr(kb_module.ka, "auth", lambda svr=None: None)

    # Instantiate broker
    broker = KISBroker(env_mode="demo")

    # Capture notify_order calls
    calls = []

    def fake_notify_order(action, symbol, qty, price, success, *args, **kwargs):
        calls.append({
            "action": action,
            "symbol": symbol,
            "qty": qty,
            "price": price,
            "success": success,
            "kwargs": kwargs,
        })

    monkeypatch.setattr(kb_module, "notify_order", fake_notify_order)

    # Simulate two partial fills for the same order (30 @ 10,000 and 70 @ 10,050)
    rows = [
        {
            "CNTG_YN": "2",
            "ODER_NO": "ORD1",
            "ODER_QTY": 100,
            "CNTG_QTY": 30,
            "CNTG_UNPR": 10000,
            "SELN_BYOV_CLS": "1",
            "STCK_SHRN_ISCD": "005930",
        },
        {
            "CNTG_YN": "2",
            "ODER_NO": "ORD1",
            "ODER_QTY": 100,
            "CNTG_QTY": 70,
            "CNTG_UNPR": 10050,
            "SELN_BYOV_CLS": "1",
            "STCK_SHRN_ISCD": "005930",
        },
    ]

    df = pd.DataFrame(rows)

    # Call the handler
    broker._on_ws_result(None, "TR", df, {})

    # Expect single final notification (only when cumulative == order_qty)
    assert len(calls) == 1, f"expected 1 notify call, got {len(calls)}"
    c = calls[0]
    assert c["action"] == "BUY"
    assert c["symbol"] == "005930"
    assert c["qty"] == 100
    # avg_exec_price = round((30*10000 + 70*10050) / 100) = 10035
    assert c["price"] == 10035
    assert c["success"] is True
