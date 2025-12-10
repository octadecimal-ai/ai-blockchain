"""
Extended Trading Models
=======================
Rozszerzone modele dla strategii i rejestru transakcji.
"""

from datetime import datetime, timezone
from typing import Optional
import json

from sqlalchemy import (
    Column, String, Float, Integer, DateTime, 
    ForeignKey, Boolean, Text, JSON
)
from sqlalchemy.orm import relationship

from src.database.models import Base


def utcnow():
    """Zwraca aktualny czas UTC."""
    return datetime.now(timezone.utc)


class Strategy(Base):
    """
    Rejestr strategii tradingowych.
    """
    __tablename__ = 'strategies'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identyfikacja
    name = Column(String(100), nullable=False, unique=True)  # np. "piotrek_breakout_strategy"
    display_name = Column(String(200), nullable=False)  # np. "Strategia Breakout Piotrka"
    version = Column(String(20), nullable=False, default="1.0.0")
    
    # Opis
    description = Column(Text, nullable=True)
    author = Column(String(100), nullable=True)
    
    # Konfiguracja (JSON)
    default_config = Column(JSON, nullable=True)  # Domyślna konfiguracja strategii
    
    # Parametry handlowe
    min_confidence = Column(Float, default=5.0)  # Minimalna pewność sygnału
    risk_reward_ratio = Column(Float, default=2.0)  # Stosunek zysku do ryzyka
    max_drawdown_percent = Column(Float, default=20.0)  # Maksymalny drawdown (%)
    
    # Statystyki backtestów
    backtest_win_rate = Column(Float, nullable=True)
    backtest_profit_factor = Column(Float, nullable=True)
    backtest_total_trades = Column(Integer, nullable=True)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    # Relacje
    trade_registers = relationship("TradeRegister", back_populates="strategy")
    
    def __repr__(self):
        return f"<Strategy {self.name} v{self.version}>"
    
    def get_config(self) -> dict:
        """Zwraca konfigurację jako dict."""
        if isinstance(self.default_config, str):
            return json.loads(self.default_config)
        return self.default_config or {}
    
    def set_config(self, config: dict):
        """Ustawia konfigurację."""
        self.default_config = config


class TradeRegister(Base):
    """
    Kompletny rejestr wszystkich transakcji.
    
    Rejestruje WSZYSTKIE szczegóły transakcji dla audytu i analizy.
    """
    __tablename__ = 'trade_registers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Powiązania
    account_id = Column(Integer, ForeignKey('paper_accounts.id'), nullable=False)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=True)
    paper_trade_id = Column(Integer, ForeignKey('paper_trades.id'), nullable=True)
    
    # Podstawowe info
    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)  # long/short
    mode = Column(String(10), nullable=False)  # paper/real
    
    # Wejście
    entry_timestamp = Column(DateTime, nullable=False)
    entry_price = Column(Float, nullable=False)
    entry_size = Column(Float, nullable=False)
    entry_value_usd = Column(Float, nullable=False)
    
    # Leverage i margin
    leverage = Column(Float, nullable=False, default=1.0)
    margin_required = Column(Float, nullable=False)
    margin_available_before = Column(Float, nullable=False)
    
    # Wyjście
    exit_timestamp = Column(DateTime, nullable=True)
    exit_price = Column(Float, nullable=True)
    exit_reason = Column(String(100), nullable=True)  # stop_loss, take_profit, signal, manual, time_limit, max_loss
    
    # PnL
    pnl_gross = Column(Float, nullable=True)  # Brutto (przed opłatami)
    pnl_net = Column(Float, nullable=True)  # Netto (po opłatach)
    pnl_percent = Column(Float, nullable=True)
    
    # Opłaty
    fee_entry = Column(Float, default=0.0)
    fee_exit = Column(Float, default=0.0)
    fee_total = Column(Float, default=0.0)
    fee_percent = Column(Float, default=0.0)
    
    # Stop Loss / Take Profit
    stop_loss_price = Column(Float, nullable=True)
    take_profit_price = Column(Float, nullable=True)
    stop_loss_triggered = Column(Boolean, default=False)
    take_profit_triggered = Column(Boolean, default=False)
    
    # Kontekst rynkowy (w momencie wejścia)
    market_price_at_entry = Column(Float, nullable=True)
    market_volume_24h = Column(Float, nullable=True)
    market_volatility = Column(Float, nullable=True)
    
    # Wskaźniki techniczne (w momencie wejścia)
    rsi_at_entry = Column(Float, nullable=True)
    macd_at_entry = Column(Float, nullable=True)
    bb_position_at_entry = Column(Float, nullable=True)  # Pozycja w Bollinger Bands (0-1)
    
    # Dane strategii
    signal_confidence = Column(Float, nullable=True)  # Pewność sygnału (0-10)
    signal_reason = Column(Text, nullable=True)  # Powód wejścia
    strategy_parameters = Column(JSON, nullable=True)  # Parametry strategii użyte w transakcji
    
    # Timing
    duration_seconds = Column(Integer, nullable=True)
    duration_human = Column(String(50), nullable=True)  # np. "2h 15m 30s"
    
    # Limity i kontrole
    max_loss_limit = Column(Float, nullable=True)  # Limit maksymalnej straty (USD)
    max_loss_triggered = Column(Boolean, default=False)
    time_limit_seconds = Column(Integer, nullable=True)  # Limit czasu (sekundy)
    time_limit_triggered = Column(Boolean, default=False)
    
    # Slippage i execution
    expected_entry_price = Column(Float, nullable=True)
    actual_entry_price = Column(Float, nullable=True)
    entry_slippage_percent = Column(Float, nullable=True)
    
    expected_exit_price = Column(Float, nullable=True)
    actual_exit_price = Column(Float, nullable=True)
    exit_slippage_percent = Column(Float, nullable=True)
    
    # Notatki i tagi
    notes = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)  # Lista tagów
    
    # Session info
    session_id = Column(String(100), nullable=True)  # ID sesji tradingowej
    bot_version = Column(String(50), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    # Relacje
    strategy = relationship("Strategy", back_populates="trade_registers")
    
    def __repr__(self):
        status = "OPEN" if self.exit_timestamp is None else "CLOSED"
        return f"<TradeRegister {self.symbol} {self.side} {status} PnL: ${self.pnl_net or 0:.2f}>"
    
    @property
    def is_open(self) -> bool:
        """Czy transakcja jest otwarta."""
        return self.exit_timestamp is None
    
    @property
    def is_profitable(self) -> bool:
        """Czy transakcja była zyskowna."""
        return self.pnl_net is not None and self.pnl_net > 0
    
    def calculate_duration(self):
        """Oblicza czas trwania transakcji."""
        if self.exit_timestamp and self.entry_timestamp:
            delta = self.exit_timestamp - self.entry_timestamp
            self.duration_seconds = int(delta.total_seconds())
            
            # Format czytelny dla człowieka
            hours = self.duration_seconds // 3600
            minutes = (self.duration_seconds % 3600) // 60
            seconds = self.duration_seconds % 60
            
            parts = []
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0:
                parts.append(f"{minutes}m")
            if seconds > 0 or not parts:
                parts.append(f"{seconds}s")
            
            self.duration_human = " ".join(parts)
    
    def add_tag(self, tag: str):
        """Dodaje tag do transakcji."""
        if self.tags is None:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)
    
    def to_dict(self) -> dict:
        """Konwertuje do słownika (do exportu)."""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side,
            'mode': self.mode,
            'entry_timestamp': self.entry_timestamp.isoformat() if self.entry_timestamp else None,
            'exit_timestamp': self.exit_timestamp.isoformat() if self.exit_timestamp else None,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'size': self.entry_size,
            'leverage': self.leverage,
            'pnl_net': self.pnl_net,
            'pnl_percent': self.pnl_percent,
            'exit_reason': self.exit_reason,
            'duration': self.duration_human,
            'strategy': self.strategy.name if self.strategy else None,
            'signal_confidence': self.signal_confidence,
            'tags': self.tags
        }


class TradingSession(Base):
    """
    Sesja tradingowa - grupuje transakcje z jednego uruchomienia bota.
    """
    __tablename__ = 'trading_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identyfikacja
    session_id = Column(String(100), nullable=False, unique=True)
    account_id = Column(Integer, ForeignKey('paper_accounts.id'), nullable=False)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=True)
    
    # Konfiguracja sesji
    mode = Column(String(10), nullable=False)  # paper/real
    symbols = Column(JSON, nullable=False)  # Lista symboli
    
    # Timing
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Limity
    time_limit_seconds = Column(Integer, nullable=True)
    max_loss_limit = Column(Float, nullable=True)
    max_positions = Column(Integer, nullable=True)
    
    # Statystyki
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)
    
    # Stan konta
    starting_balance = Column(Float, nullable=False)
    ending_balance = Column(Float, nullable=True)
    peak_balance = Column(Float, nullable=True)
    max_drawdown = Column(Float, default=0.0)
    
    # Powód zakończenia
    end_reason = Column(String(100), nullable=True)  # time_limit, max_loss, manual, error
    
    # Notatki
    notes = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    def __repr__(self):
        status = "ACTIVE" if self.ended_at is None else "ENDED"
        return f"<TradingSession {self.session_id} {status}>"
    
    @property
    def is_active(self) -> bool:
        """Czy sesja jest aktywna."""
        return self.ended_at is None
    
    @property
    def win_rate(self) -> float:
        """Procent wygranych transakcji."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    @property
    def roi(self) -> float:
        """ROI sesji."""
        if self.starting_balance == 0:
            return 0.0
        balance = self.ending_balance or self.starting_balance
        return ((balance - self.starting_balance) / self.starting_balance) * 100

