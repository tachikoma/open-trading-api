import pytest
from trading_bot.strategies.infinite_buy.factory import create_infinite_buy


def test_daily_once_per_T():
    cfg = {"version": "v2.2", "one_shot_amount": 100.0, "total_amount": 400.0, "market": "overseas", "order_type": "LOC"}
    strat = create_infinite_buy(cfg)

    quote = {"symbol": "AAPL", "price": 100.0}
    intents1 = strat.decide_buy("2026-01-29", quote)
    assert len(intents1) == 1
    intent = intents1[0]
    T = intent.get("T")
    exec_date = intent.get("exec_date")
    # 처음 실행 가능 여부
    assert strat._can_execute_T_today(T, exec_date) is True
    # 마킹 후에는 동일 날짜에서 재실행 불가
    strat._mark_executed_T(T, exec_date)
    assert strat._can_execute_T_today(T, exec_date) is False

    # 다음 날에는 실행 가능
    assert strat._can_execute_T_today(T, "2026-01-30") is True
