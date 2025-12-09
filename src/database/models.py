"""
Database Models
===============
Modele SQLAlchemy dla danych kryptowalutowych.

Używamy:
- TimescaleDB (PostgreSQL) dla danych produkcyjnych - idealny do szeregów czasowych
- SQLite dla development/testów

TimescaleDB automatycznie partycjonuje dane po czasie,
co daje 10-100x lepszą wydajność na dużych zbiorach danych.
"""

from datetime import datetime, timezone
from typing import Optional


def utcnow():
    """Zwraca aktualny czas UTC (kompatybilne z Python 3.12+)."""
    return datetime.now(timezone.utc)
from sqlalchemy import (
    Column, String, Float, Integer, DateTime, BigInteger,
    Index, UniqueConstraint, ForeignKey, Boolean, Text, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class Exchange(enum.Enum):
    """Obsługiwane giełdy."""
    BINANCE = "binance"
    DYDX = "dydx"
    COINBASE = "coinbase"
    KRAKEN = "kraken"


class MarketType(enum.Enum):
    """Typ rynku."""
    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURES = "futures"


# === Główne tabele danych rynkowych ===

class OHLCV(Base):
    """
    Tabela świec OHLCV (Open, High, Low, Close, Volume).
    
    To główna tabela z danymi cenowymi.
    W TimescaleDB zostanie skonwertowana na hypertable.
    """
    __tablename__ = 'ohlcv'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    exchange = Column(String(50), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)  # np. BTC/USDT, BTC-USD
    timeframe = Column(String(10), nullable=False, index=True)  # 1m, 5m, 1h, 1d
    
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    
    # Opcjonalne pola
    quote_volume = Column(Float, nullable=True)  # Wolumen w walucie kwotowanej
    trades_count = Column(Integer, nullable=True)  # Liczba transakcji
    
    created_at = Column(DateTime, default=utcnow)
    
    __table_args__ = (
        UniqueConstraint('timestamp', 'exchange', 'symbol', 'timeframe', name='uq_ohlcv'),
        Index('ix_ohlcv_lookup', 'exchange', 'symbol', 'timeframe', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<OHLCV {self.exchange}:{self.symbol} {self.timeframe} @ {self.timestamp}>"


class Ticker(Base):
    """
    Snapshoty tickerów - aktualne ceny i wolumeny.
    Przydatne do analizy sentymentu w czasie rzeczywistym.
    """
    __tablename__ = 'tickers'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    exchange = Column(String(50), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    
    price = Column(Float, nullable=False)
    bid = Column(Float, nullable=True)
    ask = Column(Float, nullable=True)
    spread = Column(Float, nullable=True)
    
    volume_24h = Column(Float, nullable=True)
    change_24h = Column(Float, nullable=True)
    high_24h = Column(Float, nullable=True)
    low_24h = Column(Float, nullable=True)
    
    # Dla perpetual (dYdX)
    funding_rate = Column(Float, nullable=True)
    open_interest = Column(Float, nullable=True)
    
    __table_args__ = (
        Index('ix_ticker_lookup', 'exchange', 'symbol', 'timestamp'),
    )


class FundingRate(Base):
    """
    Historia funding rates dla kontraktów perpetual.
    Kluczowe dla strategii arbitrażowych i analizy sentymentu.
    """
    __tablename__ = 'funding_rates'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    exchange = Column(String(50), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    
    funding_rate = Column(Float, nullable=False)  # Stawka (zazwyczaj -0.01% do +0.01%)
    price_at_funding = Column(Float, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('timestamp', 'exchange', 'symbol', name='uq_funding'),
        Index('ix_funding_lookup', 'exchange', 'symbol', 'timestamp'),
    )


class Trade(Base):
    """
    Pojedyncze transakcje - przydatne do analizy on-chain.
    """
    __tablename__ = 'trades'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    exchange = Column(String(50), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    
    trade_id = Column(String(100), nullable=True)  # ID z giełdy
    side = Column(String(10), nullable=False)  # buy/sell
    price = Column(Float, nullable=False)
    size = Column(Float, nullable=False)
    
    __table_args__ = (
        Index('ix_trade_lookup', 'exchange', 'symbol', 'timestamp'),
    )


# === Wskaźniki techniczne (pre-obliczone) ===

class TechnicalIndicator(Base):
    """
    Pre-obliczone wskaźniki techniczne.
    Pozwala na szybkie zapytania bez obliczania w locie.
    """
    __tablename__ = 'technical_indicators'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    exchange = Column(String(50), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    
    # Średnie kroczące
    sma_20 = Column(Float, nullable=True)
    sma_50 = Column(Float, nullable=True)
    sma_200 = Column(Float, nullable=True)
    ema_9 = Column(Float, nullable=True)
    ema_21 = Column(Float, nullable=True)
    
    # Oscylatory
    rsi = Column(Float, nullable=True)
    macd = Column(Float, nullable=True)
    macd_signal = Column(Float, nullable=True)
    macd_histogram = Column(Float, nullable=True)
    
    # Bollinger Bands
    bb_upper = Column(Float, nullable=True)
    bb_middle = Column(Float, nullable=True)
    bb_lower = Column(Float, nullable=True)
    
    # Zmienność
    atr = Column(Float, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('timestamp', 'exchange', 'symbol', 'timeframe', name='uq_indicators'),
    )


# === Analiza sentymentu ===

class SentimentScore(Base):
    """
    Wyniki analizy sentymentu z różnych źródeł.
    """
    __tablename__ = 'sentiment_scores'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    source = Column(String(50), nullable=False)  # twitter, reddit, news, llm
    
    score = Column(Float, nullable=False)  # -100 do +100
    sentiment = Column(String(20), nullable=False)  # bullish/bearish/neutral
    confidence = Column(Float, nullable=True)  # 0-1
    
    sample_size = Column(Integer, nullable=True)  # Liczba przeanalizowanych tekstów
    raw_data = Column(Text, nullable=True)  # JSON z dodatkowymi danymi
    
    __table_args__ = (
        Index('ix_sentiment_lookup', 'symbol', 'source', 'timestamp'),
    )


# === Alerty i sygnały ===

class Signal(Base):
    """
    Sygnały handlowe wygenerowane przez system.
    """
    __tablename__ = 'signals'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(50), nullable=False, index=True)
    
    signal_type = Column(String(50), nullable=False)  # buy, sell, hold
    strategy = Column(String(100), nullable=False)  # nazwa strategii
    strength = Column(Float, nullable=True)  # 0-1
    
    price_at_signal = Column(Float, nullable=False)
    target_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    
    notes = Column(Text, nullable=True)
    executed = Column(Boolean, default=False)


# === Konfiguracja portfolio ===

class Portfolio(Base):
    """
    Śledzenie pozycji w portfolio.
    """
    __tablename__ = 'portfolio'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    initial_capital = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class Position(Base):
    """
    Pozycje w portfolio.
    """
    __tablename__ = 'positions'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey('portfolio.id'), nullable=False)
    
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)  # long/short
    
    entry_price = Column(Float, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    size = Column(Float, nullable=False)
    
    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    
    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    
    status = Column(String(20), default='open')  # open/closed
    notes = Column(Text, nullable=True)


# === Helper do tworzenia tabel TimescaleDB ===

TIMESCALE_HYPERTABLES = [
    ('ohlcv', 'timestamp'),
    ('tickers', 'timestamp'),
    ('funding_rates', 'timestamp'),
    ('trades', 'timestamp'),
    ('technical_indicators', 'timestamp'),
    ('sentiment_scores', 'timestamp'),
]

def create_timescale_hypertables(engine):
    """
    Konwertuje tabele na hypertables TimescaleDB.
    Wywoływane po create_all() dla PostgreSQL z TimescaleDB.
    """
    from sqlalchemy import text
    
    with engine.connect() as conn:
        # Sprawdź czy TimescaleDB jest zainstalowany
        result = conn.execute(text("SELECT * FROM pg_extension WHERE extname = 'timescaledb'"))
        if not result.fetchone():
            print("TimescaleDB nie jest zainstalowany, używam zwykłych tabel")
            return
        
        for table_name, time_column in TIMESCALE_HYPERTABLES:
            try:
                conn.execute(text(
                    f"SELECT create_hypertable('{table_name}', '{time_column}', "
                    f"if_not_exists => TRUE, migrate_data => TRUE)"
                ))
                print(f"✓ Utworzono hypertable: {table_name}")
            except Exception as e:
                print(f"⚠ Hypertable {table_name}: {e}")
        
        conn.commit()

