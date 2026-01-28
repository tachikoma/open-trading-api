import pytest
from trading_bot.strategies.infinite_buy.factory import create_infinite_buy


def test_default_instance():
    cfg = {"version": "v2.2", "one_shot_amount": 1000.0, "base_currency": "USD", "splits": 40}
    inst = create_infinite_buy(cfg)
    assert inst.version == "v2.2"
    assert inst.base_currency == "USD"
    assert inst.splits == 40


def test_compute_T_ceil2():
    cfg = {"version": "v2.2", "one_shot_amount": 1000.0}
    inst = create_infinite_buy(cfg)
    T = inst.compute_T(1935.0)  # 1935 / 1000 = 1.935 -> ceil2 -> 1.94
    assert T == pytest.approx(1.94)
