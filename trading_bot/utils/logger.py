"""
로깅 유틸리티
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Union

from trading_bot.config import Config


def _apply_third_party_logger_levels(level: str):
    """외부 라이브러리 로거 레벨 적용"""
    # matplotlib는 폰트 탐색 DEBUG 로그가 매우 많아 별도 레벨로 제어
    mpl_level = getattr(logging, Config.MATPLOTLIB_LOG_LEVEL, logging.WARNING)
    logging.getLogger("matplotlib").setLevel(mpl_level)
    logging.getLogger("matplotlib.font_manager").setLevel(mpl_level)

    # DEBUG 모드일 때만 HTTP 디버그 로그 활성화
    if level == "DEBUG":
        logging.getLogger("urllib3").setLevel(logging.DEBUG)
        logging.getLogger("requests").setLevel(logging.DEBUG)
        logging.getLogger("http.client").setLevel(logging.DEBUG)


def setup_logger(name: str, log_dir: Path, level: str = "INFO"):
    """
    로거 설정
    
    Args:
        name: 로거 이름
        log_dir: 로그 디렉토리
        level: 로그 레벨
    
    Returns:
        logging.Logger: 설정된 로거
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))

    # 포맷 설정 (공통)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- 루트에 단일 RotatingFileHandler 추가 (중복 추가 방지) ---
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))

    # Ensure log directory exists
    log_file_path: Path
    if isinstance(Config.LOG_FILE, (str, Path)):
        log_file_path = Path(Config.LOG_FILE)
    else:
        log_file_path = Path(str(Config.LOG_DIR / "app.log"))

    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Check existing RotatingFileHandler for same filename
    has_rotating = False
    for h in root_logger.handlers:
        if isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", None) == str(log_file_path):
            has_rotating = True
            break

    if not has_rotating:
        rotating_handler = RotatingFileHandler(
            filename=str(log_file_path),
            maxBytes=int(Config.LOG_MAX_BYTES),
            backupCount=int(Config.LOG_BACKUP_COUNT),
            encoding="utf-8",
        )
        rotating_handler.setFormatter(formatter)
        root_logger.addHandler(rotating_handler)

    # JSON 로그 파일 핸들러: 기존 로그파일 이름에 .json 확장자를 붙여 저장
    try:
        json_log_path = Path(str(log_file_path) + ".json")
        has_json = False
        for h in root_logger.handlers:
            if isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", None) == str(json_log_path):
                has_json = True
                break
        if not has_json:
            json_handler = RotatingFileHandler(
                filename=str(json_log_path),
                maxBytes=int(Config.LOG_MAX_BYTES),
                backupCount=int(Config.LOG_BACKUP_COUNT),
                encoding="utf-8",
            )
            json_handler.setFormatter(JsonFormatter())
            root_logger.addHandler(json_handler)
    except Exception:
        # JSON 핸들러에 실패해도 기존 파일 로깅은 유지
        pass

    # Remove duplicate RotatingFileHandler entries pointing to same file (safety)
    seen_files = set()
    for h in list(root_logger.handlers):
        if isinstance(h, RotatingFileHandler):
            fname = getattr(h, "baseFilename", None)
            if fname in seen_files:
                root_logger.removeHandler(h)
            else:
                seen_files.add(fname)

    # Remove any non-file StreamHandler from root logger (basicConfig adds one to stderr)
    console_exists = False
    for h in list(root_logger.handlers):
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            if getattr(h, "stream", None) is sys.stdout:
                console_exists = True
            else:
                root_logger.removeHandler(h)

    # 루트 로거에 콘솔 핸들러 추가 (외부 라이브러리 로그가 콘솔에 나타나게 함)
    if not console_exists:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # --- 외부 라이브러리 로거 설정 ---
    _apply_third_party_logger_levels(level)

    # --- 모듈별 로거 설정: 핸들러 제거하고 전파 활성화 (루트 로거의 핸들러 사용) ---
    # Remove any FileHandler attached directly to the module logger to avoid duplicate files
    for h in list(logger.handlers):
        if isinstance(h, logging.FileHandler):
            logger.removeHandler(h)

    # 모듈 로거의 모든 콘솔 핸들러 제거 (루트 로거의 핸들러로 처리하기 위함)
    # 이렇게 하면 propagate=True일 때 메시지가 두 번 출력되지 않음
    for h in list(logger.handlers):
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            logger.removeHandler(h)

    # Propagate to root logger (root has all handlers: file + console)
    logger.propagate = True

    return logger


def setup_legacy_logger(name: str, log_dir: Path, level: str = "INFO"):
    """
    기존 동작(일별 로그 파일)을 사용하는 레거시 로거 설정.

    - 모듈별로 날짜를 붙인 파일을 생성합니다: `{name}_{YYYYMMDD}.log`
    - 주로 백테스트나 독립 실행 스크립트에서 사용합니다.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))

    # 기존 핸들러 제거
    logger.handlers.clear()

    # 포맷 설정
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 콘솔 핸들러: 중복 StreamHandler(sys.stdout)가 여러 개 붙지 않도록 정리
    seen_console = False
    for h in list(logger.handlers):
        if isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout:
            if seen_console:
                logger.removeHandler(h)
            else:
                seen_console = True

    if not seen_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # 파일 핸들러 (일별 로그)
    log_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    import pytz

    kst = pytz.timezone("Asia/Seoul")
    now_kst = datetime.now(kst)
    log_file = log_dir / f"{name}_{now_kst.strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 파일 핸들러를 사용하므로 전파를 비활성화
    logger.propagate = False

    # 레거시 로거 경로에서도 외부 라이브러리 레벨 제어를 동일하게 적용
    _apply_third_party_logger_levels(level)

    return logger
