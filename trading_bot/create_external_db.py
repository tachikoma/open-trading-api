#!/usr/bin/env python3
"""
백테스트용 외부 DB 생성 템플릿

FinanceDataReader를 사용하여 한국 주식 데이터를 다운로드하고 SQLite DB에 저장합니다.

설치:
    uv pip install finance-datareader

실행:
    uv run create_external_db.py
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import FinanceDataReader as fdr
except ImportError:
    print("❌ FinanceDataReader가 설치되지 않았습니다!")
    print("   설치: uv pip install finance-datareader")
    sys.exit(1)


def create_external_db(db_path: str, symbols: list, start_date: str, end_date: str = None):
    """
    외부 DB 생성
    
    Args:
        db_path: DB 파일 경로
        symbols: 종목코드 리스트
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD, 기본값: 오늘)
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    print("="*80)
    print("백테스트용 외부 DB 생성 - FinanceDataReader".center(80))
    print("="*80)
    print()
    print(f"📂 DB 경로: {db_path}")
    print(f"📅 기간: {start_date} ~ {end_date}")
    print(f"📊 종목 수: {len(symbols)}")
    print(f"📋 종목: {', '.join(symbols)}")
    print()
    print("-"*80)
    
    # DB 연결
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 테이블 생성 (형식 1: 통합 테이블)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_daily (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            PRIMARY KEY (symbol, date)
        )
    """)
    
    # 인덱스 생성
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_daily_date ON stock_daily(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_daily_symbol ON stock_daily(symbol)")
    
    # 데이터 다운로드 및 저장
    total_records = 0
    success_count = 0
    
    for symbol in symbols:
        print(f"📥 {symbol} 다운로드 중...")
        
        try:
            # FinanceDataReader로 데이터 다운로드
            df = fdr.DataReader(symbol, start_date, end_date)
            
            if df.empty:
                print(f"⚠️  {symbol}: 데이터 없음")
                continue
            
            # 데이터 변환
            df = df.reset_index()
            df['symbol'] = symbol
            df['date'] = df['Date'].dt.strftime('%Y%m%d')
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # DB에 저장 (중복 제거)
            for _, row in df.iterrows():
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO stock_daily 
                        (symbol, date, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row['symbol'],
                        row['date'],
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        int(row['volume'])
                    ))
                except Exception as e:
                    print(f"   ⚠️  {row['date']} 저장 실패: {e}")
            
            conn.commit()
            
            print(f"✅ {symbol}: {len(df)}건 저장")
            total_records += len(df)
            success_count += 1
            
        except Exception as e:
            print(f"❌ {symbol} 다운로드 실패: {e}")
    
    # DB 최적화
    print()
    print("🔧 DB 최적화 중...")
    cursor.execute("VACUUM")
    conn.commit()
    
    # 통계 출력
    cursor.execute("SELECT COUNT(*) FROM stock_daily")
    total_rows = cursor.fetchone()[0]
    
    cursor.execute("SELECT DISTINCT symbol FROM stock_daily")
    saved_symbols = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT MIN(date), MAX(date) FROM stock_daily")
    date_range = cursor.fetchone()
    
    conn.close()
    
    print()
    print("="*80)
    print("✅ DB 생성 완료!")
    print("="*80)
    print(f"📂 DB 파일: {db_path}")
    print(f"📊 총 레코드 수: {total_rows:,}건")
    print(f"📈 저장된 종목 수: {len(saved_symbols)}/{len(symbols)}")
    print(f"📅 데이터 기간: {date_range[0]} ~ {date_range[1]}")
    print()
    print("💡 백테스트 실행:")
    print(f"   uv run run_backtest.py --source db --db-path {db_path}")
    print()


def main():
    """메인 함수"""
    
    # ========================================
    # 🔧 여기를 수정하세요!
    # ========================================
    
    # DB 파일 경로
    DB_PATH = "backtest_data.db"
    
    # 종목 리스트 (6자리 종목코드)
    SYMBOLS = [
        "005930",  # 삼성전자
        "000660",  # SK하이닉스
        "035720",  # 카카오
        "035420",  # NAVER
        "051910",  # LG화학
        "006400",  # 삼성SDI
        "373220",  # LG에너지솔루션
        "207940",  # 삼성바이오로직스
        "068270",  # 셀트리온
        "005380",  # 현대차
    ]
    
    # 데이터 기간 (최대 10년 권장)
    START_DATE = "2020-01-01"  # YYYY-MM-DD
    END_DATE = None            # None = 오늘까지
    
    # ========================================
    
    try:
        create_external_db(DB_PATH, SYMBOLS, START_DATE, END_DATE)
    except KeyboardInterrupt:
        print("\n⚠️  사용자가 중단했습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
