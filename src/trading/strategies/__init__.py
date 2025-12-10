"""
Strategie tradingowe.
"""

from .piotrek_strategy import PiotrekBreakoutStrategy
from .base_strategy import BaseStrategy

__all__ = [
    'BaseStrategy',
    'PiotrekBreakoutStrategy'
]

