"""
백테스트 데이터 소스 모듈

SQLite DB, KIS API, 또는 FinanceDataReader에서 과거 데이터를 로드합니다.
"""
import sqlite3
import pandas as pd
from pathlib import Path
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
