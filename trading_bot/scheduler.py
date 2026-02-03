"""
간단한 스케줄러

지정된 시간 간격으로 전략을 실행합니다.
"""
import time
from datetime import datetime, time as dt_time, timedelta
from typing import List, Any, Dict
import pytz

try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False

from trading_bot.config import Config
from trading_bot.utils.logger import setup_logger


class SimpleScheduler:
    """
    간단한 스케줄러
    
    정해진 시간 간격으로 전략을 실행합니다.
    """
    
    # MARKET_HOURS는 중앙 설정(Config.MARKET_HOURS)을 사용합니다.

    def __init__(self, broker: Any, strategies: List):
        """
        Args:
            broker: KISBroker 인스턴스
            strategies: 실행할 전략 리스트
        """
        self.logger = setup_logger("Scheduler", Config.LOG_DIR, Config.LOG_LEVEL)
        self.broker = broker
        self.strategies = strategies
        self.is_running = False
        
        # 전략별 마지막 실행 시간(UTC)
        self._last_run: Dict[str, datetime] = {}
        # 전략별 시장 오픈 상태 추적 (strategy_id -> {market: bool})
        self._last_market_state: Dict[str, Dict[str, bool]] = {}

        self.logger.info(f"스케줄러 초기화 완료 (전략 수: {len(strategies)})")
    
    def is_market_hours(self) -> bool:
        """
        장 운영 시간인지 확인
        
        Returns:
            장 운영 시간이면 True
        """
        # 한국 시간대 사용
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        
        # 주말 체크
        if now.weekday() >= 5:  # 토요일(5), 일요일(6)
            return False
        
        # 시간 체크 (09:00 ~ 15:30)
        current_time = now.time()
        market_open = dt_time(9, 0)
        market_close = dt_time(15, 30)
        
        return market_open <= current_time <= market_close

    def _strategy_id(self, strategy: Any) -> str:
        return f"{strategy.__class__.__name__}:{id(strategy)}"

    def _get_strategy_cfg(self, strategy: Any) -> Dict:
        # 우선적으로 strategy에 직접 저장된 config 사용
        cfg = {}
        if hasattr(strategy, "config") and isinstance(getattr(strategy, "config"), dict):
            cfg = dict(getattr(strategy, "config"))

        # 마감/간격 등의 설정은 Config.STRATEGIES_CONFIG_TEMPLATE 에서도 올 수 있으므로
        # registry가 팩토리에서 전달한 경우 이미 strategy.config에 반영되어 있을 것임
        # 추가: 인스턴스 속성에서 직접 읽어 병합
        if hasattr(strategy, "watch_list"):
            cfg.setdefault("symbols", getattr(strategy, "watch_list"))
        return cfg

    def _is_market_open(self, market: str, now_utc: datetime) -> bool:
        mh = Config.MARKET_HOURS.get(market)
        if mh is None:
            # 미지정 마켓은 KRX로 간주
            mh = Config.MARKET_HOURS.get("KRX")
        tz = pytz.timezone(mh["tz"])
        now_local = now_utc.astimezone(tz)
        # weekday: Mon=0
        if now_local.weekday() not in mh.get("days", [0,1,2,3,4]):
            return False
        t = now_local.time()
        open_t = datetime.strptime(mh["open"], "%H:%M").time()
        close_t = datetime.strptime(mh["close"], "%H:%M").time()
        return open_t <= t <= close_t

    def _near_run_time(self, now_utc: datetime, market_tz: str, run_times: List[str], tolerance_seconds: int) -> bool:
        if not run_times:
            return False
        tz = pytz.timezone(market_tz)
        now_local = now_utc.astimezone(tz)
        for rt in run_times:
            try:
                hhmm = datetime.strptime(rt, "%H:%M").time()
            except Exception:
                continue
            target = datetime.combine(now_local.date(), hhmm).replace(tzinfo=tz)
            delta = abs((now_local - target).total_seconds())
            if delta <= tolerance_seconds:
                return True
        return False
    
    def run_strategies(self):
        """전략 실행 (전략별 실행 허용 조건 적용)"""
        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)

        self.logger.info("=" * 50)
        self.logger.info(f"전략 실행 체크: {now_utc.isoformat()} UTC")
        self.logger.info("=" * 50)

        for strategy in self.strategies:
            sid = self._strategy_id(strategy)
            cfg = self._get_strategy_cfg(strategy)

            # 기본 마켓 및 스케줄링 파라미터
            markets = cfg.get("markets", cfg.get("market", ["KRX"]))
            if isinstance(markets, str):
                markets = [markets]

            interval = int(cfg.get("run_interval_minutes", Config.SCHEDULE_INTERVAL_MINUTES))
            run_times = cfg.get("run_times", []) or []
            run_on_open = bool(cfg.get("run_on_open", False))
            run_on_close = bool(cfg.get("run_on_close", False))

            # tolerance: half interval to avoid missing exact minute matches
            tolerance = max(30, int(interval * 60 / 2))

            # 시장 열림 허용 여부 (하나라도 열려있으면 허용)
            market_allowed = False
            for m in markets:
                try:
                    if self._is_market_open(m, now_utc):
                        market_allowed = True
                        break
                except Exception:
                    continue

            # 기본: 시장이 전부 닫혔다면 스킵
            if not market_allowed:
                self.logger.debug(f"스킵: {strategy.__class__.__name__} - 지정된 시장({markets})에 개장 중인 시장이 없습니다.")
                continue

            # run_times 우선 체크 (정시 실행)
            time_trigger = False
            for m in markets:
                mh = Config.MARKET_HOURS.get(m, Config.MARKET_HOURS.get("KRX"))
                if self._near_run_time(now_utc, mh["tz"], run_times, tolerance):
                    time_trigger = True
                    break

            # 간격 기반 체크
            last = self._last_run.get(sid)
            elapsed_ok = False
            if last is None:
                elapsed_ok = True
            else:
                if (now_utc - last).total_seconds() >= interval * 60:
                    elapsed_ok = True

            # open/close 이벤트 트리거 체크
            event_trigger = False
            for m in markets:
                mh = Config.MARKET_HOURS.get(m, Config.MARKET_HOURS.get("KRX"))
                tz = pytz.timezone(mh["tz"])
                now_local = now_utc.astimezone(tz)
                open_t = datetime.strptime(mh["open"], "%H:%M").time()
                close_t = datetime.strptime(mh["close"], "%H:%M").time()
                prev_map = self._last_market_state.setdefault(sid, {})
                prev_state = prev_map.get(m, False)
                cur_state = (open_t <= now_local.time() <= close_t) and (now_local.weekday() in mh.get("days", [0,1,2,3,4]))
                if cur_state and not prev_state and run_on_open:
                    event_trigger = True
                if not cur_state and prev_state and run_on_close:
                    event_trigger = True
                prev_map[m] = cur_state

            should_run = (time_trigger or elapsed_ok or event_trigger)

            if not should_run:
                self.logger.debug(f"스킵: {strategy.__class__.__name__} - 실행 조건 미충족 (time_trigger={time_trigger}, elapsed_ok={elapsed_ok}, event_trigger={event_trigger})")
                continue

            # 실행
            try:
                self.logger.info(f"전략 실행: {strategy.__class__.__name__} (reason: {'time' if time_trigger else ('interval' if elapsed_ok else 'event')})")
                strategy.execute()
                self._last_run[sid] = now_utc
            except Exception as e:
                self.logger.error(f"전략 실행 중 오류 발생 ({strategy.__class__.__name__}): {e}")

        self.logger.info("=" * 50)
        self.logger.info("전략 체크 완료")
        self.logger.info("=" * 50)
    
    def start(self):
        """
        스케줄러 시작 (schedule 라이브러리 사용)
        """
        if not SCHEDULE_AVAILABLE:
            self.logger.warning("schedule 패키지가 설치되지 않았습니다. start_simple() 메서드를 사용합니다.")
            return self.start_simple()
        
        self.is_running = True
        self.logger.info(f"스케줄러 시작 (간격: {Config.SCHEDULE_INTERVAL_MINUTES}분)")
        
        # 스케줄 등록
        schedule.every(Config.SCHEDULE_INTERVAL_MINUTES).minutes.do(self.run_strategies)
        
        # 즉시 한 번 실행
        self.run_strategies()
        
        # 스케줄 루프
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("사용자에 의해 중단되었습니다.")
            self.stop()
    
    def start_simple(self):
        """
        스케줄러 시작 (단순 time.sleep 방식)
        
        schedule 라이브러리 없이 간단한 루프로 구현
        """
        self.is_running = True
        self.logger.info(f"스케줄러 시작 (간격: {Config.SCHEDULE_INTERVAL_MINUTES}분)")
        
        try:
            while self.is_running:
                self.run_strategies()
                
                # 다음 실행까지 대기
                wait_seconds = Config.SCHEDULE_INTERVAL_MINUTES * 60
                self.logger.info(f"{Config.SCHEDULE_INTERVAL_MINUTES}분 후 다음 실행...")
                time.sleep(wait_seconds)
        except KeyboardInterrupt:
            self.logger.info("사용자에 의해 중단되었습니다.")
            self.stop()
    
    def stop(self):
        """스케줄러 중지"""
        self.is_running = False
        self.logger.info("스케줄러 중지")
