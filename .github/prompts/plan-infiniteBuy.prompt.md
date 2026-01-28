## Plan: 무한매수법 추가

TL;DR: `InfiniteBuy` 전략을 버전화하여 추가합니다(기본 버전 `v2.2`). 기본 통화는 USD, `splits` 기본값은 40, T 반올림 규칙은 소수점 둘째 자리 올림(`ceil(value*100)/100`)으로 고정해 백테스트·라이브 연동과 테스트를 준비합니다.

### Steps
1. 새 전략 파일 생성: [trading_bot/strategies/infinite_buy.py](trading_bot/strategies/infinite_buy.py) — `InfiniteBuy` 클래스, 생성자 인자 `version='v2.2'`, `base_currency='USD'`, `splits=40`.  
2. 버전 구현 분리: [trading_bot/strategies/infinite_buy/v2_2.py](trading_bot/strategies/infinite_buy/v2_2.py) 및 [trading_bot/strategies/infinite_buy/v3_0.py](trading_bot/strategies/infinite_buy/v3_0.py) 생성(버전별 `compute_T`, `compute_star_percent`, `quota` 규칙).  
3. 팩토리 및 등록: [trading_bot/strategies/infinite_buy/factory.py](trading_bot/strategies/infinite_buy/factory.py) 추가 후 [trading_bot/main.py](trading_bot/main.py) 또는 전략 로더에 `create_infinite_buy` 호출로 등록(기본 `enabled=False`).  
4. 백테스트·브로커 연동: [trading_bot/backtest](trading_bot/backtest) 엔진에서 전략 반환 `investment_amount`/주문 의도 우선 반영하고 전략 상태(`cum_buy_amt`) 보존 허용.  
5. 테스트·문서 추가: [trading_bot/tests/test_infinite_buy.py](trading_bot/tests/test_infinite_buy.py) (T 계산, `ceil2`, splits=40, v2.2/v3.0 케이스), [trading_bot/docs/INFINITE_BUY.md](trading_bot/docs/INFINITE_BUY.md) 작성.

### Further Considerations
1. 환율: 계좌가 원화인 경우 USD 기반 주문액을 원화로 환산하는 설정·검증 필요.  
2. 버전 파라미터화: `version`으로 내부 파라미터(분할수, 목표수익률, star% 수식)를 선택하도록 설계.  
3. 권장 검증: 백테스트에서 `splits` 민감도, 수수료·슬리피지 영향 확인.  

진행 전 확인사항: 계속 진행해도 될까요? (특히 `enabled=False` 기본 배포, 백테스트 엔진 소폭 수정 허용 여부)

진행 완료: 계획 파일과 전략 템플릿(베이스·v2.2·v3.0·팩토리) 및 테스트 스켈레톤을 생성했습니다.

생성된 파일(요약)

plan-infiniteBuy.prompt.md
__init__.py
base.py
v2_2.py
v3_0.py
factory.py
test_infinite_buy.py
다음으로 할 일 제안 (선택)

백테스트 엔진과 주문 수량/금액 연동 코드를 수정해 전략의 investment_amount 제안을 반영합니다.
decide_buy/decide_sell 로직을 v2.2 규칙에 맞게 상세 구현하고 통합 테스트 실행합니다.
원하시면 다음 단계 중 무엇을 먼저 만들지 알려주세요.
