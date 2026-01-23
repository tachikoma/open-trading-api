import os
import time
from typing import Any

class TokenRefreshError(Exception):
    pass


def is_token_expired_response(obj: Any) -> bool:
    """응답이나 예외에서 토큰 만료를 판정합니다.

    다양한 문구를 폭넓게 검사: EGW 코드, 영어/한국어로 된 토큰 관련 문구,
    HTTP 상태 코드(401/403) 등도 함께 검사합니다.
    - 문자열/예외: 소문자화된 str()로 검사
    - dict/list/tuple: 내부 값을 문자열로 결합해 검사
    - DataFrame: 문자열 변환 후 검사
    """
    try:
        # Exception 인스턴스면 메시지로 변환
        if isinstance(obj, Exception):
            msg = str(obj)
            text = msg.lower()
            # 다양한 패턴 검사
            if "egw00123" in text:
                return True
            if "토큰" in text or "토큰이" in text or "만료" in text or "만료된" in text:
                return True
            if "token" in text and ("expire" in text or "expired" in text or "invalid" in text):
                return True
            if "access_token" in text or "access token" in text:
                if "expired" in text or "expire" in text or "invalid" in text:
                    return True
            # HTTP 상태 코드 포함 메시지에서 인증 관련 코드 검사
            if "401" in text or "403" in text or "unauthorized" in text:
                return True
            return False

        # 문자열이면 바로 검사
        if isinstance(obj, str):
            text = obj.lower()
            if "egw00123" in text:
                return True
            if "토큰" in text or "만료" in text:
                return True
            if "token" in text and ("expire" in text or "expired" in text or "invalid" in text):
                return True
            if "401" in text or "403" in text or "unauthorized" in text:
                return True
            return False

        # pandas DataFrame이면 문자열화
        try:
            import pandas as _pd
        except Exception:
            _pd = None

        if _pd is not None and isinstance(obj, _pd.DataFrame):
            try:
                text = obj.astype(str).to_string().lower()
            except Exception:
                text = str(obj).lower()
            if "egw00123" in text or "토큰" in text or "만료" in text:
                return True
            if "token" in text and ("expire" in text or "expired" in text or "invalid" in text):
                return True
            return False

        # dict/list/tuple 등 iterable 검사
        if isinstance(obj, dict):
            parts = []
            for v in obj.values():
                if v is None:
                    continue
                parts.append(str(v))
            text = " ".join(parts).lower()
            if "egw00123" in text or "토큰" in text or "만료" in text:
                return True
            if "token" in text and ("expire" in text or "expired" in text or "invalid" in text):
                return True
            if "401" in text or "403" in text or "unauthorized" in text:
                return True
            return False

        if isinstance(obj, (list, tuple)):
            parts = []
            for v in obj:
                if v is None:
                    continue
                parts.append(str(v))
            text = " ".join(parts).lower()
            if "egw00123" in text or "토큰" in text or "만료" in text:
                return True
            if "token" in text and ("expire" in text or "expired" in text or "invalid" in text):
                return True
            if "401" in text or "403" in text or "unauthorized" in text:
                return True
            return False

        # 기타 객체는 문자열화 후 검사
        text = str(obj).lower()
        if "egw00123" in text or "토큰" in text or "만료" in text:
            return True
        if "token" in text and ("expire" in text or "expired" in text or "invalid" in text):
            return True
        if "401" in text or "403" in text or "unauthorized" in text:
            return True
        return False
    except Exception:
        return False


def refresh_token(ka_module, svr: str, logger, delay_sec: float = 0.5, token_attr: str = "token_tmp"):
    """토큰 파일 삭제 및 재인증 시도. 실패 시 TokenRefreshError 발생."""
    try:
        token_path = getattr(ka_module, token_attr, None)
        removed_any = False
        # 기본 token_attr에서 파일이 있으면 삭제
        if token_path and isinstance(token_path, str) and os.path.exists(token_path):
            try:
                os.remove(token_path)
                logger.info(f"로컬 토큰 파일 삭제: {token_path}")
                removed_any = True
            except Exception as rem_e:
                logger.warning(f"로컬 토큰 파일 삭제 실패: {rem_e}")

        # token_path가 없거나 삭제되지 않았다면, examples_user의 통상 경로를 시도
        if not removed_any:
            cfg_root = getattr(ka_module, "config_root", None)
            if not cfg_root:
                cfg_root = os.path.join(os.path.expanduser("~"), "KIS", "config")
            try:
                today_candidate = os.path.join(cfg_root, f"KIS{time.strftime('%Y%m%d')}")
                if os.path.exists(today_candidate):
                    os.remove(today_candidate)
                    logger.info(f"로컬 토큰 파일 삭제(대체경로): {today_candidate}")
                    removed_any = True
            except Exception as rem_e:
                logger.warning(f"대체 토큰 파일 삭제 시도 실패: {rem_e}")

        # 인증 재시도
        ka_module.auth(svr=svr)
        logger.info("토큰 재발급 완료.")
        time.sleep(delay_sec)
    except Exception as e:
        logger.error(f"토큰 재발급 실패: {e}")
        raise TokenRefreshError(str(e))
