#!/usr/bin/env python3
"""
통합 백테스트 실행 스크립트

이동평균 교차 전략을 과거 데이터로 백테스트합니다.

데이터 소스:
    - api: KIS Open Trading API (최대 100거래일)
    - db: SQLite 데이터베이스 (무제한, 외부에서 준비)
    - fdr: FinanceDataReader (무제한, 인터넷 필요)

실행 방법:
    # FDR 사용 (권장)
    uv run run_backtest.py --source fdr --start 20220101 --end 20241231
    
    # KIS API 사용 (최근 100일)
    uv run run_backtest.py --source api
    
    # 외부 DB 사용
    uv run run_backtest.py --source db --db-path /path/to/data.db --start 20230101
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pytz

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from trading_bot.config import Config
from trading_bot.backtest.engine import BacktestEngine
from trading_bot.backtest.report import BacktestReport
from trading_bot.broker.kis_broker import KISBroker
from trading_bot.strategies.ma_crossover import MovingAverageCrossover
from trading_bot.utils.ma_screening import ScreeningConfig
from trading_bot.utils.universe import resolve_universe_symbols


def parse_args():
    """명령행 인자 파싱"""
    parser = argparse.ArgumentParser(
        description='백테스트 실행 - 이동평균 교차 전략',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # FinanceDataReader로 2년 백테스트 (권장)
  %(prog)s --source fdr --start 20220101 --end 20241231
  
  # KIS API로 최근 100일 백테스트
  %(prog)s --source api
  
  # 외부 DB로 백테스트
  %(prog)s --source db --db-path /path/to/data.db --start 20230101 --end 20241231
  
  # 종목 지정
  %(prog)s --source fdr --symbols 005930 000660 035720

    # 유니버스 스크리닝 적용
    %(prog)s --source fdr --start 20220101 --end 20241231 --enable-screening --screen-top-n 15
        """
    )
    
    parser.add_argument(
        '--source',
        choices=['api', 'db', 'fdr'],
        default='fdr',
        help='데이터 소스 선택 (기본값: fdr)'
    )
    
    parser.add_argument(
        '--db-path',
        type=str,
        help='SQLite DB 파일 경로 (source=db일 때 필수)'
    )
    
    parser.add_argument(
        '--start',
        '--start-date',
        type=str,
        help='백테스트 시작일 (YYYYMMDD, 기본값: 2년 전)'
    )
    
    parser.add_argument(
        '--end',
        '--end-date',
        type=str,
        help='백테스트 종료일 (YYYYMMDD, 기본값: 어제)'
    )
    
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='백테스트 종목 리스트 (기본값: Config.WATCH_LIST)'
    )

    parser.add_argument(
        '--universe-target',
        type=str,
        default=Config.UNIVERSE_TARGET,
        help='후보군 타깃 (watchlist/kospi/kosdaq/kospi_kosdaq/kospi200/kosdaq150/kospi200_kosdaq150)'
    )
    
    parser.add_argument(
        '--capital',
        type=int,
        default=10000000,
        help='초기 자본금 (기본값: 10,000,000원)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='결과 저장 경로 (기본값: backtest_results_{source}_{timestamp}.png)'
    )
    
    parser.add_argument(
        '--short-period',
        type=int,
        default=5,
        help='단기 이동평균 기간 (기본값: 5)'
    )
    
    parser.add_argument(
        '--long-period',
        type=int,
        default=20,
        help='장기 이동평균 기간 (기본값: 20)'
    )

    parser.add_argument(
        '--enable-screening',
        action='store_true',
        help='백테스트 시작 전 유니버스 스크리닝(거래대금/ADX/장기MA/ATR) 적용'
    )

    parser.add_argument(
        '--screen-min-avg-value',
        type=float,
        default=Config.MA_SCREENING_MIN_AVG_VALUE,
        help='스크리닝 20일 평균 거래대금 최소값(원)'
    )

    parser.add_argument(
        '--screen-adx-threshold',
        type=float,
        default=Config.MA_SCREENING_ADX_THRESHOLD,
        help='스크리닝 ADX 최소값'
    )

    parser.add_argument(
        '--screen-trend-ma-period',
        type=int,
        default=Config.MA_SCREENING_TREND_MA_PERIOD,
        help='스크리닝 장기 추세 MA 기간'
    )

    parser.add_argument(
        '--screen-atr-pct-min',
        type=float,
        default=Config.MA_SCREENING_ATR_PCT_MIN,
        help='스크리닝 ATR%% 최소값'
    )

    parser.add_argument(
        '--screen-atr-pct-max',
        type=float,
        default=Config.MA_SCREENING_ATR_PCT_MAX,
        help='스크리닝 ATR%% 최대값'
    )

    parser.add_argument(
        '--screen-top-n',
        type=int,
        default=Config.MA_SCREENING_TOP_N,
        help='스크리닝 상위 선정 종목 수'
    )
    
    return parser.parse_args()


def main():
    """백테스트 실행"""
    
    # 명령행 인자 파싱
    args = parse_args()
    
    print("\n" + "="*80)
    print("KIS 자동매매 봇 - 통합 백테스트".center(80))
    print("="*80 + "\n")
    
    # 데이터 소스 검증
    if args.source == 'db' and not args.db_path:
        print("❌ 오류: --source db 사용 시 --db-path 필수")
        sys.exit(1)
    
    if args.source == 'db' and not Path(args.db_path).exists():
        print(f"❌ 오류: DB 파일이 없습니다: {args.db_path}")
        sys.exit(1)
    
    # 한국 시간대 사용
    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst)
    
    # 날짜 설정
    if args.end:
        end_date = args.end
    else:
        end_date = (now_kst - timedelta(days=1)).strftime("%Y%m%d")
    
    if args.start:
        start_date = args.start
    else:
        if args.source == 'api':
            # API는 최대 100일
            start_date = (now_kst - timedelta(days=100)).strftime("%Y%m%d")
        else:
            # DB/FDR는 2년
            start_date = (now_kst - timedelta(days=730)).strftime("%Y%m%d")
    
    # 워밍업 기간 계산 (장기 이동평균 계산을 위해 추가 데이터 필요)
    # 장기 이동평균 기간만큼 시작일을 앞당김
    warmup_days = args.long_period
    # *3을 곱하는 이유: 주말/공휴일 제외하고 충분한 거래일 확보 (200일*3 = 600력일)
    data_start_date = (datetime.strptime(start_date, "%Y%m%d") - timedelta(days=warmup_days * 3)).strftime("%Y%m%d")
    
    # 종목 설정
    if args.symbols:
        symbols = args.symbols
        universe_info = None
    else:
        universe_info = resolve_universe_symbols(
            target=args.universe_target,
            default_symbols=list(Config.WATCH_LIST),
            cache_dir=Config.UNIVERSE_CACHE_DIR,
            refresh_daily=Config.UNIVERSE_REFRESH_DAILY,
            max_symbols=Config.UNIVERSE_MAX_SYMBOLS,
        )
        symbols = universe_info.symbols

    if not symbols:
        print("❌ 오류: 백테스트 대상 종목이 없습니다.")
        sys.exit(1)
    
    # 데이터 소스 표시
    source_names = {
        'api': 'KIS Open Trading API',
        'db': 'SQLite Database',
        'fdr': 'FinanceDataReader'
    }
    
    print(f"📊 백테스트 설정")
    print(f"  데이터 소스: {source_names[args.source]}")
    if args.source == 'db':
        print(f"  DB 경로: {args.db_path}")
    print(f"  초기 자본금: {args.capital:,}원")
    print(f"  백테스트 기간: {start_date} ~ {end_date}")
    print(f"  데이터 로드 기간: {data_start_date} ~ {end_date} (워밍업 {warmup_days}일 포함)")
    print(f"  대상 종목: {', '.join(symbols)}")
    if universe_info is not None:
        if universe_info.csv_path:
            print(f"  유니버스 파일: {universe_info.csv_path}")
        print(f"  유니버스 타깃: {universe_info.target} ({len(symbols)}종목)")
    print(f"  전략: 이동평균 교차 (단기 {args.short_period}일, 장기 {args.long_period}일)")
    if args.enable_screening:
        print(
            "  유니버스 스크리닝: ON "
            f"(거래대금20>={args.screen_min_avg_value:,.0f}, "
            f"ADX>={args.screen_adx_threshold}, "
            f"Close>MA{args.screen_trend_ma_period}, "
            f"ATR%={args.screen_atr_pct_min}~{args.screen_atr_pct_max}, "
            f"TOP {args.screen_top_n})"
        )
    else:
        print("  유니버스 스크리닝: OFF")
    print()

    screening_cfg = ScreeningConfig(
        min_avg_value=args.screen_min_avg_value,
        adx_threshold=args.screen_adx_threshold,
        trend_ma_period=args.screen_trend_ma_period,
        atr_pct_min=args.screen_atr_pct_min,
        atr_pct_max=args.screen_atr_pct_max,
        top_n=args.screen_top_n,
    )
    
    # Broker 초기화 (API 사용 시)
    broker = None
    if args.source == 'api':
        print("🔐 KIS API 인증 중...")
        try:
            broker = KISBroker(env_mode="demo")
            print("✅ 인증 완료\n")
        except Exception as e:
            print(f"❌ 인증 실패: {e}")
            sys.exit(1)
    
    # 전략 초기화
    strategy = MovingAverageCrossover(
        broker=broker,
        short_period=args.short_period,
        long_period=args.long_period
    )
    
    # 백테스트 엔진 생성
    engine = BacktestEngine(
        initial_capital=args.capital,
        commission_rate=0.00015  # 0.015%
    )
    
    # 백테스트 실행
    print("🚀 백테스트 시작...")
    print("-" * 80)
    
    try:
        # 데이터 소스별 실행
        if args.source == 'fdr':
            results = engine.run(
                strategy=strategy,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                use_fdr=True,
                data_start_date=data_start_date,
                enable_universe_screening=args.enable_screening,
                screening_config=screening_cfg,
            )
        elif args.source == 'db':
            results = engine.run(
                strategy=strategy,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                db_path=Path(args.db_path),
                data_start_date=data_start_date,
                enable_universe_screening=args.enable_screening,
                screening_config=screening_cfg,
            )
        else:  # api
            results = engine.run(
                strategy=strategy,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                broker=broker,
                data_start_date=data_start_date,
                enable_universe_screening=args.enable_screening,
                screening_config=screening_cfg,
            )
        
        if not results or not results.get('trades'):
            print("\n⚠️  경고: 거래 내역이 없습니다.")
            print("   - 기간이 너무 짧거나")
            print("   - 전략 조건을 만족하는 시그널이 없습니다.")
            return
        
        # 결과 출력
        BacktestReport.print_summary(results)
        
        # 결과 저장 디렉토리 생성 (trading_bot 하위)
        output_dir = Path(__file__).parent / "backtest_results"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일명 생성: {전략이름}_{데이터소스}_{타입}_{날짜}_{시간}.{확장자}
        kst = pytz.timezone('Asia/Seoul')
        timestamp = datetime.now(kst).strftime("%Y%m%d_%H%M%S")
        strategy_name = "ma_crossover"  # 전략 이름
        data_source = args.source  # 데이터 소스 (api, db, fdr)
        
        # 결과 파일 경로 결정
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = output_dir / f"{strategy_name}_{data_source}_chart_{timestamp}.png"
        
        # 그래프 생성
        print()
        BacktestReport.plot_equity_curve(results, output_path)
        print(f"✅ 차트 저장: {output_path}")
        
        # CSV 저장 (equity curve)
        equity_path = output_dir / f"{strategy_name}_{data_source}_equity_{timestamp}.csv"
        BacktestReport.save_equity_curve(results, equity_path)
        
        # 거래 내역 저장
        if results.get('trades'):
            trades_path = output_dir / f"{strategy_name}_{data_source}_trades_{timestamp}.csv"
            BacktestReport.save_trades(results, trades_path)
        
        print("\n✅ 백테스트 완료!")
        
    except ImportError as e:
        if 'FinanceDataReader' in str(e):
            print("\n❌ FinanceDataReader가 설치되지 않았습니다!")
            print("   설치: uv pip install finance-datareader")
        else:
            print(f"\n❌ 오류: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 백테스트 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
