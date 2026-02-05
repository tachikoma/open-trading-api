"""
KIS Broker 래퍼 클래스

기존 examples_user의 domestic_stock_functions를 래핑하여
전략 모듈에서 쉽게 사용할 수 있도록 추상화합니다.
"""
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import threading
import pandas as pd
import time
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
from overseas_stock import overseas_stock_functions as osf

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

    def _extract_exec_price_and_qty(self, res) -> tuple:
        """다양한 API 응답 포맷에서 실행가격(exec_price)과 실행수량(exec_qty)을 추출합니다.

        반환값: (exec_price: float|None, exec_qty: int|None)
        - res는 execute_intents에서 사용하는 `res` 객체일 수 있으며,
          dict({'data': ...}), pandas.DataFrame, list[dict], 또는 중첩 dict 형태일 수 있습니다.
        """
        exec_price = None
        exec_qty = None

        # 후보 키 목록 (우선순위)
        price_keys = [
            "exec_price", "exec_prc", "execPrz", "execPr", "exec_prc", "trade_price", "trade_prc",
            "trd_prc", "price", "filledPrice", "filled_price", "avg_price", "avg_prc",
            "체결가", "체결가격", "fm_ccld_pric", "fm_ccld_amt", "trdPrice", "tradePrice",
        ]
        qty_keys = [
            "exec_qty", "exec_qy", "execQy", "trade_qty", "trade_qy", "trd_qty", "qty", "quantity",
            "체결수량", "ccld_qty", "fm_ccld_qty", "filledQty", "filledQuantity", "filled_qty",
        ]

        # 원시 데이터가 dict 형태로 감싸져 있는 경우(data 키)
        d = None
        if isinstance(res, dict) and "data" in res:
            d = res.get("data")
        else:
            d = res

        # pandas DataFrame 처리
        try:
            import pandas as _pd
        except Exception:
            _pd = None

        if _pd is not None and isinstance(d, _pd.DataFrame):
            if not d.empty:
                row = d.iloc[0]
                for k in price_keys:
                    if k in row.index and row.get(k) is not None:
                        try:
                            exec_price = float(row.get(k))
                            break
                        except Exception:
                            continue
                for k in qty_keys:
                    if k in row.index and row.get(k) is not None:
                        try:
                            exec_qty = int(float(row.get(k)))
                            break
                        except Exception:
                            continue
                return exec_price, exec_qty

        # 리스트(예: [{'exec_price':...}, ...])
        if isinstance(d, (list, tuple)) and len(d) > 0 and isinstance(d[0], dict):
            first = d[0]
            for k in price_keys:
                if k in first and first.get(k) is not None:
                    try:
                        exec_price = float(first.get(k))
                        break
                    except Exception:
                        continue
            for k in qty_keys:
                if k in first and first.get(k) is not None:
                    try:
                        exec_qty = int(float(first.get(k)))
                        break
                    except Exception:
                        continue
            return exec_price, exec_qty

        # dict의 경우 여러 레벨 탐색 (얕은 탐색)
        if isinstance(d, dict):
            # 우선 최상위에서 찾기
            for k in price_keys:
                if k in d and d.get(k) is not None:
                    try:
                        exec_price = float(d.get(k))
                        break
                    except Exception:
                        continue
            for k in qty_keys:
                if k in d and d.get(k) is not None:
                    try:
                        exec_qty = int(float(d.get(k)))
                        break
                    except Exception:
                        continue

            # 필요 시 nested 구조(예: {'body': {...}}) 한 단계 더 탐색
            if exec_price is None or exec_qty is None:
                for v in d.values():
                    if isinstance(v, dict):
                        for k in price_keys:
                            if k in v and v.get(k) is not None:
                                try:
                                    exec_price = float(v.get(k))
                                    break
                                except Exception:
                                    continue
                        for k in qty_keys:
                            if k in v and v.get(k) is not None:
                                try:
                                    exec_qty = int(float(v.get(k)))
                                    break
                                except Exception:
                                    continue
                    if exec_price is not None and exec_qty is not None:
                        break

        # 마지막으로, 만약 res 자체가 단순 수치/문자열이면 시도해봄
        try:
            if exec_price is None and isinstance(res, (int, float)):
                exec_price = float(res)
        except Exception:
            pass

        return exec_price, exec_qty

    def _check_retry_on_empty_or_rate_limit(self, result, exception) -> bool:
        """기본 재시도 판정기

        - 예외가 주어지면 rate-limit 관련 메시지(EGW00201 등)가 있는지 검사
        - 결과가 None 또는 DataFrame이고 비어있으면 재시도 권장
        - 결과가 튜플인 경우 모든 요소가 비어있을 때만 재시도 권장
        """
        # 예외 기반 판정
        if exception is not None:
            msg = str(exception)
            if "EGW00201" in msg or "초당 거래건수" in msg or "초당 거래건수를 초과" in msg:
                return True
            return False

        # 결과 기반 판정
        if result is None:
            return True

        # pandas 판정을 지연 import로 처리
        try:
            import pandas as _pd
        except Exception:
            _pd = None

        # DataFrame 빈값 판정
        if _pd is not None and isinstance(result, _pd.DataFrame):
            return result.empty

        # 튜플/리스트인 경우 모든 요소가 비어있을 때만 재시도
        if isinstance(result, (tuple, list)):
            has_any = False
            for r in result:
                if r is None:
                    continue
                if _pd is not None and isinstance(r, _pd.DataFrame):
                    if not r.empty:
                        has_any = True
                        break
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
        현재가 조회 (국내 주식)
        
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
    
    def get_current_price_overseas(self, symbol: str, exch: str = "NAS") -> Optional[pd.DataFrame]:
        """
        해외 주식 현재가 조회
        
        Args:
            symbol: 해외 종목코드 (예: "AAPL", "TQQQ")
            exch: 거래소 코드 (NAS: 나스닥, NYS: 뉴욕, AMS: 아멕스 등)
        
        Returns:
            현재가 정보 DataFrame
        """
        try:
            # 거래소 코드 정규화 (사용자 입력 허용)
            exch_map = {
                "NASD": "NAS",
                "NYSE": "NYS",
                "AMEX": "AMS",
            }
            excd = exch_map.get((exch or "").upper(), (exch or "NAS").upper())

            df = self._call_with_retry(
                osf.price,
                auth="",
                excd=excd,
                symb=symbol,
                env_dv=self.env_mode,
                check_result=self._check_retry_on_empty_or_rate_limit
            )
            # 빈 응답일 경우 price_detail로 폴백 시도
            if df is None or (hasattr(df, "empty") and df.empty):
                try:
                    detail_df = self._call_with_retry(
                        osf.price_detail,
                        auth="",
                        excd=excd,
                        symb=symbol,
                        check_result=self._check_retry_on_empty_or_rate_limit
                    )
                    return detail_df
                except Exception as e:
                    self.logger.error(f"해외 현재가 상세 조회 실패 ({symbol}): {e}")
            return df
        except Exception as e:
            self.logger.error(f"해외 현재가 조회 실패 ({symbol}): {e}")
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
        잔고 조회 (국내 주식)
        
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
    
    def get_balance_overseas(self, ovrs_excg_cd: str = "NASD", tr_crcy_cd: str = "USD") -> Optional[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        해외 주식 잔고 조회
        
        Args:
            ovrs_excg_cd: 해외거래소코드 (NASD:나스닥, NYSE:뉴욕, AMEX:아멕스, SEHK:홍콩 등)
            tr_crcy_cd: 거래통화코드 (USD:미국달러, HKD:홍콩달러, CNY:중국위안화, JPY:일본엔화, VND:베트남동)
        
        Returns:
            (보유종목 DataFrame, 계좌요약 DataFrame)
        """
        try:
            df1, df2 = self._call_with_retry(
                osf.inquire_balance,
                cano=self.account,
                acnt_prdt_cd=self.product_code,
                ovrs_excg_cd=ovrs_excg_cd,
                tr_crcy_cd=tr_crcy_cd,
                FK200="",
                NK200="",
                env_dv=self.env_mode,
                check_result=self._check_retry_on_rate_limit_only
            )
            return df1, df2
        except Exception as e:
            self.logger.error(f"해외 주식 잔고 조회 실패 (거래소: {ovrs_excg_cd}, 통화: {tr_crcy_cd}): {e}")
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
                notify_order("BUY", symbol, qty, price, True, order_id=order_id)
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
                                try:
                                    exec_price = int(float(v))
                                except Exception:
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
                notify_order("BUY", symbol, qty, price, False, message=str(e))
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
                notify_order("SELL", symbol, qty, price, True, order_id=order_id)
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
                                try:
                                    exec_price = int(float(v))
                                except Exception:
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
                notify_order("SELL", symbol, qty, price, False, message=str(e))
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

    # ==================== 해외 주문 지원 ====================
    def _map_overseas_ord_dvsn(self, order_type: str, side: str) -> Tuple[str, str]:
        """주문유형(전략에서 전달되는 'LIMIT'/'LOC' 등)을 API 파라미터로 매핑합니다.

        Returns:
            (ord_svr_dvsn_cd, ord_dvsn)
        """
        ot = (order_type or "LIMIT").upper()
        # ord_svr_dvsn_cd는 대부분 '0'을 사용
        ord_svr = "0"
        # ord_dvsn: 해외 API 문서에 따른 값 매핑
        mapping = {
            "LIMIT": "00",
            "LOO": "32",
            "LOC": "34",
            "MOO": "31",
            "MOC": "33",
        }
        ord_dvsn = mapping.get(ot, "00")
        # 일부 주문 유형은 매도/매수에서 유효값이 다르므로 필요 시 side에 따라 조정 가능
        return ord_svr, ord_dvsn

    def buy_overseas(self, symbol: str, qty: int, price: float, order_type: str = "LIMIT", ovrs_excg_cd: str = None) -> Optional[Dict]:
        """해외주식 매수 주문 래퍼

        Args:
            symbol: 해외 종목 코드 (예: AAPL)
            qty: 주문 수량
            price: 해외 통화 단가 (예: 150.25)
            order_type: 전략이 지정하는 주문유형 (예: 'LIMIT', 'LOC')
            ovrs_excg_cd: 거래소 코드(예: 'NASD'). 미지정 시 기본 'NASD' 사용
        """
        if not Config.TRADING_ENABLED:
            self.logger.warning(f"[DRY RUN] 해외 매수 주문: {symbol}, qty={qty}, price={price}, type={order_type}")
            return {"success": False, "message": "TRADING_ENABLED=False"}

        try:
            ord_svr, ord_dvsn = self._map_overseas_ord_dvsn(order_type, side="buy")
            ovrs_excg = ovrs_excg_cd or self.config_overseas_default() if hasattr(self, 'config_overseas_default') else ("NASD")
            res = self._call_with_retry(
                osf.order,
                cano=self.account,
                acnt_prdt_cd=self.product_code,
                ovrs_excg_cd=ovrs_excg,
                pdno=symbol,
                ord_qty=str(qty),
                ovrs_ord_unpr=str(price),
                ord_dv="buy",
                ctac_tlno="",
                mgco_aptm_odno="",
                ord_svr_dvsn_cd=ord_svr,
                ord_dvsn=ord_dvsn,
                env_dv=self.env_mode,
                check_result=self._check_retry_on_empty_or_rate_limit,
            )
            return {"success": True, "data": res}
        except Exception as e:
            self.logger.error(f"해외 매수 주문 실패 ({symbol}): {e}")
            try:
                notify_order("BUY_OVR", symbol, qty, price, False, message=str(e))
            except Exception:
                pass
            return {"success": False, "message": str(e)}

    def sell_overseas(self, symbol: str, qty: int, price: float, order_type: str = "LIMIT", ovrs_excg_cd: str = None) -> Optional[Dict]:
        """해외주식 매도 주문 래퍼
        """
        if not Config.TRADING_ENABLED:
            self.logger.warning(f"[DRY RUN] 해외 매도 주문: {symbol}, qty={qty}, price={price}, type={order_type}")
            return {"success": False, "message": "TRADING_ENABLED=False"}

        try:
            ord_svr, ord_dvsn = self._map_overseas_ord_dvsn(order_type, side="sell")
            ovrs_excg = ovrs_excg_cd or self.config_overseas_default() if hasattr(self, 'config_overseas_default') else ("NASD")
            res = self._call_with_retry(
                osf.order,
                cano=self.account,
                acnt_prdt_cd=self.product_code,
                ovrs_excg_cd=ovrs_excg,
                pdno=symbol,
                ord_qty=str(qty),
                ovrs_ord_unpr=str(price),
                ord_dv="sell",
                ctac_tlno="",
                mgco_aptm_odno="",
                ord_svr_dvsn_cd=ord_svr,
                ord_dvsn=ord_dvsn,
                env_dv=self.env_mode,
                check_result=self._check_retry_on_empty_or_rate_limit,
            )
            return {"success": True, "data": res}
        except Exception as e:
            self.logger.error(f"해외 매도 주문 실패 ({symbol}): {e}")
            try:
                notify_order("SELL_OVR", symbol, qty, price, False, message=str(e))
            except Exception:
                pass
            return {"success": False, "message": str(e)}

    def execute_intents(self, intents: List[Dict[str, Any]], strategy: Any = None, simulate_only: bool = False) -> List[Dict[str, Any]]:
        """전략이 생성한 주문 의도(intent) 목록을 실행하는 유틸 메서드.

        설명:
            전략은 `decide_buy`/`decide_sell`에서 의도(intent) 딕셔너리 목록을 반환합니다.
            이 메서드는 그 의도들을 받아서 실제 주문을 실행하거나(라이브),
            시뮬레이션(드라이런) 결과를 반환합니다. 또한 주문 성공 시 선택적으로
            전략 인스턴스의 상태(`state['cum_buy_amt']`)를 갱신하고 거래 기록을 남깁니다.

        인자:
            intents: 전략에서 생성한 intent 딕셔너리의 목록 (v2.2 포맷 권장)
            strategy: 선택적 전략 객체. 전달하면 주문 실행 후 `state` 갱신 및 `record_trade` 호출을 시도합니다.
            simulate_only: True이면 실제 주문을 호출하지 않고 드라이런(시뮬레이션) 결과만 반환합니다.

        반환값:
            각 intent에 대한 처리 결과를 담은 딕셔너리 리스트. 각 원소는 `{"intent": intent, "result": result}` 형태입니다.
        """
        results: List[Dict[str, Any]] = []
        processed_sell = False
        for intent in intents:
            try:
                ttype = intent.get("type")
                symbol = intent.get("symbol") or intent.get("sym")
                # API 호출에는 원시 심볼(예: AAPL, 005930)을 사용하고
                # 표시용으로는 format_symbol을 사용합니다.
                symbol_display = None
                if symbol and isinstance(symbol, str):
                    try:
                        symbol_display = format_symbol(symbol)
                    except Exception:
                        symbol_display = symbol
                # 주문 가격이 None일 수 있음(예: MOC). None이면 0으로 처리.
                raw_price = intent.get("price", 0)
                try:
                    price = int(round(float(raw_price))) if raw_price is not None else 0
                except Exception:
                    # 안전하게 0으로 폴백
                    price = 0

                # 수량 결정: intent에 'quantity'가 명시되어 있으면 우선 사용하고,
                # 없으면 'amount'와 'price'로부터 정수 수량을 계산합니다.
                qty = intent.get("quantity")
                if qty is None:
                    amount = float(intent.get("amount", 0.0))
                    if price > 0:
                        qty = int(amount // price)
                    else:
                        qty = 0
                else:
                    qty = int(qty)

                # 유효 수량 검증
                if qty <= 0:
                    msg = "zero_qty_or_invalid_price"
                    self.logger.warning(f"의도 건너뜀: {msg} intent={intent}")
                    results.append({"intent": intent, "result": {"success": False, "message": msg}})
                    continue

                # 드라이런(시뮬레이션) 경로: Config 또는 인자에 의해 실제 주문을 보내지 않을 때
                if simulate_only or not Config.TRADING_ENABLED:
                    self.logger.info(f"[DRY RUN] 의도 실행: {ttype} {symbol} qty={qty} price={price}")
                    fake_res = {"success": True, "order_id": None, "data": None}
                    results.append({"intent": intent, "result": fake_res})

                    # 전략 객체가 제공된 경우 상태 갱신 및 거래 기록(기록 함수 호출)을 시도
                    if strategy is not None and ttype == "buy" and fake_res.get("success"):
                        amt = qty * price
                        # strategy가 심볼별 누적 함수를 제공하면 사용
                        try:
                            if hasattr(strategy, 'add_cum_buy'):
                                strategy.add_cum_buy(symbol, amt)
                            else:
                                strategy.state["cum_buy_amt"] = strategy.state.get("cum_buy_amt", 0.0) + float(amt)
                        except Exception:
                            strategy.state["cum_buy_amt"] = strategy.state.get("cum_buy_amt", 0.0) + float(amt)
                        try:
                            strategy.record_trade({"symbol": symbol, "qty": qty, "price": price, "amount": amt, "side": "buy"})
                        except Exception:
                            pass
                    elif strategy is not None and ttype == "sell" and fake_res.get("success"):
                        try:
                            strategy.record_trade({"symbol": symbol, "qty": qty, "price": price, "amount": qty * price, "side": "sell"})
                        except Exception:
                            pass
                    continue

                # 라이브 경로: 실제 매수/매도 API 호출
                # 전략 상태에 따라 LOC/LIMIT 주문을 즉시 실행하지 않고 EOD에서 확정하도록
                # strategy.state['pending_orders']에 저장할 수 있습니다.
                defer_loc_buy = False
                defer_loc_sell = False
                try:
                    if strategy is not None:
                        defer_loc_buy = bool(strategy.state.get("defer_loc_buy", False))
                        defer_loc_sell = bool(strategy.state.get("defer_loc_sell", False))
                except Exception:
                    defer_loc_buy = False
                    defer_loc_sell = False
                # 해외주식 라우팅: intent에 'market'=='overseas' 또는 'ovrs_excg_cd'가 포함된 경우
                is_overseas = bool(intent.get("market") == "overseas" or intent.get("ovrs_excg_cd"))

                if is_overseas:
                    ovrs_excg = intent.get("ovrs_excg_cd")
                    ord_type = str(intent.get("order_type", "LIMIT"))
                    # 해외 LOC/LIMIT을 지연 저장할 경우
                    if ttype == "buy" and ord_type.upper() in ("LOC", "LIMIT") and defer_loc_buy:
                        try:
                            pending = strategy.state.setdefault("pending_orders", []) if strategy is not None else []
                            pending.append({"order_id": None, "side": "buy", "symbol": symbol, "qty": qty, "price": intent.get("price"), "order_type": ord_type, "intent": intent})
                            results.append({"intent": intent, "result": {"success": True, "deferred": True}})
                        except Exception:
                            results.append({"intent": intent, "result": {"success": False, "message": "defer_store_failed"}})
                        continue
                    if ttype == "buy":
                        res = self.buy_overseas(symbol, qty, price, order_type=ord_type, ovrs_excg_cd=ovrs_excg)
                    elif ttype == "sell" and ord_type.upper() in ("LOC", "LIMIT") and defer_loc_sell:
                        try:
                            pending = strategy.state.setdefault("pending_orders", []) if strategy is not None else []
                            pending.append({"order_id": None, "side": "sell", "symbol": symbol, "qty": qty, "price": intent.get("price"), "order_type": ord_type, "intent": intent})
                            results.append({"intent": intent, "result": {"success": True, "deferred": True}})
                        except Exception:
                            results.append({"intent": intent, "result": {"success": False, "message": "defer_store_failed"}})
                        continue
                    elif ttype == "sell":
                        res = self.sell_overseas(symbol, qty, price, order_type=ord_type, ovrs_excg_cd=ovrs_excg)
                    else:
                        res = {"success": False, "message": f"알 수 없는 intent 타입: {ttype}"}
                else:
                    # 국내 주문(예: KOSPI/KOSDAQ)은 LOC/LIMIT/MOC 등 고급 주문 타입이
                    # 적용되지 않는 환경일 수 있으므로 단순 매수/매도 호출로 처리합니다.
                    if ttype == "buy":
                        res = self.buy(symbol, qty, price, order_type=str(intent.get("order_type", "00")))
                    elif ttype == "sell":
                        res = self.sell(symbol, qty, price, order_type=str(intent.get("order_type", "00")))
                    else:
                        res = {"success": False, "message": f"알 수 없는 intent 타입: {ttype}"}
                

                results.append({"intent": intent, "result": res})

                # 주문이 성공적으로 응답된 경우(확정 응답이라고 가정) 전략 상태 갱신 시도
                if strategy is not None and isinstance(res, dict) and res.get("success"):
                    if ttype == "buy":
                        amt = qty * price
                        try:
                            if hasattr(strategy, 'add_cum_buy'):
                                strategy.add_cum_buy(symbol, amt)
                            else:
                                strategy.state["cum_buy_amt"] = strategy.state.get("cum_buy_amt", 0.0) + float(amt)
                        except Exception:
                            strategy.state["cum_buy_amt"] = strategy.state.get("cum_buy_amt", 0.0) + float(amt)
                        try:
                            strategy.record_trade({"symbol": symbol, "qty": qty, "price": price, "amount": amt, "side": "buy", "order_id": res.get("order_id")})
                        except Exception:
                            pass
                        # 쿼터 모드 재진입 회차 증가 및 재진입 금액 소모 반영
                        try:
                            if intent.get("quota_mode"):
                                strategy.state["quota_cycle_count"] = int(strategy.state.get("quota_cycle_count", 0)) + 1
                                # 소모된 금액만큼 재진입 잔액에서 차감
                                strategy.state["quota_reentry_amount"] = float(strategy.state.get("quota_reentry_amount", 0.0)) - float(amt)
                                if strategy.state["quota_reentry_amount"] < 0:
                                    strategy.state["quota_reentry_amount"] = 0.0
                        except Exception:
                            pass
                        # 성공적으로 매수가 실행되었으면 해당 T에 대해 실행표시를 남깁니다(하루 1회 제한)
                        try:
                            t_val = intent.get("T")
                            exec_date = intent.get("exec_date")
                            if hasattr(strategy, "_mark_executed_T") and t_val is not None and exec_date is not None:
                                try:
                                    strategy._mark_executed_T(t_val, exec_date)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    else:
                        try:
                            strategy.record_trade({"symbol": symbol, "qty": qty, "price": price, "amount": qty * price, "side": "sell", "order_id": res.get("order_id")})
                        except Exception:
                            pass
                        # 쿼터 모드 매도 처리: MOC 체결 가격을 시도 추출하고 재진입 금액에 반영
                        try:
                            if intent.get("quota_mode"):
                                # 실행가격/수량 추출(다양한 포맷 지원)
                                try:
                                    exec_price, exec_qty = self._extract_exec_price_and_qty(res if isinstance(res, dict) else {"data": res})
                                except Exception:
                                    exec_price, exec_qty = (None, None)

                                # fallback to intent.price if available
                                if exec_price is None:
                                    try:
                                        exec_price = float(intent.get("price")) if intent.get("price") is not None else None
                                    except Exception:
                                        exec_price = None

                                # proceeds 계산 및 quota_reentry_amount에 반영
                                if exec_price is not None:
                                    try:
                                        proceeds = float(exec_price) * float(qty)
                                        strategy.state["quota_reentry_amount"] = float(strategy.state.get("quota_reentry_amount", 0.0)) + proceeds
                                    except Exception:
                                        pass

                                # MOC 체결인 경우 -10% 이하 체결 시 쿼터 모드 해제
                                ord_type = (intent.get("order_type") or "").upper()
                                ref_avg = None
                                try:
                                    ref_avg = float(intent.get("ref_avg_price")) if intent.get("ref_avg_price") is not None else None
                                except Exception:
                                    ref_avg = None
                                try:
                                    reason = (intent.get("reason") or "").lower()
                                    if "initial" in reason:
                                        strategy.state["quota_initial_moc_done"] = True
                                    if "final" in reason:
                                        strategy.state["quota_final_moc_done"] = True
                                except Exception:
                                    pass

                                if ord_type == "MOC" and exec_price is not None and ref_avg is not None:
                                    try:
                                        if float(exec_price) <= float(ref_avg) * 0.90:
                                            strategy.state["quota_stop_loss_mode"] = False
                                            strategy.state["quota_cycle_count"] = 0
                                            # quota_reentry_amount는 이미 선입금/체결금으로 채워졌음
                                    except Exception:
                                        pass
                                # 판매가 처리됨을 표시
                                processed_sell = True
                        except Exception:
                            pass

            except Exception as e:
                self.logger.error(f"execute_intents: failed to process intent {intent}: {e}")
                results.append({"intent": intent, "result": {"success": False, "message": str(e)}})

        # 배치 처리 후: 판매가 처리되었고 전략 상태에 쿼터 진입 대기 플래그가 있으면
        # 다음 매수 턴에서 쿼터 모드를 활성화하도록 표시합니다.
        try:
            if processed_sell and strategy is not None:
                if strategy.state.get("quota_enter_pending"):
                    strategy.state["quota_activate_on_next_buy"] = True
                    # 진입 대기 플래그는 제거
                    strategy.state.pop("quota_enter_pending", None)
        except Exception:
            pass


        return results
