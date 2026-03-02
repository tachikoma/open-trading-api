import os
import time
from typing import Any

class TokenRefreshError(Exception):
    pass


def _contains_token_expired_keywords(text: str) -> bool:
    text = str(text).lower()
    # 토큰 발급 빈도 제한(EGW00133)은 만료가 아니라 재발급 과다 호출 상태입니다.
    if "egw00133" in text or "접근토큰 발급 잠시 후 다시 시도" in text:
        return False

    if "egw00123" in text:
        return True
    if "토큰" in text or "토큰이" in text or "만료" in text or "만료된" in text:
        return True
    if "token" in text and ("expire" in text or "expired" in text or "invalid" in text):
        return True
    if "access_token" in text or "access token" in text:
        if "expired" in text or "expire" in text or "invalid" in text:
            return True
    if ("401" in text or "403" in text or "unauthorized" in text) and (
        "token" in text or "access_token" in text or "인증" in text or "토큰" in text
    ):
        return True
    return False


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
            return _contains_token_expired_keywords(str(obj))

        # 문자열이면 바로 검사
        if isinstance(obj, str):
            return _contains_token_expired_keywords(obj)

        # pandas DataFrame이면 문자열화
        try:
            import pandas as _pd
        except Exception:
            _pd = None

        if _pd is not None and isinstance(obj, _pd.DataFrame):
            # DataFrame.attrs에 에러 페이로드가 붙어있는 경우 우선 판정
            try:
                attrs_payload = obj.attrs.get("error_payload") if hasattr(obj, "attrs") else None
                if attrs_payload is not None and is_token_expired_response(attrs_payload):
                    return True
            except Exception:
                pass

            try:
                text = obj.astype(str).to_string().lower()
            except Exception:
                text = str(obj).lower()
            return _contains_token_expired_keywords(text)

        # dict/list/tuple 등 iterable 검사
        if isinstance(obj, dict):
            for value in obj.values():
                if value is None:
                    continue
                if is_token_expired_response(value):
                    return True

            # 값 전체 문자열 결합에 대한 최종 검사(기존 호환)
            text = " ".join([str(v) for v in obj.values() if v is not None]).lower()
            if _contains_token_expired_keywords(text):
                return True
            return False

        if isinstance(obj, (list, tuple)):
            for value in obj:
                if value is None:
                    continue
                if is_token_expired_response(value):
                    return True

            text = " ".join([str(v) for v in obj if v is not None]).lower()
            if _contains_token_expired_keywords(text):
                return True
            return False

        # 기타 객체는 문자열화 후 검사
        return _contains_token_expired_keywords(str(obj))
    except Exception:
        return False


def refresh_token(
    ka_module,
    svr: str,
    logger,
    delay_sec: float = 0.5,
    token_attr: str = "token_tmp",
    max_attempts: int = 3,
    backoff_base_sec: float = 0.5,
    backoff_multiplier: float = 2.0,
    backoff_max_sec: float = 8.0,
):
    """토큰 파일 삭제 및 재인증 시도. 실패 시 TokenRefreshError 발생.

    Note:
        examples_user.kis_auth.auth()는 HTTP 403 등 실패 케이스에서 예외를 던지지 않고
        조용히 return 할 수 있으므로, auth() 호출 이후 read_token()으로 실제 발급 여부를
        검증합니다.
    """
    token_path = getattr(ka_module, token_attr, None)
    removed_any = False

    if token_path and isinstance(token_path, str) and os.path.exists(token_path):
        try:
            os.remove(token_path)
            logger.info(f"로컬 토큰 파일 삭제: {token_path}")
            removed_any = True
        except Exception as rem_e:
            logger.warning(f"로컬 토큰 파일 삭제 실패: {rem_e}")

    if not removed_any:
        cfg_root = getattr(ka_module, "config_root", None)
        if not cfg_root:
            cfg_root = os.path.join(os.path.expanduser("~"), "KIS", "config")
        try:
            date_key = time.strftime("%Y%m%d")
            # 모드별 파일명을 우선 정리한 뒤, 레거시 파일명(KISYYYYMMDD)도 함께 정리합니다.
            candidates = [
                os.path.join(cfg_root, f"KIS{date_key}_{svr}"),
                os.path.join(cfg_root, f"KIS{date_key}"),
            ]
            for candidate in candidates:
                if os.path.exists(candidate):
                    os.remove(candidate)
                    logger.info(f"로컬 토큰 파일 삭제(대체경로): {candidate}")
                    removed_any = True
        except Exception as rem_e:
            logger.warning(f"대체 토큰 파일 삭제 시도 실패: {rem_e}")

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            ka_module.auth(svr=svr)

            # auth()가 예외 없이 끝났더라도 실제 토큰이 생성/저장되었는지 검증
            token_ok = True
            read_token_fn = getattr(ka_module, "read_token", None)
            if callable(read_token_fn):
                token_ok = bool(read_token_fn())

            if token_ok:
                logger.info("토큰 재발급 완료.")
                time.sleep(delay_sec)
                return

            last_error = TokenRefreshError("auth() 호출 후 유효 토큰이 확인되지 않았습니다.")
            logger.warning(
                f"토큰 재발급 검증 실패: 유효 토큰 없음 (시도 {attempt}/{max_attempts})"
            )
        except Exception as e:
            last_error = e
            logger.warning(f"토큰 재발급 시도 실패 (시도 {attempt}/{max_attempts}): {e}")

        if attempt < max_attempts:
            backoff_sec = min(backoff_base_sec * (backoff_multiplier ** (attempt - 1)), backoff_max_sec)
            logger.warning(f"토큰 재발급 재시도 전 대기: {backoff_sec:.2f}초")
            time.sleep(backoff_sec)

    error_message = f"토큰 재발급 실패: {last_error}" if last_error else "토큰 재발급 실패"
    logger.error(error_message)
    raise TokenRefreshError(error_message)
