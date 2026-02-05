from .base import InfiniteBuyBase
import math
from typing import Any, Dict, List
from trading_bot.utils.format import format_price


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
        # 최초 쿼터 진입 시 1/4 MOC 수행 플래그
        self.state.setdefault("quota_initial_moc_done", False)

    def compute_T(self, cum_buy_amt: float, symbol: str = None) -> float:
        # 누적 매수금액을 기준으로 T를 계산하고 소수점 둘째 자리에서 올림
        cfg = self.cfg_for(symbol)
        one_shot = float(cfg.get("one_shot_amount", 1000.0))
        T = (cum_buy_amt) / one_shot if one_shot else 0.0
        return math.ceil(T * 100) / 100.0

    def compute_star_percent(self, T: float, symbol: str) -> float:
        # 분할수(splits)를 고려한 별퍼센트 계산
        # 공식: 별퍼센트 = 10 - (T/2 * 40 / splits)
        cfg = self.cfg_for(symbol)
        try:
            splits = float(cfg.get("splits", 40))
            if splits <= 0:
                splits = 40.0
        except Exception:
            splits = 40.0

        raw = 10.0 - (T / 2.0) * (40.0 / splits)
        return max(0.0, float(raw))

    def decide_buy(self, date, quote: Dict) -> List[Dict[str, Any]]:
        # v2.2 매수 의도 생성 로직 (심볼별 total_amount, splits 기준)
        # 1) 심볼/가격 먼저 추출
        self.logger.debug("decide_buy: entry date=%s quote=%s state={quota_stop_loss_mode:%s, quota_cycle_count:%s, quota_enter_pending:%s}",
                          date, quote,
                          self.state.get("quota_stop_loss_mode"),
                          self.state.get("quota_cycle_count"),
                          self.state.get("quota_enter_pending"))
        if bool(self.state.get("quota_activate_on_next_buy", False)):
            self.state["quota_stop_loss_mode"] = True
            self.state["quota_activate_on_next_buy"] = False
            # do not place any buy orders on this turn (entry-only turn)
            self.logger.info("decide_buy: activate_quota_mode -> no_orders state={quota_stop_loss_mode:%s}",
                             self.state.get("quota_stop_loss_mode"))
            return []

        if not isinstance(quote, dict):
            self.logger.warning("decide_buy: invalid_quote_type type=%s", type(quote))
            return []
        price = float(quote.get("price") or 0.0)
        symbol = quote.get("symbol")
        if symbol is None or price <= 0:
            self.logger.warning("decide_buy: invalid_symbol_or_price symbol=%s price=%s", symbol, price)
            return []

        # 2) 심볼별 설정 병합
        cfg = self.cfg_for(symbol)
        try:
            total_amount = float(cfg.get("total_amount", 0.0))
        except Exception:
            total_amount = 0.0
        try:
            splits_cfg = int(cfg.get("splits", 40))
        except Exception:
            splits_cfg = 40

        # per-symbol 규칙 검증: total_amount와 splits는 반드시 필요
        if total_amount <= 0 or splits_cfg <= 0:
            # 설정이 없으면 실행하지 않음
            self.logger.warning(f"{symbol}: total_amount 또는 splits 설정이 유효하지 않습니다. total_amount={total_amount}, splits={splits_cfg}")
            return []

        cum_buy = float(self.get_cum_buy(symbol))
        # 분할당 1회 금액: total_amount / splits
        per_split = float(total_amount) / float(splits_cfg)
        amount = self.ceil2(per_split)

        # T 및 목표 퍼센트 계산
        T = self.compute_T(cum_buy)
        star_pct = self.compute_star_percent(T, symbol)
        target_star = price * (1.0 + float(star_pct) / 100.0)
        self.logger.debug("decide_buy: metrics symbol=%s price=%s cum_buy=%s T=%s star_pct=%s target_star=%s",
                  symbol, format_price(price, "USD"), cum_buy, T, star_pct, format_price(target_star, "USD"))

        # 모든 매수 주문은 LOC 타입으로 처리
        order_type = "LOC"

        # 실제 주문 가능한 정수 수량
        qty_float = amount / price
        qty_int = int(math.floor(qty_float))

        # 최소 2주 이상 가능해야 분할 매수 규칙 적용
        if qty_int < 2:
            # 소수 수량(또는 1주 미만)인 경우 fractional intent로 반환
            self.logger.info("decide_buy: fractional_only symbol=%s amount=%s qty_float=%s", symbol, amount, qty_float)
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
        splits_cfg = int(cfg.get("splits", 40))

        intents: List[Dict[str, Any]] = []
        # 쿼터 손절 모드 재진입 처리
        if bool(self.state.get("quota_stop_loss_mode", False)):
            # quota_cycle_count: 이미 수행된 재진입 횟수
            cycle_done = int(self.state.get("quota_cycle_count", 0))
            # quota_reentry_amount: 재진입에 사용할 총금액
            total_reentry = float(self.state.get("quota_reentry_amount", 0.0))
            # 이미 10회 수행했으면 추가 매수는 생성하지 않음
            if cycle_done >= 10 or total_reentry <= 0:
                self.logger.info("decide_buy: quota_mode_no_orders symbol=%s cycle_done=%s total_reentry=%s",
                                 symbol, cycle_done, total_reentry)
                return []

            per_round = total_reentry / 10.0
            amount_round = self.ceil2(per_round)
            # -10% LOC 매수 가격
            buy_price = round(float(price * 0.90), 2)
            qty_float_r = amount_round / (buy_price if buy_price > 0 else price)
            qty_int_r = int(math.floor(qty_float_r))

            # 의도 생성: fractional 또는 정수
            if qty_int_r < 1:
                self.logger.info("decide_buy: quota_reentry_fractional symbol=%s round=%s amount=%s qty_float=%s price=%s",
                                 symbol, cycle_done + 1, amount_round, qty_float_r, buy_price)
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
                self.logger.info("decide_buy: quota_reentry_integer symbol=%s round=%s amount=%s qty_int=%s price=%s",
                                 symbol, cycle_done + 1, amount_round, qty_int_r, buy_price)
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
            self.logger.info("decide_buy: pre_split symbol=%s T=%s splits_half=%s qty_int=%s",
                             symbol, T, splits_half, qty_int)
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
            self.logger.info("decide_buy: post_split symbol=%s T=%s splits_half=%s qty_int=%s star_pct=%s",
                             symbol, T, splits_half, qty_int, star_pct)
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

        # 원금 소진 대응 플래그 (심볼별 total_amount 기준)
        cum_buy_state = float(self.get_cum_buy(symbol))
        if total_amount > 0 and (cum_buy_state + (price * qty_int)) >= total_amount:
            # 마지막 분할 매수(한 회차의 매수)가 끝난 뒤 쿼터 손절 모드로 진입하도록
            # 즉시 `quota_stop_loss_mode`를 활성화하지 않고 다음 턴(매도 실행 시)에 진입하도록 표시
            self.state["quota_enter_pending"] = True
            self.state["quota_cycle_count"] = 0
            # 남은 자금(원금) - 실제 계산은 더 정밀해야 하지만 우선 잔여 원금으로 설정
            remaining = max(0.0, total_amount - cum_buy_state)
            self.state["quota_reentry_amount"] = remaining
            self.state["quota_final_moc_done"] = False
            # 최초 진입 시 초기 MOC가 아직 수행되지 않음
            self.state["quota_initial_moc_done"] = False
            for it in intents:
                # 표시는 남기되 즉시 재진입 매수로 처리되면 안되므로 'quota_pending' 메타만 추가
                it["quota_pending"] = True
            self.logger.info("decide_buy: quota_pending_set symbol=%s cum_buy_state=%s total_amount=%s remaining=%s",
                             symbol, cum_buy_state, total_amount, remaining)
        self.logger.info("decide_buy: exit symbol=%s intents=%s", symbol, len(intents))
        return intents

    def decide_sell(self, position:Dict, market_price) -> List[Dict[str, Any]]:
        # v2.2 매도 규칙 (일별 자동 매도 포함)
        # - 1/4 수량: 평단가 대비 별퍼센트에 LOC 매도
        # - 3/4 수량: 평단가 대비 +10%에 지정가 매도
        # position에는 최소한 `symbol`, `quantity`, `avg_price`가 포함되어야 합니다.
        self.logger.debug("decide_sell: entry position=%s market_price=%s state={quota_stop_loss_mode:%s, quota_cycle_count:%s}",
                          position, market_price,
                          self.state.get("quota_stop_loss_mode"),
                          self.state.get("quota_cycle_count"))
        if not isinstance(position, dict):
            self.logger.warning("decide_sell: invalid_position_type type=%s", type(position))
            return []
        qty = float(position.get("quantity", 0.0))
        avg_price = float(position.get("avg_price", position.get("price", 0.0)))
        symbol = position.get("symbol")
        cum_buy = float(position.get("cum_buy_amt", self.get_cum_buy(symbol)))
        if qty <= 0 or avg_price <= 0:
            self.logger.warning("decide_sell: invalid_qty_or_price symbol=%s qty=%s avg_price=%s", symbol, qty, avg_price)
            return []

        T = self.compute_T(cum_buy)
        star_pct = self.compute_star_percent(T, symbol)

        target_star = avg_price * (1.0 + float(star_pct) / 100.0)
        target_plus10 = avg_price * 1.10

        sell_qty1 = qty * 0.25
        sell_qty2 = qty - sell_qty1
        self.logger.debug("decide_sell: metrics symbol=%s qty=%s avg_price=%s T=%s star_pct=%s target_star=%s target_plus10=%s",
                  symbol, qty, avg_price, T, star_pct, round(float(target_star), 2), round(float(target_plus10), 2))

        intents: List[Dict[str, Any]] = []
        # 쿼터 손절 모드 처리
        if bool(self.state.get("quota_stop_loss_mode", False)):
            cycle_done = int(self.state.get("quota_cycle_count", 0))
            initial_moc_done = bool(self.state.get("quota_initial_moc_done", False))
            # 최초 진입 시에는 우선 누적수량의 1/4을 MOC로 즉시 매도하고 종료
            if not initial_moc_done and sell_qty1 > 0:
                self.logger.info("decide_sell: quota_initial_moc symbol=%s qty=%s", symbol, sell_qty1)
                intents.append({
                    "type": "sell",
                    "symbol": symbol,
                    "price": None,
                    "quantity": sell_qty1,
                    "order_type": "MOC",
                    "reason": "quota_initial_moc_sell",
                    "ref_avg_price": avg_price,
                    "quota_mode": True,
                })
                # mark initial MOC done so it won't repeat
                self.state["quota_initial_moc_done"] = True
                return intents
            # 1~10회 재진입 중(또는 그 직후)에는 1/4을 -10% LOC로 손절, 나머지 +10% 지정가
            if cycle_done < 10:
                self.logger.info("decide_sell: quota_cycle_sell symbol=%s cycle=%s sell_qty1=%s sell_qty2=%s",
                                 symbol, cycle_done, sell_qty1, sell_qty2)
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
                    self.logger.info("decide_sell: quota_final_moc symbol=%s qty=%s", symbol, sell_qty1)
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
        self.logger.info("decide_sell: exit symbol=%s intents=%s", symbol, len(intents))
        return intents
