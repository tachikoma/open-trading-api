"""
백테스트 데이터 소스 모듈

SQLite DB, KIS API, 또는 FinanceDataReader에서 과거 데이터를 로드합니다.
"""
import sqlite3
import pandas as pd
import warnings
from pathlib import Path
from trading_bot.config import Config
from typing import Optional, Dict
from datetime import datetime


class BacktestDataSource:
    """백테스트 데이터 소스 클래스"""
    
    @staticmethod
    def load_from_fdr(symbols: list, start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """
        FinanceDataReader에서 과거 데이터 로드
        
        Args:
            symbols: 종목 코드 리스트
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
        
        Returns:
            {종목코드: DataFrame} 딕셔너리
            
        Note:
            FinanceDataReader 설치 필요: uv pip install finance-datareader
        """
        try:
            import FinanceDataReader as fdr
        except ImportError:
            print("❌ FinanceDataReader가 설치되지 않았습니다")
            print("   설치: uv pip install finance-datareader")
            return {}
        
        historical_data = {}

        # 캐시 디렉토리 사용: FinanceDataReader 결과를 Parquet로 저장/재사용
        cache_dir = Config.FDR_CACHE_DIR if hasattr(Config, 'FDR_CACHE_DIR') else Path(__file__).parent / 'data' / 'fdr_cache'
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        
        # 날짜 형식 변환 (YYYYMMDD -> YYYY-MM-DD)
        start_dt = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")
        
        for symbol in symbols:
            try:
                cache_file = cache_dir / f"{symbol}.parquet"
                csv_cache = cache_file.with_suffix('.csv')

                # 캐시(Parquet/CSV) 전체 내용을 우선 로드해 범위가 요청 기간을 포함하는지 확인
                cached_df = None
                try:
                    # 둘 다 있으면 최신 파일 우선
                    if cache_file.exists() and csv_cache.exists():
                        p_mtime = cache_file.stat().st_mtime
                        c_mtime = csv_cache.stat().st_mtime
                        use_csv = c_mtime >= p_mtime
                    elif csv_cache.exists():
                        use_csv = True
                    else:
                        use_csv = False

                    if use_csv:
                        try:
                            cached_df = pd.read_csv(csv_cache, parse_dates=['date'])
                            if 'date' in cached_df.columns:
                                cached_df['date'] = pd.to_datetime(cached_df['date'])
                        except Exception:
                            cached_df = None
                    else:
                        try:
                            if cache_file.exists():
                                cached_df = pd.read_parquet(cache_file)
                                if 'date' in cached_df.columns:
                                    cached_df['date'] = pd.to_datetime(cached_df['date'])
                        except Exception:
                            # parquet 읽기 실패 시 CSV로 재시도
                            if csv_cache.exists():
                                try:
                                    cached_df = pd.read_csv(csv_cache, parse_dates=['date'])
                                    if 'date' in cached_df.columns:
                                        cached_df['date'] = pd.to_datetime(cached_df['date'])
                                except Exception:
                                    cached_df = None
                except Exception:
                    cached_df = None

                if cached_df is not None:
                    try:
                        cached_min = cached_df['date'].min()
                        cached_max = cached_df['date'].max()
                        req_start = pd.to_datetime(start_dt)
                        req_end = pd.to_datetime(end_dt)

                        # 캐시가 요청 범위를 완전 포함하면 캐시를 사용
                        if (cached_min <= req_start) and (cached_max >= req_end):
                            df = cached_df[(cached_df['date'] >= req_start) & (cached_df['date'] <= req_end)]
                            print(f"✅ {symbol}: {len(df)}건 로드됨 (FDR 캐시)")
                            historical_data[symbol] = df
                            continue

                        # 누락된 구간(앞/뒤/중간)을 찾아 필요한 부분만 다운로드하여 병합
                        missing_ranges = []

                        # 앞쪽 누락
                        if req_start < cached_min:
                            missing_ranges.append((req_start, min(req_end, cached_min - pd.Timedelta(days=1))))

                        # 뒤쪽 누락
                        if req_end > cached_max:
                            missing_ranges.append((max(req_start, cached_max + pd.Timedelta(days=1)), req_end))

                        # 내부 결손 검사: 요청 구간의 전체 영업일과 캐시된 날짜를 비교
                        try:
                            full_range = pd.bdate_range(req_start, req_end)
                            cached_dates = pd.to_datetime(cached_df['date'])
                            cached_set = set(d.date() for d in cached_dates if (d >= req_start and d <= req_end))
                            missing_dates = [d for d in full_range if d.date() not in cached_set]
                            if missing_dates:
                                # 연속된 누락일들을 범위로 묶기
                                start_md = missing_dates[0]
                                prev = missing_dates[0]
                                for cur in missing_dates[1:]:
                                    if (cur - prev).days > 1:
                                        missing_ranges.append((start_md, prev))
                                        start_md = cur
                                    prev = cur
                                missing_ranges.append((start_md, prev))
                        except Exception:
                            pass

                        # 중복 범위 제거 및 정렬
                        if missing_ranges:
                            # normalize ranges to within req_start/req_end
                            norm = []
                            for s, e in missing_ranges:
                                s = max(s, req_start)
                                e = min(e, req_end)
                                if s <= e:
                                    norm.append((s, e))
                            # merge overlapping
                            norm.sort()
                            merged = []
                            for s, e in norm:
                                if not merged:
                                    merged.append([s, e])
                                else:
                                    if s <= merged[-1][1] + pd.Timedelta(days=1):
                                        merged[-1][1] = max(merged[-1][1], e)
                                    else:
                                        merged.append([s, e])

                            # 실제로 다운로드할 범위 목록
                            download_ranges = [(m[0], m[1]) for m in merged]

                            fetched_parts = []
                            for ds, de in download_ranges:
                                ds_str = ds.strftime("%Y-%m-%d")
                                de_str = de.strftime("%Y-%m-%d")
                                print(f"📥 {symbol} 누락 구간 다운로드: {ds_str} ~ {de_str}")
                                with warnings.catch_warnings():
                                    warnings.filterwarnings(
                                        "ignore",
                                        message=".*ChainedAssignmentError.*",
                                        category=FutureWarning,
                                    )
                                    part = fdr.DataReader(symbol, ds_str, de_str)
                                if part is None or part.empty:
                                    continue
                                part = part.reset_index().rename(columns={
                                    'Date': 'date',
                                    'Open': 'stck_oprc',
                                    'High': 'stck_hgpr',
                                    'Low': 'stck_lwpr',
                                    'Close': 'stck_clpr',
                                    'Volume': 'acml_vol'
                                }).copy()
                                if 'date' in part.columns:
                                    part['date'] = pd.to_datetime(part['date'])
                                    part.loc[:, 'stck_bsop_date'] = part['date'].dt.strftime('%Y%m%d')
                                fetched_parts.append(part)

                            # 병합 및 저장
                            if fetched_parts:
                                all_parts = [cached_df] + fetched_parts
                                merged_df = pd.concat(all_parts, ignore_index=True)
                                merged_df = merged_df.drop_duplicates(subset=['date'])
                                merged_df = merged_df.sort_values('date').reset_index(drop=True)
                                # 캐시 업데이트: CSV로 먼저 저장(항상 시도), parquet은 선택적으로 시도
                                # 캐시 업데이트: 먼저 CSV로 안전하게 저장한 뒤 parquet를 원자적으로 교체 시도
                                try:
                                    csv_cache = cache_file.with_suffix('.csv')
                                    tmp_csv = csv_cache.with_suffix('.csv.tmp')
                                    merged_df.to_csv(tmp_csv, index=False)
                                    tmp_csv.replace(csv_cache)
                                    print(f"ℹ️  {symbol}: CSV 캐시에 저장됨 ({csv_cache})")
                                    # CSV 저장 후 기존 parquet 제거(있다면)
                                    try:
                                        if cache_file.exists():
                                            cache_file.unlink()
                                    except Exception:
                                        pass
                                except Exception as e:
                                    print(f"⚠️  {symbol}: CSV 저장 실패: {e}")

                                # parquet는 pyarrow 엔진으로 임시파일에 쓰고 교체
                                try:
                                    tmp_parquet = cache_file.with_suffix('.parquet.tmp')
                                    try:
                                        merged_df.to_parquet(tmp_parquet, engine='pyarrow', index=False)
                                    except Exception:
                                        # pyarrow 지정이 실패하면 엔진 지정 없이 재시도
                                        merged_df.to_parquet(tmp_parquet, index=False)
                                    tmp_parquet.replace(cache_file)
                                    print(f"ℹ️  {symbol}: Parquet 캐시에 저장됨 ({cache_file})")
                                except Exception as e:
                                    print(f"⚠️  {symbol}: Parquet 저장 실패: {e}")

                                # 요청 기간 잘라서 결과로 사용
                                df = merged_df[(merged_df['date'] >= req_start) & (merged_df['date'] <= req_end)].copy()
                                print(f"✅ {symbol}: {len(df)}건 로드됨 (FDR 캐시+증분)")
                                historical_data[symbol] = df
                                continue
                        # 다운로드할 누락 구간이 없고 캐시가 범위를 완전 포함하지 않는다면 재다운로드
                        print(f"ℹ️  {symbol}: 캐시 범위 불충분 ({cached_min.date()}~{cached_max.date()}), 전체 기간 재다운로드")
                        cached_df = None
                    except Exception:
                        # 검사 중 문제 발생 시 캐시 무시하고 재다운로드
                        cached_df = None

                print(f"📥 {symbol} 데이터 다운로드 중 (FinanceDataReader)...")

                # FinanceDataReader로 데이터 가져오기
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message=".*ChainedAssignmentError.*",
                        category=FutureWarning,
                    )
                    df = fdr.DataReader(symbol, start_dt, end_dt)
                
                if df is None or df.empty:
                    print(f"⚠️  {symbol}: 데이터 없음")
                    continue
                
                # KIS API 형식에 맞게 컬럼 변환
                df = df.reset_index()
                df = df.rename(columns={
                    'Date': 'date',
                    'Open': 'stck_oprc',
                    'High': 'stck_hgpr',
                    'Low': 'stck_lwpr',
                    'Close': 'stck_clpr',
                    'Volume': 'acml_vol'
                }).copy()
                
                # 날짜 형식 처리
                if 'date' in df.columns:
                    converted_date = pd.to_datetime(df['date'])
                    df.loc[:, 'stck_bsop_date'] = converted_date.dt.strftime('%Y%m%d')
                    df.loc[:, 'date'] = converted_date
                
                historical_data[symbol] = df
                print(f"✅ {symbol}: {len(df)}건 로드됨 (FDR)")

                # 다운로드 성공 시 캐시에 저장 (원자적 저장: CSV 먼저, parquet 시도)
                try:
                    csv_cache = cache_file.with_suffix('.csv')
                    tmp_csv = csv_cache.with_suffix('.csv.tmp')
                    df.to_csv(tmp_csv, index=False)
                    tmp_csv.replace(csv_cache)
                    print(f"ℹ️  {symbol}: CSV 캐시에 저장됨 ({csv_cache})")
                except Exception as e:
                    print(f"⚠️  {symbol}: CSV 저장 실패: {e}")

                try:
                    tmp_parquet = cache_file.with_suffix('.parquet.tmp')
                    try:
                        df.to_parquet(tmp_parquet, engine='pyarrow', index=False)
                    except Exception:
                        df.to_parquet(tmp_parquet, index=False)
                    tmp_parquet.replace(cache_file)
                    print(f"ℹ️  {symbol}: Parquet 캐시에 저장됨 ({cache_file})")
                except Exception as e:
                    print(f"⚠️  {symbol}: Parquet 저장 실패: {e}")

                # API 호출 제한 대응
                import time
                time.sleep(0.1)
                
            except Exception as e:
                print(f"⚠️  {symbol} 다운로드 실패: {e}")
                continue
        
        return historical_data
    
    @staticmethod
    def load_from_sqlite(db_path: Path, symbols: list, start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """
        SQLite DB에서 과거 데이터 로드
        
        Args:
            db_path: SQLite DB 파일 경로
            symbols: 종목 코드 리스트
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
        
        Returns:
            {종목코드: DataFrame} 딕셔너리
            
        DB 스키마 (두 가지 형식 지원):
        
        1. 통합 테이블 형식:
            CREATE TABLE stock_daily (
                symbol TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (symbol, date)
            );
        
        2. 종목별 테이블 형식 (현재 DB):
            CREATE TABLE "005930" (
                index TEXT,   -- 날짜 (YYYYMMDD)
                open INTEGER,
                high INTEGER,
                low INTEGER,
                close INTEGER,
                volume INTEGER
            );
        """
        if not db_path.exists():
            raise FileNotFoundError(f"DB 파일을 찾을 수 없습니다: {db_path}")
        
        conn = sqlite3.connect(db_path)
        historical_data = {}
        
        try:
            # 테이블 목록 확인
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cursor.fetchall()]
            
            # 통합 테이블 형식인지 확인
            if 'stock_daily' in tables:
                # 통합 테이블 형식
                for symbol in symbols:
                    start_dt = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
                    end_dt = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")
                    
                    query = """
                        SELECT 
                            symbol,
                            date,
                            open as stck_oprc,
                            high as stck_hgpr,
                            low as stck_lwpr,
                            close as stck_clpr,
                            volume as acml_vol
                        FROM stock_daily
                        WHERE symbol = ? 
                        AND date BETWEEN ? AND ?
                        ORDER BY date
                    """
                    
                    df = pd.read_sql_query(query, conn, params=(symbol, start_dt, end_dt))
                    
                    if not df.empty:
                        df = df.copy()
                        converted_date = pd.to_datetime(df['date'])
                        df.loc[:, 'stck_bsop_date'] = converted_date.dt.strftime('%Y%m%d')
                        df.loc[:, 'date'] = converted_date
                        historical_data[symbol] = df
                        print(f"✅ {symbol}: {len(df)}건 로드됨 (DB-통합)")
                    else:
                        print(f"⚠️  {symbol}: DB에 데이터 없음")
            else:
                # 종목별 테이블 형식
                for symbol in symbols:
                    # 테이블명으로 종목코드 사용
                    if symbol not in tables:
                        print(f"⚠️  {symbol}: 테이블 없음")
                        continue
                    
                    # 날짜 범위 조건
                    start_dt = start_date  # YYYYMMDD 그대로 사용
                    end_dt = end_date
                    
                    query = f"""
                        SELECT 
                            [index] as date_str,
                            open as stck_oprc,
                            high as stck_hgpr,
                            low as stck_lwpr,
                            close as stck_clpr,
                            volume as acml_vol
                        FROM "{symbol}"
                        WHERE [index] BETWEEN ? AND ?
                        ORDER BY [index]
                    """
                    
                    df = pd.read_sql_query(query, conn, params=(start_dt, end_dt))
                    
                    if not df.empty:
                        # 날짜 컬럼 처리 (.copy()로 경고 방지)
                        df = df.copy()
                        df['stck_bsop_date'] = df['date_str']
                        df['date'] = pd.to_datetime(df['date_str'], format='%Y%m%d')
                        df = df.drop('date_str', axis=1)
                        historical_data[symbol] = df
                        print(f"✅ {symbol}: {len(df)}건 로드됨 (DB)")
                    else:
                        print(f"⚠️  {symbol}: DB에 데이터 없음")
        
        finally:
            conn.close()
        
        return historical_data
    
    @staticmethod
    def load_from_api(broker, symbols: list, start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """
        KIS API에서 과거 데이터 로드 (최대 100건)
        
        Args:
            broker: KISBroker 인스턴스
            symbols: 종목 코드 리스트
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
        
        Returns:
            {종목코드: DataFrame} 딕셔너리
        """
        historical_data = {}
        
        for i, symbol in enumerate(symbols):
            # API 호출 제한 대응
            if i > 0:
                import time
                time.sleep(0.2)
            
            df = broker.get_period_price(symbol, start_date, end_date, period="D")
            
            if df is None or df.empty:
                print(f"⚠️  {symbol} 데이터 로드 실패 (API)")
                continue
            
            # 날짜 컬럼 추가
            df = df.copy()
            df.loc[:, 'date'] = pd.to_datetime(df['stck_bsop_date'], format='%Y%m%d')
            
            # 날짜 필터링
            start_dt = pd.to_datetime(start_date, format='%Y%m%d')
            end_dt = pd.to_datetime(end_date, format='%Y%m%d')
            df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]
            df = df.sort_values('date')
            
            historical_data[symbol] = df
            print(f"✅ {symbol}: {len(df)}건 로드됨 (API)")
        
        return historical_data
    
    @staticmethod
    def create_sample_db(db_path: Path, symbols: list, broker=None):
        """
        샘플 DB 생성 (API 데이터를 SQLite로 저장)
        
        Args:
            db_path: 저장할 DB 파일 경로
            symbols: 종목 코드 리스트
            broker: KISBroker 인스턴스
        """
        if db_path.exists():
            print(f"⚠️  DB 파일이 이미 존재합니다: {db_path}")
            overwrite = input("덮어쓰시겠습니까? (y/N): ")
            if overwrite.lower() != 'y':
                return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_daily (
                symbol TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol_date 
            ON stock_daily(symbol, date)
        """)
        
        conn.commit()
        
        if broker is None:
            print("⚠️  Broker가 없어 샘플 데이터를 생성할 수 없습니다")
            conn.close()
            return
        
        # API에서 데이터 가져와서 저장
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)  # 1년
        
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        
        for i, symbol in enumerate(symbols):
            print(f"📥 {symbol} 데이터 가져오는 중...")
            
            if i > 0:
                import time
                time.sleep(0.2)
            
            df = broker.get_period_price(symbol, start_str, end_str, period="D")
            
            if df is None or df.empty:
                print(f"⚠️  {symbol} 데이터 없음")
                continue
            
            # DB에 저장
            for _, row in df.iterrows():
                date_str = pd.to_datetime(row['stck_bsop_date'], format='%Y%m%d').strftime('%Y-%m-%d')
                
                cursor.execute("""
                    INSERT OR REPLACE INTO stock_daily 
                    (symbol, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    date_str,
                    float(row['stck_oprc']),
                    float(row['stck_hgpr']),
                    float(row['stck_lwpr']),
                    float(row['stck_clpr']),
                    int(row['acml_vol']) if 'acml_vol' in row else 0
                ))
            
            conn.commit()
            print(f"✅ {symbol}: {len(df)}건 저장됨")
        
        conn.close()
        print(f"\n✅ DB 파일 생성 완료: {db_path}")
