"""
Strategies 모듈 초기화
"""
from .base_strategy import BaseStrategy
from .ma_crossover import MovingAverageCrossover

__all__ = ['BaseStrategy', 'MovingAverageCrossover']
