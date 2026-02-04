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
