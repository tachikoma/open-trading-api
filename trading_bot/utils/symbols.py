from pathlib import Path
import csv
import os
from typing import Dict
from trading_bot.config import Config

# Module-level cache
_SYMBOL_MAP: Dict[str, str] = {}
_LOADED = False


def _default_data_dir() -> Path:
    # trading_bot/data relative to this file
    return Path(__file__).parent.parent / "data"


def load_symbol_map(dir_path: str = None) -> Dict[str, str]:
    """Load symbol->name mapping.

    Priority:
    1. CSV files under `dir_path` (or default trading_bot/data)
    2. Fallback: attempt to load from `stocks_info` master modules
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
    """Return the mapped name for symbol, or empty string if not found.

    This uses the configured `Config.SYMBOL_MAP_DIR` (or repository default)
    and does not accept a directory argument so existing call sites stay unchanged.
    """
    if not symbol:
        return ""
    load_symbol_map()
    key = symbol.strip()
    return _SYMBOL_MAP.get(key, "")


def format_symbol(symbol: str) -> str:
    """Return '이름(종목코드)' if name exists, else original symbol.

    Uses `get_symbol_name()` (which relies on `Config.SYMBOL_MAP_DIR`).
    """
    name = get_symbol_name(symbol)
    if name:
        return f"{name}({symbol})"
    return symbol
