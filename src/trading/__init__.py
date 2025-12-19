"""
Moduł tradingowy
================
Paper trading, strategie i zarządzanie pozycjami.
"""

from .paper_trading import PaperTradingEngine
from .strategies.piotrek_strategy import PiotrekBreakoutStrategy

# Import wszystkich modeli aby Base.metadata je widział
from .models import (
    Base as TradingBase,
    PaperAccount,
    PaperPosition,
    PaperOrder,
    PaperTrade,
    OrderSide,
    OrderType,
    OrderStatus,
    PositionStatus
)

from .models_extended import (
    Strategy,
    TradeRegister,
    TradingSession
)

__all__ = [
    'PaperTradingEngine',
    'PiotrekBreakoutStrategy',
    # Modele
    'TradingBase',
    'PaperAccount',
    'PaperPosition',
    'PaperOrder',
    'PaperTrade',
    'Strategy',
    'TradeRegister',
    'TradingSession',
    'OrderSide',
    'OrderType',
    'OrderStatus',
    'PositionStatus'
]

