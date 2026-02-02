import pytest
from trading_bot.utils.fees import calculate_fees_and_taxes


def test_buy_fees_basic():
    # 가격 10,000원, 수량 10 -> gross=100000
    res = calculate_fees_and_taxes(10000, 10, side="buy")
    assert res['gross_amount'] == 100000
    # commission 0.015% -> 15 (rounded)
    assert res['commission'] == 15
    # tax on buy should be 0
    assert res['tax'] == 0
    assert res['total_fees'] == 15
    # net_amount for buy is negative (cash outflow)
    assert res['net_amount'] == -(100000 + 15)


def test_sell_fees_basic():
    # 가격 20000원, 수량 5 -> gross=100000
    res = calculate_fees_and_taxes(20000, 5, side="sell")
    assert res['gross_amount'] == 100000
    # commission 0.015% -> 15
    assert res['commission'] == 15
    # trade tax 0.2% -> 200
    assert res['tax'] == 200
    assert res['total_fees'] == 215
    # net_amount for sell is gross - fees
    assert res['net_amount'] == 100000 - 215
