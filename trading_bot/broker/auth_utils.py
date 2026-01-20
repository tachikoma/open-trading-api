import os
import time
from typing import Any

class TokenRefreshError(Exception):
    pass


def is_token_expired_response(obj: Any) -> bool:
    """응답이나 예외에서 토큰 만료를 판정합니다.

    정확 매칭만 검사: "EGW00123" 또는 "기간이 만료된 token"
    - 문자열/예외: str()로 변환해 검사
    - dict/list/tuple: 내부 값을 문자열로 결합해 검사
    - DataFrame: 문자열 변환 후 검사
    """
    try:
        # Exception 인스턴스면 메시지로 변환
        if isinstance(obj, Exception):
            msg = str(obj)
            return ("EGW00123" in msg) or ("기간이 만료된 token" in msg)

        # 문자열이면 바로 검사
        if isinstance(obj, str):
            return ("EGW00123" in obj) or ("기간이 만료된 token" in obj)

        # pandas DataFrame이면 문자열화
        try:
            import pandas as _pd
        except Exception:
            _pd = None

        if _pd is not None and isinstance(obj, _pd.DataFrame):
            try:
                text = obj.astype(str).to_string()
            except Exception:
                text = str(obj)
            return ("EGW00123" in text) or ("기간이 만료된 token" in text)

        # dict/list/tuple 등 iterable 검사
        if isinstance(obj, dict):
            parts = []
            for v in obj.values():
                if v is None:
                    continue
                parts.append(str(v))
            text = " ".join(parts)
            return ("EGW00123" in text) or ("기간이 만료된 token" in text)

        if isinstance(obj, (list, tuple)):
            parts = []
            for v in obj:
                if v is None:
                    continue
                parts.append(str(v))
            text = " ".join(parts)
            return ("EGW00123" in text) or ("기간이 만료된 token" in text)

        # 기타 객체는 문자열화 후 검사
        text = str(obj)
        return ("EGW00123" in text) or ("기간이 만료된 token" in text)
    except Exception:
        return False


def refresh_token(ka_module, svr: str, logger, delay_sec: float = 0.5, token_attr: str = "token_tmp"):
    """토큰 파일 삭제 및 재인증 시도. 실패 시 TokenRefreshError 발생."""
    try:
        token_path = getattr(ka_module, token_attr, None)
        if token_path and isinstance(token_path, str) and os.path.exists(token_path):
            try:
                os.remove(token_path)
                logger.info(f"로컬 토큰 파일 삭제: {token_path}")
            except Exception as rem_e:
                logger.warning(f"로컬 토큰 파일 삭제 실패: {rem_e}")

        ka_module.auth(svr=svr)
        logger.info("토큰 재발급 완료.")
        time.sleep(delay_sec)
    except Exception as e:
        logger.error(f"토큰 재발급 실패: {e}")
        raise TokenRefreshError(str(e))
