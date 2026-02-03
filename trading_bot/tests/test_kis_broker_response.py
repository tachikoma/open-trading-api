import pytest
from trading_bot.broker.kis_broker import KISBroker


def test_format_order_response_schema():
    kb = KISBroker(env_mode="demo")

    # 성공 케이스
    res = kb._format_order_response(True, {"ok": 1}, qty=10, price=100, order_id="OID123", side="buy", fees={"commission": 1}, message=None)
    assert isinstance(res, dict)
    assert res.get("success") is True
    assert res.get("side") == "buy"
    assert res.get("data") == {"ok": 1}
    assert res.get("order_id") == "OID123"
    assert isinstance(res.get("fees"), dict)

    # 실패 케이스
    res2 = kb._format_order_response(False, None, side="sell", message="ERR")
    assert isinstance(res2, dict)
    assert res2.get("success") is False
    assert res2.get("side") == "sell"
    assert res2.get("data") is None
    assert res2.get("message") == "ERR"
