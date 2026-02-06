"""
KIS Broker 래퍼 클래스

기존 examples_user의 domestic_stock_functions를 래핑하여
전략 모듈에서 쉽게 사용할 수 있도록 추상화합니다.
"""
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import threading
import pandas as pd
import time
import os
import importlib.util

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
# examples_user의 kis_auth.py를 우선 사용하도록 경로를 정렬합니다.
# (예시 코드(examples_*)들이 동일한 모듈명을 사용하므로 import 우선순위를
#  명시적으로 제어해야 합니다.)
sys.path.insert(0, str(PROJECT_ROOT / "examples_llm"))
sys.path.insert(0, str(PROJECT_ROOT / "examples_user"))

# KIS 인증 및 함수들 import
# 예시 폴더(examples_user)와 exemples_llm에 동일한 모듈명이 있어 충돌할 수 있습니다.
# 따라서 examples_user의 `kis_auth.py`를 명시적으로 로드하고 `sys.modules`에
# 등록하여 이후 `import kis_auth` 호출이 올바른 모듈을 참조하도록 합니다.
_kis_auth_path = PROJECT_ROOT / "examples_user" / "kis_auth.py"
spec = importlib.util.spec_from_file_location("kis_auth", str(_kis_auth_path))
ka = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ka)
sys.modules["kis_auth"] = ka

from domestic_stock import domestic_stock_functions as dsf

# trading_bot 모듈 import (절대 경로)
from trading_bot.config import Config
from trading_bot.utils.logger import setup_logger
from trading_bot.utils.telegram import notify_order, send_telegram_message
from trading_bot.utils.symbols import format_symbol
from trading_bot.broker.auth_utils import is_token_expired_response, refresh_token, TokenRefreshError
from trading_bot.utils.fees import calculate_fees_and_taxes


class KISBroker:
    """
    KIS API 래퍼 클래스
    
    기존 domestic_stock_functions의 함수들을 감싸서
    사용하기 편한 인터페이스를 제공합니다.
    """
    
    def __init__(self, env_mode: str = "demo"):
        """
        Args:
            env_mode: 'real' (실전투자) 또는 'demo' (모의투자)
        
        Note:
            KIS API 인증은 kis_auth.py에서 다음 경로의 설정 파일을 사용합니다:
            ~/KIS/config/kis_devlp.yaml
        """
        self.logger = setup_logger("KISBroker", Config.LOG_DIR, Config.LOG_LEVEL)
        self.env_mode = env_mode
        # thread-local storage for last API error payload captured by monkey-patch
        self._local = threading.local()
        
        # KIS 인증 초기화
        self._init_auth()
        
        self.logger.info(f"KISBroker 초기화 완료 (모드: {self.env_mode})")
    
    def _init_auth(self):
        """KIS 인증 초기화
        
        사용자 설정(real/demo)을 KIS API 내부 파라미터(prod/vps)로 변환
        """
        try:
            # env_mode를 KIS API 서버 파라미터로 변환
            # real -> prod (실전투자 서버)
            # demo -> vps (모의투자 서버)
            svr = "prod" if self.env_mode == "real" else "vps"
            self._svr = svr

            # KIS 인증 수행 (토큰 자동 재발급)
            ka.auth(svr=svr)
            # --- monkey-patch: examples_user의 printError 출력이 stdout으로만 가는 문제를 보정
            # APIResp.printError / APIRespError.printError를 덮어써서
            # print() 대신 broker의 logger로 기록하도록 합니다.
            try:
                def _print_error_to_logger(self_resp, url=""):
                    # 안전하게 상태코드와 본문을 추출
                    try:
                        status_raw = getattr(self_resp, "status_code", None)
                        try:
                            status = int(status_raw) if status_raw is not None else None
                        except Exception:
                            status = None
                        body = None
                        if hasattr(self_resp, "error_text"):
                            body = getattr(self_resp, "error_text")
                        elif hasattr(self_resp, "getErrorMessage"):
                            try:
                                body = self_resp.getErrorMessage()
                            except Exception:
                                body = None
                    except Exception:
                        status, body = None, None

                    # 로깅 정책: 2xx 무시, 3xx DEBUG, 4xx WARNING, 5xx WARNING
                    try:
                        if status is not None and 200 <= status < 300:
                            # 정상 응답: 기본적으로 로깅하지 않음
                            return
                        elif status is not None and 300 <= status < 400:
                            self.logger.debug(f"API redirect {status} - body (truncated): {str(body)[:1000]}")
                        elif status is not None and 400 <= status < 500:
                            self.logger.warning(f"API client error {status} - body (truncated): {str(body)[:2000]}")
                        elif status is not None and status >= 500:
                            self.logger.warning(f"API server error {status} - body (truncated): {str(body)[:2000]}")
                        else:
                            # 상태 코드 정보가 없거나 비정형 응답
                            self.logger.info(f"API error (unknown status) - body (truncated): {str(body)[:1000]}")
                    except Exception:
                        try:
                            self.logger.warning("API error (failed to format body)")
                        except Exception:
                            pass

                    # 구조화된 페이로드는 항상 debug로 남김 (수집기/파서용)
                    try:
                        payload = {
                            "context": "APIResp.printError",
                            "http_status": status,
                            "http_body_truncated": (str(body)[:5000] if body is not None else None),
                        }
                        try:
                            self.logger.debug("structured_response", extra={"json_payload": payload})
                        except Exception:
                            import json as _json
                            try:
                                self.logger.debug(f"structured_response_payload: {_json.dumps(payload, ensure_ascii=False)[:2000]}")
                            except Exception:
                                pass

                        # mark this response as logged to avoid duplicate logging later
                        try:
                            try:
                                setattr(self_resp, "_logged_by_kisbroker", True)
                            except Exception:
                                pass
                            # store compact payload in thread-local for later attachment to returned DataFrame
                            try:
                                self._local.last_error_payload = payload
                            except Exception:
                                try:
                                    self._local.__dict__["last_error_payload"] = payload
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    except Exception:
                        pass

                if hasattr(ka, "APIResp"):
                    try:
                        ka.APIResp.printError = _print_error_to_logger
                    except Exception:
                        pass
                if hasattr(ka, "APIRespError"):
                    try:
                        ka.APIRespError.printError = _print_error_to_logger
                    except Exception:
                        pass
            except Exception:
                # monkey-patch가 실패해도 인증 흐름에는 영향 없도록 무시
                self.logger.debug("printError monkey-patch 실패")
            
            # 환경 정보 가져오기
            trenv = ka.getTREnv()
            self.account = trenv.my_acct
            self.product_code = trenv.my_prod
            
            self.logger.info(f"계좌 정보 로드 완료: {self.account}-{self.product_code} (서버: {svr})")
        except Exception as e:
            self.logger.error(f"KIS 인증 초기화 실패: {e}")
            raise

    def _call_with_retry(self, func, *args, max_retries: int = 3, delay_sec: float = 0.5, check_result=None, **kwargs):
        """공통 재시도 래퍼

        - 예외가 발생하거나 `check_result` 콜백이 재시도를 요청하는 경우
          `delay_sec` 만큼 대기 후 최대 `max_retries` 회 재시도합니다.
        - `check_result(result, exception)`는 호출 결과와 예외(있을 경우)를
          받아 `True`(재시도 필요) 또는 `False`(재시도 불필요)를 반환해야 합니다.
        - 기본 동작은 기존과 동일: 예외 메시지에 `EGW00201` 또는 '초당 거래건수'
          관련 텍스트가 포함되면 재시도합니다.
        """
        for attempt in range(1, max_retries + 1):
            try:
                # 사전 토큰 검사: 토큰 파일/내용이 만료되었는지 확인하고
                # 필요 시 재발급을 시도합니다. (500 에러로 토큰 만료를 감지하지 못하는 경우 대비)
                try:
                    svr = getattr(self, "_svr", ("prod" if self.env_mode == "real" else "vps"))
                    if callable(getattr(ka, "read_token", None)):
                        current_token = ka.read_token()
                        if current_token is None:
                            self.logger.info(f"사전 토큰 만료 감지: 로컬 토큰 없음/만료. 재발급 시도 (서버: {svr})")
                            try:
                                refresh_token(ka, svr, self.logger, delay_sec=delay_sec)
                            except TokenRefreshError as tr_e:
                                self.logger.error(f"사전 토큰 재발급 실패: {tr_e}")
                                raise
                except Exception as pre_e:
                    # 토큰 검사/재발급 중 문제 발생해도 호출 시도를 계속 진행하도록 경고만 로깅
                    self.logger.warning(f"사전 토큰 검사/재발급 중 오류: {pre_e}")

                result = func(*args, **kwargs)

                # If a recent API error payload was captured by the monkey-patch,
                # attach it to empty DataFrame results so callers can inspect the cause.
                try:
                    payload = getattr(self._local, "last_error_payload", None)
                    if payload is not None:
                        try:
                            import pandas as _pd
                        except Exception:
                            _pd = None

                        try:
                            if _pd is not None and isinstance(result, _pd.DataFrame) and result.empty:
                                try:
                                    # use DataFrame.attrs for storing metadata
                                    result.attrs["error_payload"] = payload
                                except Exception:
                                    pass
                                try:
                                    delattr(self._local, "last_error_payload")
                                except Exception:
                                    try:
                                        self._local.last_error_payload = None
                                    except Exception:
                                        pass
                        except Exception:
                            # result may be non-DataFrame or partially structured; handle tuples/lists
                            try:
                                if isinstance(result, (list, tuple)):
                                    changed = False
                                    for r in result:
                                        try:
                                            if _pd is not None and isinstance(r, _pd.DataFrame) and r.empty:
                                                try:
                                                    r.attrs["error_payload"] = payload
                                                    changed = True
                                                except Exception:
                                                    pass
                                        except Exception:
                                            continue
                                    if changed:
                                        try:
                                            delattr(self._local, "last_error_payload")
                                        except Exception:
                                            try:
                                                self._local.last_error_payload = None
                                            except Exception:
                                                pass
                            except Exception:
                                pass
                except Exception:
                    pass

                # 결과 기반 토큰 만료 검사: API가 HTTP 200으로 응답하면서
                # body에 만료 코드(EGW00123 등)를 담아오는 경우를 감지
                try:
                    if is_token_expired_response(result):
                        self.logger.warning(f"토큰 만료 응답 감지(결과 기반). (시도 {attempt}/{max_retries})")
                        svr = getattr(self, "_svr", ("prod" if self.env_mode == "real" else "vps"))
                        try:
                            refresh_token(ka, svr, self.logger, delay_sec=delay_sec)
                            if attempt < max_retries:
                                continue
                            else:
                                raise TokenRefreshError("토큰 재발급 후에도 실패")
                        except TokenRefreshError:
                            raise
                        except Exception as auth_e:
                            self.logger.error(f"토큰 재발급 실패(결과 기반): {auth_e}")
                            raise TokenRefreshError(str(auth_e))
                except Exception:
                    # 헬퍼 내부 오류는 무시하고 정상 흐름 유지
                    pass

                # 결과 기반 재시도 판단 콜백이 제공된 경우 호출
                if callable(check_result):
                    try:
                        should_retry = bool(check_result(result, None))
                    except Exception as cb_e:
                        self.logger.warning(f"check_result 콜백 실행 중 오류: {cb_e}")
                        should_retry = False

                    if should_retry:
                        self.logger.warning(f"check_result 요청으로 재시도합니다. (시도 {attempt}/{max_retries})")
                        # 최소한의 요약 정보를 WARNING 레벨로 남겨서
                        # INFO/ERROR 로그 레벨에서도 원인 파악이 가능하도록 합니다.
                        try:
                            if result is None:
                                self.logger.warning("check_result 요약: 결과가 None입니다.")
                            else:
                                try:
                                    import pandas as _pd
                                except Exception:
                                    _pd = None

                                if _pd is not None and isinstance(result, _pd.DataFrame):
                                    try:
                                        self.logger.warning(
                                            f"check_result 요약: DataFrame 빈값={result.empty}, shape={result.shape}"
                                        )
                                    except Exception:
                                        self.logger.warning("check_result 요약: DataFrame (요약 불가)")
                                elif isinstance(result, (dict, list, tuple)):
                                    try:
                                        self.logger.warning(
                                            f"check_result 요약: payload type={type(result).__name__}, len={len(result) if hasattr(result, '__len__') else 'N/A'}"
                                        )
                                    except Exception:
                                        self.logger.warning("check_result 요약: payload (요약 불가)")
                                else:
                                    try:
                                        self.logger.warning(f"check_result 요약: {str(result)[:200]}")
                                    except Exception:
                                        self.logger.warning("check_result 요약: 결과(문자열화 실패)")
                        except Exception:
                            # 요약 로깅에서 오류가 발생해도 진행
                            pass

                        try:
                            # 결과가 있을 경우 가능한 상세 응답/헤더를 추출해 로깅
                            self._log_response_details(result, f"check_result 재시도 (시도 {attempt}/{max_retries})")
                        except Exception as _e:
                            self.logger.debug(f"상세 응답 로깅 중 오류: {_e}")

                        if attempt < max_retries:
                            time.sleep(delay_sec)
                            continue
                        else:
                            raise Exception("check_result 요청으로 재시도했으나 최대 시도 초과")

                return result

            except Exception as e:
                # 예외 기반 재시도 판단: check_result에 예외를 전달해 의사결정 위임
                if callable(check_result):
                    try:
                        should_retry = bool(check_result(None, e))
                    except Exception as cb_e:
                        self.logger.warning(f"check_result 콜백 실행 중 오류: {cb_e}")
                        should_retry = False

                    if should_retry:
                        self.logger.warning(f"check_result 요청으로 예외에서 재시도합니다: {e} (시도 {attempt}/{max_retries})")
                        try:
                            # 예외가 포함하는 응답 객체가 있으면 상세 로깅
                            self._log_response_details(e, f"check_result 예외 재시도 (시도 {attempt}/{max_retries})")
                        except Exception as _e:
                            self.logger.debug(f"상세 예외 로깅 중 오류: {_e}")
                        if attempt < max_retries:
                            time.sleep(delay_sec)
                            continue
                        else:
                            raise
                # 토큰 만료 감지시 자동 갱신 시도 (중앙 헬퍼 사용)
                try:
                    if is_token_expired_response(e):
                        self.logger.warning(f"토큰 만료 응답 감지: {e} (시도 {attempt}/{max_retries})")
                        svr = getattr(self, "_svr", ("prod" if self.env_mode == "real" else "vps"))
                        try:
                            refresh_token(ka, svr, self.logger, delay_sec=delay_sec)
                            if attempt < max_retries:
                                continue
                            else:
                                raise TokenRefreshError("토큰 재발급 후에도 실패")
                        except TokenRefreshError:
                            raise
                        except Exception as auth_e:
                            self.logger.error(f"토큰 재발급 실패: {auth_e}")
                            raise TokenRefreshError(str(auth_e))
                except Exception:
                    # 헬퍼 내부 오류는 무시하고 기존 흐름으로 진행
                    pass

                # 기존 예외 메시지 기반 재시도 (rate limit)
                msg = str(e)
                if "EGW00201" in msg or "초당 거래건수" in msg or "초당 거래건수를 초과" in msg:
                    self.logger.warning(f"API rate limit 응답 감지: {msg} (시도 {attempt}/{max_retries}). 재시도합니다.")
                    if attempt < max_retries:
                        try:
                            self._log_response_details(e, f"rate-limit 예외 재시도 (시도 {attempt}/{max_retries})")
                        except Exception:
                            pass
                        time.sleep(delay_sec)
                        continue

                # 재시도 대상이 아니거나 마지막 시도인 경우, 가능하면 상세 응답을 로그에 남기고 예외 재발생
                try:
                    self._log_response_details(e, f"최종 예외 (시도 {attempt}/{max_retries})")
                except Exception:
                    pass
                raise

    def _log_response_details(self, obj, context: str = "response"):
        """안전하게 다양한 응답/예외 객체에서 헤더와 본문을 추출해 로그로 남깁니다.

        - `obj`는 requests.Response, 예외(HTTPError), examples_user의 APIResp, dict, pandas.DataFrame 등 다양할 수 있음.
        - 본문은 길이 제한(1000자)으로 잘라서 로깅합니다.
        """
        try:
            # None 무시
            if obj is None:
                self.logger.debug(f"{context}: no response object")
                return

            # monkey-patch에서 이미 로깅한 응답이면 중복 로깅을 방지
            try:
                if getattr(obj, "_logged_by_kisbroker", False):
                    try:
                        self.logger.debug(f"{context}: response already logged by KISBroker, skipping duplicate")
                    except Exception:
                        pass
                    return
            except Exception:
                pass

            # examples_user의 APIResp 타입(유사 객체)
            if hasattr(obj, "getHeader") and hasattr(obj, "getBody"):
                try:
                    hdr = obj.getHeader()
                    body = obj.getBody()
                    hdr_items = {}
                    try:
                        hdr_items = {f: getattr(hdr, f) for f in getattr(hdr, "_fields", [])}
                    except Exception:
                        hdr_items = {f: getattr(hdr, f, None) for f in getattr(hdr, "_fields", [])}
                    body_items = {}
                    try:
                        body_items = {f: getattr(body, f) for f in getattr(body, "_fields", [])}
                    except Exception:
                        body_items = {f: getattr(body, f, None) for f in getattr(body, "_fields", [])}

                    payload = {
                        "context": context,
                        "type": "APIResp",
                        "header": hdr_items,
                        "body": {k: (str(v)[:1000] if v is not None else None) for k, v in body_items.items()},
                    }
                    # human-friendly console debug
                    self.logger.debug(f"{context} - APIResp header: {hdr_items}")
                    # structured JSON log (for parsers)
                    self.logger.debug("structured_response", extra={"json_payload": payload})
                    return
                except Exception:
                    pass

            # examples_user의 APIRespError 또는 간단한 에러 객체 처리
            # 일부 KIS 예제는 HTTP 에러시 APIRespError(status_code, error_text)를 반환합니다.
            # 이 객체는 'status_code'와 'error_text' 속성이 있으므로 이를 감지하여 본문을 로깅합니다.
            try:
                if hasattr(obj, "status_code") and (hasattr(obj, "error_text") or hasattr(obj, "getErrorMessage") or hasattr(obj, "getErrorMessage")):
                    try:
                        status_code = getattr(obj, "status_code", None)
                        # error text may be in different attributes
                        body_text = None
                        if hasattr(obj, "error_text"):
                            body_text = getattr(obj, "error_text")
                        elif hasattr(obj, "getErrorMessage"):
                            try:
                                body_text = obj.getErrorMessage()
                            except Exception:
                                body_text = None
                        elif hasattr(obj, "getErrorCode"):
                            try:
                                body_text = obj.getErrorCode()
                            except Exception:
                                body_text = None

                        payload = {
                            "context": context,
                            "type": "api_error",
                            "http_status": status_code,
                            "http_body_truncated": (str(body_text)[:5000] if body_text is not None else None),
                        }
                        # WARNING 수준으로 본문을 남김(500 경우 조사에 용이)
                        try:
                            already_logged = False
                            try:
                                already_logged = bool(getattr(obj, "_logged_by_kisbroker", False))
                            except Exception:
                                already_logged = False

                            if not already_logged:
                                if status_code is not None and int(status_code) >= 500:
                                    self.logger.warning(f"{context} - HTTP {status_code} body (truncated 5k): {str(body_text)[:5000]}")
                                else:
                                    self.logger.info(f"{context} - API error: {str(body_text)[:1000]}")
                        except Exception:
                            pass

                        try:
                            # structured 형태로도 남김
                            self.logger.debug("structured_response", extra={"json_payload": payload})
                        except Exception:
                            try:
                                import json as _json
                                compact = _json.dumps(payload, ensure_ascii=False)
                            except Exception:
                                compact = str(payload)
                            try:
                                self.logger.debug(f"{context} - structured_response_payload: {compact[:2000]}")
                            except Exception:
                                pass

                        # 500대면 추가 경고 (중복 로깅 방지)
                        try:
                            already_logged = False
                            try:
                                already_logged = bool(getattr(obj, "_logged_by_kisbroker", False))
                            except Exception:
                                already_logged = False

                            if status_code is not None and int(status_code) >= 500 and not already_logged:
                                self.logger.warning(f"{context} - 비JSON 500 응답(원문 일부): {str(body_text)[:2000]}")
                        except Exception:
                            pass

                        return
                    except Exception:
                        pass
            except Exception:
                pass

            # requests.Response 또는 response 속성이 있는 예외
            resp = None
            if hasattr(obj, "response"):
                resp = getattr(obj, "response")
            elif hasattr(obj, "getResponse"):
                try:
                    resp = obj.getResponse()
                except Exception:
                    resp = None
            elif hasattr(obj, "headers") and hasattr(obj, "text"):
                resp = obj

            if resp is not None:
                try:
                    headers = dict(resp.headers) if hasattr(resp, "headers") else {}
                except Exception:
                    headers = {}
                try:
                    text = resp.text if hasattr(resp, "text") else str(resp)
                except Exception:
                    text = str(resp)

                # 상태 코드 추출을 시도
                status_code = None
                try:
                    status_code = getattr(resp, "status_code", None) or getattr(resp, "status", None)
                except Exception:
                    status_code = None

                # JSON 파싱 시도
                parsed_json = None
                is_json = False
                try:
                    import json as _json

                    if text is not None and isinstance(text, str) and text.strip():
                        parsed_json = _json.loads(text)
                        is_json = True
                except Exception:
                    parsed_json = None
                    is_json = False

                # payload에 비JSON 처리 포함 (원문은 잘라서 저장)
                payload = {
                    "context": context,
                    "type": "http",
                    "http_status": status_code,
                    "http_headers": headers,
                    "http_body_truncated": (text[:5000] if text is not None else None),
                    "http_body_is_json": is_json,
                }
                if is_json:
                    payload["http_json"] = parsed_json

                # human console: 항상 headers와 본문 요약은 남김
                try:
                    self.logger.debug(f"{context} - HTTP headers: {headers}")
                except Exception:
                    pass

                try:
                    # 500대 에러는 WARNING으로 본문을 남겨 원인 조사에 용이하게 합니다.
                    if status_code is not None and int(status_code) >= 500:
                        self.logger.warning(f"{context} - HTTP {status_code} body (truncated 5k): {text[:5000]}")
                    else:
                        self.logger.debug(f"{context} - HTTP body (truncated 1k): {text[:1000]}")
                except Exception:
                    pass

                # structured JSON 로그는 항상 남김(파서/로그 수집기용)
                try:
                    # structured payload를 extra로 남기고, 포맷터가 extra를 사용하지 않을 경우
                    # 콘솔/파일에 표시되도록 메시지 문자열로도 남깁니다.
                    try:
                        self.logger.debug("structured_response", extra={"json_payload": payload})
                    except Exception:
                        pass
                    try:
                        import json as _json
                        compact = _json.dumps(payload, ensure_ascii=False)
                    except Exception:
                        compact = str(payload)
                    # 길이가 너무 길면 잘라서 남김
                    try:
                        self.logger.debug(f"{context} - structured_response_payload: {compact[:2000]}")
                    except Exception:
                        pass
                except Exception:
                    # structured JSON 로깅 중 오류가 발생해도 진행
                    pass

                # 비JSON일 경우 추가 경고 로그를 남겨서 원문 분석이 필요함을 표시
                if not is_json and status_code is not None and int(status_code) >= 500:
                    try:
                        self.logger.warning(f"{context} - 비JSON 500 응답(원문 일부): {text[:2000]}")
                    except Exception:
                        pass

                return

            # pandas DataFrame
            try:
                import pandas as _pd

                if isinstance(obj, _pd.DataFrame):
                    df_head = obj.head(5).to_dict(orient="list")
                    payload = {"context": context, "type": "dataframe", "head": df_head}
                    self.logger.debug(f"{context} - DataFrame head:\n{obj.head(5).to_string()}")
                    self.logger.debug("structured_response", extra={"json_payload": payload})
                    return
            except Exception:
                pass

            # dict/list/tuple
            if isinstance(obj, (dict, list, tuple)):
                payload = {"context": context, "type": "payload", "payload": obj}
                self.logger.debug(f"{context} - payload: {str(obj)[:1000]}")
                self.logger.debug("structured_response", extra={"json_payload": payload})
                return

            # fallback: 문자열화하여 로깅
            payload = {"context": context, "type": "text", "text": str(obj)[:1000]}
            self.logger.debug(f"{context} - {str(obj)[:1000]}")
            self.logger.debug("structured_response", extra={"json_payload": payload})
        except Exception as ex:
            # 절대 예외를 일으키지 않음
            self.logger.debug(f"{context} - 상세 응답 로깅 실패: {ex}")

    def _check_retry_on_empty_or_rate_limit(self, result, exception) -> bool:
        """기본 재시도 판정기

        - 예외가 주어지면 rate-limit 관련 메시지(EGW00201 등)가 있는지 검사
        - 호가단위 오류는 재시도하지 않음 (비즈니스 로직 오류)
        - 장운영시간 오류는 재시도하지 않음 (시간 외 주문 불가)
        - 결과가 None 또는 DataFrame이고 비어있으면 재시도 권장
        - 결과가 튜플인 경우 모든 요소가 비어있을 때만 재시도 권장
        """
        # 예외 기반 판정
        if exception is not None:
            msg = str(exception)
            if "EGW00201" in msg or "초당 거래건수" in msg or "초당 거래건수를 초과" in msg:
                return True
            # 장운영시간 오류는 재시도하지 않음
            if "장운영시간이 아닙니다" in msg or "장운영시간" in msg:
                self.logger.debug(f"장운영시간 오류 감지: 재시도하지 않음")
                return False
            return False

        # 결과 기반 판정
        if result is None:
            return True

        # pandas 판정을 지연 import로 처리
        try:
            import pandas as _pd
        except Exception:
            _pd = None

        # DataFrame 빈값 판정 (단, 호가단위/장운영시간 오류는 제외)
        if _pd is not None and isinstance(result, _pd.DataFrame):
            if result.empty:
                # error_payload를 확인해서 재시도하면 안 되는 오류가 있는지 체크
                try:
                    error_payload = result.attrs.get("error_payload")
                    if error_payload is not None:
                        error_msg = str(error_payload)
                        # 호가단위 오류
                        if "호가단위" in error_msg or "호가 단위" in error_msg:
                            self.logger.debug(f"호가단위 오류 감지: 재시도하지 않음")
                            return False
                        # 장운영시간 오류
                        if "장운영시간이 아닙니다" in error_msg or "장운영시간" in error_msg:
                            self.logger.debug(f"장운영시간 오류 감지: 재시도하지 않음")
                            return False
                except Exception:
                    pass
                return True
            return False

        # 튜플/리스트인 경우 모든 요소가 비어있을 때만 재시도 (호가단위/장운영시간 오류 체크)
        if isinstance(result, (tuple, list)):
            has_any = False
            for r in result:
                if r is None:
                    continue
                if _pd is not None and isinstance(r, _pd.DataFrame):
                    if not r.empty:
                        has_any = True
                        break
                    # DataFrame이 비어있어도 재시도하면 안 되는 오류는 제외
                    try:
                        error_payload = r.attrs.get("error_payload")
                        if error_payload is not None:
                            error_msg = str(error_payload)
                            # 호가단위 오류
                            if "호가단위" in error_msg or "호가 단위" in error_msg:
                                self.logger.debug(f"호가단위 오류 감지: 재시도하지 않음")
                                return False
                            # 장운영시간 오류
                            if "장운영시간이 아닙니다" in error_msg or "장운영시간" in error_msg:
                                self.logger.debug(f"장운영시간 오류 감지: 재시도하지 않음")
                                return False
                    except Exception:
                        pass
                else:
                    # 비-DataFrame 결과가 존재하면 재시도 불필요
                    has_any = True
                    break
            return not has_any

        return False
    
    def _check_retry_on_rate_limit_only(self, result, exception) -> bool:
        """재시도 판정: 오직 rate-limit 또는 토큰만료같은 오류에 대해서만 재시도하도록 제한합니다.

        - 예외가 주어지면 rate-limit 관련 메시지(EGW00201 등)가 있는지 검사
        - 결과 기반 판정은 항상 재시도하지 않음(빈 결과로 인한 불필요한 재시도 방지)
        """
        if exception is not None:
            msg = str(exception)
            if "EGW00201" in msg or "초당 거래건수" in msg or "초당 거래건수를 초과" in msg:
                return True
            return False

        # 결과가 비어있다고 해서 자동 재시도하지 않음
        return False

    def _format_order_response(self, success: bool, result, qty: int = None, price: int = None,
                               order_id: str = None, side: str = None, fees: dict = None, message: str = None) -> Dict:
        """
        주문 응답을 일관된 dict 포맷으로 반환합니다.

        반환 키(하위 호환 유지):
          - success: bool
          - side: 'buy'|'sell'|None
          - data: 원본 응답 객체
          - order_id: 주문 아이디(가능할 경우)
          - fees: 수수료/세금 계산 결과 dict (가능할 경우)
          - message: 에러 또는 상태 메시지
        """
        payload = {
            "success": bool(success),
            "side": side,
            "data": result,
            "order_id": order_id,
            "fees": fees,
            "message": message,
        }

        # 하위호환: 일부 호출부에서 직접 result.get('success') / result.get('fees') 등을 사용하므로
        # 동일한 접근이 가능하도록 dict 형태로 반환
        return payload
    
    pass
    
    # ==================== 시세 조회 ====================
    
    def get_current_price(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        현재가 조회
        
        Args:
            symbol: 종목코드 (예: "005930")
        
        Returns:
            현재가 정보 DataFrame
        """
        try:
            df = self._call_with_retry(
                dsf.inquire_price,
                env_dv=self.env_mode,
                fid_cond_mrkt_div_code="J",
                fid_input_iscd=symbol,
                check_result=self._check_retry_on_empty_or_rate_limit
            )
            return df
        except Exception as e:
            self.logger.error(f"현재가 조회 실패 ({symbol}): {e}")
            return None
    
    def get_daily_price(self, symbol: str, period: str = "D") -> Optional[pd.DataFrame]:
        """
        일별 시세 조회 (최근 30일 제한)
        
        Args:
            symbol: 종목코드
            period: 기간 구분 (D:일, W:주, M:월)
        
        Returns:
            일별 시세 DataFrame
        """
        try:
            df = self._call_with_retry(
                dsf.inquire_daily_price,
                env_dv=self.env_mode,
                fid_cond_mrkt_div_code="J",
                fid_input_iscd=symbol,
                fid_period_div_code=period,
                fid_org_adj_prc="0",  # 0:수정주가, 1:원주가
                check_result=self._check_retry_on_empty_or_rate_limit
            )
            return df
        except Exception as e:
            self.logger.error(f"일별 시세 조회 실패 ({symbol}): {e}")
            return None
    
    def get_period_price(self, symbol: str, start_date: str, end_date: str, period: str = "D") -> Optional[pd.DataFrame]:
        """
        기간별 시세 조회 (최대 100건)
        
        Args:
            symbol: 종목코드
            start_date: 조회 시작일 (YYYYMMDD)
            end_date: 조회 종료일 (YYYYMMDD)
            period: 기간 구분 (D:일봉, W:주봉, M:월봉, Y:년봉)
        
        Returns:
            기간별 시세 DataFrame (output2)
        """
        try:
            output1, output2 = self._call_with_retry(
                dsf.inquire_daily_itemchartprice,
                env_dv=self.env_mode,
                fid_cond_mrkt_div_code="J",
                fid_input_iscd=symbol,
                fid_input_date_1=start_date,
                fid_input_date_2=end_date,
                fid_period_div_code=period,
                fid_org_adj_prc="0",  # 0:수정주가, 1:원주가
                check_result=self._check_retry_on_empty_or_rate_limit
            )
            return output2  # output2에 일별 시세 데이터가 있음
        except Exception as e:
            self.logger.error(f"기간별 시세 조회 실패 ({symbol}): {e}")
            return None
    
    def get_asking_price(self, symbol: str) -> Optional[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        호가 조회
        
        Args:
            symbol: 종목코드
        
        Returns:
            (호가정보, 예상체결정보) 튜플
        """
        try:
            result = self._call_with_retry(
                dsf.inquire_asking_price_exp_ccn,
                env_dv=self.env_mode,
                fid_cond_mrkt_div_code="J",
                fid_input_iscd=symbol,
                check_result=self._check_retry_on_empty_or_rate_limit
            )
            return result
        except Exception as e:
            self.logger.error(f"호가 조회 실패 ({symbol}): {e}")
            return None, None
    
    # ==================== 계좌 조회 ====================
    
    def get_balance(self) -> Optional[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        잔고 조회
        
        Returns:
            (보유종목 DataFrame, 계좌요약 DataFrame)
        """
        try:
            df1, df2 = self._call_with_retry(
                dsf.inquire_balance,
                env_dv=self.env_mode,
                cano=self.account,
                acnt_prdt_cd=self.product_code,
                afhr_flpr_yn="N",
                inqr_dvsn="01",
                unpr_dvsn="01",
                fund_sttl_icld_yn="N",
                fncg_amt_auto_rdpt_yn="N",
                prcs_dvsn="00",
                check_result=self._check_retry_on_rate_limit_only
            )
            return df1, df2
        except Exception as e:
            self.logger.error(f"잔고 조회 실패: {e}")
            return None, None
    
    def get_buyable_cash(self, symbol: str = "", price: int = 0) -> Optional[int]:
        """
        매수가능 현금 조회

        Args:
            symbol: 조회할 종목코드 (빈문자열이면 종목 미지정)
            price: 주문가 (정수, 기본 0: 시장가)

        Returns:
            매수가능 금액
        """
        try:
            df = self._call_with_retry(
                dsf.inquire_psbl_order,
                env_dv=self.env_mode,
                cano=self.account,
                acnt_prdt_cd=self.product_code,
                pdno=symbol,
                ord_unpr=str(price),
                ord_dvsn="01",
                cma_evlu_amt_icld_yn="N",
                ovrs_icld_yn="N",
                check_result=self._check_retry_on_empty_or_rate_limit,
            )

            if df is not None and not df.empty:
                return int(df.iloc[0].get('ord_psbl_cash') or df.iloc[0].get('nrcvb_buy_amt') or df.iloc[0].get('max_buy_amt') or 0)

            self.logger.warning(f"매수가능 현금 조회 응답 비어있음. symbol={symbol!r}, price={price}. 재시도하지 않습니다.")
            return 0
        except Exception as e:
            self.logger.error(f"매수가능 현금 조회 실패: {e}")
            return 0
    
    # ==================== 주문 ====================
    
    @staticmethod
    def _get_tick_unit(price: int, env_mode: str = "demo") -> int:
        """
        주식 가격대별 호가 단위(tick size)를 반환합니다.
        
        한국거래소(KRX) 기준 호가 단위 규칙:
        - 1,000원 미만: 1원
        - 1,000 ~ 5,000원: 5원
        - 5,000 ~ 10,000원: 10원
        - 10,000 ~ 50,000원: 50원
        - 50,000 ~ 100,000원: 100원
        - 100,000 ~ 500,000원: 500원
        - 500,000원 이상: 1,000원
        
        모의투자(VPS)와 실전투자(PROD) 모두 동일한 규칙을 적용합니다.
        
        Args:
            price: 주문 가격
            env_mode: 'real' (실전투자) 또는 'demo' (모의투자)
        
        Returns:
            해당 가격대의 호가 단위
        """
        if price < 0:
            return 1
        
        if price < 1_000:
            return 1
        elif price < 5_000:
            return 5
        elif price < 10_000:
            return 10
        elif price < 50_000:
            return 50
        elif price < 100_000:
            return 100
        elif price < 500_000:
            return 500
        else:
            return 1_000
    
    @staticmethod
    def _adjust_price_to_tick_unit(price: int, env_mode: str = "demo") -> int:
        """
        주식 가격을 호가 단위(tick size)에 맞춥니다.
        
        KRX 기준 가격대별 호가 단위:
        - 1,000원 미만: 1원
        - 1,000 ~ 5,000원: 5원
        - 5,000 ~ 10,000원: 10원
        - 10,000 ~ 50,000원: 50원
        - 50,000 ~ 100,000원: 100원
        - 100,000 ~ 500,000원: 500원
        - 500,000원 이상: 1,000원
        
        Args:
            price: 조정 전 가격
            env_mode: 'real' (실전투자) 또는 'demo' (모의투자)
        
        Returns:
            호가 단위에 맞춘 가격 (내림)
        """
        if price <= 0:
            return 0
        
        tick_unit = KISBroker._get_tick_unit(price, env_mode)
        return (price // tick_unit) * tick_unit
    
    @staticmethod
    def _validate_price_tick_unit(price: int, env_mode: str = "demo") -> Tuple[bool, str]:
        """
        주문 가격이 호가 단위를 만족하는지 검증합니다.
        
        Args:
            price: 검증할 가격
            env_mode: 'real' (실전투자) 또는 'demo' (모의투자)
        
        Returns:
            (유효성, 오류메시지) 튜플
            - (True, "") : 유효한 가격
            - (False, "오류메시지") : 호가 단위 위반
        """
        if price <= 0:
            return True, ""  # 시장가(0)는 검증 대상 외
        
        tick_unit = KISBroker._get_tick_unit(price, env_mode)
        remainder = price % tick_unit
        
        if remainder != 0:
            adjusted_price = (price // tick_unit) * tick_unit
            return False, (
                f"호가 단위 오류: 가격 {price}원은 호가 단위 {tick_unit}원에 맞지 않습니다. "
                f"조정된 가격: {adjusted_price}원 또는 {adjusted_price + tick_unit}원"
            )
        
        return True, ""
    
    def buy(self, symbol: str, qty: int, price: int = 0, order_type: str = "00") -> Optional[Dict]:
        """
        매수 주문
        
        Args:
            symbol: 종목코드
            qty: 수량
            price: 가격 (0이면 시장가)
            order_type: 주문유형 (00:지정가, 01:시장가)
        
        Returns:
            주문 결과 dict
        """
        if not Config.TRADING_ENABLED:
            self.logger.warning(f"[DRY RUN] 매수 주문: {symbol}, 수량: {qty}, 가격: {price}")
            return self._format_order_response(False, None, qty=qty, price=price, side="buy", message="TRADING_ENABLED=False")
        
        try:
            # 지정가 주문인 경우 호가 단위 검증 및 조정
            original_price = price
            if order_type == "00" and price > 0:
                # 호가 단위 검증
                is_valid, error_msg = self._validate_price_tick_unit(price, env_mode=self.env_mode)
                if not is_valid:
                    self.logger.warning(f"[호가 단위] {symbol} 매수 주문: {error_msg}")
                
                # 호가 단위에 맞게 가격 조정
                adjusted_price = self._adjust_price_to_tick_unit(price, env_mode=self.env_mode)
                if adjusted_price != original_price:
                    self.logger.info(
                        f"가격 조정: {symbol} 매수 {original_price}원 → {adjusted_price}원 "
                        f"(호가 단위: {self._get_tick_unit(original_price, self.env_mode)}원)"
                    )
                price = adjusted_price
            
            result = self._call_with_retry(
                dsf.order_cash,
                env_dv=self.env_mode,
                ord_dv="buy",
                cano=self.account,
                acnt_prdt_cd=self.product_code,
                pdno=symbol,
                ord_dvsn=order_type,
                ord_qty=str(qty),
                ord_unpr=str(price),
                excg_id_dvsn_cd=Config.DEFAULT_EXCHANGE,
                check_result=self._check_retry_on_empty_or_rate_limit
            )
            
            self.logger.info(f"매수 주문 완료: {symbol}, 수량: {qty}, 가격: {price}")
            
            # 시도: result에서 주문ID 추출
            order_id = None
            try:
                import pandas as _pd
                if isinstance(result, _pd.DataFrame) and not result.empty:
                    for col in ("ord_no", "ordno", "odno", "orgn_odno", "order_no", "orderId", "order_id"):
                        if col in result.columns:
                            v = result.iloc[0].get(col)
                            if v:
                                order_id = str(v)
                                break
            except Exception:
                pass
            if not order_id:
                try:
                    if isinstance(result, dict):
                        for k in ("order_no", "ord_no", "odno", "orgn_odno", "ordno", "orderId", "order_id"):
                            v = result.get(k)
                            if v:
                                order_id = str(v)
                                break
                except Exception:
                    pass
            
            # 알림 전송 (성공)
            try:
                notify_order("BUY", symbol, qty, price, True, order_id=order_id, currency="KRW")
            except Exception:
                pass
            
            # 수수료/세금 계산: 가격이 0(시장가)이면 응답에서 체결가를 시도 추출
            exec_price = price
            try:
                import pandas as _pd
                if exec_price == 0 and isinstance(result, _pd.DataFrame) and not result.empty:
                    for col in ("ord_unpr", "prc", "exec_prc", "exec_price", "trd_prc", "order_price"):
                        if col in result.columns:
                            v = result.iloc[0].get(col)
                            if v:
                                exec_price = int(v)
                                break
            except Exception:
                pass
            
            fees = calculate_fees_and_taxes(exec_price or 0, qty, side="buy")
            return self._format_order_response(True, result, qty=qty, price=exec_price or price, order_id=order_id, side="buy", fees=fees)
        except Exception as e:
            self.logger.error(f"매수 주문 실패 ({symbol}): {e}")
            # 알림 전송 (실패)
            try:
                notify_order("BUY", symbol, qty, price, False, message=str(e), currency="KRW")
            except Exception:
                pass
            return self._format_order_response(False, None, qty=qty, price=price, side="buy", message=str(e))
    
    def sell(self, symbol: str, qty: int, price: int = 0, order_type: str = "00") -> Optional[Dict]:
        """
        매도 주문
        
        Args:
            symbol: 종목코드
            qty: 수량
            price: 가격 (0이면 시장가)
            order_type: 주문유형 (00:지정가, 01:시장가)
        
        Returns:
            주문 결과 dict
        """
        if not Config.TRADING_ENABLED:
            self.logger.warning(f"[DRY RUN] 매도 주문: {symbol}, 수량: {qty}, 가격: {price}")
            return self._format_order_response(False, None, qty=qty, price=price, side="sell", message="TRADING_ENABLED=False")
        
        try:
            # 지정가 주문인 경우 호가 단위 검증 및 조정
            original_price = price
            if order_type == "00" and price > 0:
                # 호가 단위 검증
                is_valid, error_msg = self._validate_price_tick_unit(price, env_mode=self.env_mode)
                if not is_valid:
                    self.logger.warning(f"[호가 단위] {symbol} 매도 주문: {error_msg}")
                
                # 호가 단위에 맞게 가격 조정
                adjusted_price = self._adjust_price_to_tick_unit(price, env_mode=self.env_mode)
                if adjusted_price != original_price:
                    self.logger.info(
                        f"가격 조정: {symbol} 매도 {original_price}원 → {adjusted_price}원 "
                        f"(호가 단위: {self._get_tick_unit(original_price, self.env_mode)}원)"
                    )
                price = adjusted_price
            
            result = self._call_with_retry(
                dsf.order_cash,
                env_dv=self.env_mode,
                ord_dv="sell",
                cano=self.account,
                acnt_prdt_cd=self.product_code,
                pdno=symbol,
                ord_dvsn=order_type,
                ord_qty=str(qty),
                ord_unpr=str(price),
                excg_id_dvsn_cd=Config.DEFAULT_EXCHANGE,
                check_result=self._check_retry_on_empty_or_rate_limit
            )
            
            self.logger.info(f"매도 주문 완료: {symbol}, 수량: {qty}, 가격: {price}")
            
            # 시도: result에서 주문ID 추출
            order_id = None
            try:
                import pandas as _pd
                if isinstance(result, _pd.DataFrame) and not result.empty:
                    for col in ("ord_no", "ordno", "odno", "orgn_odno", "order_no", "orderId", "order_id"):
                        if col in result.columns:
                            v = result.iloc[0].get(col)
                            if v:
                                order_id = str(v)
                                break
            except Exception:
                pass
            if not order_id:
                try:
                    if isinstance(result, dict):
                        for k in ("order_no", "ord_no", "odno", "orgn_odno", "ordno", "orderId", "order_id"):
                            v = result.get(k)
                            if v:
                                order_id = str(v)
                                break
                except Exception:
                    pass
            
            # 알림 전송 (성공)
            try:
                notify_order("SELL", symbol, qty, price, True, order_id=order_id, currency="KRW")
            except Exception:
                pass
            
            # 수수료/세금 계산: 가격이 0(시장가)이면 응답에서 체결가를 시도 추출
            exec_price = price
            try:
                import pandas as _pd
                if exec_price == 0 and isinstance(result, _pd.DataFrame) and not result.empty:
                    for col in ("ord_unpr", "prc", "exec_prc", "exec_price", "trd_prc", "order_price"):
                        if col in result.columns:
                            v = result.iloc[0].get(col)
                            if v:
                                exec_price = int(v)
                                break
            except Exception:
                pass
            
            fees = calculate_fees_and_taxes(exec_price or 0, qty, side="sell")
            return self._format_order_response(True, result, qty=qty, price=exec_price or price, order_id=order_id, side="sell", fees=fees)
        except Exception as e:
            self.logger.error(f"매도 주문 실패 ({symbol}): {e}")
            # 알림 전송 (실패)
            try:
                notify_order("SELL", symbol, qty, price, False, message=str(e), currency="KRW")
            except Exception:
                pass
            return self._format_order_response(False, None, qty=qty, price=price, side="sell", message=str(e))
    
    def cancel_order(self, order_no: str, qty: int, symbol: str, order_type: str) -> Optional[Dict]:
        """
        주문 취소
        
        Args:
            order_no: 주문번호
            qty: 취소수량
            symbol: 종목코드
            order_type: 주문유형
        
        Returns:
            취소 결과 dict
        """
        if not Config.TRADING_ENABLED:
            self.logger.warning(f"[DRY RUN] 주문 취소: {order_no}")
            return self._format_order_response(False, None, side="cancel", message="TRADING_ENABLED=False")
        
        try:
            result = self._call_with_retry(
                dsf.order_rvsecncl,
                env_dv=self.env_mode,
                cano=self.account,
                acnt_prdt_cd=self.product_code,
                krx_fwdg_ord_orgno="",  # 한국거래소전송주문조직번호
                orgn_odno=order_no,
                ord_dvsn=order_type,
                rvse_cncl_dvsn_cd="02",  # 취소:02
                ord_qty=str(qty),
                ord_unpr="0",
                qty_all_ord_yn="Y" if qty == 0 else "N",
                check_result=self._check_retry_on_empty_or_rate_limit
            )
            
            self.logger.info(f"주문 취소 완료: {order_no}")
            return self._format_order_response(True, result, side="cancel", order_id=order_no)
        except Exception as e:
            self.logger.error(f"주문 취소 실패 ({order_no}): {e}")
            return self._format_order_response(False, None, side="cancel", message=str(e))
