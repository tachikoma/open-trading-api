#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration test for real `ka.auth()` call.

WARNING: This script will perform real network calls to KIS Open API.
Ensure the following before running:
  - ~/KIS/config/kis_devlp.yaml exists and contains valid app keys
  - You understand that network requests will be made

Usage (recommended):
  cd trading_bot
  # only auth (no API call)
  uv run examples/integration_test_kis_auth.py

  # auth + sample API call (set env var RUN_API=1)
  RUN_API=1 uv run examples/integration_test_kis_auth.py

Behavior:
  - Calls `ka.auth()` for the configured server (prod/vps based on env_mode)
  - Prints token file path, token read result, and TRENV values
  - If RUN_API=1, attempts a harmless sample API call (`inquire_price`)
"""

import sys
import os
import logging
import json

sys.path.extend(['..', '.'])

from trading_bot.broker import kis_broker as kb_mod
from trading_bot.broker.kis_broker import KISBroker

# access kis_auth through the kis_broker module to avoid direct import resolution issues
ka = kb_mod.ka

try:
    # prefer broker API for sample calls
    from trading_bot.broker.kis_broker import KISBroker
except Exception:
    KISBroker = None

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger('integration_test')


def check_config():
    cfg_path = os.path.join(os.path.expanduser('~'), 'KIS', 'config', 'kis_devlp.yaml')
    if not os.path.exists(cfg_path):
        logger.error(f"설정 파일 없음: {cfg_path}\n먼저 kis_devlp.yaml을 복사/설정하세요.")
        return False
    logger.info(f"설정 파일 확인: {cfg_path}")
    return True


def run_auth_and_report(svr='vps', product='01'):
    logger.info(f"Auth 호출 via KISBroker (svr={svr}, product={product})")

    # Instantiate broker which calls _init_auth() during init
    broker = KISBroker(env_mode='demo') if KISBroker is not None else None

    # 토큰 파일 및 TRENV 정보 출력
    token_path = getattr(ka, 'token_tmp', None)
    token_value = ka.read_token()
    trenv = ka.getTREnv()

    logger.info(f"token_tmp: {token_path}")
    logger.info(f"read_token(): {token_value}")
    try:
        logger.info(f"TRENV: app={trenv.my_app}, acct={trenv.my_acct}, prod={trenv.my_prod}, url={trenv.my_url}")
    except Exception:
        logger.info(f"TRENV: {trenv}")

    return broker


def optional_api_call(broker: KISBroker, env_mode='demo'):
    # 작은 호출: broker.get_current_price (주의: 실사용 요청이며 요금/제한이 있을 수 있음)
    if broker is None:
        logger.error('KISBroker 인스턴스가 없습니다. API 호출을 건너뜁니다.')
        return

    logger.info("샘플 API 호출(broker.get_current_price) 시작")
    try:
        df = broker.get_current_price('005930')
        # 출력 요약
        try:
            print(json.dumps(df.to_dict(orient='records'), indent=2, ensure_ascii=False))
        except Exception:
            logger.info(f"API 반환: {df}")
    except Exception as e:
        logger.error(f"샘플 API 호출 실패: {e}")


if __name__ == '__main__':
    if not check_config():
        sys.exit(1)

    # 실행할 서버: demo->vps, real->prod
    env_mode = os.environ.get('ENV_MODE', 'demo')
    svr = 'prod' if env_mode == 'real' else 'vps'

    try:
        broker = run_auth_and_report(svr=svr, product='01')
    except Exception as e:
        logger.error(f"ka.auth() 호출 중 예외 발생: {e}")
        sys.exit(2)

    # optional API call
    if os.environ.get('RUN_API') == '1' or os.environ.get('RUN_API') == 'true':
        optional_api_call(broker, env_mode=env_mode)
    else:
        logger.info('RUN_API not set -> API 호출 미실행')
