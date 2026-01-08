"""
백테스트 데이터 소스 모듈

SQLite DB, KIS API, 또는 FinanceDataReader에서 과거 데이터를 로드합니다.
"""
import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
import time
import random


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
        
        # 날짜 형식 변환 (YYYYMMDD -> YYYY-MM-DD)
        start_dt = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")
        
        for symbol in symbols:
            try:
                print(f"📥 {symbol} 데이터 다운로드 중 (FinanceDataReader)...")
                
                # FinanceDataReader로 데이터 가져오기
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
                })
                
                # 날짜 형식 처리
                if 'date' in df.columns:
                    df['stck_bsop_date'] = pd.to_datetime(df['date']).dt.strftime('%Y%m%d')
                    df['date'] = pd.to_datetime(df['date'])
                
                historical_data[symbol] = df
                print(f"✅ {symbol}: {len(df)}건 로드됨 (FDR)")
                
                # API 호출 제한 대응
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
                        df['stck_bsop_date'] = pd.to_datetime(df['date']).dt.strftime('%Y%m%d')
                        df['date'] = pd.to_datetime(df['date'])
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

        # 날짜 파싱
        start_dt = pd.to_datetime(start_date, format='%Y%m%d')
        end_dt = pd.to_datetime(end_date, format='%Y%m%d')

        for i, symbol in enumerate(symbols):
            # per-symbol rate limit 완화
            if i > 0:
                time.sleep(0.2)

            parts = []
            # 역순 페이징: 종료일(end_date)에서 과거로 100일 단위 요청
            current = end_dt
            print(f"📥 {symbol} 데이터 다운로드 중 (API, 역순 100일 단위 페이징)...")

            # 청크 크기: 100일(포함)
            while current >= start_dt:
                chunk_start = max(start_dt, current - pd.Timedelta(days=99))
                s = chunk_start.strftime('%Y%m%d')
                e = current.strftime('%Y%m%d')

                # 호출 실패에 대해서는 rate-limit인지 여부만 재시도
                df_chunk = None
                max_retries = 5
                delay_sec = 0.5
                for attempt in range(1, max_retries + 1):
                    try:
                        df_chunk = broker.get_period_price(symbol, s, e, period="D")

                        # 빈 응답(데이터 없음)은 재시도하지 않고 다음 구간으로 간주
                        if df_chunk is None or (hasattr(df_chunk, 'empty') and df_chunk.empty):
                            print(f"⚠️  {symbol}: 빈 응답 또는 데이터 없음 ({s} ~ {e}) - 건너뜁니다.")
                            break

                        # 정상 데이터 수신
                        break
                    except Exception as ex:
                        msg = str(ex)
                        # rate limit 감지 시에만 재시도
                        if "EGW00201" in msg or "초당 거래건수" in msg or "초당 거래건수를 초과" in msg:
                            print(f"⚠️  {symbol}: API rate limit 감지 ({msg}) (시도 {attempt}/{max_retries})")
                            if attempt < max_retries:
                                time.sleep(delay_sec)
                                delay_sec *= 2
                                continue
                        # 기타 예외는 재시도하지 않음
                        print(f"⚠️  {symbol} 구간 호출 실패: {s} ~ {e}: {ex}")
                        df_chunk = None
                        break

                if df_chunk is None or (hasattr(df_chunk, 'empty') and df_chunk.empty):
                    print(f"⚠️  {symbol}: 빈 응답 또는 데이터 없음 ({s} ~ {e}) - 해당 심볼 페이징 중단합니다.")
                    # 빈 응답을 만나면 더 과거로 진행하지 않고 즉시 중단
                    break
                else:
                    # 정규화: 날짜 컬럼 생성
                    try:
                        dfc = df_chunk.copy()
                        if 'stck_bsop_date' in dfc.columns:
                            dfc.loc[:, 'date'] = pd.to_datetime(dfc['stck_bsop_date'], format='%Y%m%d', errors='coerce')
                        else:
                            # 인덱스를 날짜로 변환 시도
                            try:
                                dfc = dfc.reset_index()
                                dfc.loc[:, 'date'] = pd.to_datetime(dfc.iloc[:, 0], errors='coerce')
                            except Exception:
                                dfc.loc[:, 'date'] = pd.NaT

                        dfc = dfc.dropna(subset=['date'])
                        parts.append(dfc)
                    except Exception as e:
                        print(f"⚠️  {symbol} 구간 파싱 실패: {s} ~ {e}")

                # 다음 구간: 현재를 이번 청크의 시작일 - 1일로 이동(역순)
                current = chunk_start - pd.Timedelta(days=1)
                # 요청 사이에 랜덤 지터를 추가 (0.2 ~ 0.6s)
                time.sleep(0.2 + random.random() * 0.4)

            if not parts:
                print(f"⚠️  {symbol}: 전체 구간에서 데이터 없음 (API). FinanceDataReader로 폴백 시도합니다...")
                # KIS에서 전체 구간 데이터가 없으면 FinanceDataReader로 폴백 시도
                try:
                    import FinanceDataReader as fdr
                except Exception:
                    print(f"⚠️  {symbol}: FinanceDataReader 미설치 또는 호출 불가. 건너뜁니다.")
                    continue

                try:
                    # FDR은 YYYY-MM-DD 형식 사용
                    fdr_start = start_dt.strftime('%Y-%m-%d')
                    fdr_end = end_dt.strftime('%Y-%m-%d')
                    df_fdr = fdr.DataReader(symbol, fdr_start, fdr_end)

                    if df_fdr is None or df_fdr.empty:
                        print(f"⚠️  {symbol}: FDR에도 데이터 없음. 건너뜁니다.")
                        continue

                    # FDR 결과를 기존 포맷과 유사하게 변환
                    dfc = df_fdr.reset_index().rename(columns={
                        'Date': 'date',
                        'Open': 'stck_oprc',
                        'High': 'stck_hgpr',
                        'Low': 'stck_lwpr',
                        'Close': 'stck_clpr',
                        'Volume': 'acml_vol'
                    })
                    if 'date' in dfc.columns:
                        dfc['stck_bsop_date'] = pd.to_datetime(dfc['date']).dt.strftime('%Y%m%d')
                        dfc['date'] = pd.to_datetime(dfc['date'])

                    historical_data[symbol] = dfc
                    print(f"✅ {symbol}: {len(dfc)}건 로드됨 (FDR 폴백)")
                except Exception as e:
                    print(f"⚠️  {symbol}: FDR 폴백 실패: {e}")
                continue

            # 병합 및 정리
            try:
                df_all = pd.concat(parts, ignore_index=True)
                df_all = df_all.drop_duplicates(subset=['date'])
                df_all = df_all.sort_values('date')
                # 날짜 필터 적용(안전망)
                df_all = df_all[(df_all['date'] >= start_dt) & (df_all['date'] <= end_dt)]

                historical_data[symbol] = df_all
                print(f"✅ {symbol}: {len(df_all)}건 로드됨 (API, paged)")
            except Exception as e:
                print(f"⚠️  {symbol}: 병합 실패: {e}")

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
                time.sleep(0.2)
            
            df = broker.get_period_price(symbol, start_str, end_str, period="D")
            
            if df is None or df.empty:
                print(f"⚠️  {symbol} 데이터 없음")
                continue
            
            # DB에 저장
            for i, symbol in enumerate(symbols):
                # per-symbol rate limit 완화
                if i > 0:
                    time.sleep(0.2)

                parts = []
                current_end = end_dt
                print(f"📥 {symbol} 데이터 다운로드 중 (API, 최신->과거, 100일 단위)...")

                # iterate from end -> start in 100-day chunks
                while current_end >= start_dt:
                    chunk_start = max(start_dt, current_end - pd.Timedelta(days=99))
                    s = chunk_start.strftime('%Y%m%d')
                    e = current_end.strftime('%Y%m%d')

                    # rate-limit 재시도 로직: rate-limit일 때만 retry (고정 delay)
                    df_chunk = None
                    max_retries = 5
                    delay_sec = 0.5
                    rate_limit_retry = False
                    for attempt in range(1, max_retries + 1):
                        try:
                            df_chunk = broker.get_period_price(symbol, s, e, period="D")

                            # 빈 응답이면 '데이터 없음'으로 간주하고 탐색 중단
                            if df_chunk is None or (hasattr(df_chunk, 'empty') and df_chunk.empty):
                                print(f"⚠️  {symbol}: 빈 응답 또는 데이터 없음 ({s} ~ {e}) - 탐색 중단")
                                rate_limit_retry = False
                                break

                            # 정상 데이터 수신
                            rate_limit_retry = False
                            break
                        except Exception as ex:
                            msg = str(ex)
                            if "EGW00201" in msg or "초당 거래건수" in msg or "초당 거래건수를 초과" in msg:
                                rate_limit_retry = True
                                print(f"⚠️  {symbol}: API rate limit 감지 ({msg}) (시도 {attempt}/{max_retries})")
                                if attempt < max_retries:
                                    time.sleep(delay_sec)
                                    continue
                            # 기타 에러는 재시도하지 않음
                            print(f"⚠️  {symbol} 구간 호출 실패: {s} ~ {e}: {ex}")
                            df_chunk = None
                            rate_limit_retry = False
                            break

                    # 빈 응답으로 탐색 중단된 경우, break outer loop (move to next symbol)
                    if df_chunk is None or (hasattr(df_chunk, 'empty') and (getattr(df_chunk, 'empty', False) or df_chunk is None)):
                        # 만약 rate-limit으로 인한 마지막 실패라면 계속 시도하지 않고 다음 심볼로 넘어감
                        if rate_limit_retry:
                            print(f"⚠️  {symbol}: rate-limit으로 데이터 수신 실패 (구간 {s} ~ {e}), 다음 구간으로 진행하지 않습니다.")
                        # no data: stop backward scanning
                        break

                    # 정규화: 날짜 컬럼 생성 및 parts에 추가
                    try:
                        dfc = df_chunk.copy()
                        if 'stck_bsop_date' in dfc.columns:
                            dfc.loc[:, 'date'] = pd.to_datetime(dfc['stck_bsop_date'], format='%Y%m%d', errors='coerce')
                        else:
                            dfc = dfc.reset_index()
                            dfc.loc[:, 'date'] = pd.to_datetime(dfc.iloc[:, 0], errors='coerce')
                        dfc = dfc.dropna(subset=['date'])
                        parts.append(dfc)
                    except Exception as e:
                        print(f"⚠️  {symbol} 구간 파싱 실패: {s} ~ {e}")

                    # 다음(이전) 구간으로 이동
                    current_end = chunk_start - pd.Timedelta(days=1)
                    time.sleep(0.2)

                if not parts:
                    # KIS가 최신 구간부터 전체적으로 데이터를 주지 않았음 -> FDR 폴백 시도
                    print(f"⚠️  {symbol}: 전체 구간에서 데이터 없음 (API). FinanceDataReader로 폴백 시도합니다...")
                    try:
                        import FinanceDataReader as fdr
                    except Exception:
                        print(f"⚠️  {symbol}: FinanceDataReader 미설치 또는 호출 불가. 건너뜁니다.")
                        continue

                    try:
                        fdr_start = start_dt.strftime('%Y-%m-%d')
                        fdr_end = end_dt.strftime('%Y-%m-%d')
                        df_fdr = fdr.DataReader(symbol, fdr_start, fdr_end)

                        if df_fdr is None or df_fdr.empty:
                            print(f"⚠️  {symbol}: FDR에도 데이터 없음. 건너뜁니다.")
                            continue

                        dfc = df_fdr.reset_index().rename(columns={
                            'Date': 'date',
                            'Open': 'stck_oprc',
                            'High': 'stck_hgpr',
                            'Low': 'stck_lwpr',
                            'Close': 'stck_clpr',
                            'Volume': 'acml_vol'
                        })
                        if 'date' in dfc.columns:
                            dfc['stck_bsop_date'] = pd.to_datetime(dfc['date']).dt.strftime('%Y%m%d')
                            dfc['date'] = pd.to_datetime(dfc['date'])

                        historical_data[symbol] = dfc
                        print(f"✅ {symbol}: {len(dfc)}건 로드됨 (FDR 폴백)")
                    except Exception as e:
                        print(f"⚠️  {symbol}: FDR 폴백 실패: {e}")
                    continue

                # 병합 및 정리 (parts는 최신->과거 순으로 쌓였으므로 정렬 필요)
                try:
                    df_all = pd.concat(parts, ignore_index=True)
                    df_all = df_all.drop_duplicates(subset=['date'])
                    df_all = df_all.sort_values('date')
                    df_all = df_all[(df_all['date'] >= start_dt) & (df_all['date'] <= end_dt)]

                    historical_data[symbol] = df_all
                    print(f"✅ {symbol}: {len(df_all)}건 로드됨 (API, paged)")
                except Exception as e:
                    print(f"⚠️  {symbol}: 병합 실패: {e}")
