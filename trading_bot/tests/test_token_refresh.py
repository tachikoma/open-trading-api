import os
import pytest
import pandas as pd

from trading_bot.broker import kis_broker
from trading_bot.broker.auth_utils import refresh_token, TokenRefreshError, is_token_expired_response


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
    monkeypatch.setattr(kis_broker.KISBroker, "_validate_startup_config", lambda self: None)

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
    monkeypatch.setattr(kis_broker.KISBroker, "_validate_startup_config", lambda self: None)

    broker = kis_broker.KISBroker(env_mode="demo")
    broker._svr = "vps"

    res = broker.get_current_price("005930")

    # 예외 경로에서도 토큰 재발급 시도되어야 함
    assert fake_ka.auth_called is True
    assert not token_file.exists()


class _DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


def test_refresh_token_raises_when_auth_returns_without_token(tmp_path, monkeypatch):
    token_file = tmp_path / "KIS20260116"
    token_file.write_text("dummy-token")

    class FakeKA:
        def __init__(self, token_path):
            self.token_tmp = str(token_path)
            self.auth_calls = 0

        def auth(self, svr):
            self.auth_calls += 1

        def read_token(self):
            return None

    fake_ka = FakeKA(token_file)
    logger = _DummyLogger()

    sleep_calls = []
    monkeypatch.setattr("trading_bot.broker.auth_utils.time.sleep", lambda sec: sleep_calls.append(sec))

    with pytest.raises(TokenRefreshError):
        refresh_token(
            fake_ka,
            "vps",
            logger,
            max_attempts=3,
            backoff_base_sec=0.2,
            backoff_multiplier=2.0,
            backoff_max_sec=1.0,
        )

    assert fake_ka.auth_calls == 3
    assert sleep_calls == [0.2, 0.4]


def test_refresh_token_succeeds_after_retry(tmp_path, monkeypatch):
    token_file = tmp_path / "KIS20260116"
    token_file.write_text("dummy-token")

    class FakeKA:
        def __init__(self, token_path):
            self.token_tmp = str(token_path)
            self.auth_calls = 0
            self._has_token = False

        def auth(self, svr):
            self.auth_calls += 1
            if self.auth_calls >= 2:
                self._has_token = True

        def read_token(self):
            return "new-token" if self._has_token else None

    fake_ka = FakeKA(token_file)
    logger = _DummyLogger()

    sleep_calls = []
    monkeypatch.setattr("trading_bot.broker.auth_utils.time.sleep", lambda sec: sleep_calls.append(sec))

    refresh_token(
        fake_ka,
        "vps",
        logger,
        delay_sec=0.1,
        max_attempts=3,
        backoff_base_sec=0.2,
        backoff_multiplier=2.0,
        backoff_max_sec=1.0,
    )

    assert fake_ka.auth_calls == 2
    assert sleep_calls == [0.2, 0.1]


def test_is_token_expired_response_from_dataframe_attrs_payload():
    df = pd.DataFrame()
    df.attrs["error_payload"] = {
        "http_status": 500,
        "http_body_truncated": '{"rt_cd":"1","msg1":"기간이 만료된 token 입니다.","msg_cd":"EGW00123"}',
    }

    assert is_token_expired_response(df) is True


def test_is_token_expired_response_false_on_invalid_check_acno_payload():
    df = pd.DataFrame()
    df.attrs["error_payload"] = {
        "http_status": 200,
        "http_body_truncated": "ERROR : INPUT INVALID_CHECK_ACNO",
    }

    assert is_token_expired_response(df) is False


def test_is_token_expired_response_false_on_plain_403_text():
    assert is_token_expired_response("HTTP 403 Forbidden") is False


def test_startup_config_validation_raises_on_demo_invalid_account(monkeypatch):
    class FakeKA:
        _cfg = {
            "my_prod": "01",
            "paper_app": "demo-app-key",
            "paper_sec": "demo-app-secret",
            "my_paper_stock": "ABC12345",  # 숫자 8자리 아님
        }

    monkeypatch.setattr(kis_broker, "ka", FakeKA)

    with pytest.raises(ValueError) as exc:
        kis_broker.KISBroker(env_mode="demo")

    assert "KIS 시작 전 설정 검증 실패" in str(exc.value)
    assert "계좌번호 형식 오류" in str(exc.value)


def test_startup_config_validation_passes_on_demo_valid(monkeypatch):
    class FakeKA:
        _cfg = {
            "my_prod": "01",
            "paper_app": "demo-app-key",
            "paper_sec": "demo-app-secret",
            "my_paper_stock": "12345678",
        }

    monkeypatch.setattr(kis_broker, "ka", FakeKA)
    monkeypatch.setattr(kis_broker.KISBroker, "_init_auth", lambda self: None)

    broker = kis_broker.KISBroker(env_mode="demo")
    assert broker.env_mode == "demo"
