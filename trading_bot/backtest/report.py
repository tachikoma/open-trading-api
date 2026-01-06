"""
백테스트 리포트 생성 모듈

백테스트 결과를 텍스트, CSV 형식으로 출력합니다.
"""
import pandas as pd
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


class BacktestReport:
    """백테스트 결과 리포트 생성 클래스"""
    
    @staticmethod
    def print_summary(results: Dict):
        """
        백테스트 결과 요약 출력
        
        Args:
            results: 백테스트 결과 딕셔너리
        """
        metrics = results.get('metrics', {})
        
        if not metrics:
            print("\n⚠️  백테스트 결과가 없습니다.")
            return
        
        print("\n" + "="*70)
        print("백테스트 결과 요약".center(70))
        print("="*70)
        
        print("\n📅 백테스트 기간")
        print(f"  시작일: {metrics['start_date']}")
        print(f"  종료일: {metrics['end_date']}")
        
        print("\n💰 자본금 및 수익")
        print(f"  초기 자본:    {metrics['initial_capital']:>15,.0f}원")
        print(f"  최종 자본:    {metrics['final_capital']:>15,.0f}원")
        print(f"  총 수익:      {metrics['final_capital'] - metrics['initial_capital']:>15,.0f}원")
        print(f"  총 수익률:    {metrics['total_return_pct']:>15.2f}%")
        print(f"  연평균 수익률: {metrics['cagr_pct']:>14.2f}%")
        
        print("\n📊 리스크 지표")
        print(f"  최대 낙폭(MDD): {metrics['mdd_pct']:>13.2f}%")
        print(f"  샤프 비율:     {metrics['sharpe_ratio']:>14.2f}")
        
        print("\n📈 거래 통계")
        print(f"  총 거래 횟수:  {metrics['total_trades']:>14}회")
        print(f"  승률:         {metrics['win_rate_pct']:>15.2f}%")
        print(f"  손익비:       {metrics['profit_factor']:>15.2f}")
        print(f"  평균 손익:    {metrics['avg_profit']:>15,.0f}원")
        
        print("\n💼 최종 포지션")
        final_positions = results.get('final_positions', {})
        if final_positions:
            for symbol, pos in final_positions.items():
                print(f"  {symbol}: {pos['qty']:>6}주 @ {pos['avg_price']:>10,.0f}원")
        else:
            print("  (없음)")
        
        print(f"\n💵 최종 현금: {results['final_cash']:,.0f}원")
        print("="*70 + "\n")
    
    @staticmethod
    def save_equity_curve(results: Dict, output_path: Path):
        """
        자산 곡선을 CSV로 저장
        
        Args:
            results: 백테스트 결과 딕셔너리
            output_path: 저장 경로
        """
        equity_df = pd.DataFrame(results['equity_curve'])
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        equity_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        print(f"✅ 자산 곡선 저장: {output_path}")
    
    @staticmethod
    def save_trades(results: Dict, output_path: Path):
        """
        거래 내역을 CSV로 저장
        
        Args:
            results: 백테스트 결과 딕셔너리
            output_path: 저장 경로
        """
        if not results['trades']:
            print("⚠️  거래 내역이 없습니다")
            return
        
        trades_df = pd.DataFrame(results['trades'])
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        trades_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        print(f"✅ 거래 내역 저장: {output_path}")
    
    @staticmethod
    def save_metrics(results: Dict, output_path: Path):
        """
        성과 지표를 CSV로 저장
        
        Args:
            results: 백테스트 결과 딕셔너리
            output_path: 저장 경로
        """
        metrics = results['metrics']
        metrics_df = pd.DataFrame([metrics])
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        print(f"✅ 성과 지표 저장: {output_path}")
    
    @staticmethod
    def save_all(results: Dict, output_dir: Path, prefix: str = "backtest"):
        """
        모든 결과를 파일로 저장
        
        Args:
            results: 백테스트 결과 딕셔너리
            output_dir: 출력 디렉토리
            prefix: 파일명 접두사
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 디렉토리 생성
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 각 파일 저장
        BacktestReport.save_equity_curve(
            results, 
            output_dir / f"{prefix}_equity_{timestamp}.csv"
        )
        
        BacktestReport.save_trades(
            results,
            output_dir / f"{prefix}_trades_{timestamp}.csv"
        )
        
        BacktestReport.save_metrics(
            results,
            output_dir / f"{prefix}_metrics_{timestamp}.csv"
        )
        
        print(f"\n📁 모든 결과가 저장되었습니다: {output_dir}")
    
    @staticmethod
    def plot_equity_curve(results: Dict, save_path: Optional[Path] = None):
        """
        자산 곡선 그래프 생성 (matplotlib 필요)
        
        Args:
            results: 백테스트 결과 딕셔너리
            save_path: 저장 경로 (None이면 화면에 표시)
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            import platform
            import numpy as np
            
            # 한글 폰트 설정 (경고 방지)
            system = platform.system()
            if system == 'Darwin':  # macOS
                plt.rcParams['font.family'] = 'AppleGothic'
            elif system == 'Windows':
                plt.rcParams['font.family'] = 'Malgun Gothic'
            else:  # Linux
                plt.rcParams['font.family'] = 'NanumGothic'
            
            # 마이너스 기호 깨짐 방지
            plt.rcParams['axes.unicode_minus'] = False
            
            # 데이터 준비
            metrics = results['metrics']
            equity_df = pd.DataFrame(results['equity_curve']).copy()
            equity_df.loc[:, 'date'] = pd.to_datetime(equity_df['date'])
            
            # 누적 수익률 계산
            equity_df.loc[:, 'return_pct'] = ((equity_df['equity'] / metrics['initial_capital']) - 1) * 100
            
            # 보유 종목 수 계산 (equity_curve에 이미 포함되어 있음)
            # holdings_count 컬럼이 있으면 사용, 없으면 0으로 채움
            if 'holdings_count' in equity_df.columns:
                pass  # 이미 있음
            else:
                # holdings_count가 없으면 0으로 채움
                equity_df.loc[:, 'holdings_count'] = 0
            
            # Figure 생성 (3개 서브플롯, 비율 조정)
            fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True,
                                    gridspec_kw={'height_ratios': [2, 1, 1.5]})
            fig.patch.set_facecolor('white')
            
            # 제목에 주요 통계 포함
            title = f"백테스트 결과\n"
            title += f"총 수익률: {metrics['total_return_pct']:.2f}% | "
            title += f"연환산 수익률: {metrics['cagr_pct']:.2f}%"
            fig.suptitle(title, fontsize=14, fontweight='bold', y=0.98)
            
            # 1. 포트폴리오 가치 (상단)
            ax1 = axes[0]
            ax1.plot(equity_df['date'], equity_df['equity'], 
                    linewidth=2, color='#1f77b4', label='포트폴리오 가치')
            ax1.axhline(y=metrics['initial_capital'], 
                       color='r', linestyle='--', label='초기 자본', alpha=0.5, linewidth=1)
            
            ax1.set_ylabel('자산 (원)', fontsize=10, fontweight='bold')
            ax1.legend(loc='upper left', fontsize=8, framealpha=0.9)
            ax1.grid(True, alpha=0.2, linestyle=':', linewidth=0.5)
            ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x/1e6):.1f}M' if x >= 1e6 else f'{int(x/1e3):.0f}K'))
            
            # 통계 정보 표시 (위치 조정)
            stats_text = f"최종 자본: {metrics['final_capital']:,.0f}원"
            ax1.text(0.98, 0.97, stats_text, transform=ax1.transAxes,
                    fontsize=8, verticalalignment='top', horizontalalignment='right',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='wheat', alpha=0.5, edgecolor='gray'))
            
            # 2. 보유 종목 수 (중단)
            ax2 = axes[1]
            ax2.plot(equity_df['date'], equity_df['holdings_count'], 
                    linewidth=2, color='#2ca02c', drawstyle='steps-post', label='보유 종목 수')
            ax2.fill_between(equity_df['date'], 0, equity_df['holdings_count'], 
                            alpha=0.3, color='#2ca02c', step='post')
            
            ax2.set_ylabel('보유 종목 수', fontsize=10, fontweight='bold')
            ax2.legend(loc='upper left', fontsize=8, framealpha=0.9)
            ax2.grid(True, alpha=0.2, linestyle=':', linewidth=0.5)
            ax2.set_ylim(bottom=0)
            
            # 거래 횟수 정보 (하단 배치, 배경색 변경)
            trades_text = f"총 거래: {metrics['total_trades']}회 | 승률: {metrics['win_rate_pct']:.1f}%"
            ax2.text(0.98, 0.03, trades_text, transform=ax2.transAxes,
                    fontsize=8, verticalalignment='bottom', horizontalalignment='right',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.7, edgecolor='gray'))
            
            # 3. 누적 수익률 (하단)
            ax3 = axes[2]
            
            # 수익/손실 구간 색상 구분
            positive_mask = equity_df['return_pct'] >= 0
            ax3.fill_between(equity_df['date'], 0, equity_df['return_pct'],
                            where=positive_mask, alpha=0.3, color='green', 
                            interpolate=True, label='수익 구간')
            ax3.fill_between(equity_df['date'], 0, equity_df['return_pct'],
                            where=~positive_mask, alpha=0.3, color='red', 
                            interpolate=True, label='손실 구간')
            
            ax3.plot(equity_df['date'], equity_df['return_pct'], 
                    linewidth=2, color='purple', label='누적 수익률')
            ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5, alpha=0.3)
            
            ax3.set_xlabel('날짜', fontsize=10, fontweight='bold')
            ax3.set_ylabel('누적 수익률 (%)', fontsize=10, fontweight='bold')
            ax3.legend(loc='upper left', fontsize=8, framealpha=0.9)
            ax3.grid(True, alpha=0.2, linestyle=':', linewidth=0.5)
            
            # MDD 정보 (위치 조정)
            mdd_text = f"MDD: {metrics['mdd_pct']:.2f}% | 샤프 비율: {metrics['sharpe_ratio']:.2f}"
            ax3.text(0.98, 0.03, mdd_text, transform=ax3.transAxes,
                    fontsize=8, verticalalignment='bottom', horizontalalignment='right',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='lightcoral', alpha=0.5, edgecolor='gray'))
            
            # 날짜 포맷 설정 (x축 공통)
            ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            fig.autofmt_xdate(rotation=45)
            
            # 서브플롯 간격 조정
            plt.subplots_adjust(left=0.08, right=0.95, top=0.94, bottom=0.08, hspace=0.15)
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
                print(f"✅ 그래프 저장: {save_path}")
            else:
                plt.show()
            
            plt.close()
            
        except ImportError:
            print("⚠️  matplotlib이 설치되지 않아 그래프를 생성할 수 없습니다")
            print("   설치: uv pip install matplotlib")
