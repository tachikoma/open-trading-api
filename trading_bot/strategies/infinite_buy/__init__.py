"""InfiniteBuy 전략 팩토리 노출용 모듈

이 모듈은 외부에서 버전별 InfiniteBuy 전략 인스턴스를 생성하기 위한
팩토리 함수를 노출합니다. 사용 예:

```python
from trading_bot.strategies.infinite_buy import create_infinite_buy

cfg = {"version": "v2.2", "total_amount": 400.0}
strat = create_infinite_buy(cfg)
```
"""

from .factory import create_infinite_buy

__all__ = ["create_infinite_buy"]
