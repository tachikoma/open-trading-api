from pathlib import Path
import csv
import os
from typing import Dict
from trading_bot.config import Config

# Module-level cache
_SYMBOL_MAP: Dict[str, str] = {}
_LOADED = False


def _default_data_dir() -> Path:
    # trading_bot/data를 기본 데이터 디렉토리로 사용합니다 (이 파일 기준 상대경로)
    return Path(__file__).parent.parent / "data"


def load_symbol_map(dir_path: str = None) -> Dict[str, str]:
    """심볼(종목코드) -> 이름 매핑을 로드합니다.

    우선순위:
    1. `dir_path`(또는 기본 `trading_bot/data`) 아래의 CSV 파일들
    2. 대안으로 `stocks_info` 패키지의 마스터 데이터를 시도해서 로드합니다
    """
    global _SYMBOL_MAP, _LOADED
    if _LOADED:
        return _SYMBOL_MAP

    _SYMBOL_MAP = {}

    # If caller provides dir_path, use it. Otherwise default to Config.SYMBOL_MAP_DIR
    if dir_path:
        data_dir = Path(dir_path)
    else:
        try:
            data_dir = Path(Config.SYMBOL_MAP_DIR)
        except Exception:
            data_dir = _default_data_dir()

    # CSV-first: look for files named symbols_*.csv
    try:
        if data_dir.exists():
            for p in data_dir.glob("symbols_*.csv"):
                try:
                    with p.open("r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            key = row.get("symbol")
                            name = row.get("name")
                            if key and name:
                                _SYMBOL_MAP[key.strip()] = name.strip()
                except Exception:
                    # ignore individual file errors
                    continue
    except Exception:
        pass

    # If CSV didn't provide anything, try stocks_info fallback
    if not _SYMBOL_MAP:
        try:
            # kospi
            from stocks_info.kis_kospi_code_mst import get_kospi_master

            df = get_kospi_master()
            if df is not None:
                for _, r in df.iterrows():
                    try:
                        code = str(r.get("isu_cd") or r.get("isu_cd_cd") or r.get("code") or "").strip()
                        name = str(r.get("kor_isu_nm") or r.get("isu_nm") or r.get("name") or "").strip()
                        if code and name:
                            _SYMBOL_MAP[code] = name
                    except Exception:
                        continue
        except Exception:
            # ignore if module not available
            pass

        try:
            # kosdaq
            from stocks_info.kis_kosdaq_code_mst import get_kosdaq_master

            df = get_kosdaq_master()
            if df is not None:
                for _, r in df.iterrows():
                    try:
                        code = str(r.get("isu_cd") or r.get("code") or "").strip()
                        name = str(r.get("kor_isu_nm") or r.get("isu_nm") or r.get("name") or "").strip()
                        if code and name:
                            _SYMBOL_MAP[code] = name
                    except Exception:
                        continue
        except Exception:
            pass

    _LOADED = True
    return _SYMBOL_MAP


def get_symbol_name(symbol: str) -> str:
    """주어진 종목코드의 매핑된 이름을 반환합니다.

    찾지 못하면 빈 문자열을 반환합니다. 내부적으로 `Config.SYMBOL_MAP_DIR` 또는
    저장소 기본 위치를 사용합니다. 기존 호출부와 호환되도록 디렉토리 인자는 받지 않습니다.
    """
    if not symbol:
        return ""
    load_symbol_map()
    key = symbol.strip()
    return _SYMBOL_MAP.get(key, "")


def format_symbol(symbol: str, dir_path: str = None) -> str:
    """이름이 존재하면 '이름(종목코드)' 형식으로 반환하고, 없으면 원래 symbol을 반환합니다.

    선택적으로 `dir_path`를 전달하면 해당 디렉토리의 CSV를 우선 사용하여 매핑을 로드합니다.
    """
    if not symbol:
        return ""

    # dir_path가 주어지면 명시적으로 해당 디렉토리에서 매핑을 로드합니다.
    if dir_path:
        load_symbol_map(dir_path)
    else:
        load_symbol_map()

    key = symbol.strip()
    name = _SYMBOL_MAP.get(key, "")
    if name:
        return f"{name}({symbol})"
    return symbol
