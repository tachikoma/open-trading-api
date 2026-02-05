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
