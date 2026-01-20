import os
import pytest

from trading_bot.broker import kis_broker


def test_token_refresh_on_result(tmp_path, monkeypatch):
    # 준비: 임시 토큰 파일 생성
    token_file = tmp_path / "KIS20260116"
    token_file.write_text("dummy-token")

    class FakeKA:
        def __init__(self, token_path):
            self.token_tmp = str(token_path)
            self.auth_called = False

        def auth(self, svr):
            self.auth_called = True

    fake_ka = FakeKA(token_file)

    # kis_broker 모듈의 ka를 페이크로 교체
    monkeypatch.setattr(kis_broker, "ka", fake_ka)

    # dsf.inquire_price가 만료 메시지를 포함한 결과를 반환하도록 모킹
    def fake_inquire_price(*args, **kwargs):
        return {"msg1": "EGW00123"}

    monkeypatch.setattr(kis_broker.dsf, "inquire_price", fake_inquire_price)

    # _init_auth의 부작용 방지
    monkeypatch.setattr(kis_broker.KISBroker, "_init_auth", lambda self: None)

    broker = kis_broker.KISBroker(env_mode="demo")
    broker._svr = "vps"

    # 호출: 결과 기반으로 토큰 만료 감지 후 재발급 시도해야 함
    res = broker.get_current_price("005930")

    assert fake_ka.auth_called is True
    assert not token_file.exists()


def test_token_refresh_on_exception(tmp_path, monkeypatch):
    # 준비: 임시 토큰 파일 생성
    token_file = tmp_path / "KIS20260116"
    token_file.write_text("dummy-token")

    class FakeKA:
        def __init__(self, token_path):
            self.token_tmp = str(token_path)
            self.auth_called = False

        def auth(self, svr):
            self.auth_called = True

    fake_ka = FakeKA(token_file)

    monkeypatch.setattr(kis_broker, "ka", fake_ka)

    # dsf.inquire_price가 예외를 발생시키는 경우
    def fake_inquire_price_raise(*args, **kwargs):
        raise Exception("EGW00123")

    monkeypatch.setattr(kis_broker.dsf, "inquire_price", fake_inquire_price_raise)

    monkeypatch.setattr(kis_broker.KISBroker, "_init_auth", lambda self: None)

    broker = kis_broker.KISBroker(env_mode="demo")
    broker._svr = "vps"

    res = broker.get_current_price("005930")

    # 예외 경로에서도 토큰 재발급 시도되어야 함
    assert fake_ka.auth_called is True
    assert not token_file.exists()
