#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Token Refresh Sample

샘플: API 호출 중 토큰 만료 응답(EGW00123)을 감지하면 로컬 토큰 파일을 삭제하고
`kis_auth.auth()`로 토큰을 재발급한 뒤 호출을 재시도합니다.

위치: trading_bot/examples/token_refresh.py

실행:
  cd trading_bot
  uv run examples/token_refresh.py

주의: 프로젝트의 `kis_devlp.yaml`(~/KIS/config/)이 올바르게 설정되어 있어야 합니다.
"""

import sys
import os
import logging
import time
import json

sys.path.extend(['..', '.'])

# 기존 kis_auth 모듈 활용
import kis_auth as ka

# examples_llm helper (protected API 호출 예시)
from examples_llm.domestic_stock.inquire_price.inquire_price import inquire_price

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def remove_local_token_if_exists():
    """로컬에 저장된 토큰 파일을 삭제하여 강제 재발급을 유도합니다."""
    try:
        token_path = ka.token_tmp
    except Exception:
        token_path = None

    if token_path and os.path.exists(token_path):
        try:
            os.remove(token_path)
            logger.info(f"로컬 토큰 파일 삭제: {token_path}")
        except Exception as e:
            logger.warning(f"로컬 토큰 파일 삭제 실패: {e}")


def call_protected_api_with_retry(env_dv: str = "demo", market: str = "J", symbol: str = "005930"):
    """토큰 만료를 감지하면 재발급 후 재시도하는 샘플 호출 함수.

    Args:
        env_dv: 'real' 또는 'demo' (이 샘플은 demo/vps 권장)
        market: 시장 구분 코드 (예: 'J')
        symbol: 종목코드 (예: '005930')
    Returns:
        API 응답 (pandas.DataFrame 또는 None)
    """

    # 1) 인증 (모의투자 예시)
    try:
        ka.auth(svr="vps", product="01")  # 모의투자
        # ka.auth(svr="prod", product="01")  # 실전투자 시 주석 해제
    except Exception as e:
        logger.error(f"초기 인증 실패: {e}")
        return None

    # 유량 제어
    ka.smart_sleep()

    # 2) 최초 호출
    try:
        logger.info("API 호출 시도: inquire_price")
        df = inquire_price(env_dv, market, symbol)

        # 빈 데이터프레임 반환 시, 내부에서 오류가 발생했을 가능성
        if getattr(df, "empty", False) is True:
            logger.warning("API가 빈 결과를 반환했습니다. 토큰 만료 가능성 확인 후 재시도합니다.")
            # 로컬 토큰 파일 삭제 -> 재발급 유도
            remove_local_token_if_exists()
            ka.auth(svr="vps", product="01")
            ka.smart_sleep()
            logger.info("재인증 후 재요청 수행")
            df = inquire_price(env_dv, market, symbol)

        return df

    except Exception as e:
        # 응답 메시지에 토큰 만료 코드(EGW00123)가 포함된 경우 재발급 처리
        msg = str(e)
        logger.error(f"API 호출 오류: {msg}")

        if "EGW00123" in msg or "토큰" in msg or "expired" in msg.lower():
            logger.info("토큰 만료로 보이는 오류 감지. 로컬 토큰 삭제 후 재발급 시도합니다.")
            remove_local_token_if_exists()
            try:
                ka.auth(svr="vps", product="01")
                ka.smart_sleep()
                logger.info("재발급 성공. API 재시도합니다.")
                df = inquire_price(env_dv, market, symbol)
                return df
            except Exception as e2:
                logger.error(f"재발급 또는 재요청 실패: {e2}")
                return None
        else:
            return None


def websocket_function():
    # 필요시 WebSocket 인증/구독 예시
    ka.auth_ws()
    kws = ka.KISWebSocket(api_url="/tryitout")

    # 주의: 1개 appkey당 최대 41건까지만 등록 가능
    pass


if __name__ == "__main__":
    try:
        result = call_protected_api_with_retry(env_dv="demo", market="J", symbol="005930")
        if result is None:
            print("결과를 가져올 수 없습니다.")
        else:
            # pandas.DataFrame 출력을 JSON으로 변환하여 보기 좋게 출력
            try:
                # pandas -> dict 가능 시 JSON 출력
                print(json.dumps(result.to_dict(orient="records"), indent=2, ensure_ascii=False))
            except Exception:
                print(str(result))
    except Exception as e:
        logger.error(f"실행 오류: {e}")
