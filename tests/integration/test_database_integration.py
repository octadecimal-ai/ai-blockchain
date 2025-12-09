"""
Testy integracyjne dla DatabaseManager.

UWAGA: Dla testów z PostgreSQL/TimescaleDB wymagane są zmienne środowiskowe:
- DATABASE_URL (postgresql://user:pass@localhost:5432/test)
- USE_TIMESCALE=true (opcjonalnie)

Dla testów SQLite nie są wymagane żadne konfiguracje.
"""

import pytest
import os
import pandas as pd
from datetime import datetime, timedelta

from src.database.manager import DatabaseManager


@pytest.mark.integration
class TestDatabaseIntegration:
    """Testy integracyjne dla bazy danych."""
    
    @pytest.fixture
    def db_manager(self, temp_db_path):
        """Inicjalizacja DatabaseManager."""
        # Użyj PostgreSQL jeśli dostępny, w przeciwnym razie SQLite
        db_url = os.getenv('DATABASE_URL')
        use_timescale = os.getenv('USE_TIMESCALE', 'false').lower() == 'true'
        
        if db_url and 'postgresql' in db_url:
            db = DatabaseManager(
                database_url=db_url,
                use_timescale=use_timescale
            )
        else:
            # SQLite dla testów
            db = DatabaseManager(database_url=f"sqlite:///{temp_db_path}")
        
        db.create_tables()
        return db
    
    def test_save_and_retrieve_ohlcv(self, db_manager, sample_ohlcv_dataframe):
        """Test zapisu i odczytu danych OHLCV."""
        # Zapisz dane
        count = db_manager.save_ohlcv(
            sample_ohlcv_dataframe.head(20),
            "binance",
            "BTC/USDT",
            "1h"
        )
        
        assert count > 0
        
        # Pobierz dane
        df = db_manager.get_ohlcv("binance", "BTC/USDT", "1h", limit=10)
        
        assert len(df) > 0
        assert 'close' in df.columns
        # exchange i symbol nie są zwracane w get_ohlcv DataFrame
    
    def test_bulk_insert_performance(self, db_manager, sample_ohlcv_dataframe):
        """Test wydajności bulk insert."""
        import time
        
        # Użyj oryginalnych danych (bez duplikatów)
        df = sample_ohlcv_dataframe.head(50)
        
        start = time.time()
        count = db_manager.save_ohlcv(
            df,
            "binance",
            "ETH/USDT",  # Użyj innego symbolu, żeby uniknąć konfliktów
            "1h"
        )
        elapsed = time.time() - start
        
        assert count > 0
        # Bulk insert powinien być szybki
        assert elapsed < 5.0
    
    def test_get_stats_real(self, db_manager, sample_ohlcv_dataframe):
        """Test statystyk z rzeczywistymi danymi."""
        # Dodaj dane
        db_manager.save_ohlcv(
            sample_ohlcv_dataframe.head(10),
            "binance",
            "BTC/USDT",
            "1h"
        )
        db_manager.save_signal(
            "binance",
            "BTC/USDT",
            "buy",
            "test_strategy",
            50000.0
        )
        
        stats = db_manager.get_stats()
        
        assert stats['ohlcv_count'] > 0
        assert stats['signals_count'] > 0
    
    def test_get_available_data(self, db_manager, sample_ohlcv_dataframe):
        """Test podsumowania dostępnych danych."""
        # Dodaj dane z różnych źródeł
        db_manager.save_ohlcv(
            sample_ohlcv_dataframe.head(10),
            "binance",
            "BTC/USDT",
            "1h"
        )
        db_manager.save_ohlcv(
            sample_ohlcv_dataframe.head(10),
            "dydx",
            "BTC-USD",
            "1h"
        )
        
        available = db_manager.get_available_data()
        
        assert len(available) >= 2
        assert any(
            row['exchange'] == 'binance' and row['symbol'] == 'BTC/USDT'
            for _, row in available.iterrows()
        )

