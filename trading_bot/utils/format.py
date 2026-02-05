"""
가격 및 통화 포맷팅 유틸리티
"""


def format_price(price: float, currency: str = "USD", decimal_places: int = 2) -> str:
    """
    가격을 통화 기호와 함께 포맷팅
    
    Args:
        price: 가격
        currency: 통화 코드 ('USD', 'KRW' 등)
        decimal_places: 소수점 자릿수 (기본 2)
    
    Returns:
        포맷된 가격 문자열 (예: "$49.76", "₩49,760")
    
    Example:
        >>> format_price(49.76, "USD")
        "$49.76"
        >>> format_price(49.761, "USD")
        "$49.76"
        >>> format_price(49760, "KRW")
        "₩49,760"
    """
    currency_symbols = {
        "USD": "$",
        "KRW": "₩",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "CNY": "¥",
    }
    
    symbol = currency_symbols.get(currency.upper(), currency.upper())
    
    if currency.upper() == "KRW":
        # 원화는 천 단위 구분, 소수점 없음
        return f"{symbol}{int(price):,}"
    else:
        # 달러 등은 소수점 표시
        return f"{symbol}{price:.{decimal_places}f}"


def format_quantity(qty: int, precision: int = 0) -> str:
    """
    수량을 포맷팅
    
    Args:
        qty: 수량
        precision: 소수점 자릿수
    
    Returns:
        포맷된 수량 (예: "100", "100.50")
    """
    if precision == 0:
        return f"{int(qty):,}"
    else:
        return f"{qty:,.{precision}f}"
