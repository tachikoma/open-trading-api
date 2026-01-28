"""Simple Telegram notifier utility.

Behavior:
- Respects `trading_bot.config.Config.TELEGRAM_ENABLED`.
- Uses `requests` if available, falls back to `urllib`.
- Catches all exceptions and logs via `logging` to avoid raising in caller.
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
    """Send a message to configured Telegram chat.

    Returns True on success, False otherwise.
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
                logger.warning(f"Telegram API responded not ok: {resp}")
            return ok
        else:
            data = _urllib_parse.urlencode(payload).encode()
            req = _urllib_request.Request(url, data=data)
            with _urllib_request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                j = json.loads(body)
                ok = bool(j.get("ok"))
                if not ok:
                    logger.warning(f"Telegram API responded not ok: {j}")
                return ok

    except Exception as e:
        logger.warning(f"Failed to send Telegram message: {e}")
        return False


def _html_escape(s: str) -> str:
    if s is None:
        return ""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))


def notify_order(action: str, symbol: str, qty: int, price: int, success: bool, message: Optional[str] = None, order_id: Optional[str] = None):
    """Format and send an HTML-safe order notification including optional order_id."""
    display = format_symbol(symbol)
    status = "성공" if success else "실패"
    # Escape values for HTML
    display_e = _html_escape(display)
    msg_parts = [f"<b>{_html_escape(action)}</b> {display_e}"]
    msg_parts.append(f"qty={_html_escape(str(qty))} price={_html_escape(str(price))} — <b>{_html_escape(status)}</b>")
    if order_id:
        msg_parts.append(f"Order ID: <code>{_html_escape(str(order_id))}</code>")
    if message:
        msg_parts.append(_html_escape(str(message)))

    text = "\n".join(msg_parts)
    # send with HTML parse mode
    send_telegram_message(text, parse_mode="HTML")
