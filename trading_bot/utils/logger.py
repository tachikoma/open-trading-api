"""
로깅 유틸리티
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Union

from trading_bot.config import Config


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

    # --- 모듈별 로거 설정: 콘솔 출력만 추가하고 파일은 루트 핸들러로 전파 ---
    # Remove any FileHandler attached directly to the module logger to avoid duplicate files
    for h in list(logger.handlers):
        if isinstance(h, logging.FileHandler):
            logger.removeHandler(h)

    # Ensure only one console handler (stream=sys.stdout)
    seen_console = False
    for h in list(logger.handlers):
        if isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout:
            if seen_console:
                logger.removeHandler(h)   # 중복된 핸들러 제거
            else:
                seen_console = True

    if not seen_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Let messages bubble up to root (where rotating file handler lives)
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

    return logger
