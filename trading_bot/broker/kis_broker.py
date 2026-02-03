"""
KIS Broker 래퍼 클래스

기존 examples_user의 domestic_stock_functions를 래핑하여
전략 모듈에서 쉽게 사용할 수 있도록 추상화합니다.
"""
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
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
                    self.logger.debug("structured_response", extra={"json_payload": payload})
                except Exception:
                    # 로거가 extra를 지원하지 않을 경우 대비하여 대체 로그
                    try:
                        self.logger.debug(f"{context} - structured_response_payload: {str(payload)[:2000]}")
                    except Exception:
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
            # 알림 전송 (성공)
            try:
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
            # 알림 전송 (성공)
            try:
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
