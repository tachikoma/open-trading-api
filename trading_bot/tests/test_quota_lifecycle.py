import types
import logging

import pandas as pd

from trading_bot.broker.kis_broker import KISBroker
from trading_bot.strategies.infinite_buy.v2_2 import InfiniteBuyV2_2
from trading_bot.config import Config


def _make_broker_without_auth():
    # KISBroker.__init__ calls _init_auth which tries to access local tokens.
    # For unit tests we bypass network/auth by stubbing _init_auth.
    orig = KISBroker._init_auth
    KISBroker._init_auth = lambda self: None
    try:
        b = KISBroker(env_mode="demo")
    finally:
        KISBroker._init_auth = orig
    # minimal attributes
    b.logger = logging.getLogger("test_kis_broker")
    b.account = "TEST"
    b.product_code = "01"
    return b


def test_extract_exec_price_and_qty_various_formats():
    broker = _make_broker_without_auth()

    # dict with data
    res1 = {"data": {"exec_price": "123.45", "exec_qty": "10"}}
    p, q = broker._extract_exec_price_and_qty(res1)
    assert p == 123.45
    assert q == 10

    # pandas DataFrame
    df = pd.DataFrame([{"trd_prc": "200.5", "trd_qty": "3"}])
    res2 = {"data": df}
    p2, q2 = broker._extract_exec_price_and_qty(res2)
    assert p2 == 200.5
    assert q2 == 3

    # list of dicts
    res3 = {"data": [{"price": 150.0, "qty": 2}]}
    p3, q3 = broker._extract_exec_price_and_qty(res3)
    assert p3 == 150.0
    assert q3 == 2


def test_quota_buy_increments_cycle_and_deducts_reentry_amount():
    broker = _make_broker_without_auth()
    config = {"total_amount": 1000, "one_shot_amount": 100, "market": "overseas"}
    strategy = InfiniteBuyV2_2(config=config, broker=broker)

    # prepare state
    strategy.state["quota_reentry_amount"] = 1000.0
    strategy.state["quota_cycle_count"] = 0

    # monkeypatch broker.buy to avoid real API call
    def fake_buy(self, symbol, qty, price, order_type="00"):
        return {"success": True, "data": {"exec_price": price, "exec_qty": qty}, "order_id": "id"}

    broker.buy = types.MethodType(fake_buy, broker)

    # ensure live path
    prev = Config.TRADING_ENABLED
    Config.TRADING_ENABLED = True

    try:
        intent = {"type": "buy", "symbol": "TST", "price": 10, "quantity": 5, "order_type": "LOC", "quota_mode": True}
        results = broker.execute_intents([intent], strategy=strategy, simulate_only=False)

        # cycle incremented and quota_reentry_amount reduced by amt (10*5=50)
        assert strategy.state.get("quota_cycle_count", 0) == 1
        assert abs(strategy.state.get("quota_reentry_amount", 0.0) - (1000.0 - 50.0)) < 1e-6
    finally:
        Config.TRADING_ENABLED = prev


def test_quota_final_moc_exit_on_negative_fill():
    broker = _make_broker_without_auth()
    config = {"total_amount": 1000, "one_shot_amount": 100, "market": "overseas"}
    strategy = InfiniteBuyV2_2(config=config, broker=broker)

    # prepare state for final MOC
    strategy.state["quota_stop_loss_mode"] = True
    strategy.state["quota_cycle_count"] = 10
    strategy.state["quota_final_moc_done"] = False
    strategy.state["quota_reentry_amount"] = 0.0

    # monkeypatch broker.sell to return MOC fill at 89 (ref_avg 100 -> -11%)
    def fake_sell(self, symbol, qty, price, order_type="00"):
        return {"success": True, "data": {"exec_price": 89.0, "exec_qty": qty}, "order_id": "sellid"}

    broker.sell = types.MethodType(fake_sell, broker)

    prev = Config.TRADING_ENABLED
    Config.TRADING_ENABLED = True
    try:
        intent = {"type": "sell", "symbol": "TST", "quantity": 1, "order_type": "MOC", "quota_mode": True, "ref_avg_price": 100.0, "price": None}
        res = broker.execute_intents([intent], strategy=strategy, simulate_only=False)

        # quota mode should be cleared and counters reset
        assert strategy.state.get("quota_stop_loss_mode") is False
        assert strategy.state.get("quota_cycle_count") == 0
        # quota_reentry_amount should have been increased by proceeds (89.0)
        assert abs(strategy.state.get("quota_reentry_amount", 0.0) - 89.0) < 1e-6
    finally:
        Config.TRADING_ENABLED = prev


def test_initial_moc_flow_and_state_update():
    broker = _make_broker_without_auth()
    config = {"total_amount": 1000, "one_shot_amount": 100, "market": "overseas"}
    strategy = InfiniteBuyV2_2(config=config, broker=broker)

    # prepare state: quota mode entered but initial MOC not done
    strategy.state["quota_stop_loss_mode"] = True
    strategy.state["quota_initial_moc_done"] = False
    strategy.state["quota_reentry_amount"] = 0.0

    # position with quantity so that 1/4 exists
    position = {"symbol": "TST", "quantity": 4, "avg_price": 100.0, "cum_buy_amt": strategy.state.get("cum_buy_amt", 0.0)}

    intents = strategy.decide_sell(position, market_price=None)
    # 최초 진입시에는 MOC 의도가 생성되어야 함
    assert any((it.get("order_type") == "MOC" and "initial" in (it.get("reason") or "")) for it in intents)

    # monkeypatch broker.sell to return MOC fill at 95.0
    def fake_sell(self, symbol, qty, price, order_type="00"):
        return {"success": True, "data": {"exec_price": 95.0, "exec_qty": qty}, "order_id": "sell_init"}

    broker.sell = types.MethodType(fake_sell, broker)

    prev = Config.TRADING_ENABLED
    Config.TRADING_ENABLED = True
    try:
        results = broker.execute_intents(intents, strategy=strategy, simulate_only=False)

        # quota_initial_moc_done가 True로 설정되고, 체결금액이 quota_reentry_amount에 반영되어야 함
        assert strategy.state.get("quota_initial_moc_done") is True
        # proceeds = 95.0 * sold_qty (sold_qty should be 1/4 of 4 = 1.0)
        assert abs(strategy.state.get("quota_reentry_amount", 0.0) - 95.0) < 1e-6
        # exec_price 95 > ref_avg*0.9(=90) 이므로 quota_stop_loss_mode는 여전히 True여야 함
        assert strategy.state.get("quota_stop_loss_mode") is True
    finally:
        Config.TRADING_ENABLED = prev


def test_decide_buy_sets_quota_on_last_split():
    broker = _make_broker_without_auth()
    # Use splits=1 to make per-split amount equal total_amount so qty_int is significant
    config = {"total_amount": 100, "one_shot_amount": 100, "splits": 1, "market": "overseas"}
    strategy = InfiniteBuyV2_2(config=config, broker=broker)

    # make cum_buy_amt such that next buy will exhaust the total_amount
    strategy.state["cum_buy_amt"] = 0.0

    # quote price 10, per_split = 100, qty_int will be 10 -> price*qty_int = 100 meets total_amount
    quote = {"symbol": "TST", "price": 10}
    intents = strategy.decide_buy("2026-01-29", quote)

    # after decide_buy the strategy should have a pending quota entry (to be applied on next sell turn)
    assert strategy.state.get("quota_enter_pending") is True
    assert strategy.state.get("quota_cycle_count") == 0
    # quota_reentry_amount should be set to remaining (total_amount - cum_buy_amt)
    assert abs(strategy.state.get("quota_reentry_amount", 0.0) - 100.0) < 1e-6
    # intents should be marked as quota_pending (not immediate quota_mode)
    assert all(it.get("quota_pending") is True for it in intents)
