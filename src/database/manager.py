"""
Database Manager
================
Zarządzanie połączeniem z bazą danych i operacjami CRUD.

Obsługuje:
- SQLite (development)
- PostgreSQL + TimescaleDB (produkcja)
- Automatyczne tworzenie tabel
- Bulk insert dla dużych zbiorów danych
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from loguru import logger

from .models import (
    Base, OHLCV, Ticker, FundingRate, Trade, 
    TechnicalIndicator, SentimentScore, Signal,
    create_timescale_hypertables
)


class DatabaseManager:
    """
    Manager do zarządzania bazą danych.
    
    Przykłady użycia:
    
    # SQLite (development)
    db = DatabaseManager()
    
    # PostgreSQL (produkcja)
    db = DatabaseManager("postgresql://user:pass@localhost:5432/ai_blockchain")
    
    # TimescaleDB
    db = DatabaseManager("postgresql://...", use_timescale=True)
    """
    
    def __init__(
        self,
        database_url: str = None,
        use_timescale: bool = False,
        echo: bool = False
    ):
        """
        Inicjalizacja managera bazy danych.
        
        Args:
            database_url: URL do bazy (domyślnie SQLite w data/)
            use_timescale: Czy użyć TimescaleDB (wymaga PostgreSQL)
            echo: Czy logować zapytania SQL
        """
        if database_url is None:
            # Domyślnie SQLite
            db_path = os.path.join(
                os.path.dirname(__file__), 
                '..', '..', 'data', 'ai_blockchain.db'
            )
            database_url = f"sqlite:///{os.path.abspath(db_path)}"
        
        self.database_url = database_url
        self.use_timescale = use_timescale
        
        # Konfiguracja connection pool
        pool_config = {}
        if 'postgresql' in database_url:
            pool_config = {
                'poolclass': QueuePool,
                'pool_size': 5,
                'max_overflow': 10,
                'pool_timeout': 30
            }
        
        self.engine = create_engine(
            database_url,
            echo=echo,
            **pool_config
        )
        
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
            expire_on_commit=False  # Pozwala na dostęp do atrybutów po zamknięciu sesji
        )
        
        logger.info(f"DatabaseManager zainicjalizowany: {self._safe_url()}")
    
    def _safe_url(self) -> str:
        """Zwraca URL bez hasła."""
        url = self.database_url
        if '@' in url:
            parts = url.split('@')
            creds = parts[0].split('://')
            return f"{creds[0]}://***@{parts[1]}"
        return url
    
    def create_tables(self):
        """Tworzy wszystkie tabele."""
        Base.metadata.create_all(bind=self.engine)
        logger.success("Tabele utworzone")
        
        if self.use_timescale and 'postgresql' in self.database_url:
            create_timescale_hypertables(self.engine)
    
    def drop_tables(self):
        """Usuwa wszystkie tabele (UWAGA!)."""
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("Tabele usunięte")
    
    @contextmanager
    def get_session(self) -> Session:
        """Context manager dla sesji."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    # === OHLCV Operations ===
    
    def save_ohlcv(
        self,
        df: pd.DataFrame,
        exchange: str,
        symbol: str,
        timeframe: str
    ) -> int:
        """
        Zapisuje DataFrame OHLCV do bazy (bulk insert z obsługą duplikatów).
        
        Args:
            df: DataFrame z kolumnami open, high, low, close, volume
            exchange: Nazwa giełdy
            symbol: Symbol pary
            timeframe: Interwał czasowy
            
        Returns:
            Liczba zapisanych rekordów
        """
        if df.empty:
            return 0
        
        records = []
        for timestamp, row in df.iterrows():
            records.append({
                'timestamp': timestamp,
                'exchange': exchange,
                'symbol': symbol,
                'timeframe': timeframe,
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume'],
                'trades_count': row.get('trades', None),
            })
        
        inserted_count = 0
        
        # Bulk insert z obsługą duplikatów
        if 'postgresql' in self.database_url:
            # PostgreSQL: użyj ON CONFLICT DO NOTHING
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            
            with self.get_session() as session:
                stmt = pg_insert(OHLCV).values(records)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=['timestamp', 'exchange', 'symbol', 'timeframe']
                )
                result = session.execute(stmt)
                inserted_count = result.rowcount if result.rowcount else len(records)
        else:
            # SQLite/inne: batch insert z ignorowaniem błędów
            with self.get_session() as session:
                for record in records:
                    try:
                        # Sprawdź czy istnieje (optymalizacja: można użyć INSERT OR IGNORE)
                        existing = session.query(OHLCV).filter(
                            OHLCV.timestamp == record['timestamp'],
                            OHLCV.exchange == record['exchange'],
                            OHLCV.symbol == record['symbol'],
                            OHLCV.timeframe == record['timeframe']
                        ).first()
                        
                        if not existing:
                            session.add(OHLCV(**record))
                            inserted_count += 1
                    except Exception:
                        continue
        
        logger.info(f"Zapisano {inserted_count}/{len(records)} świec {exchange}:{symbol} {timeframe}")
        return inserted_count
    
    def get_ohlcv(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = None
    ) -> pd.DataFrame:
        """
        Pobiera dane OHLCV z bazy.
        
        Args:
            exchange: Nazwa giełdy
            symbol: Symbol pary
            timeframe: Interwał czasowy
            start_date: Data początkowa
            end_date: Data końcowa
            limit: Limit rekordów
            
        Returns:
            DataFrame z danymi OHLCV
        """
        with self.get_session() as session:
            query = session.query(OHLCV).filter(
                OHLCV.exchange == exchange,
                OHLCV.symbol == symbol,
                OHLCV.timeframe == timeframe
            )
            
            if start_date:
                query = query.filter(OHLCV.timestamp >= start_date)
            if end_date:
                query = query.filter(OHLCV.timestamp <= end_date)
            
            query = query.order_by(OHLCV.timestamp.desc())
            
            if limit:
                query = query.limit(limit)
            
            results = query.all()
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame([{
            'timestamp': r.timestamp,
            'open': r.open,
            'high': r.high,
            'low': r.low,
            'close': r.close,
            'volume': r.volume,
        } for r in results])
        
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        return df
    
    # === Funding Rates ===
    
    def save_funding_rates(
        self,
        df: pd.DataFrame,
        exchange: str,
        symbol: str
    ) -> int:
        """Zapisuje funding rates do bazy."""
        if df.empty:
            return 0
        
        with self.get_session() as session:
            for timestamp, row in df.iterrows():
                existing = session.query(FundingRate).filter(
                    FundingRate.timestamp == timestamp,
                    FundingRate.exchange == exchange,
                    FundingRate.symbol == symbol
                ).first()
                
                if not existing:
                    session.add(FundingRate(
                        timestamp=timestamp,
                        exchange=exchange,
                        symbol=symbol,
                        funding_rate=row['funding_rate'],
                        price_at_funding=row.get('price', None)
                    ))
        
        logger.info(f"Zapisano {len(df)} funding rates {exchange}:{symbol}")
        return len(df)
    
    # === Sygnały ===
    
    def save_signal(
        self,
        exchange: str,
        symbol: str,
        signal_type: str,
        strategy: str,
        price: float,
        **kwargs
    ):
        """Zapisuje sygnał handlowy."""
        with self.get_session() as session:
            signal = Signal(
                timestamp=datetime.now(timezone.utc),
                exchange=exchange,
                symbol=symbol,
                signal_type=signal_type,
                strategy=strategy,
                price_at_signal=price,
                **kwargs
            )
            session.add(signal)
        
        logger.info(f"📢 Sygnał: {signal_type.upper()} {symbol} @ ${price:,.2f} ({strategy})")
    
    def get_recent_signals(
        self,
        symbol: str = None,
        hours: int = 24,
        limit: int = 50
    ) -> List[Signal]:
        """Pobiera ostatnie sygnały."""
        with self.get_session() as session:
            query = session.query(Signal).filter(
                Signal.timestamp >= datetime.now(timezone.utc) - timedelta(hours=hours)
            )
            
            if symbol:
                query = query.filter(Signal.symbol == symbol)
            
            return query.order_by(Signal.timestamp.desc()).limit(limit).all()
    
    # === Statystyki ===
    
    def get_stats(self) -> dict:
        """Zwraca statystyki bazy danych."""
        with self.get_session() as session:
            stats = {
                'ohlcv_count': session.query(OHLCV).count(),
                'tickers_count': session.query(Ticker).count(),
                'funding_rates_count': session.query(FundingRate).count(),
                'trades_count': session.query(Trade).count(),
                'signals_count': session.query(Signal).count(),
            }
            
            # Ostatni timestamp
            latest_ohlcv = session.query(OHLCV).order_by(OHLCV.timestamp.desc()).first()
            if latest_ohlcv:
                stats['latest_ohlcv'] = latest_ohlcv.timestamp.isoformat()
                stats['latest_symbol'] = f"{latest_ohlcv.exchange}:{latest_ohlcv.symbol}"
        
        return stats
    
    def get_available_data(self) -> pd.DataFrame:
        """Zwraca podsumowanie dostępnych danych."""
        query = """
            SELECT 
                exchange,
                symbol,
                timeframe,
                MIN(timestamp) as first_date,
                MAX(timestamp) as last_date,
                COUNT(*) as candle_count
            FROM ohlcv
            GROUP BY exchange, symbol, timeframe
            ORDER BY exchange, symbol, timeframe
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
        
        if not rows:
            return pd.DataFrame()
        
        return pd.DataFrame(rows, columns=[
            'exchange', 'symbol', 'timeframe', 
            'first_date', 'last_date', 'candle_count'
        ])


# === Przykład użycia ===
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Dodaj ścieżkę projektu
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    from src.collectors.exchange.binance_collector import BinanceCollector
    
    # Inicjalizacja bazy
    db = DatabaseManager()
    db.create_tables()
    
    print("\n📊 DATABASE STATS:")
    print(db.get_stats())
    
    # Pobierz i zapisz dane
    print("\n⬇️ Pobieram dane z Binance...")
    collector = BinanceCollector()
    df = collector.fetch_ohlcv("BTC/USDT", "1h", limit=100)
    
    print(f"Pobrano {len(df)} świec")
    
    # Zapisz do bazy
    saved = db.save_ohlcv(df, "binance", "BTC/USDT", "1h")
    print(f"Zapisano {saved} świec do bazy")
    
    # Odczytaj z bazy
    print("\n⬆️ Odczytuję z bazy...")
    df_from_db = db.get_ohlcv("binance", "BTC/USDT", "1h", limit=5)
    print(df_from_db)
    
    # Statystyki
    print("\n📈 Dostępne dane:")
    print(db.get_available_data())

