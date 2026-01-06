"""
백테스트 성과 지표 계산 모듈

수익률, MDD, 샤프비율, 승률 등 다양한 성과 지표를 계산합니다.
"""
import numpy as np
import pandas as pd
from typing import Dict, List


class PerformanceMetrics:
    """백테스트 성과 지표 계산 클래스"""
    
    @staticmethod
    def calculate_returns(equity_curve: pd.Series) -> pd.Series:
        """
        수익률 계산
        
        Args:
            equity_curve: 자산 가치 시계열
            
        Returns:
            일별 수익률 시계열
        """
        return equity_curve.pct_change().fillna(0)
    
    @staticmethod
    def calculate_total_return(equity_curve: pd.Series) -> float:
        """
        총 수익률 계산
        
        Args:
            equity_curve: 자산 가치 시계열
            
        Returns:
            총 수익률 (%)
        """
        if len(equity_curve) == 0:
            return 0.0
        return ((equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1) * 100
    
    @staticmethod
    def calculate_cagr(equity_curve: pd.Series, years: float) -> float:
        """
        연평균 복리 수익률(CAGR) 계산
        
        Args:
            equity_curve: 자산 가치 시계열
            years: 투자 기간(년)
            
        Returns:
            CAGR (%)
        """
        if len(equity_curve) == 0 or years <= 0:
            return 0.0
        total_return = equity_curve.iloc[-1] / equity_curve.iloc[0]
        return (pow(total_return, 1/years) - 1) * 100
    
    @staticmethod
    def calculate_mdd(equity_curve: pd.Series) -> float:
        """
        최대 낙폭(MDD) 계산
        
        Args:
            equity_curve: 자산 가치 시계열
            
        Returns:
            MDD (%) - 음수로 반환 (예: -15.3%)
        """
        if len(equity_curve) == 0:
            return 0.0
        
        cumulative_max = equity_curve.cummax()
        drawdown = (equity_curve - cumulative_max) / cumulative_max * 100
        return drawdown.min()  # 음수로 반환 (abs 제거)
    
    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """
        샤프 비율 계산
        
        Args:
            returns: 일별 수익률 시계열
            risk_free_rate: 무위험 이자율 (연율)
            
        Returns:
            샤프 비율
        """
        if len(returns) == 0:
            return 0.0
        
        # 일별 무위험 수익률
        daily_rf = risk_free_rate / 252
        excess_returns = returns - daily_rf
        
        if excess_returns.std() == 0:
            return 0.0
        
        # 연율화된 샤프 비율
        return np.sqrt(252) * (excess_returns.mean() / excess_returns.std())
    
    @staticmethod
    def calculate_win_rate(trades: List[Dict]) -> float:
        """
        승률 계산
        
        Args:
            trades: 거래 내역 리스트
            
        Returns:
            승률 (%)
        """
        if len(trades) == 0:
            return 0.0
        
        winning_trades = sum(1 for t in trades if t.get('profit', 0) > 0)
        return (winning_trades / len(trades)) * 100
    
    @staticmethod
    def calculate_profit_factor(trades: List[Dict]) -> float:
        """
        손익비 계산
        
        Args:
            trades: 거래 내역 리스트
            
        Returns:
            손익비 (총이익 / 총손실)
        """
        if len(trades) == 0:
            return 0.0
        
        total_profit = sum(t.get('profit', 0) for t in trades if t.get('profit', 0) > 0)
        total_loss = abs(sum(t.get('profit', 0) for t in trades if t.get('profit', 0) < 0))
        
        if total_loss == 0:
            return float('inf') if total_profit > 0 else 0.0
        
        return total_profit / total_loss
    
    @staticmethod
    def calculate_avg_profit(trades: List[Dict]) -> float:
        """
        평균 수익 계산
        
        Args:
            trades: 거래 내역 리스트
            
        Returns:
            평균 수익
        """
        if len(trades) == 0:
            return 0.0
        
        return sum(t.get('profit', 0) for t in trades) / len(trades)
    
    @staticmethod
    def calculate_all_metrics(equity_curve: pd.Series, trades: List[Dict], 
                             start_date: str, end_date: str) -> Dict:
        """
        모든 성과 지표 계산
        
        Args:
            equity_curve: 자산 가치 시계열
            trades: 거래 내역 리스트
            start_date: 시작일
            end_date: 종료일
            
        Returns:
            성과 지표 딕셔너리
        """
        returns = PerformanceMetrics.calculate_returns(equity_curve)
        
        # 투자 기간 계산 (년)
        try:
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            years = (end - start).days / 365.25
        except:
            years = 1.0
        
        metrics = {
            'start_date': start_date,
            'end_date': end_date,
            'initial_capital': equity_curve.iloc[0] if len(equity_curve) > 0 else 0,
            'final_capital': equity_curve.iloc[-1] if len(equity_curve) > 0 else 0,
            'total_return_pct': PerformanceMetrics.calculate_total_return(equity_curve),
            'cagr_pct': PerformanceMetrics.calculate_cagr(equity_curve, years),
            'mdd_pct': PerformanceMetrics.calculate_mdd(equity_curve),
            'sharpe_ratio': PerformanceMetrics.calculate_sharpe_ratio(returns),
            'total_trades': len(trades),
            'win_rate_pct': PerformanceMetrics.calculate_win_rate(trades),
            'profit_factor': PerformanceMetrics.calculate_profit_factor(trades),
            'avg_profit': PerformanceMetrics.calculate_avg_profit(trades),
        }
        
        return metrics
