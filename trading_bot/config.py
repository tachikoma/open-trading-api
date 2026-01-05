"""
자동매매 봇 설정 파일

주의: KIS API 인증은 kis_auth.py에서 다음 경로의 설정 파일을 사용합니다:
    ~/KIS/config/kis_devlp.yaml
    
프로젝트 루트의 kis_devlp.yaml은 예시/템플릿 파일입니다.
실제 사용을 위해서는 ~/KIS/config/kis_devlp.yaml을 생성해야 합니다.
"""
import os
from pathlib import Path

class Config:
    """자동매매 봇 설정 클래스"""
    
    # 프로젝트 루트 경로
    ROOT_DIR = Path(__file__).parent.parent
    
    # 실전/모의 구분
    # "real": 실전 투자 (KIS API 내부적으로 prod 사용)
    # "demo": 모의 투자 (KIS API 내부적으로 vps 사용)
    # 개발 단계에서는 'demo' 사용 권장
    ENV_MODE = "demo"  # "real" or "demo"
    
    # 매매 설정
    # 테스트 완료 전까지는 False로 유지하세요!
    TRADING_ENABLED = False  # False로 설정하면 실제 주문 없이 로그만 출력
    
    # 스케줄 설정 (방안 3)
    SCHEDULE_INTERVAL_MINUTES = 5  # 5분마다 전략 실행
    
    # 거래 시간 설정
    MARKET_OPEN_TIME = "09:00"
    MARKET_CLOSE_TIME = "15:30"
    
    # 주문 설정
    MAX_POSITION_SIZE = 1000000  # 최대 투자 금액 (100만원)
    MAX_ORDER_AMOUNT = 500000    # 1회 최대 주문 금액 (50만원)
    
    # 로깅 설정
    LOG_DIR = Path(__file__).parent / "logs"
    LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
    
    # 전략 설정
    STRATEGIES_ENABLED = ["ma_crossover"]  # 활성화할 전략 목록
    
    # 감시 종목 리스트
    WATCH_LIST = [
        "005930",  # 삼성전자
        "000660",  # SK하이닉스
        "035720",  # 카카오
        "035420",  # NAVER
    ]
    
    # 이동평균 전략 설정
    MA_SHORT_PERIOD = 5   # 단기 이동평균 (5일)
    MA_LONG_PERIOD = 20   # 장기 이동평균 (20일)
    
    # 리스크 관리
    STOP_LOSS_PERCENT = 3.0    # 손절 비율 (3%)
    TAKE_PROFIT_PERCENT = 5.0   # 익절 비율 (5%)
    
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
