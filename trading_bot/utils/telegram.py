"""간단한 텔레그램 알림 유틸리티.

동작 원칙:
- `trading_bot.config.Config.TELEGRAM_ENABLED` 설정을 따릅니다.
- 가능한 경우 `requests`를 사용하고, 없으면 `urllib`로 대체합니다.
- 내부 예외는 모두 잡아서 로깅으로 처리하므로 호출자에서 예외가 발생하지 않습니다.
"""
from typing import Optional, Dict
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
from trading_bot.utils.format import format_quantity, format_price
from trading_bot.utils.fees import calculate_fees_and_taxes

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


def _format_krw(value) -> str:
    try:
        if value is None:
            return ""
        return f"{int(round(float(value))):,}원"
    except Exception:
        try:
            return str(value)
        except Exception:
            return ""


def notify_order(action: str, symbol: str, qty: int, price: int, success: bool,
                 message: Optional[str] = None, order_id: Optional[str] = None,
                 currency: str = "KRW", fees: Optional[Dict] = None,
                 exec_price: Optional[int] = None, avg_buy_price: Optional[float] = None,
                 stage: str = "receipt", estimated: bool = False, is_final: bool = False,
                 extras: Optional[Dict] = None):
    """주문 알림 메시지를 HTML 안전하게 포맷하여 전송합니다.

    확장된 인자:
      - fees: calculate_fees_and_taxes 반환 형식의 dict
      - exec_price: 체결 가격(있을 경우)
      - avg_buy_price: 보유중 평균매수가 (체결시 수익률 계산용)
      - stage: 'receipt' 또는 'execution' 등의 구분
      - estimated: 접수 시 추정치 표시 여부
      - is_final: 최종 체결 알림 여부
      - extras: 여분의 정보 딕셔너리
    """
    display = format_symbol(symbol)
    # header 결정
    if is_final:
        header = "주문 체결" if success else "주문 실패"
    else:
        header = "주문 접수" if success else "주문 실패"

    display_e = _html_escape(display)
    action_e = _html_escape(action)
    status_e = _html_escape("성공" if success else "실패")

    msg_parts = [f"<b>{_html_escape(header)}</b> {action_e} {display_e}"]

    # 수량 및 가격 정보
    try:
        formatted_qty = format_quantity(qty)
    except Exception:
        formatted_qty = str(qty)

    if is_final and exec_price:
        msg_parts.append(f"체결가: <b>{_html_escape(_format_krw(exec_price))}</b>")
    else:
        if price and int(price) > 0:
            msg_parts.append(f"주문가: {_html_escape(_format_krw(price))}")
        else:
            msg_parts.append("주문가: 시장가")

    msg_parts.append(f"수량: {_html_escape(formatted_qty)}")

    if order_id:
        msg_parts.append(f"Order ID: <code>{_html_escape(str(order_id))}</code>")

    if message:
        msg_parts.append(_html_escape(str(message)))

    # 접수(추정) 시 표시: 예상비용 / 예상수령
    if not is_final and estimated and fees:
        try:
            total_fees = fees.get("total_fees")
            net_amount = fees.get("net_amount")
            if str(action).strip().lower().startswith("buy"):
                if total_fees is not None:
                    msg_parts.append(f"예상비용(수수료+세금): {_html_escape(_format_krw(total_fees))}")
            else:
                if net_amount is not None:
                    tf = _format_krw(total_fees) if total_fees is not None else ""
                    msg_parts.append(f"예상수령: {_html_escape(_format_krw(net_amount))} (수수료+세금: {_html_escape(tf)})")
        except Exception:
            pass

    # 체결(최종) 표시: 체결가, 수수료, net, 예상수익률(매도시 avg_buy_price 있으면)
    if is_final:
        try:
            if fees is not None:
                total_fees = fees.get("total_fees")
                net_amount = fees.get("net_amount")
                if total_fees is not None:
                    msg_parts.append(f"수수료+세금: {_html_escape(_format_krw(total_fees))}")
                if net_amount is not None:
                    msg_parts.append(f"예상수령: {_html_escape(_format_krw(net_amount))} (수수료+세금: {_html_escape(_format_krw(total_fees))})")

            # 매도일 때 평균매수가 주어지면 예상수익률 계산
            if str(action).strip().lower().startswith("sell") and avg_buy_price:
                try:
                    # buy쪽 추정 수수료
                    buy_fees = calculate_fees_and_taxes(int(round(float(avg_buy_price))), int(qty), side="buy")
                    buy_fees_total = buy_fees.get("total_fees", 0)
                    buy_cost_total = int(round(float(avg_buy_price))) * int(qty) + int(buy_fees_total)
                    if fees is not None and fees.get("net_amount") is not None and buy_cost_total > 0:
                        expected_net_receive = int(fees.get("net_amount"))
                        pnl_pct = (expected_net_receive - buy_cost_total) / float(buy_cost_total) * 100.0
                        msg_parts.append(f"예상수익률: {pnl_pct:.2f}%")
                except Exception:
                    pass
        except Exception:
            pass

    text = "\n".join(msg_parts)
    send_telegram_message(text, parse_mode="HTML")
