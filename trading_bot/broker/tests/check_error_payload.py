from trading_bot.broker.kis_broker import KISBroker
import pandas as pd

# Avoid performing real auth during the unit smoke test
KISBroker._init_auth = lambda self: None

b = KISBroker(env_mode='demo')

# Simulate that the monkey-patch captured a payload
b._local.last_error_payload = {'simulated': True, 'msg': 'server error body (truncated)'}

# Call a function that returns an empty DataFrame via the retry wrapper
res = b._call_with_retry(lambda: pd.DataFrame(), max_retries=1, delay_sec=0)

print('is_dataframe:', isinstance(res, pd.DataFrame))
print('empty:', res.empty if isinstance(res, pd.DataFrame) else 'N/A')
print('has error_payload in attrs:', isinstance(res, pd.DataFrame) and ('error_payload' in getattr(res, 'attrs', {})))
print('payload:', res.attrs.get('error_payload') if isinstance(res, pd.DataFrame) else None)
