"""
자동매매 봇 설정 파일

주의: KIS API 인증은 kis_auth.py에서 다음 경로의 설정 파일을 사용합니다:
    ~/KIS/config/kis_devlp.yaml

프로젝트 루트의 kis_devlp.yaml은 예시/템플릿 파일입니다.
실제 사용을 위해서는 ~/KIS/config/kis_devlp.yaml을 생성해야 합니다.
"""
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# load .env from repository root (if present)
load_dotenv(find_dotenv())


class Config:
    """자동매매 봇 설정 클래스

    - `ENV_MODE`와 `TRADING_ENABLED`는 우선순위로
      실제 환경변수 > 프로젝트 루트의 `.env` > 기본값 순으로 결정됩니다.
    - `.env` 파일 경로: 프로젝트 루트(현재 파일의 부모 부모)/.env
    """

    # 프로젝트 루트 경로
    ROOT_DIR = Path(__file__).parent.parent

    # 기본값
    _DEFAULT_ENV_MODE = "demo"
    _DEFAULT_TRADING_ENABLED = False

    # ENV_MODE: 환경변수 > 기본값('demo')
    _raw_env_mode = os.environ.get("ENV_MODE", _DEFAULT_ENV_MODE)
    if isinstance(_raw_env_mode, str):
        ENV_MODE = _raw_env_mode.strip().lower()
    else:
        # boolean 등 비문자 입력이 들어오면 안전하게 기본값으로 설정
        try:
            ENV_MODE = str(_raw_env_mode).strip().lower()
        except Exception:
            ENV_MODE = _DEFAULT_ENV_MODE

    # TRADING_ENABLED: 환경변수 > 기본값
    _raw_trading = os.environ.get("TRADING_ENABLED", str(_DEFAULT_TRADING_ENABLED))
    if isinstance(_raw_trading, bool):
        TRADING_ENABLED = _raw_trading
    else:
        TRADING_ENABLED = str(_raw_trading).strip().lower() in ("1", "true", "yes", "on")

    # 스케줄 설정 (방안 3)
    SCHEDULE_INTERVAL_MINUTES = 5  # 5분마다 전략 실행

    # 시장 시간 매핑 (전략별/마켓별 스케줄링에 사용)
    # 방법 2 + 방법 3 혼합: 각 시장별 세션 구분 + 유연한 확장성
    #
    # 사용 예시:
    #   1. 정규장만 거래: market="NYSE"
    #   2. 전체 시간(Pre + Regular + After): market="NYSE_EXTENDED"
    #   3. Pre-market만: market="NYSE_PRE"
    #   4. After-hours만: market="NYSE_AFTER"
    #   5. 한국 낮 시간 거래: market="NYSE_DAY" (미국 주간거래)
    #
    MARKET_HOURS = {
        # ===== 국내 장 (KRX) =====
        "KRX": {
            "tz": "Asia/Seoul",
            "sessions": {
                "regular": {"open": "09:00", "close": "15:30"},
            },
            "days": [0, 1, 2, 3, 4],  # 월-금
        },

        # ===== 미국 장 (NYSE/NASDAQ) =====
        # 미국 시간(US/Eastern 기준):
        #   - Pre-market:  04:00 ~ 09:30 (개장 전)
        #   - Regular:     09:30 ~ 16:00 (정규장)
        #   - After-hours: 16:00 ~ 20:00 (폐장 후)
        # 
        # 한국 시간(서머타임 제외, +14시간):
        #   - Pre-market:  18:00 (전일) ~ 23:30
        #   - Regular:     23:30 ~ 06:00 (익일)
        #   - After-hours: 06:00 ~ 10:00
        #   - Day Market:  10:00 ~ 17:50 (KIS 주간거래)

        "NYSE": {
            "tz": "US/Eastern",
            "sessions": {
                "regular": {"open": "09:30", "close": "16:00"},
            },
            "days": [0, 1, 2, 3, 4],  # 월-금
            "description": "정규장만 (유동성 최고)",
        },

        "NYSE_PRE": {
            "tz": "US/Eastern",
            "sessions": {
                "pre": {"open": "04:00", "close": "09:30"},
            },
            "days": [0, 1, 2, 3, 4],  # 월-금
            "description": "Pre-market (개장 전, 낮은 유동성)",
        },

        "NYSE_AFTER": {
            "tz": "US/Eastern",
            "sessions": {
                "after": {"open": "16:00", "close": "20:00"},
            },
            "days": [0, 1, 2, 3, 4],  # 월-금
            "description": "After-hours (폐장 후, 낮은 유동성)",
        },

        "NYSE_EXTENDED": {
            "tz": "US/Eastern",
            "sessions": {
                "pre": {"open": "04:00", "close": "09:30"},
                "regular": {"open": "09:30", "close": "16:00"},
                "after": {"open": "16:00", "close": "20:00"},
            },
            "days": [0, 1, 2, 3, 4],  # 월-금
            "description": "확장 시간대 (전체: 04:00 ~ 20:00)",
        },

        "NYSE_DAY": {
            "tz": "Asia/Seoul",  # 한국 시간 기준
            "sessions": {
                "day": {"open": "10:00", "close": "17:50"},
            },
            "days": [0, 1, 2, 3, 4],  # 월-금
            "description": "미국 주간거래 (한국 낮 시간, 지정가 주문만, 주간거래까지만 유지)",
            "restrictions": {
                "order_type": "limit_only",  # 지정가만 가능
                "duration": "day_only",       # 주간거래까지만
                "realtime_quote": "limited",  # 일부 종목 실시간 시세 제한
            },
        },

        # ===== NASDAQ (NYSE와 동일한 시간대) =====
        "NASDAQ": {
            "tz": "US/Eastern",
            "sessions": {
                "regular": {"open": "09:30", "close": "16:00"},
            },
            "days": [0, 1, 2, 3, 4],  # 월-금
            "description": "정규장만",
        },

        "NASDAQ_EXTENDED": {
            "tz": "US/Eastern",
            "sessions": {
                "pre": {"open": "04:00", "close": "09:30"},
                "regular": {"open": "09:30", "close": "16:00"},
                "after": {"open": "16:00", "close": "20:00"},
            },
            "days": [0, 1, 2, 3, 4],  # 월-금
            "description": "확장 시간대 (전체: 04:00 ~ 20:00)",
        },
    }

    @staticmethod
    def get_market_session(market: str, session_name: str = "regular") -> dict:
        """
        특정 시장의 세션 정보 조회 헬퍼 함수

        Args:
            market: 시장명 (예: "NYSE", "KRX")
            session_name: 세션명 (예: "regular", "pre", "after"). 생략하면 "regular"

        Returns:
            {"open": "HH:MM", "close": "HH:MM"} 형태의 dict, 없으면 None

        Example:
            >>> Config.get_market_session("NYSE")
            {'open': '09:30', 'close': '16:00'}
            >>> Config.get_market_session("NYSE", "pre")
            {'open': '04:00', 'close': '09:30'}
        """
        market_config = Config.MARKET_HOURS.get(market)
        if not market_config:
            return None
        sessions = market_config.get("sessions", {})
        return sessions.get(session_name)

    # 주문 설정
    MAX_POSITION_SIZE = 1000000  # 최대 투자 금액 (100만원)
    MAX_ORDER_AMOUNT = 500000    # 1회 최대 주문 금액 (50만원)

    # 기본 거래소 코드 (예: KRX)
    DEFAULT_EXCHANGE = "KRX"

    # 로깅 설정
    LOG_DIR = Path(__file__).parent / "logs"
    # LOG_LEVEL: 환경변수 > .env > 기본값
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()  # DEBUG, INFO, WARNING, ERROR
    # 로그 파일명 (통합 로그)
    LOG_FILE = Path(os.environ.get("LOG_FILE", str(LOG_DIR / "app.log")))
    # 로테이션 설정 (.env 또는 환경변수로 오버라이드 가능)
    try:
        LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
    except Exception:
        LOG_MAX_BYTES = 10 * 1024 * 1024

    try:
        LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", str(10)))
    except Exception:
        LOG_BACKUP_COUNT = 10

    # 심볼 매핑 설정
    _raw_symbol_enabled = os.environ.get("SYMBOL_MAP_ENABLED", "1")
    if isinstance(_raw_symbol_enabled, bool):
        SYMBOL_MAP_ENABLED = _raw_symbol_enabled
    else:
        SYMBOL_MAP_ENABLED = str(_raw_symbol_enabled).strip().lower() in ("1", "true", "yes", "on")

    SYMBOL_MAP_DIR = os.environ.get("SYMBOL_MAP_DIR", str(Path(__file__).parent / "data"))

    # Telegram 알림 설정
    _raw_tele_enabled = os.environ.get("TELEGRAM_ENABLED", "0")
    if isinstance(_raw_tele_enabled, bool):
        TELEGRAM_ENABLED = _raw_tele_enabled
    else:
        TELEGRAM_ENABLED = str(_raw_tele_enabled).strip().lower() in ("1", "true", "yes", "on")

    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
    TELEGRAM_TIMEOUT_SEC = int(os.environ.get("TELEGRAM_TIMEOUT_SEC", "3"))

    # 전략 설정
    # 기존 호환: 문자열 리스트로 전략 이름만 나열할 수 있습니다.
    STRATEGIES_ENABLED = ["ma_crossover", "infinite_buy"]  # 활성화할 전략 목록

    # 권장: 전략별 개별 설정을 포함하는 리스트 형태로 구성하면
    # 각 전략 인스턴스에 대한 `config`를 전달할 수 있습니다.
    # 예시 템플릿 (사용 시 STRATEGIES_ENABLED 대신 이 구조로 바꿔 사용):
    STRATEGIES_CONFIG_TEMPLATE = [
        {
            "name": "ma_crossover",
            "config": {
                "markets": "KRX",
                # 인스턴스별 감시 종목 리스트(없으면 Config.WATCH_LIST 사용)
                "symbols": [   
                    "319400", # 현대무벡스
                    "240810", # 원익IPS
                    "042700", # 한미반도체
                    "214450", # 파마리서치
                    "950160", # 코오롱티슈진
                    "035900", # JYP Ent.
                    "005290", # 동진쎄미켐
                    "476830", # 알지노믹스
                    "068270", # 셀트리온
                    "095340", # ISC
                    "058470", # 리노공업
                    "039030", # 이오테크닉스
                    "475830", # 오름테라퓨틱
                    "140410", # 메지온
                    "352820", # 하이브
                    "108490", # 로보티즈
                    "069500", # KODEX 200
                    "347850", # 디앤디파마텍
                    "006800", # 미래에셋증권
                    "009150", # 삼성전기
                    "068760", # 셀트리온제약
                    "257720", # 실리콘투
                    "010120", # LS ELECTRIC
                    "0009K0", # 에임드바이오
                    "237690", # 에스티팜
                    "357780", # 솔브레인
                    "090430", # 아모레퍼시픽
                    "003230", # 삼양식품
                    "000250", # 삼천당제약
                    "028300", # HLB
                    "403870", # HPSP
                    "214150", # 클래시스
                    "263750", # 펄어비스
                    "086520", # 에코프로
                    "003670", # 포스코퓨처엠
                    "298380", # 에이비엘바이오
                    "087010", # 펩트론
                    "041510", # 에스엠
                    "035720", # 카카오
                    "079550", # LIG넥스원
                    "006260", # LS
                    "000660", # SK하이닉스
                    "267260", # HD현대일렉트릭
                    "006400", # 삼성SDI
                    "402340", # SK스퀘어
                    "298040", # 효성중공업
                    "007660", # 이수페타시스
                    "000150", # 두산
                    "454910", # 두산로보틱스
                    "247540", # 에코프로비엠
                    "214370", # 케어젠
                    "445680", # 큐리옥스바이오시스템즈
                    "035420", # NAVER
                    "064350", # 현대로템
                    "039490", # 키움증권
                    "141080", # 리가켐바이오
                    "009540", # HD한국조선해양
                    "000720", # 현대건설
                    "128940", # 한미약품
                    "226950", # 올릭스
                    "051910", # LG화학
                    "196170", # 알테오젠
                    "452430", # 사피엔반도체
                    "377300", # 카카오페이
                    "360750", # TIGER 미국S&P500
                    "379800", # KODEX 미국S&P500
                    "307950", # 현대오토에버
                    "310210", # 보로노이
                    "047050", # 포스코인터내셔널
                    "064400", # LG씨엔에스
                    "010950", # S-Oil
                    "133690", # TIGER 미국나스닥100
                    "011070", # LG이노텍
                    "145020", # 휴젤
                    "003490", # 대한항공
                    "272210", # 한화시스템
                    "278470", # 에이피알
                    "005830", # DB손해보험
                    "411060", # ACE KRX금현물
                    "018260", # 삼성에스디에스
                    "015760", # 한국전력
                    "028260", # 삼성물산
                    "016360", # 삼성증권
                    "267250", # HD현대
                    "042660", # 한화오션
                    "010130", # 고려아연
                    "078930", # GS
                    "021240", # 코웨이
                    "161390", # 한국타이어앤테크놀로지
                    "029780", # 삼성카드
                    "030200", # KT
                    "005380", # 현대차
                    "180640", # 한진칼
                    "326030", # SK바이오팜
                    "012330", # 현대모비스
                    "373220", # LG에너지솔루션
                    "032640", # LG유플러스
                    "033780", # KT&G
                    "010140", # 삼성중공업
                    "088980", # 맥쿼리인프라
                ],
                "short_period": 5,
                "long_period": 20,
            },
        },
        {
            "name": "infinite_buy",
            "config": {
                "version": "v2.2",
                "markets": ["NYSE", "NYSE_DAY"],
                # 권장(필수): 심볼별 설정 맵 (키: 티커, 값: {"total_amount":..., "splits": ...})
                # 예시: 각 티커마다 총투자금(total_amount)과 분할횟수(splits)를 반드시 명시하세요.
                "symbols": {
                    "TQQQ": {"total_amount": 300000, "splits": 30},
                    "SOXL": {"exchange":"AMS", "total_amount": 500000, "splits": 20},
                },
            },
        },
    ]

    # 감시 종목 리스트 (생략 가능, 기존 내용 유지)
    WATCH_LIST = [
        "319400", # 현대무벡스
        "240810", # 원익IPS
        "042700", # 한미반도체
        "214450", # 파마리서치
        "950160", # 코오롱티슈진
        "035900", # JYP Ent.
        "005290", # 동진쎄미켐
        "476830", # 알지노믹스
        "068270", # 셀트리온
        "095340", # ISC
        "058470", # 리노공업
        "039030", # 이오테크닉스
        "475830", # 오름테라퓨틱
        "140410", # 메지온
        "352820", # 하이브
        "108490", # 로보티즈
        "069500", # KODEX 200
        "347850", # 디앤디파마텍
        "006800", # 미래에셋증권
        "009150", # 삼성전기
        "068760", # 셀트리온제약
        "257720", # 실리콘투
        "010120", # LS ELECTRIC
        "0009K0", # 에임드바이오
        "237690", # 에스티팜
        "357780", # 솔브레인
        "090430", # 아모레퍼시픽
        "003230", # 삼양식품
        "000250", # 삼천당제약
        "028300", # HLB
        "403870", # HPSP
        "214150", # 클래시스
        "263750", # 펄어비스
        "086520", # 에코프로
        "003670", # 포스코퓨처엠
        "298380", # 에이비엘바이오
        "087010", # 펩트론
        "041510", # 에스엠
        "035720", # 카카오
        "079550", # LIG넥스원
        "006260", # LS
        "000660", # SK하이닉스
        "267260", # HD현대일렉트릭
        "006400", # 삼성SDI
        "402340", # SK스퀘어
        "298040", # 효성중공업
        "007660", # 이수페타시스
        "000150", # 두산
        "454910", # 두산로보틱스
        "247540", # 에코프로비엠
        "214370", # 케어젠
        "445680", # 큐리옥스바이오시스템즈
        "035420", # NAVER
        "064350", # 현대로템
        "039490", # 키움증권
        "141080", # 리가켐바이오
        "009540", # HD한국조선해양
        "000720", # 현대건설
        "128940", # 한미약품
        "226950", # 올릭스
        "051910", # LG화학
        "196170", # 알테오젠
        "452430", # 사피엔반도체
        "377300", # 카카오페이
        "360750", # TIGER 미국S&P500
        "379800", # KODEX 미국S&P500
        "307950", # 현대오토에버
        "310210", # 보로노이
        "047050", # 포스코인터내셔널
        "064400", # LG씨엔에스
        "010950", # S-Oil
        "133690", # TIGER 미국나스닥100
        "011070", # LG이노텍
        "145020", # 휴젤
        "003490", # 대한항공
        "272210", # 한화시스템
        "278470", # 에이피알
        "005830", # DB손해보험
        "411060", # ACE KRX금현물
        "018260", # 삼성에스디에스
        "015760", # 한국전력
        "028260", # 삼성물산
        "016360", # 삼성증권
        "267250", # HD현대
        "042660", # 한화오션
        "010130", # 고려아연
        "078930", # GS
        "021240", # 코웨이
        "161390", # 한국타이어앤테크놀로지
        "029780", # 삼성카드
        "030200", # KT
        "005380", # 현대차
        "180640", # 한진칼
        "326030", # SK바이오팜
        "012330", # 현대모비스
        "373220", # LG에너지솔루션
        "032640", # LG유플러스
        "033780", # KT&G
        "010140", # 삼성중공업
        "088980", # 맥쿼리인프라
    ]

    # 이동평균 전략 설정
    MA_SHORT_PERIOD = 5   # 단기 이동평균 (5일)
    MA_LONG_PERIOD = 20   # 장기 이동평균 (20일)

    # 리스크 관리
    STOP_LOSS_PERCENT = 3.0    # 손절 비율 (3%)
    TAKE_PROFIT_PERCENT = 5.0   # 익절 비율 (5%)

    # 백테스트 설정
    BACKTEST_INITIAL_CAPITAL = 10000000  # 백테스트 초기 자본금 (1천만원)
    BACKTEST_COMMISSION_RATE = 0.00015   # 수수료율 0.015% (편도)
    BACKTEST_SLIPPAGE_RATE = 0.001       # 슬리피지 0.1%
    BACKTEST_RESULTS_DIR = Path(__file__).parent / "backtest_results"

    # 실제/시뮬레이션 모두에서 사용할 기본 수수료/세금 설정
    # 국내 주식 기준: 수수료(편도) 0.015% = 0.00015, 거래세(매도시) 0.20% = 0.002
    # 환경변수 또는 .env로 오버라이드 가능 (예: COMMISSION_RATE, TRADE_TAX_RATE)
    try:
        COMMISSION_RATE = float(os.environ.get("COMMISSION_RATE", str(0.00015)))
    except Exception:
        COMMISSION_RATE = 0.00015

    try:
        COMMISSION_MIN = int(os.environ.get("COMMISSION_MIN", "0"))
    except Exception:
        COMMISSION_MIN = 0

    try:
        TRADE_TAX_RATE = float(os.environ.get("TRADE_TAX_RATE", str(0.002)))
    except Exception:
        TRADE_TAX_RATE = 0.002

    @classmethod
    def validate(cls):
        """설정 유효성 검증

        주의: KIS 설정 파일(kis_devlp.yaml)은 kis_auth.py에서
              ~/KIS/config/kis_devlp.yaml 경로를 사용합니다.
        """
        if cls.ENV_MODE not in ["real", "demo"]:
            raise ValueError("ENV_MODE는 'real' 또는 'demo'여야 합니다.")

        if not cls.LOG_DIR.exists():
            cls.LOG_DIR.mkdir(parents=True, exist_ok=True)

        # KIS 설정 파일 경로 안내
        kis_config = Path.home() / "KIS" / "config" / "kis_devlp.yaml"
        if not kis_config.exists():
            raise FileNotFoundError(
                f"KIS 설정 파일을 찾을 수 없습니다: {kis_config}\n"
                f"다음 위치에 kis_devlp.yaml 파일을 생성해주세요: {kis_config.parent}/\n"
                f"프로젝트 루트의 kis_devlp.yaml을 템플릿으로 사용할 수 있습니다."
            )

        # 전략별 권장 설정 검증 (경고 수준)
        import logging
        logger = logging.getLogger(__name__)

        # STRATEGIES_CONFIG_TEMPLATE 사용 권장 시 구조 점검
        if hasattr(cls, "STRATEGIES_CONFIG_TEMPLATE") and isinstance(cls.STRATEGIES_CONFIG_TEMPLATE, list):
            for entry in cls.STRATEGIES_CONFIG_TEMPLATE:
                if not isinstance(entry, dict):
                    logger.warning("STRATEGIES_CONFIG_TEMPLATE 항목은 dict여야 합니다: %s", entry)
                    continue
                name = entry.get("name")
                cfg = entry.get("config", {}) or {}
                if name == "ma_crossover":
                    symbols = cfg.get("symbols") or cls.WATCH_LIST
                    if not symbols:
                        logger.warning("ma_crossover: 감시 종목(symbols)이 비어있습니다. Config.WATCH_LIST 사용 예정")
                    # 기간 검증
                    sp = cfg.get("short_period", cls.MA_SHORT_PERIOD)
                    lp = cfg.get("long_period", cls.MA_LONG_PERIOD)
                    try:
                        if int(sp) <= 0 or int(lp) <= 0:
                            logger.warning("ma_crossover: short_period/long_period는 양수여야 합니다. 현재: %s/%s", sp, lp)
                    except Exception:
                        logger.warning("ma_crossover: short_period/long_period 형식이 올바르지 않습니다: %s/%s", sp, lp)
                if name == "infinite_buy":
                    # symbols는 티커->설정(dict) 맵이어야 함 (필수)
                    symbols_map = cfg.get("symbols", {}) or {}
                    
                    if not isinstance(symbols_map, dict) or len(symbols_map) == 0:
                        logger.error("infinite_buy: 'symbols' 설정이 필수입니다. 티커별 total_amount, splits, exchange를 지정해야 합니다.")
                        continue
                    
                    for sym, entry in symbols_map.items():
                        if not isinstance(entry, dict):
                            logger.warning("infinite_buy: symbols[%s] 값은 dict여야 합니다. 현재형: %s", sym, type(entry).__name__)
                            continue
                        
                        # total_amount 검증 (필수)
                        ta = entry.get("total_amount")
                        if ta is None:
                            logger.error("infinite_buy: symbols[%s].total_amount는 필수입니다.", sym)
                        else:
                            try:
                                if float(ta) <= 0:
                                    logger.warning("infinite_buy: symbols[%s].total_amount는 양수여야 합니다. 현재: %s", sym, ta)
                            except Exception:
                                logger.warning("infinite_buy: symbols[%s].total_amount 형식이 잘못되었습니다: %s", sym, ta)
                        
                        # splits 검증 (필수)
                        sp = entry.get("splits")
                        if sp is None:
                            logger.error("infinite_buy: symbols[%s].splits는 필수입니다.", sym)
                        else:
                            try:
                                if int(sp) <= 0:
                                    logger.warning("infinite_buy: symbols[%s].splits는 양의 정수여야 합니다. 현재: %s", sym, sp)
                            except Exception:
                                logger.warning("infinite_buy: symbols[%s].splits 형식이 잘못되었습니다: %s", sym, sp)
                        
                        # exchange 검증 (선택, 기본값 NAS)
                        exch = entry.get("exchange")
                        if exch and not isinstance(exch, str):
                            logger.warning("infinite_buy: symbols[%s].exchange는 문자열이어야 합니다. 현재: %s", sym, type(exch).__name__)

        return True
