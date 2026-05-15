from unittest.mock import patch

from trading_bot.utils.telegram import notify_order


def test_notify_receipt_includes_estimated_fees():
    fees = {
        "commission": 1000,
        "tax": 0,
        "total_fees": 19053,
        "gross_amount": 1000000,
        "net_amount": -1019053,
    }

    with patch("trading_bot.utils.telegram.send_telegram_message") as mock_send:
        notify_order("BUY", "005930", 100, 10000, True, order_id="OID123", currency="KRW", fees=fees, estimated=True, stage="receipt")
        assert mock_send.called
        sent_text = mock_send.call_args[0][0]
        assert "<b>주문 접수</b>" in sent_text
        assert "예상비용(수수료+세금): 19,053원" in sent_text


def test_notify_execution_includes_net_and_pnl():
    # Construct values to match expected strings in the specification example
    fees = {
        "commission": 1000,
        "tax": 2645,
        "total_fees": 3645,
        "gross_amount": 1044800,
        "net_amount": 1041155,
    }

    # Choose avg_buy_price and qty that produce pnl 7.05% when formatted
    qty = 1
    avg_buy_price = 971117  # chosen so buy_cost_total = 972574
    exec_price = 1044800

    with patch("trading_bot.utils.telegram.send_telegram_message") as mock_send:
        notify_order("SELL", "005930", qty, 0, True, order_id="OID999", currency="KRW",
                     fees=fees, exec_price=exec_price, avg_buy_price=avg_buy_price, stage="execution", is_final=True)
        assert mock_send.called
        sent_text = mock_send.call_args[0][0]
        assert "예상수령: 1,041,155원 (수수료+세금: 3,645원)" in sent_text
        assert "예상수익률: 7.05%" in sent_text
