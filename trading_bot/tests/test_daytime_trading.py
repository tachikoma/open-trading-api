import datetime
import pytz

from trading_bot.config import Config
from trading_bot.broker import kis_broker as kis_broker_module
from trading_bot.broker.kis_broker import KISBroker
from trading_bot.utils.market_time import is_daytime_trading_hours


def _make_broker(monkeypatch):
    monkeypatch.setattr(KISBroker, "_init_auth", lambda self: None)
    return KISBroker(env_mode="demo")


def test_is_daytime_trading_hours_kst_window():
    tz = pytz.timezone("Asia/Seoul")

    assert not is_daytime_trading_hours(tz.localize(datetime.datetime(2026, 2, 6, 9, 59)))
    assert is_daytime_trading_hours(tz.localize(datetime.datetime(2026, 2, 6, 10, 0)))
    assert is_daytime_trading_hours(tz.localize(datetime.datetime(2026, 2, 6, 17, 59)))
    assert not is_daytime_trading_hours(tz.localize(datetime.datetime(2026, 2, 6, 18, 0)))
    assert not is_daytime_trading_hours(tz.localize(datetime.datetime(2026, 2, 7, 10, 0)))


def test_buy_overseas_routes_to_daytime_limit(monkeypatch):
    broker = _make_broker(monkeypatch)
    monkeypatch.setattr(Config, "TRADING_ENABLED", True)
    monkeypatch.setattr(kis_broker_module, "is_daytime_trading_hours", lambda: True)

    called = {}

    def fake_buy_daytime(symbol, qty, price, ovrs_excg_cd=None):
        called["symbol"] = symbol
        called["qty"] = qty
        called["price"] = price
        called["ovrs_excg_cd"] = ovrs_excg_cd
        return {"success": True, "data": {"mock": True}}

    monkeypatch.setattr(broker, "buy_overseas_daytime", fake_buy_daytime)

    res = broker.buy_overseas("AAPL", 1, 150.0, order_type="LIMIT", ovrs_excg_cd="NASD")
    assert res.get("success") is True
    assert called.get("symbol") == "AAPL"
    assert called.get("ovrs_excg_cd") == "NASD"


def test_buy_overseas_rejects_non_limit_during_daytime(monkeypatch):
    broker = _make_broker(monkeypatch)
    monkeypatch.setattr(Config, "TRADING_ENABLED", True)
    monkeypatch.setattr(kis_broker_module, "is_daytime_trading_hours", lambda: True)

    res = broker.buy_overseas("AAPL", 1, 150.0, order_type="LOC", ovrs_excg_cd="NASD")
    assert res.get("success") is False
    assert "LIMIT" in (res.get("message") or "")


def test_sell_overseas_rejects_non_limit_during_daytime(monkeypatch):
    broker = _make_broker(monkeypatch)
    monkeypatch.setattr(Config, "TRADING_ENABLED", True)
    monkeypatch.setattr(kis_broker_module, "is_daytime_trading_hours", lambda: True)

    res = broker.sell_overseas("AAPL", 1, 150.0, order_type="MOC", ovrs_excg_cd="NASD")
    assert res.get("success") is False
    assert "LIMIT" in (res.get("message") or "")
