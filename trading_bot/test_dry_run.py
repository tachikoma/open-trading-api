# 간단한 드라이런 스크립트
import sys
import types
from pathlib import Path

# 테스트용 스텁 모듈을 삽입하여 외부 의존성을 우회합니다.
# 0) pandas 스텁 (환경에 pandas 미설치 시 import 오류 방지)
import types as _types
pandas_stub = _types.ModuleType('pandas')
class _DF:
    pass
pandas_stub.DataFrame = _DF
pandas_stub.__version__ = '0.0'
sys.modules['pandas'] = pandas_stub

# 1) kis_auth 스텁
ka = types.SimpleNamespace()
ka.auth = lambda svr=None: None
class TREnv:
    def __init__(self):
        self.my_acct = "00000000"
        self.my_prod = "01"
ka.getTREnv = lambda: TREnv()
sys.modules['kis_auth'] = ka

# 2) domestic_stock.domestic_stock_functions 스텁
import types as _types
mod = _types.ModuleType('domestic_stock')
class DSF:
    @staticmethod
    def order_cash(**kwargs):
        print("[stub] order_cash called with:", kwargs)
        return {"order_no": "STUB12345", "status": "accepted"}
    @staticmethod
    def order_rvsecncl(**kwargs):
        print("[stub] order_rvsecncl called with:", kwargs)
        return {"cancel_no": "CANCEL123", "status": "accepted"}
mod.domestic_stock_functions = DSF
sys.modules['domestic_stock'] = mod

# 3) pytz 스텁 (logger에서 사용)
pytz_mod = _types.ModuleType('pytz')
import datetime as _dt
def _timezone(name):
    return _dt.timezone.utc
pytz_mod.timezone = _timezone
sys.modules['pytz'] = pytz_mod

# 프로젝트 루트를 sys.path에 추가 (trading_bot 내부 import 동작 보장)
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 실제 테스트: KISBroker 인스턴스 만들고 buy() 호출
from trading_bot.broker.kis_broker import KISBroker
from trading_bot.config import Config

# TRADING_ENABLED를 드라이런으로 확실히 설정
Config.TRADING_ENABLED = False

# monkeypatch _init_auth가 실제 인증을 하지 않도록 함
KISBroker._init_auth = lambda self: None

b = KISBroker(env_mode="demo")
# 수동으로 계좌/상품 코드 설정 (정상 동작 확인용)
b.account = "12345678"
b.product_code = "01"

print("Calling buy() in dry-run mode...")
res = b.buy(symbol="257720", qty=1, price=0, order_type="01")
print("Result:", res)
