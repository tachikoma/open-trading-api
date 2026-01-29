from typing import Any, Dict
from .v2_2 import InfiniteBuyV2_2
from .v3_0 import InfiniteBuyV3_0


def create_infinite_buy(config: Dict[str, Any], broker: Any = None) -> Any:
    """`config` 딕셔너리를 사용해 버전별 InfiniteBuy 전략 인스턴스를 생성합니다.

    기대되는 `config` 키:
    - `version`: 예: "v2.2" (기본값)
    - 그 외 전략에서 참조하는 파라미터들(ex: `total_amount`, `one_shot_amount`, `splits` 등)

    사용법 예:
    ```python
    cfg = {"version": "v2.2", "total_amount": 400.0}
    strat = create_infinite_buy(cfg)
    ```
    """
    version = str(config.get("version", "v2.2"))
    if version == "v2.2":
        return InfiniteBuyV2_2(config, broker)
    if version == "v3.0":
        return InfiniteBuyV3_0(config, broker)
    raise ValueError(f"지원되지 않는 InfiniteBuy 버전: {version}")
