# InfiniteBuy 전략

버전: v2.2 (기본)

개요
- InfiniteBuy는 큰 투자금액을 여러 회차로 분할하여 순차적으로 매수하는 전략입니다.
- 목표: 분할 매수로 평균 단가를 낮추고, 각 회차별 목표 수익률에 따라 일부를 익절합니다.

v2.2 핵심 규칙
- 기본 분할 수(`splits`): 설정값(기본 40)
- 한 번에 투입하는 기본 단위(`one_shot_amount`)로 계산된 금액을 사용
- T 계산: 누적 매수금액(`cum_buy_amt`)을 `one_shot_amount`로 나눈 뒤 소수점 둘째 자리에서 올림
	- 수식: `T = ceil((cum_buy_amt / one_shot_amount) * 100) / 100`
- `star_percent` 산출(간단 예시): `max(0, 10 - T/2)` — 실제 수식은 버전별로 다를 수 있음
- 매수 분할: v2.2에서는 매수 시점에 총 매수 물량을 두 개의 목표(25% @ star%, 75% @ +10%)로 나눠 지정

의사결정 함수(요약)
- `decide_buy(date, quote)` → 매수 의도(intent) 반환
	- intent 예시 필드:
		- `symbol`, `amount`(금액), `qty`(수량, 가능 시), `T`, `star_percent`
		- `targets`: list of {"pct": float, "price": float, "qty": int} — 분할 매도 목표
- `decide_sell(position, market_price)` → 청산/익절 의도 리스트 반환

Intent 스키마 (권장)
- `type`: "buy" 또는 "sell"
- `symbol`: 종목 코드
- `amount`: 주문 금액(현금 기준) — 선택적
- `qty`: 주문 수량(가능하면)
- `targets`: 매도 타깃 목록 (각 항목에 `pct`와 `price` 또는 `price_rel`)

브로커 연동
- `trading_bot/broker/kis_broker.py`의 `execute_intents(intents, strategy=None, simulate_only=False)`를 사용하면
	전략이 반환한 intent들을 실제 주문 또는 시뮬레이션으로 실행할 수 있습니다.
- `execute_intents`는 시뮬레이션 모드일 때 `strategy.state['cum_buy_amt']`을 갱신하고
	`strategy.record_trade(...)`를 호출하여 전략 내부 상태를 갱신합니다.

사용 예시
```python
from trading_bot.strategies.infinite_buy import create_infinite_buy
from trading_bot.broker.kis_broker import KISBroker

cfg = {"version": "v2.2", "one_shot_amount": 10.0, "splits": 40}
strat = create_infinite_buy(cfg)
broker = KISBroker(env_mode="demo")

intent = strat.decide_buy(date="2026-01-29", quote={"symbol":"005930","price":70000})
# 시뮬레이션 실행
broker.execute_intents([intent], strategy=strat, simulate_only=True)
```

테스트 가이드
- 전략 유닛 테스트는 `trading_bot/tests/test_infinite_buy.py`를 참고하세요.
- 변경 후 전체 테스트는 프로젝트 루트에서 다음으로 실행합니다:
```bash
cd open-trading-api
uv run pytest -q
```

추가 개선 아이디어
- `star_percent` 계산을 구성파일로 노출하여 튜닝 가능하게 만들기
- 부분 체결, 수수료, 슬리피지 모델을 도입한 시뮬레이션 강화
- `v3.0`에서 심볼별 또는 자산군별 다른 규칙을 지원

파일 참조
- 전략 코드: `trading_bot/strategies/infinite_buy/`
- 브로커 연동: `trading_bot/broker/kis_broker.py`


