"""
자동매매 봇 설정 파일

주의: KIS API 인증은 kis_auth.py에서 다음 경로의 설정 파일을 사용합니다:
    ~/KIS/config/kis_devlp.yaml

프로젝트 루트의 kis_devlp.yaml은 예시/템플릿 파일입니다.
실제 사용을 위해서는 ~/KIS/config/kis_devlp.yaml을 생성해야 합니다.
"""
import os
from pathlib import Path
from typing import Optional


def _parse_env_file(path: Path) -> dict:
    """간단한 .env 파서: KEY=VALUE 형태를 읽어 dict 반환

    - 주석(#)과 빈 줄 무시
    - 값은 따옴표(' or ")로 감싸져 있을 수 있음
    """
    result = {}
    if not path.exists():
        return result

    try:
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # strip optional quotes
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                result[key] = val
    except Exception:
        return {}

    return result


class Config:
    """자동매매 봇 설정 클래스

    - `ENV_MODE`와 `TRADING_ENABLED`는 우선순위로
      실제 환경변수 > 프로젝트 루트의 `.env` > 기본값 순으로 결정됩니다.
    - `.env` 파일 경로: 프로젝트 루트(현재 파일의 부모 부모)/.env
    """

    # 프로젝트 루트 경로
    ROOT_DIR = Path(__file__).parent.parent

    # 기본값
    _DEFAULT_ENV_MODE = "real"
    _DEFAULT_TRADING_ENABLED = False

    # .env 파일에서 값을 읽음
    _env_file = ROOT_DIR / ".env"
    _env_vals = _parse_env_file(_env_file)

    # ENV_MODE: 환경변수 > .env > 기본값
    ENV_MODE = os.environ.get("ENV_MODE", _env_vals.get("ENV_MODE", _DEFAULT_ENV_MODE))

    # TRADING_ENABLED: 환경변수 > .env > 기본값
    _raw_trading = os.environ.get("TRADING_ENABLED", _env_vals.get("TRADING_ENABLED", str(_DEFAULT_TRADING_ENABLED)))
    if isinstance(_raw_trading, bool):
        TRADING_ENABLED = _raw_trading
    else:
        TRADING_ENABLED = str(_raw_trading).strip().lower() in ("1", "true", "yes", "on")

    # 스케줄 설정 (방안 3)
    SCHEDULE_INTERVAL_MINUTES = 5  # 5분마다 전략 실행

    # 거래 시간 설정
    MARKET_OPEN_TIME = "09:00"
    MARKET_CLOSE_TIME = "15:30"

    # 주문 설정
    MAX_POSITION_SIZE = 1000000  # 최대 투자 금액 (100만원)
    MAX_ORDER_AMOUNT = 500000    # 1회 최대 주문 금액 (50만원)

    # 기본 거래소 코드 (예: KRX)
    DEFAULT_EXCHANGE = "KRX"

    # 로깅 설정
    LOG_DIR = Path(__file__).parent / "logs"
    LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR

    # 전략 설정
    STRATEGIES_ENABLED = ["ma_crossover"]  # 활성화할 전략 목록

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
        "459580", # KODEX CD금리액티브(합성)
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
        "488770", # KODEX 머니마켓액티브
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

        return True
