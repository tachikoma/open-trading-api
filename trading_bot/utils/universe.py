"""
국내주식 유니버스 생성/캐시 유틸리티.

- KOSPI/KOSDAQ 전체 종목
- KOSPI200/KOSDAQ150 구성 종목(마스터 플래그 기반)
를 일자별 캐시 파일로 관리합니다.
"""

from __future__ import annotations

import io
import re
import ssl
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


KOSPI_MASTER_ZIP_URL = "https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip"
KOSDAQ_MASTER_ZIP_URL = "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip"


@dataclass
class UniverseResult:
    symbols: list[str]
    csv_path: Optional[Path]
    target: str
    source: str


def _download_master_zip(url: str, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib.request.urlretrieve(url, str(zip_path))


def _extract_zip(zip_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)


def _parse_master_file(mst_path: Path, right_len: int, part1_layout: list[tuple[str, int, int]]) -> tuple[pd.DataFrame, str]:
    left_rows: list[str] = []
    right_rows: list[str] = []

    with open(mst_path, mode="r", encoding="cp949") as f:
        for row in f:
            line = row.rstrip("\n")
            left = line[:-right_len]
            right = line[-right_len:]
            parsed = []
            for _, start, end in part1_layout:
                parsed.append(left[start:end].rstrip())
            left_rows.append(",".join(parsed))
            right_rows.append(right)

    left_df = pd.read_csv(io.StringIO("\n".join(left_rows)), header=None, encoding="cp949")
    right_text = "\n".join(right_rows)
    return left_df, right_text


def _load_kospi_master(raw_dir: Path) -> pd.DataFrame:
    zip_path = raw_dir / "kospi_code.zip"
    mst_path = raw_dir / "kospi_code.mst"

    _download_master_zip(KOSPI_MASTER_ZIP_URL, zip_path)
    _extract_zip(zip_path, raw_dir)

    left_layout = [
        ("단축코드", 0, 9),
        ("표준코드", 9, 21),
        ("한글명", 21, 10_000),
    ]

    left_df, right_text = _parse_master_file(mst_path, right_len=228, part1_layout=left_layout)
    left_df.columns = ["단축코드", "표준코드", "한글명"]

    field_specs = [
        2, 1, 4, 4, 4,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 1,
        1, 9, 5, 5, 1,
        1, 1, 2, 1, 1,
        1, 2, 2, 2, 3,
        1, 3, 12, 12, 8,
        15, 21, 2, 7, 1,
        1, 1, 1, 1, 9,
        9, 9, 5, 9, 8,
        9, 3, 1, 1, 1,
    ]
    right_cols = [
        "그룹코드", "시가총액규모", "지수업종대분류", "지수업종중분류", "지수업종소분류",
        "제조업", "저유동성", "지배구조지수종목", "KOSPI200섹터업종", "KOSPI100",
        "KOSPI50", "KRX", "ETP", "ELW발행", "KRX100",
        "KRX자동차", "KRX반도체", "KRX바이오", "KRX은행", "SPAC",
        "KRX에너지화학", "KRX철강", "단기과열", "KRX미디어통신", "KRX건설",
        "Non1", "KRX증권", "KRX선박", "KRX섹터_보험", "KRX섹터_운송",
        "SRI", "기준가", "매매수량단위", "시간외수량단위", "거래정지",
        "정리매매", "관리종목", "시장경고", "경고예고", "불성실공시",
        "우회상장", "락구분", "액면변경", "증자구분", "증거금비율",
        "신용가능", "신용기간", "전일거래량", "액면가", "상장일자",
        "상장주수", "자본금", "결산월", "공모가", "우선주",
        "공매도과열", "이상급등", "KRX300", "KOSPI", "매출액",
        "영업이익", "경상이익", "당기순이익", "ROE", "기준년월",
        "시가총액", "그룹사코드", "회사신용한도초과", "담보대출가능", "대주가능",
    ]

    right_df = pd.read_fwf(io.StringIO(right_text), widths=field_specs, names=right_cols)
    return pd.merge(left_df, right_df, how="outer", left_index=True, right_index=True)


def _load_kosdaq_master(raw_dir: Path) -> pd.DataFrame:
    zip_path = raw_dir / "kosdaq_code.zip"
    mst_path = raw_dir / "kosdaq_code.mst"

    _download_master_zip(KOSDAQ_MASTER_ZIP_URL, zip_path)
    _extract_zip(zip_path, raw_dir)

    left_layout = [
        ("단축코드", 0, 9),
        ("표준코드", 9, 21),
        ("한글종목명", 21, 10_000),
    ]

    left_df, right_text = _parse_master_file(mst_path, right_len=222, part1_layout=left_layout)
    left_df.columns = ["단축코드", "표준코드", "한글종목명"]

    field_specs = [
        2, 1,
        4, 4, 4, 1, 1,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 9,
        5, 5, 1, 1, 1,
        2, 1, 1, 1, 2,
        2, 2, 3, 1, 3,
        12, 12, 8, 15, 21,
        2, 7, 1, 1, 1,
        1, 9, 9, 9, 5,
        9, 8, 9, 3, 1,
        1, 1,
    ]
    right_cols = [
        "증권그룹구분코드", "시가총액규모", "지수업종대분류", "지수업종중분류", "지수업종소분류",
        "벤처기업", "저유동성", "KRX", "ETP", "KRX100",
        "KRX자동차", "KRX반도체", "KRX바이오", "KRX은행", "SPAC",
        "KRX에너지화학", "KRX철강", "단기과열", "KRX미디어통신", "KRX건설",
        "투자주의환기", "KRX증권", "KRX선박", "KRX섹터보험", "KRX섹터운송",
        "KOSDAQ150", "기준가", "매매수량단위", "시간외수량단위", "거래정지",
        "정리매매", "관리종목", "시장경고", "경고예고", "불성실공시",
        "우회상장", "락구분", "액면변경", "증자구분", "증거금비율",
        "신용가능", "신용기간", "전일거래량", "액면가", "상장일자",
        "상장주수", "자본금", "결산월", "공모가", "우선주",
        "공매도과열", "이상급등", "KRX300", "매출액", "영업이익",
        "경상이익", "당기순이익", "ROE", "기준년월", "시가총액",
        "그룹사코드", "회사신용한도초과", "담보대출가능", "대주가능",
    ]

    right_df = pd.read_fwf(io.StringIO(right_text), widths=field_specs, names=right_cols)
    return pd.merge(left_df, right_df, how="outer", left_index=True, right_index=True)


def _clean_symbols(df: pd.DataFrame, code_col: str, name_col: str, market: str) -> pd.DataFrame:
    out = df[[code_col, name_col]].copy()
    out = out.rename(columns={code_col: "symbol", name_col: "name"})
    out = out.copy()
    out.loc[:, "symbol"] = out["symbol"].astype(str).str.strip()
    out.loc[:, "name"] = out["name"].astype(str).str.strip()
    out = out[out["symbol"].str.match(r"^\d{6}$", na=False)]
    out = out.drop_duplicates(subset=["symbol"]).reset_index(drop=True)
    out["market"] = market
    return out


def _is_true_series(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip().str.upper()
    return (~text.isin(["", "0", "N", "NAN", "NONE"]))


def _load_listing_fdr(market: str) -> pd.DataFrame:
    import FinanceDataReader as fdr

    df = fdr.StockListing(market)
    if df is None or df.empty:
        return pd.DataFrame(columns=["symbol", "name", "market"])

    code_col = "Code" if "Code" in df.columns else "symbol"
    name_col = "Name" if "Name" in df.columns else "name"
    out = df[[code_col, name_col]].copy()
    out = out.rename(columns={code_col: "symbol", name_col: "name"})
    out.loc[:, "symbol"] = out["symbol"].astype(str).str.strip()
    out.loc[:, "name"] = out["name"].astype(str).str.strip()
    out = out[out["symbol"].str.match(r"^\d{6}$", na=False)]
    out = out.drop_duplicates(subset=["symbol"]).reset_index(drop=True)
    out.loc[:, "market"] = market.upper()
    return out


def _find_index_ticker_by_name(target_name: str) -> Optional[str]:
    from pykrx import stock

    date = datetime.now().strftime("%Y%m%d")
    all_tickers = []
    for market in ["KOSPI", "KOSDAQ", "KRX", "테마"]:
        try:
            all_tickers.extend(stock.get_index_ticker_list(date=date, market=market))
        except Exception:
            continue

    target_compact = target_name.replace(" ", "")
    for ticker in all_tickers:
        try:
            name = stock.get_index_ticker_name(ticker)
        except Exception:
            continue
        if name and target_compact in name.replace(" ", ""):
            return ticker
    return None


def _load_index_constituents_pykrx(index_name: str) -> list[str]:
    from pykrx import stock

    date = datetime.now().strftime("%Y%m%d")
    ticker = _find_index_ticker_by_name(index_name)
    if not ticker:
        raise ValueError(f"인덱스 티커를 찾을 수 없습니다: {index_name}")

    symbols = stock.get_index_portfolio_deposit_file(ticker, date)
    symbols = [str(s).strip() for s in symbols if re.match(r"^\d{6}$", str(s).strip())]
    return sorted(list(dict.fromkeys(symbols)))


def _build_universe_df(target: str, raw_dir: Path) -> pd.DataFrame:
    target = target.lower()
    valid_targets = {
        "kospi",
        "kosdaq",
        "kospi_kosdaq",
        "all",
        "kospi200",
        "kosdaq150",
        "kospi200_kosdaq150",
    }
    if target not in valid_targets:
        raise ValueError(f"지원하지 않는 유니버스 타깃: {target}")

    need_kospi = target in {"kospi", "kospi_kosdaq", "all", "kospi200", "kospi200_kosdaq150"}
    need_kosdaq = target in {"kosdaq", "kospi_kosdaq", "all", "kosdaq150", "kospi200_kosdaq150"}

    # 1) 전체 시장 유니버스는 FDR 상장목록 사용 (안정적)
    if target in {"kospi", "kosdaq", "kospi_kosdaq", "all"}:
        fdr_frames = []
        if need_kospi:
            fdr_frames.append(_load_listing_fdr("KOSPI"))
        if need_kosdaq:
            fdr_frames.append(_load_listing_fdr("KOSDAQ"))
        out = pd.concat(fdr_frames, ignore_index=True) if fdr_frames else pd.DataFrame(columns=["symbol", "name", "market"])
        out = out.drop_duplicates(subset=["symbol"]).sort_values("symbol").reset_index(drop=True)
        return out

    # 2) 지수 구성종목은 pykrx를 우선 사용 (정확한 구성종목)
    if target in {"kospi200", "kosdaq150", "kospi200_kosdaq150"}:
        try:
            kospi_listing = _load_listing_fdr("KOSPI")
            kosdaq_listing = _load_listing_fdr("KOSDAQ")
            listing = pd.concat([kospi_listing, kosdaq_listing], ignore_index=True)

            symbols = []
            if target in {"kospi200", "kospi200_kosdaq150"}:
                symbols.extend(_load_index_constituents_pykrx("코스피200"))
            if target in {"kosdaq150", "kospi200_kosdaq150"}:
                symbols.extend(_load_index_constituents_pykrx("코스닥150"))

            symbols = sorted(list(dict.fromkeys(symbols)))
            out = listing[listing["symbol"].isin(symbols)].copy()
            out = out.drop_duplicates(subset=["symbol"]).sort_values("symbol").reset_index(drop=True)
            return out
        except Exception:
            # pykrx 실패 시 마스터 플래그 기반으로 폴백
            pass

    frames = []

    if need_kospi:
        kospi_df = _load_kospi_master(raw_dir)
        if target in {"kospi200", "kospi200_kosdaq150"}:
            kospi_df = kospi_df[_is_true_series(kospi_df["KOSPI200섹터업종"])]
        frames.append(_clean_symbols(kospi_df, code_col="단축코드", name_col="한글명", market="KOSPI"))

    if need_kosdaq:
        kosdaq_df = _load_kosdaq_master(raw_dir)
        if target in {"kosdaq150", "kospi200_kosdaq150"}:
            kosdaq_df = kosdaq_df[_is_true_series(kosdaq_df["KOSDAQ150"])]
        frames.append(_clean_symbols(kosdaq_df, code_col="단축코드", name_col="한글종목명", market="KOSDAQ"))

    if not frames:
        return pd.DataFrame(columns=["symbol", "name", "market"])

    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset=["symbol"]).sort_values("symbol").reset_index(drop=True)
    return out


def resolve_universe_symbols(
    target: str,
    default_symbols: list[str],
    cache_dir: Path,
    refresh_daily: bool = True,
    max_symbols: int = 0,
    force_refresh: bool = False,
    logger=None,
) -> UniverseResult:
    """
    유니버스 종목코드를 반환합니다.

    target:
    - watchlist: default_symbols 반환
    - kospi/kosdaq/kospi_kosdaq(all)
    - kospi200/kosdaq150/kospi200_kosdaq150
    """
    target = (target or "watchlist").lower()

    if target == "watchlist":
        symbols = list(default_symbols)
        if max_symbols and max_symbols > 0:
            symbols = symbols[:max_symbols]
        return UniverseResult(symbols=symbols, csv_path=None, target=target, source="watchlist")

    date_key = datetime.now().strftime("%Y%m%d")
    cache_dir.mkdir(parents=True, exist_ok=True)

    if refresh_daily:
        csv_path = cache_dir / f"universe_{target}_{date_key}.csv"
    else:
        csv_path = cache_dir / f"universe_{target}.csv"

    universe_df = None
    if csv_path.exists() and not force_refresh:
        try:
            universe_df = pd.read_csv(csv_path, dtype={"symbol": str})
        except Exception:
            universe_df = None

    if universe_df is None or universe_df.empty:
        raw_dir = cache_dir / "raw" / date_key
        universe_df = _build_universe_df(target, raw_dir=raw_dir)
        universe_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        if logger:
            logger.info(f"유니버스 파일 생성: {csv_path} ({len(universe_df)}종목)")
    else:
        if logger:
            logger.info(f"유니버스 파일 재사용: {csv_path} ({len(universe_df)}종목)")

    symbols = universe_df["symbol"].astype(str).str.strip().tolist()
    symbols = [s for s in symbols if re.match(r"^\d{6}$", s)]

    if max_symbols and max_symbols > 0:
        symbols = symbols[:max_symbols]

    return UniverseResult(symbols=symbols, csv_path=csv_path, target=target, source="cache")
