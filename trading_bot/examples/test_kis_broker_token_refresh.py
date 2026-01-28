#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit test script (manual) for KISBroker token refresh handling.
This script stubs `kis_auth` functions to avoid real network calls and
simulates an API function that fails first with a token-expired error
and succeeds on retry.
"""

import sys
import os
from types import SimpleNamespace

# Calculate repository root (three levels up from this file)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PROJECT_ROOT = REPO_ROOT
# Ensure examples_llm and examples_user are importable
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'examples_llm'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'examples_user'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'trading_bot'))

import kis_auth as ka
from trading_bot.broker.kis_broker import KISBroker

# Stub out ka.auth to be a no-op and provide getTREnv result
ka.auth = lambda svr=None, product=None: None
ka.getTREnv = lambda: SimpleNamespace(my_acct='00000000', my_prod='01')

# Ensure token_tmp exists so deletion path runs
tmp_token = os.path.join(os.path.expanduser('~'), 'KIS', 'config', 'KIS_TEST_TOKEN')
ka.token_tmp = tmp_token
os.makedirs(os.path.dirname(tmp_token), exist_ok=True)
with open(tmp_token, 'w') as f:
    f.write('token: dummy\nvalid-date: 2099-01-01 00:00:00')

# Create a function that raises token-expired on first call then returns success
call_state = {'count': 0}

def flaky_api(*args, **kwargs):
    call_state['count'] += 1
    if call_state['count'] == 1:
        raise Exception('Error: EGW00123 기간이 만료된 token 입니다.')
    return 'success'


def main():
    broker = KISBroker(env_mode='demo')

    try:
        res = broker._call_with_retry(flaky_api, max_retries=3, delay_sec=0.1)
        print('Result:', res)
    except Exception as e:
        print('Test failed with exception:', e)

    # Check token file removed
    exists = os.path.exists(tmp_token)
    print('Token file still exists after test?', exists)


if __name__ == '__main__':
    main()
