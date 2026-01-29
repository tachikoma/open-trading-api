import pytest
from unittest.mock import MagicMock
from trading_bot.strategies.infinite_buy.factory import create_infinite_buy
from trading_bot.broker.kis_broker import KISBroker


def test_buy_intent_routes_to_overseas(monkeypatch):
    # 설정: v2.2 전략이 해외 마켓으로 intent 생성
    # total_amount을 충분히 크게 잡아 분할당 금액이 주문수량 1개 이상이 되도록 설정
    cfg = {"version": "v2.2", "one_shot_amount": 100.0, "total_amount": 6000.0, "market": "overseas", "order_type": "LOC", "ovrs_excg_cd": "NASD"}
    strat = create_infinite_buy(cfg)

    quote = {"symbol": "AAPL", "price": 150.0}
    intent_list = strat.decide_buy("2026-01-29", quote)
    assert len(intent_list) >= 1
    intent = intent_list[0]
    assert intent.get("market") == "overseas"
    assert intent.get("order_type") == "LOC"

    # 브로커의 buy_overseas가 호출되는지 확인
    from trading_bot.config import Config

    broker = KISBroker(env_mode="demo")
    # 테스트 동안 강제로 거래 활성화
    monkeypatch.setattr(Config, 'TRADING_ENABLED', True)
    called = {}

    def fake_buy_overseas(symbol, qty, price, order_type="LIMIT", ovrs_excg_cd=None):
        called['symbol'] = symbol
        called['qty'] = qty
        called['price'] = price
        called['order_type'] = order_type
        called['ovrs_excg_cd'] = ovrs_excg_cd
        return {"success": True, "data": {"mock": True}}

    monkeypatch.setattr(broker, 'buy_overseas', fake_buy_overseas)

    # 실행할 때는 모든 의도 리스트를 전달하여 성공한 주문이 있는지 확인
    results = broker.execute_intents(intent_list, strategy=strat, simulate_only=False)
    # results 배열 중 성공이 하나 이상 있는지 확인
    assert any(r.get("result", {}).get("success") for r in results)
    assert called.get('symbol') == "AAPL"
    assert called.get('order_type') == "LOC"


def test_order_type_mapping():
    # 매핑 헬퍼 동작 검증
    broker = KISBroker(env_mode="demo")
    # 다양한 주문타입 매핑 테스트
    tests = [
        ("LIMIT", "00"),
        ("LOC", "34"),
        ("LOO", "32"),
        ("MOO", "31"),
        ("MOC", "33"),
        ("unknown", "00"),
    ]
    for ot, expected in tests:
        ord_svr, ord_dvsn = broker._map_overseas_ord_dvsn(ot, side="buy")
        assert ord_dvsn == expected
