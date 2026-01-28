"""Factory for creating versioned InfiniteBuy strategy instances."""
from typing import Any, Dict
from .v2_2 import InfiniteBuyV22
from .v3_0 import InfiniteBuyV30

def create_infinite_buy(config: Dict[str, Any], broker: Any = None):
    version = str(config.get("version", "v2.2"))
    if version == "v2.2":
        return InfiniteBuyV22(config, broker)
    if version == "v3.0":
        return InfiniteBuyV30(config, broker)
    raise ValueError(f"Unsupported InfiniteBuy version: {version}")
