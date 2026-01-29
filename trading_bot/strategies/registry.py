"""
전략 레지스트리 모듈

`Config.STRATEGIES_ENABLED`에 정의된 전략 이름들을 팩토리로 생성해 인스턴스 리스트를 반환합니다.

허용 형식:
- 문자열: "ma_crossover" 또는 "infinite_buy"
- 딕셔너리: {"name": "infinite_buy", "config": { ... }}

각 팩토리는 `(config: dict, broker)` 시그니처를 따릅니다.
"""
from typing import Any, Callable, Dict, List
import logging

logger = logging.getLogger(__name__)

try:
    from trading_bot.strategies.infinite_buy.factory import create_infinite_buy
except Exception:
    create_infinite_buy = None

try:
    from trading_bot.strategies.ma_crossover import MovingAverageCrossover
except Exception:
    MovingAverageCrossover = None


def _create_ma_crossover(config: Dict[str, Any], broker: Any):
    """MA 교차 전략을 표준 팩토리 시그니처로 감싼 래퍼

    config 예: {"short_period": 5, "long_period": 20}
    """
    if MovingAverageCrossover is None:
        raise RuntimeError("MovingAverageCrossover 클래스가 로드되지 않았습니다")
    return MovingAverageCrossover(
        broker=broker,
        short_period=config.get("short_period"),
        long_period=config.get("long_period"),
    )


STRATEGY_FACTORIES: Dict[str, Callable[[Dict[str, Any], Any], Any]] = {
    "ma_crossover": _create_ma_crossover,
}

if create_infinite_buy is not None:
    STRATEGY_FACTORIES["infinite_buy"] = create_infinite_buy


def load_enabled_strategies(enabled: List[Any], broker: Any) -> List[Any]:
    """`enabled` 리스트를 읽어 전략 인스턴스 리스트를 반환합니다.

    - 각 항목은 문자열 또는 딕셔너리({"name": ..., "config": {...}})일 수 있습니다.
    - 존재하지 않는 전략은 경고를 남기고 스킵합니다.
    """
    strategies = []
    for entry in enabled:
        name = None
        cfg = {}
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, dict):
            name = entry.get("name")
            cfg = entry.get("config", {}) or {}
        else:
            logger.warning("알 수 없는 전략 항목 형식(스킵): %s", type(entry))
            continue

        if not name:
            logger.warning("전략 이름이 비어있음(스킵): %s", entry)
            continue

        factory = STRATEGY_FACTORIES.get(name)
        if factory is None:
            logger.warning("등록되지 않은 전략: %s (스킵)", name)
            continue

        try:
            inst = factory(cfg, broker)
            strategies.append(inst)
            logger.info("전략 생성: %s", name)
        except Exception as e:
            logger.error("전략 생성 실패: %s - %s", name, e, exc_info=True)

    return strategies
