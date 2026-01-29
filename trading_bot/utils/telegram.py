"""간단한 텔레그램 알림 유틸리티.

동작 원칙:
- `trading_bot.config.Config.TELEGRAM_ENABLED` 설정을 따릅니다.
- 가능한 경우 `requests`를 사용하고, 없으면 `urllib`로 대체합니다.
- 내부 예외는 모두 잡아서 로깅으로 처리하므로 호출자에서 예외가 발생하지 않습니다.
"""
from typing import Optional
import logging
import json

try:
    import requests
    _HAS_REQUESTS = True
except Exception:
    import urllib.request as _urllib_request
    import urllib.parse as _urllib_parse
    _HAS_REQUESTS = False

from trading_bot.config import Config
from trading_bot.utils.symbols import format_symbol

logger = logging.getLogger("Telegram")


def _build_url(token: str, chat_id: str, text: str, parse_mode: str = "HTML") -> (str, dict):
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    return api, payload


def send_telegram_message(text: str, parse_mode: str = "HTML") -> bool:
    """설정된 텔레그램 채팅으로 메시지를 전송합니다.

    성공하면 `True`, 실패하면 `False`를 반환합니다.
    """
    if not Config.TELEGRAM_ENABLED:
        return False

    token = Config.TELEGRAM_BOT_TOKEN
    chat_id = Config.TELEGRAM_CHAT_ID
    timeout = getattr(Config, "TELEGRAM_TIMEOUT_SEC", 3)

    if not token or not chat_id:
        logger.warning("Telegram configured but TOKEN/CHAT_ID missing")
        return False

    try:
        url, payload = _build_url(token, chat_id, text, parse_mode=parse_mode)

        if _HAS_REQUESTS:
            r = requests.post(url, data=payload, timeout=timeout)
            r.raise_for_status()
            resp = r.json()
            ok = bool(resp.get("ok"))
            if not ok:
                logger.warning(f"Telegram API 응답이 OK가 아닙니다: {resp}")
            return ok
        else:
            data = _urllib_parse.urlencode(payload).encode()
            req = _urllib_request.Request(url, data=data)
            with _urllib_request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                j = json.loads(body)
                ok = bool(j.get("ok"))
                if not ok:
                    logger.warning(f"Telegram API 응답이 OK가 아닙니다: {j}")
                return ok

    except Exception as e:
        logger.warning(f"Telegram 메시지 전송 실패: {e}")
        return False


def _html_escape(s: str) -> str:
    """HTML 파싱용 문자열 이스케이프.

    None이면 빈 문자열을 반환합니다.
    """
    if s is None:
        return ""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))


def notify_order(action: str, symbol: str, qty: int, price: int, success: bool, message: Optional[str] = None, order_id: Optional[str] = None):
    """주문 알림 메시지를 HTML 안전하게 포맷하여 전송합니다.

    인자:
        action: 'BUY' 또는 'SELL' 등의 액션 문자열
        symbol: 종목 코드
        qty: 수량
        price: 가격
        success: 성공 여부
        message: 선택적 상세 메시지
        order_id: 선택적 주문 ID
    """
    display = format_symbol(symbol)
    status = "성공" if success else "실패"
    # HTML 이스케이프 처리
    display_e = _html_escape(display)
    msg_parts = [f"<b>{_html_escape(action)}</b> {display_e}"]
    msg_parts.append(f"qty={_html_escape(str(qty))} price={_html_escape(str(price))} — <b>{_html_escape(status)}</b>")
    if order_id:
        msg_parts.append(f"Order ID: <code>{_html_escape(str(order_id))}</code>")
    if message:
        msg_parts.append(_html_escape(str(message)))

    text = "\n".join(msg_parts)
    # HTML 파싱 모드로 전송
    send_telegram_message(text, parse_mode="HTML")
