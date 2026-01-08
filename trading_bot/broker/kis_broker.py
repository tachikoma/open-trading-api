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

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "examples_user"))
sys.path.insert(0, str(PROJECT_ROOT / "examples_llm"))

# KIS 인증 및 함수들 import
import kis_auth as ka
from domestic_stock import domestic_stock_functions as dsf

# trading_bot 모듈 import (절대 경로)
from trading_bot.config import Config
from trading_bot.utils.logger import setup_logger


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

    def _call_with_retry(self, func, *args, max_retries: int = 3, delay_sec: float = 0.5, **kwargs):
        """공통 재시도 래퍼

        - API rate limit 응답(EGW00201 또는 '초당 거래건수' 메시지)을 감지하면
          `delay_sec` 만큼 대기 후 최대 `max_retries` 회 재시도합니다.
        - 마지막 시도에서 예외가 발생하면 예외를 재발생시킵니다.
        """
        for attempt in range(1, max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                msg = str(e)
                if "EGW00201" in msg or "초당 거래건수" in msg or "초당 거래건수를 초과" in msg:
                    self.logger.warning(f"API rate limit 응답 감지: {msg} (시도 {attempt}/{max_retries}). 재시도합니다.")
                    if attempt < max_retries:
                        time.sleep(delay_sec)
                        continue
                # 재시도 대상이 아니거나 마지막 시도인 경우 예외 재발생
                raise
    
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
                fid_input_iscd=symbol
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
                fid_org_adj_prc="0"  # 0:수정주가, 1:원주가
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
            # Use internal caller that inspects raw API response and raises only on rate-limit
            output1, output2 = self._call_with_retry(
                self._call_period_api,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                period=period
            )
            return output2  # output2에 일별 시세 데이터가 있음
        except Exception as e:
            self.logger.error(f"기간별 시세 조회 실패 ({symbol}): {e}")
            return None

    def _call_period_api(self, symbol: str, start_date: str, end_date: str, period: str = "D"):
        """
        내부: KIS API를 직접 호출하여 응답을 검사합니다.
        - rate-limit(EGW00201 등)인 경우 예외를 발생시켜 상위에서 재시도하도록 함
        - 그 외의 경우에는 빈 DataFrame을 반환하여 재시도하지 않습니다
        """
        api_url = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        tr_id = "FHKST03010100"

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": period,
            "FID_ORG_ADJ_PRC": "0",
        }

        # 직접 호출하여 APIResp를 확인
        res = ka._url_fetch(api_url, tr_id, "", params)

        try:
            if getattr(res, 'isOK', lambda: False)() is True:
                output1 = pd.DataFrame([res.getBody().output1])
                output2 = pd.DataFrame(res.getBody().output2)
                return output1, output2
            else:
                # 에러 메시지 추출
                try:
                    msg = res.getErrorMessage() or ""
                except Exception:
                    msg = str(res)

                # rate-limit인 경우 재시도하도록 예외 발생
                if "EGW00201" in msg or "초당 거래건수" in msg or "초당 거래건수를 초과" in msg:
                    raise Exception(f"API rate limit: {msg}")

                # 그 외는 빈 응답(데이터 없음)으로 간주
                return pd.DataFrame(), pd.DataFrame()
        except Exception:
            # 예외는 상위에서 처리(재시도 대상)
            raise

    def _normalize_df(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        내부: API 응답 DataFrame을 날짜 인덱스로 정규화합니다.
        """
        if df is None or df.empty:
            return None

        # 이미 DatetimeIndex라면 그대로 반환
        if isinstance(df.index, pd.DatetimeIndex):
            return df

        # 흔히 사용되는 날짜 컬럼명들 처리
        for col in ("stck_bsop_date", "trd_dd", "tdd_clse_dt", "date"):
            if col in df.columns:
                try:
                    df = df.copy()
                    df["_date_col_for_index"] = pd.to_datetime(df[col], format="%Y%m%d", errors="coerce")
                    df = df.set_index("_date_col_for_index")
                    df.index.name = None
                    return df
                except Exception:
                    continue

        # 인덱스를 DatetimeIndex로 변환 시도
        try:
            df = df.copy()
            df.index = pd.to_datetime(df.index)
            return df
        except Exception:
            return df

    def fetch_10y_daily(self, symbol: str = "005930", save_path: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        지정한 종목의 최근 10년치 일별 시세를 KIS API로 수집합니다.

        - 3개월 단위로 구간을 나누어 `get_period_price`를 호출합니다.
        - 결과를 병합하고 중복 제거 및 정렬을 수행합니다.
        """
        end = pd.Timestamp.today().normalize()
        start = end - pd.DateOffset(years=10)

        parts = []
        current = start
        while current <= end:
            chunk_end = min(current + pd.DateOffset(months=3) - pd.DateOffset(days=1), end)
            s = current.strftime("%Y%m%d")
            e = chunk_end.strftime("%Y%m%d")
            self.logger.info(f"Fetching {symbol} {s} ~ {e}")

            try:
                df = self.get_period_price(symbol, s, e, period="D")
            except Exception as ex:
                self.logger.error(f"구간 호출 실패: {s} ~ {e}: {ex}")
                df = None

            if df is not None and not df.empty:
                ndf = self._normalize_df(df)
                if ndf is not None and not ndf.empty:
                    parts.append(ndf)
            else:
                self.logger.warning(f"응답 없음 또는 빈 데이터: {s} ~ {e}")

            current = chunk_end + pd.DateOffset(days=1)
            time.sleep(0.2)

        if not parts:
            self.logger.error("데이터를 수집하지 못했습니다.")
            return None

        result = pd.concat(parts)
        try:
            result = result[~result.index.duplicated(keep='first')]
            result = result.sort_index()
        except Exception:
            result = result.drop_duplicates()

        if save_path:
            try:
                result.to_csv(save_path, index=True)
                self.logger.info(f"Saved historical data to {save_path}")
            except Exception as e:
                self.logger.warning(f"CSV 저장 실패: {e}")

        return result
    
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
                fid_input_iscd=symbol
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
                prcs_dvsn="00"
            )
            return df1, df2
        except Exception as e:
            self.logger.error(f"잔고 조회 실패: {e}")
            return None, None
    
    def get_buyable_cash(self) -> Optional[int]:
        """
        매수가능 현금 조회
        
        Returns:
            매수가능 금액
        """
        # 일부 API는 과도한 호출 시 오류를 반환하고 빈 DataFrame을 리턴합니다.
        # 따라서 빈 응답 또는 EGW00201(초당 거래건수 초과) 예외가 발생하면
        # 0.5초 대기 후 최대 3회까지 재시도합니다.
        max_retries = 3
        delay_sec = 0.5

        for attempt in range(1, max_retries + 1):
            try:
                df = dsf.inquire_psbl_order(
                    env_dv=self.env_mode,
                    cano=self.account,
                    acnt_prdt_cd=self.product_code,
                    pdno="005930",  # 임의의 종목코드 (삼성전자)
                    ord_unpr="0",
                    ord_dvsn="01",  # 시장가
                    cma_evlu_amt_icld_yn="N",
                    ovrs_icld_yn="N"
                )

                # 정상 응답이면 값 반환
                if df is not None and not df.empty:
                    return int(df.iloc[0]['ord_psbl_cash'])

                # 빈 DataFrame은 오류(예: rate limit)일 가능성이 있으므로 재시도
                self.logger.warning(f"매수가능 현금 조회 응답 비어있음 (시도 {attempt}/{max_retries}). 재시도합니다.")
            except Exception as e:
                msg = str(e)
                # EGW00201 또는 초당 거래건수 초과 메시지 감지 시 재시도
                if "EGW00201" in msg or "초당 거래건수를 초과" in msg:
                    self.logger.warning(f"API rate limit 응답 감지: {msg} (시도 {attempt}/{max_retries}). 재시도합니다.")
                else:
                    self.logger.error(f"매수가능 현금 조회 실패: {e}")
                    return 0

            # 재시도 간 대기 (마지막 시도라면 대기 없이 종료)
            if attempt < max_retries:
                time.sleep(delay_sec)

        # 모든 재시도 실패
        self.logger.error(f"매수가능 현금 조회 실패: 최대 재시도({max_retries}) 초과")
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
            return {"success": False, "message": "TRADING_ENABLED=False"}
        
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
                ord_unpr=str(price)
            )
            
            self.logger.info(f"매수 주문 완료: {symbol}, 수량: {qty}, 가격: {price}")
            return {"success": True, "data": result}
        except Exception as e:
            self.logger.error(f"매수 주문 실패 ({symbol}): {e}")
            return {"success": False, "message": str(e)}
    
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
            return {"success": False, "message": "TRADING_ENABLED=False"}
        
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
                ord_unpr=str(price)
            )
            
            self.logger.info(f"매도 주문 완료: {symbol}, 수량: {qty}, 가격: {price}")
            return {"success": True, "data": result}
        except Exception as e:
            self.logger.error(f"매도 주문 실패 ({symbol}): {e}")
            return {"success": False, "message": str(e)}
    
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
            return {"success": False, "message": "TRADING_ENABLED=False"}
        
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
                qty_all_ord_yn="Y" if qty == 0 else "N"
            )
            
            self.logger.info(f"주문 취소 완료: {order_no}")
            return {"success": True, "data": result}
        except Exception as e:
            self.logger.error(f"주문 취소 실패 ({order_no}): {e}")
            return {"success": False, "message": str(e)}


if __name__ == "__main__":
    # 간단한 수동 실행용 (uv run trading_bot/broker/kis_broker.py 권장)
    try:
        kb = KISBroker(env_mode="demo")
        df = kb.fetch_10y_daily(symbol="005930", save_path="samsung_10y_kis.csv")
        if df is not None:
            print(df.tail())
            print(f"Saved {len(df)} rows to samsung_10y_kis.csv")
        else:
            print("데이터 수집 실패")
    except Exception as e:
        print(f"실행 중 오류: {e}")
