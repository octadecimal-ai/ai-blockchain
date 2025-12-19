"""
Paper Trading Models
====================
Modele SQLAlchemy dla paper tradingu na dYdX.
"""

from datetime import datetime, timezone
from typing import Optional
import enum

from sqlalchemy import (
    Column, String, Float, Integer, DateTime, 
    ForeignKey, Boolean, Text, Enum as SQLEnum
)
from sqlalchemy.orm import relationship

from src.database.models import Base


def utcnow():
    """Zwraca aktualny czas UTC."""
    return datetime.now(timezone.utc)


class OrderSide(enum.Enum):
    """Strona zlecenia."""
    LONG = "long"
    SHORT = "short"


class OrderType(enum.Enum):
    """Typ zlecenia."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(enum.Enum):
    """Status zlecenia."""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionStatus(enum.Enum):
    """Status pozycji."""
    OPEN = "open"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"


class PaperAccount(Base):
    """
    Wirtualne konto paper trading.
    """
    __tablename__ = 'paper_accounts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Kapitał
    initial_balance = Column(Float, nullable=False, default=10000.0)  # USD
    current_balance = Column(Float, nullable=False, default=10000.0)
    
    # Ustawienia
    leverage = Column(Float, nullable=False, default=1.0)  # Dźwignia (1-20x)
    maker_fee = Column(Float, nullable=False, default=0.0002)  # 0.02%
    taker_fee = Column(Float, nullable=False, default=0.0005)  # 0.05%
    
    # Statystyki
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    peak_balance = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    # Relacje
    positions = relationship("PaperPosition", back_populates="account")
    orders = relationship("PaperOrder", back_populates="account")
    trades = relationship("PaperTrade", back_populates="account")
    
    def __repr__(self):
        return f"<PaperAccount {self.name}: ${self.current_balance:.2f}>"
    
    @property
    def win_rate(self) -> float:
        """Procent wygranych transakcji."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    @property
    def roi(self) -> float:
        """Return on Investment (%)."""
        if self.initial_balance == 0:
            return 0.0
        return ((self.current_balance - self.initial_balance) / self.initial_balance) * 100


class PaperPosition(Base):
    """
    Otwarta pozycja paper trading.
    """
    __tablename__ = 'paper_positions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('paper_accounts.id'), nullable=False)
    
    # Pozycja
    symbol = Column(String(50), nullable=False)  # np. BTC-USD
    side = Column(SQLEnum(OrderSide), nullable=False)
    
    # Rozmiar i cena
    size = Column(Float, nullable=False)  # Ilość (np. 0.1 BTC)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    
    # Leverage
    leverage = Column(Float, nullable=False, default=1.0)
    margin_used = Column(Float, nullable=False)  # Zablokowany margin
    
    # Stop Loss / Take Profit
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    
    # PnL
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_percent = Column(Float, default=0.0)
    
    # Status
    status = Column(SQLEnum(PositionStatus), default=PositionStatus.OPEN)
    
    # Timestamps
    opened_at = Column(DateTime, default=utcnow)
    closed_at = Column(DateTime, nullable=True)
    
    # Notatki (np. powód wejścia)
    strategy = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relacje
    account = relationship("PaperAccount", back_populates="positions")
    
    def __repr__(self):
        return f"<PaperPosition {self.symbol} {self.side.value} {self.size} @ {self.entry_price}>"
    
    def calculate_pnl(self, current_price: float) -> tuple:
        """
        Oblicza PnL dla pozycji.
        
        Returns:
            (pnl_usd, pnl_percent)
        """
        if self.side == OrderSide.LONG:
            pnl = (current_price - self.entry_price) * self.size * self.leverage
            pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100 * self.leverage
        else:  # SHORT
            pnl = (self.entry_price - current_price) * self.size * self.leverage
            pnl_percent = ((self.entry_price - current_price) / self.entry_price) * 100 * self.leverage
        
        return pnl, pnl_percent
    
    def is_liquidated(self, current_price: float) -> bool:
        """
        Sprawdza czy pozycja została zlikwidowana.
        Likwidacja przy stracie 100% marginu.
        """
        _, pnl_percent = self.calculate_pnl(current_price)
        return pnl_percent <= -100.0


class PaperOrder(Base):
    """
    Zlecenie paper trading.
    """
    __tablename__ = 'paper_orders'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('paper_accounts.id'), nullable=False)
    
    # Zlecenie
    symbol = Column(String(50), nullable=False)
    side = Column(SQLEnum(OrderSide), nullable=False)
    order_type = Column(SQLEnum(OrderType), nullable=False)
    
    # Rozmiar i cena
    size = Column(Float, nullable=False)
    price = Column(Float, nullable=True)  # Dla LIMIT/STOP
    
    # Stop Loss / Take Profit
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    
    # Leverage
    leverage = Column(Float, nullable=False, default=1.0)
    
    # Status
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING)
    filled_size = Column(Float, default=0.0)
    filled_price = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=utcnow)
    filled_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    
    # Dodatkowe
    strategy = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relacje
    account = relationship("PaperAccount", back_populates="orders")
    
    def __repr__(self):
        return f"<PaperOrder {self.order_type.value} {self.side.value} {self.symbol} {self.size}>"


class PaperTrade(Base):
    """
    Wykonana transakcja paper trading.
    """
    __tablename__ = 'paper_trades'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('paper_accounts.id'), nullable=False)
    
    # Trade
    symbol = Column(String(50), nullable=False)
    side = Column(SQLEnum(OrderSide), nullable=False)
    
    # Wejście
    entry_price = Column(Float, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    size = Column(Float, nullable=False)
    leverage = Column(Float, nullable=False, default=1.0)
    
    # Wyjście
    exit_price = Column(Float, nullable=False)
    exit_time = Column(DateTime, nullable=False)
    
    # Koszty
    entry_fee = Column(Float, default=0.0)
    exit_fee = Column(Float, default=0.0)
    total_fees = Column(Float, default=0.0)
    
    # PnL
    pnl = Column(Float, nullable=False)
    pnl_percent = Column(Float, nullable=False)
    net_pnl = Column(Float, nullable=False)  # Po opłatach
    
    # Dodatkowe
    strategy = Column(String(100), nullable=True)
    exit_reason = Column(String(100), nullable=True)  # stop_loss, take_profit, manual, liquidation
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=utcnow)
    
    # Relacje
    account = relationship("PaperAccount", back_populates="trades")
    
    def __repr__(self):
        return f"<PaperTrade {self.symbol} {self.side.value}: ${self.net_pnl:.2f}>"
    
    @property
    def duration_minutes(self) -> float:
        """Czas trwania transakcji w minutach."""
        delta = self.exit_time - self.entry_time
        return delta.total_seconds() / 60

