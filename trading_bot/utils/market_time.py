"""
미국 주식 시장 시간대 판정 유틸

미국 동부 시간 기준:
- Pre-market: 04:00-09:30
- Regular: 09:30-16:00  
- After-hours: 16:00-20:00
- Closed: 20:00-04:00
"""
from datetime import datetime, timedelta
import pytz


def get_us_market_time() -> datetime:
    """미국 동부 시간 (US/Eastern) 반환"""
    return datetime.now(pytz.timezone('US/Eastern'))


def get_market_phase(us_time: datetime = None) -> str:
    """
    현재 미국 시간의 시장 단계 반환
    
    Args:
        us_time: 미국 동부 시간 (None이면 현재 시간 사용)
    
    Returns:
        'pre_market', 'regular', 'after_hours', 'closed'
    """
    if us_time is None:
        us_time = get_us_market_time()
    
    hour = us_time.hour
    minute = us_time.minute
    total_minutes = hour * 60 + minute
    
    # Pre-market: 04:00-09:30
    if 4 * 60 <= total_minutes < 9 * 60 + 30:
        return 'pre_market'
    
    # Regular: 09:30-16:00
    if 9 * 60 + 30 <= total_minutes < 16 * 60:
        return 'regular'
    
    # After-hours: 16:00-20:00
    if 16 * 60 <= total_minutes < 20 * 60:
        return 'after_hours'
    
    # Closed: 20:00-04:00
    return 'closed'


def is_pre_market(us_time: datetime = None) -> bool:
    """사전장 여부 (04:00-09:30)"""
    return get_market_phase(us_time) == 'pre_market'


def is_regular_hours(us_time: datetime = None) -> bool:
    """정규장 여부 (09:30-16:00)"""
    return get_market_phase(us_time) == 'regular'


def is_after_hours(us_time: datetime = None) -> bool:
    """장후 여부 (16:00-20:00)"""
    return get_market_phase(us_time) == 'after_hours'


def is_daytime_trading_hours(kr_time: datetime = None) -> bool:
    """
    주간거래 시간 여부 (한국시간 10:00-18:00)
    
    한국투자증권의 주간거래(daytime trading) API는 **한국시간** 오전 10시 ~ 오후 6시에만
    사용 가능합니다. 이 시간은 미국 시간으로는 애프터마켓 종료 이후부터
    프리마켓 시작 직전까지에 해당합니다.
    
    이 API는 별도의 거래소를 통해 한국 거래자들이 미국 시장에 접근할 수 있도록
    한국 업무시간 중에 제공합니다.
    
    Args:
        kr_time: 한국 시간 (None이면 현재 시간 사용)
                 pytz.timezone('Asia/Seoul')을 사용한 datetime 객체 또는
                 한국 시간대 아무 datetime(자동으로 한국시간으로 해석)
    
    Returns:
        True: 주간거래 시간 (한국시간 10:00-18:00, 평일만)
        False: 주간거래 불가능 시간
    
    Note:
        - 미국 시간으로는 애프터마켓 종료 이후부터 프리마켓 시작 직전까지
        - 한국시간 10:00 KST = 미국 EST 전날 20:00 / EDT 전날 21:00
        - 한국시간 18:00 KST = 미국 EST 다음날 04:00 / EDT 다음날 05:00
    """
    if kr_time is None:
        kr_time = datetime.now(pytz.timezone('Asia/Seoul'))
    elif kr_time.tzinfo is None:
        # timezone 정보가 없으면 한국시간으로 해석
        kr_time = pytz.timezone('Asia/Seoul').localize(kr_time)
    else:
        # timezone이 있으면 한국시간으로 변환
        kr_time = kr_time.astimezone(pytz.timezone('Asia/Seoul'))
    
    # 주말 확인 (월=0, 일=6)
    if kr_time.weekday() >= 5:
        return False
    
    hour = kr_time.hour
    
    # 한국시간 10:00-18:00
    if 10 <= hour < 18:
        return True
    
    return False


def is_market_open(us_time: datetime = None) -> bool:
    """시장 개장 여부 (Pre + Regular + After)"""
    phase = get_market_phase(us_time)
    return phase in ('pre_market', 'regular', 'after_hours')


def get_next_market_phase_time(us_time: datetime = None) -> tuple:
    """
    다음 시장 단계의 시작 시간과 단계명 반환
    
    Returns:
        (다음 단계 시작 시간, 단계명)
    """
    if us_time is None:
        us_time = get_us_market_time()
    
    phase = get_market_phase(us_time)
    
    if phase == 'closed':
        # 다음 날 04:00 (Pre-market)
        next_time = us_time.replace(hour=4, minute=0, second=0, microsecond=0)
        next_time += timedelta(days=1)
        return next_time, 'pre_market'
    
    elif phase == 'pre_market':
        # 09:30 (Regular)
        return us_time.replace(hour=9, minute=30, second=0, microsecond=0), 'regular'
    
    elif phase == 'regular':
        # 16:00 (After-hours)
        return us_time.replace(hour=16, minute=0, second=0, microsecond=0), 'after_hours'
    
    elif phase == 'after_hours':
        # 다음 날 04:00 (Pre-market)
        next_time = us_time.replace(hour=4, minute=0, second=0, microsecond=0)
        next_time += timedelta(days=1)
        return next_time, 'pre_market'


def get_wait_time_to_phase(target_phase: str, us_time: datetime = None) -> timedelta:
    """
    목표 시장 단계까지의 대기 시간 반환
    
    Args:
        target_phase: 'pre_market', 'regular', 'after_hours'
        us_time: 미국 동부 시간
    
    Returns:
        대기 시간 (timedelta)
    """
    if us_time is None:
        us_time = get_us_market_time()
    
    current_phase = get_market_phase(us_time)
    
    if current_phase == target_phase:
        return timedelta(0)
    
    # 목표 시간 계산
    if target_phase == 'pre_market':
        target_time = us_time.replace(hour=4, minute=0, second=0, microsecond=0)
        if target_time <= us_time:
            target_time += timedelta(days=1)
    
    elif target_phase == 'regular':
        target_time = us_time.replace(hour=9, minute=30, second=0, microsecond=0)
        if target_time <= us_time:
            target_time += timedelta(days=1)
    
    elif target_phase == 'after_hours':
        target_time = us_time.replace(hour=16, minute=0, second=0, microsecond=0)
        if target_time <= us_time:
            target_time += timedelta(days=1)
    
    else:
        raise ValueError(f"Invalid target_phase: {target_phase}")
    
    return target_time - us_time


def is_weekday(us_time: datetime = None) -> bool:
    """평일 여부 (월-금, 미국 동부 기준)"""
    if us_time is None:
        us_time = get_us_market_time()
    
    return us_time.weekday() < 5  # 0-4: Mon-Fri


def is_market_session_open(market_name: str) -> bool:
    """
    Config.MARKET_HOURS 기반으로 특정 시장의 개장 여부 체크
    
    Args:
        market_name: 시장명 (예: "NYSE", "NYSE_DAY", "KRX" 등)
    
    Returns:
        해당 시장이 현재 개장 중이면 True, 아니면 False
    
    Example:
        >>> is_market_session_open("NYSE")  # 미국 동부 시간 기준
        True
        >>> is_market_session_open("NYSE_DAY")  # 한국 시간 기준
        True
    """
    # Config import는 함수 내부에서 (순환 참조 방지)
    from trading_bot.config import Config
    
    market_config = Config.MARKET_HOURS.get(market_name)
    if not market_config:
        # 알 수 없는 시장명이면 False
        return False
    
    # 시간대 가져오기
    tz_str = market_config.get("tz", "US/Eastern")
    tz = pytz.timezone(tz_str)
    now = datetime.now(tz)
    
    # 평일(days) 체크
    allowed_days = market_config.get("days", [0, 1, 2, 3, 4])
    if now.weekday() not in allowed_days:
        return False
    
    # 세션(sessions) 체크: 하나라도 개장 중이면 True
    sessions = market_config.get("sessions", {})
    if not sessions:
        return False
    
    current_time_minutes = now.hour * 60 + now.minute
    
    for session_name, session_info in sessions.items():
        open_str = session_info.get("open")  # "HH:MM"
        close_str = session_info.get("close")
        
        if not open_str or not close_str:
            continue
        
        # 시간 파싱
        try:
            open_h, open_m = map(int, open_str.split(":"))
            close_h, close_m = map(int, close_str.split(":"))
        except Exception:
            continue
        
        open_minutes = open_h * 60 + open_m
        close_minutes = close_h * 60 + close_m
        
        # 개장~폐장 사이인지 체크
        if open_minutes <= current_time_minutes < close_minutes:
            return True
    
    return False


def is_any_market_open(market_list: list) -> bool:
    """
    여러 시장 중 하나라도 개장 중인지 체크
    
    Args:
        market_list: 시장명 리스트 (예: ["NYSE_EXTENDED", "NYSE_DAY"])
    
    Returns:
        하나라도 개장 중이면 True, 모두 폐장이면 False
    
    Example:
        >>> is_any_market_open(["NYSE_EXTENDED", "NYSE_DAY"])
        True  # 둘 중 하나라도 열려있으면
    """
    if not market_list:
        return False
    
    for market_name in market_list:
        if is_market_session_open(market_name):
            return True
    
    return False


def get_market_status(market_name: str) -> str:
    """
    특정 시장의 현재 상태 반환
    
    Args:
        market_name: 시장명 (예: "NYSE_DAY", "NYSE_EXTENDED", "NYSE")
    
    Returns:
        'open': 개장 중 (일반 시장)
        'day_trading': 주간거래 중 (NYSE_DAY 전용)
        'closed': 폐장
    
    Example:
        >>> get_market_status("NYSE_DAY")  # 한국 낮 12시
        'day_trading'
        >>> get_market_status("NYSE_EXTENDED")  # 미국 밤 10시
        'closed'
        >>> get_market_status("NYSE")  # 미국 정규장 중
        'open'
    """
    if is_market_session_open(market_name):
        # NYSE_DAY는 특별히 'day_trading'으로 표시
        if market_name == "NYSE_DAY":
            return 'day_trading'
        return 'open'
    return 'closed'


def get_markets_status_summary(market_list: list) -> dict:
    """
    여러 시장의 상태를 요약하여 반환
    
    Args:
        market_list: 시장명 리스트 (예: ["NYSE_EXTENDED", "NYSE_DAY"])
    
    Returns:
        딕셔너리:
        {
            'markets': {
                'NYSE_EXTENDED': 'closed',
                'NYSE_DAY': 'day_trading'
            },
            'any_open': True,           # 하나라도 개장 중
            'all_open': False,          # 모두 개장 중
            'open_markets': ['NYSE_DAY'],
            'closed_markets': ['NYSE_EXTENDED']
        }
    
    Example:
        >>> status = get_markets_status_summary(["NYSE_EXTENDED", "NYSE_DAY"])
        >>> print(status['open_markets'])
        ['NYSE_DAY']
        >>> print(status['any_open'])
        True
    """
    if not market_list:
        return {
            'markets': {},
            'any_open': False,
            'all_open': False,
            'open_markets': [],
            'closed_markets': []
        }
    
    markets_status = {}
    open_markets = []
    closed_markets = []
    
    for market_name in market_list:
        status = get_market_status(market_name)
        markets_status[market_name] = status
        
        # 'open' 또는 'day_trading' 모두 개장 중으로 간주
        if status in ('open', 'day_trading'):
            open_markets.append(market_name)
        else:
            closed_markets.append(market_name)
    
    return {
        'markets': markets_status,
        'any_open': len(open_markets) > 0,
        'all_open': len(closed_markets) == 0,
        'open_markets': open_markets,
        'closed_markets': closed_markets
    }
