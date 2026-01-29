from .base import InfiniteBuyBase
import math
from typing import Any, Dict, List


class InfiniteBuyV2_2(InfiniteBuyBase):
    """InfiniteBuy 전략의 v2.2 구현.

        설명:
                - `compute_T(cum_buy_amt)`: 누적 매수금액을 `one_shot_amount`로 나누어 T를 계산하고
                    소수점 둘째 자리에서 올림합니다.
                - `compute_star_percent(T, symbol)`: T에 기반한 목표 `star%` 계산 (분할수(splits)를 반영한 규칙).
                - `decide_buy(date, quote)`: 매수 전용 의도 리스트를 반환합니다. 각 의도는 매수 주문 실행에
                    필요한 필드(`symbol`, `price`, `amount`, `quantity`, `order_type`, `market`, `exec_date` 등)를 포함하며,
                    전/후반전 규칙에 따라 절반/절반 구조 또는 단일 주문으로 분할되어 반환됩니다. 매수 의도에는
                    필요시 자동 매도 목표(`targets`) 또는 `pre_split`/`post_split` 메타가 포함될 수 있습니다.
                - `decide_sell(position, market_price)`: 매도 전용 의도 리스트를 반환합니다. 기본 규칙은
                    보유수량의 1/4을 평단 대비 `star%` 위치에 `LOC`로 매도하고, 나머지 3/4은 평단 대비 +10%에
                    `LIMIT`(지정가)으로 매도하는 형태입니다. 반환된 매도 의도는 `type: 'sell'`, `price`, `quantity`,
                    `order_type` 등의 필드를 포함합니다.
    """

    def __init__(self, config: Dict[str, Any], broker: Any = None):
        super().__init__(config, broker)
        # 쿼터 손절 모드 상태 초기값
        # - quota_stop_loss_mode: 현재 쿼터 손절 모드 활성 여부
        # - quota_cycle_count: 재진입(쿼터) 시도 횟수 (0..10)
        # - quota_reentry_amount: 쿼터 손절 후 재진입에 사용할 총금액
        # - quota_final_moc_done: 10회 재진입 이후 MOC(시장가)로 최종 1/4 매도 실행 여부
        self.state.setdefault("quota_stop_loss_mode", False)
        self.state.setdefault("quota_cycle_count", 0)
        self.state.setdefault("quota_reentry_amount", 0.0)
        self.state.setdefault("quota_final_moc_done", False)

    def compute_T(self, cum_buy_amt: float) -> float:
        # 누적 매수금액을 기준으로 T를 계산하고 소수점 둘째 자리에서 올림
        one_shot = float(self.config.get("one_shot_amount", 1000.0))
        T = (cum_buy_amt) / one_shot if one_shot else 0.0
        return math.ceil(T * 100) / 100.0

    def compute_star_percent(self, T: float, symbol: str) -> float:
        # 분할수(splits)를 고려한 별퍼센트 계산
        # 공식: 별퍼센트 = 10 - (T/2 * 40 / splits)
        try:
            splits = float(self.config.get("splits", 40))
            if splits <= 0:
                splits = 40.0
        except Exception:
            splits = 40.0

        raw = 10.0 - (T / 2.0) * (40.0 / splits)
        return max(0.0, float(raw))

    def decide_buy(self, date, quote: Dict) -> List[Dict[str, Any]]:
        # v2.2 매수 의도 생성 로직 (정수 수량 분할 처리):
        # - 설정값 `total_amount`를 `splits`로 나눈 분할당 금액으로 주문 크기 결정
        # - 실제 주문 가능한 정수 수량(qty_int)을 기준으로 분할
        # - 전반전(T < splits/2): 수량이 1이면 단일 주문, >=2이면 floor/ceil로 분할하여
        #   첫 절반은 LOC(현재가), 두번째 절반은 목표 star% 정보 포함
        # - 후반전(T >= splits/2): 전체 수량을 star% 위치에 LOC 단일 주문으로 시도
        total_amount = float(self.config.get("total_amount", 0.0))
        if not isinstance(quote, dict):
            return []
        price = float(quote.get("price") or 0.0)
        symbol = quote.get("symbol")
        if total_amount <= 0 or price <= 0:
            return []

        cum_buy = float(self.state.get("cum_buy_amt", 0.0))
        per_split = self.quota(total_amount)
        amount = self.ceil2(per_split)

        # T 및 목표 퍼센트 계산
        T = self.compute_T(cum_buy)
        star_pct = self.compute_star_percent(T, symbol)
        target_star = price * (1.0 + float(star_pct) / 100.0)

        # 모든 매수 주문은 LOC 타입으로 처리
        order_type = "LOC"

        # 실제 주문 가능한 정수 수량
        qty_float = amount / price
        qty_int = int(math.floor(qty_float))

        # 최소 2주 이상 가능해야 분할 매수 규칙 적용
        if qty_int < 2:
            # 소수 수량(또는 1주 미만)인 경우 fractional intent로 반환
            intents = [{
                "type": "buy",
                "symbol": symbol,
                "price": price,
                "amount": amount,
                "quantity": qty_float,
                "T": T,
                "order_type": order_type,
                "market": self.config.get("market", "overseas"),
                "ovrs_excg_cd": self.config.get("ovrs_excg_cd", None),
                "exec_date": date,
                "note": "insufficient_qty_fractional_qty",
            }]
            return intents

        # splits 설정
        splits_cfg = int(self.config.get("splits", 40))

        intents: List[Dict[str, Any]] = []
        # 쿼터 손절 모드 재진입 처리
        if bool(self.state.get("quota_stop_loss_mode", False)):
            # quota_cycle_count: 이미 수행된 재진입 횟수
            cycle_done = int(self.state.get("quota_cycle_count", 0))
            # quota_reentry_amount: 재진입에 사용할 총금액
            total_reentry = float(self.state.get("quota_reentry_amount", 0.0))
            # 이미 10회 수행했으면 추가 매수는 생성하지 않음
            if cycle_done >= 10 or total_reentry <= 0:
                return []

            per_round = total_reentry / 10.0
            amount_round = self.ceil2(per_round)
            # -10% LOC 매수 가격
            buy_price = round(float(price * 0.90), 2)
            qty_float_r = amount_round / (buy_price if buy_price > 0 else price)
            qty_int_r = int(math.floor(qty_float_r))

            # 의도 생성: fractional 또는 정수
            if qty_int_r < 1:
                intents = [{
                    "type": "buy",
                    "symbol": symbol,
                    "price": buy_price,
                    "amount": amount_round,
                    "quantity": qty_float_r,
                    "T": T,
                    "order_type": "LOC",
                    "market": self.config.get("market", "overseas"),
                    "ovrs_excg_cd": self.config.get("ovrs_excg_cd", None),
                    "exec_date": date,
                    "note": f"quota_reentry_fractional_round_{cycle_done+1}",
                    "quota_mode": True,
                    "quota_cycle": cycle_done + 1,
                    "quota_per_round": amount_round,
                }]
            else:
                intents = [{
                    "type": "buy",
                    "symbol": symbol,
                    "price": buy_price,
                    "amount": self.ceil2(buy_price * qty_int_r),
                    "quantity": qty_int_r,
                    "T": T,
                    "order_type": "LOC",
                    "market": self.config.get("market", "overseas"),
                    "ovrs_excg_cd": self.config.get("ovrs_excg_cd", None),
                    "exec_date": date,
                    "note": f"quota_reentry_round_{cycle_done+1}",
                    "quota_mode": True,
                    "quota_cycle": cycle_done + 1,
                    "quota_per_round": amount_round,
                }]

            return intents

        # 전반전/후반전 분기: 전체 분할수(splits)를 양분하여 전반/후반 기준 사용
        splits_half = float(splits_cfg) / 2.0
        if T < splits_half:
            # 전반전: 정수 수량을 floor/ceil로 분할하여 두 번의 매수 의도 생성
            first_qty = qty_int // 2
            second_qty = qty_int - first_qty
            intents.append({
                "type": "buy",
                "symbol": symbol,
                "price": price,
                "amount": self.ceil2(price * first_qty),
                "quantity": first_qty,
                "T": T,
                "order_type": "LOC",
                "market": self.config.get("market", "overseas"),
                "ovrs_excg_cd": self.config.get("ovrs_excg_cd", None),
                "exec_date": date,
                "note": "pre_split_first_qty_loc",
            })
            intents.append({
                "type": "buy",
                "symbol": symbol,
                "price": price,
                "amount": self.ceil2(price * second_qty),
                "quantity": second_qty,
                "T": T,
                "star_percent": star_pct,
                "order_type": order_type,
                "market": self.config.get("market", "overseas"),
                "ovrs_excg_cd": self.config.get("ovrs_excg_cd", None),
                "exec_date": date,
                "targets": [
                    {"fraction": 1.0, "price": round(float(target_star), 2)},
                ],
            })
        else:
            # 후반전: 전체 qty_int 수량을 star% 위치의 LOC 단일 주문으로 시도
            buy_at_star = (price * (1.0 + float(star_pct) / 100.0)) - 0.01
            intents.append({
                "type": "buy",
                "symbol": symbol,
                "price": round(float(buy_at_star), 2),
                "amount": self.ceil2(price * qty_int),
                "quantity": qty_int,
                "T": T,
                "order_type": "LOC",
                "market": self.config.get("market", "overseas"),
                "ovrs_excg_cd": self.config.get("ovrs_excg_cd", None),
                "exec_date": date,
                "note": "post_split_full_loc_at_star_minus_0.01",
                "targets": [
                    {"fraction": 1.0, "price": round(float(target_star), 2)},
                ],
            })

        # 원금 소진 대응 플래그
        total_amount_cfg = float(self.config.get("total_amount", 0.0))
        cum_buy_state = float(self.state.get("cum_buy_amt", 0.0))
        if total_amount_cfg > 0 and (cum_buy_state + (price * qty_int)) >= total_amount_cfg:
            # 진입 시 상태 초기화: 재진입 횟수 초기화 및 남은 원금 기록
            self.state["quota_stop_loss_mode"] = True
            self.state["quota_cycle_count"] = 0
            # 남은 자금(원금) - 실제 계산은 더 정밀해야 하지만 우선 잔여 원금으로 설정
            remaining = max(0.0, total_amount_cfg - cum_buy_state)
            self.state["quota_reentry_amount"] = remaining
            self.state["quota_final_moc_done"] = False
            for it in intents:
                it["quota_mode"] = True
                it["quota_cycle"] = 0

        return intents

    def decide_sell(self, position:Dict, market_price) -> List[Dict[str, Any]]:
        # v2.2 매도 규칙 (일별 자동 매도 포함)
        # - 1/4 수량: 평단가 대비 별퍼센트에 LOC 매도
        # - 3/4 수량: 평단가 대비 +10%에 지정가 매도
        # position에는 최소한 `symbol`, `quantity`, `avg_price`가 포함되어야 합니다.
        if not isinstance(position, dict):
            return []
        qty = float(position.get("quantity", 0.0))
        avg_price = float(position.get("avg_price", position.get("price", 0.0)))
        symbol = position.get("symbol")
        cum_buy = float(position.get("cum_buy_amt", self.state.get("cum_buy_amt", 0.0)))
        if qty <= 0 or avg_price <= 0:
            return []

        T = self.compute_T(cum_buy)
        star_pct = self.compute_star_percent(T, symbol)

        target_star = avg_price * (1.0 + float(star_pct) / 100.0)
        target_plus10 = avg_price * 1.10

        sell_qty1 = qty * 0.25
        sell_qty2 = qty - sell_qty1

        intents: List[Dict[str, Any]] = []

        # 쿼터 손절 모드 처리
        if bool(self.state.get("quota_stop_loss_mode", False)):
            cycle_done = int(self.state.get("quota_cycle_count", 0))
            # 1~10회 재진입 중(또는 그 직후)에는 1/4을 -10% LOC로 손절, 나머지 +10% 지정가
            if cycle_done < 10:
                if sell_qty1 > 0:
                    intents.append({
                        "type": "sell",
                        "symbol": symbol,
                        "price": round(float(avg_price * 0.90), 2),
                        "quantity": sell_qty1,
                        "order_type": "LOC",
                            "reason": f"quota_loc_sell_round_{cycle_done}",
                            "ref_avg_price": avg_price,
                        "quota_mode": True,
                        "quota_cycle": cycle_done,
                    })
                if sell_qty2 > 0:
                    intents.append({
                        "type": "sell",
                        "symbol": symbol,
                        "price": round(float(target_plus10), 2),
                        "quantity": sell_qty2,
                        "order_type": "LIMIT",
                            "reason": f"quota_limit_sell_round_{cycle_done}",
                            "ref_avg_price": avg_price,
                        "quota_mode": True,
                        "quota_cycle": cycle_done,
                    })
                return intents
            else:
                # 10회 재진입이 끝난 직후: 아직 final MOC를 수행하지 않았다면 1/4을 MOC로 즉시 매도
                final_done = bool(self.state.get("quota_final_moc_done", False))
                if not final_done and sell_qty1 > 0:
                    intents.append({
                        "type": "sell",
                        "symbol": symbol,
                        "price": None,
                        "quantity": sell_qty1,
                        "order_type": "MOC",
                        "reason": "quota_final_moc_sell",
                        "ref_avg_price": avg_price,
                        "quota_mode": True,
                    })
                    # 상태 업데이트: final MOC는 한 번만 수행
                    self.state["quota_final_moc_done"] = True
                    return intents

        # 기본(쿼터 모드가 아닌 경우) - 기존 동작 유지
        if sell_qty1 > 0:
            intents.append({
                "type": "sell",
                "symbol": symbol,
                "price": round(float(target_star), 2),
                "quantity": sell_qty1,
                "order_type": "LOC",
                "reason": "daily_loc_sell_at_star",
            })
        if sell_qty2 > 0:
            intents.append({
                "type": "sell",
                "symbol": symbol,
                "price": round(float(target_plus10), 2),
                "quantity": sell_qty2,
                "order_type": "LIMIT",
                "reason": "daily_limit_sell_at_plus10",
            })
        return intents
