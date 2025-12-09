"""
Testy jednostkowe dla DatabaseManager.
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.database.manager import DatabaseManager
from src.database.models import OHLCV, Signal


class TestDatabaseManager:
    """Testy dla klasy DatabaseManager."""
    
    def test_init_default_sqlite(self, temp_db_path):
        """Test inicjalizacji z domyślną bazą SQLite."""
        with patch('src.database.manager.os.path.join') as mock_join:
            mock_join.return_value = str(temp_db_path)
            
            db = DatabaseManager()
            
            assert 'sqlite' in db.database_url.lower()
            assert db.use_timescale is False
    
    def test_init_postgresql(self):
        """Test inicjalizacji z PostgreSQL."""
        db = DatabaseManager(
            database_url="postgresql://user:pass@localhost:5432/test",
            use_timescale=True
        )
        
        assert 'postgresql' in db.database_url
        assert db.use_timescale is True
    
    def test_create_tables(self, temp_db_path):
        """Test tworzenia tabel."""
        db = DatabaseManager(database_url=f"sqlite:///{temp_db_path}")
        db.create_tables()
        
        # Sprawdź czy plik bazy został utworzony
        assert temp_db_path.exists()
    
    def test_save_ohlcv(self, temp_db_path, sample_ohlcv_dataframe):
        """Test zapisu danych OHLCV."""
        db = DatabaseManager(database_url=f"sqlite:///{temp_db_path}")
        db.create_tables()
        
        # Ogranicz dane do 10 rekordów dla szybkości testu
        df = sample_ohlcv_dataframe.head(10)
        
        count = db.save_ohlcv(df, "binance", "BTC/USDT", "1h")
        
        assert count > 0
    
    def test_save_ohlcv_duplicates(self, temp_db_path, sample_ohlcv_dataframe):
        """Test zapisu duplikatów (powinny być ignorowane)."""
        db = DatabaseManager(database_url=f"sqlite:///{temp_db_path}")
        db.create_tables()
        
        df = sample_ohlcv_dataframe.head(5)
        
        # Zapisz dwa razy
        count1 = db.save_ohlcv(df, "binance", "BTC/USDT", "1h")
        count2 = db.save_ohlcv(df, "binance", "BTC/USDT", "1h")
        
        # Drugi zapis powinien zwrócić 0 (duplikaty)
        assert count2 == 0
    
    def test_get_ohlcv(self, temp_db_path, sample_ohlcv_dataframe):
        """Test pobierania danych OHLCV."""
        db = DatabaseManager(database_url=f"sqlite:///{temp_db_path}")
        db.create_tables()
        
        df = sample_ohlcv_dataframe.head(10)
        db.save_ohlcv(df, "binance", "BTC/USDT", "1h")
        
        # Pobierz dane
        result = db.get_ohlcv("binance", "BTC/USDT", "1h", limit=5)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) <= 5
        assert 'close' in result.columns
    
    def test_get_ohlcv_empty(self, temp_db_path):
        """Test pobierania z pustej bazy."""
        db = DatabaseManager(database_url=f"sqlite:///{temp_db_path}")
        db.create_tables()
        
        result = db.get_ohlcv("binance", "BTC/USDT", "1h")
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
    
    def test_save_signal(self, temp_db_path):
        """Test zapisu sygnału."""
        db = DatabaseManager(database_url=f"sqlite:///{temp_db_path}")
        db.create_tables()
        
        db.save_signal(
            exchange="binance",
            symbol="BTC/USDT",
            signal_type="buy",
            strategy="test_strategy",
            price=50000.0
        )
        
        # Sprawdź czy sygnał został zapisany
        signals = db.get_recent_signals()
        assert len(signals) > 0
        assert signals[0].symbol == "BTC/USDT"
        assert signals[0].signal_type == "buy"
    
    def test_get_recent_signals(self, temp_db_path):
        """Test pobierania ostatnich sygnałów."""
        db = DatabaseManager(database_url=f"sqlite:///{temp_db_path}")
        db.create_tables()
        
        # Zapisz kilka sygnałów
        for i in range(5):
            db.save_signal(
                exchange="binance",
                symbol="BTC/USDT",
                signal_type="buy",
                strategy="test",
                price=50000.0 + i
            )
        
        signals = db.get_recent_signals(limit=3)
        
        assert len(signals) <= 3
        assert all(s.symbol == "BTC/USDT" for s in signals)
    
    def test_get_stats(self, temp_db_path, sample_ohlcv_dataframe):
        """Test statystyk bazy danych."""
        db = DatabaseManager(database_url=f"sqlite:///{temp_db_path}")
        db.create_tables()
        
        df = sample_ohlcv_dataframe.head(10)
        db.save_ohlcv(df, "binance", "BTC/USDT", "1h")
        db.save_signal("binance", "BTC/USDT", "buy", "test", 50000.0)
        
        stats = db.get_stats()
        
        assert 'ohlcv_count' in stats
        assert 'signals_count' in stats
        assert stats['ohlcv_count'] > 0
        assert stats['signals_count'] > 0
    
    def test_get_available_data(self, temp_db_path, sample_ohlcv_dataframe):
        """Test podsumowania dostępnych danych."""
        db = DatabaseManager(database_url=f"sqlite:///{temp_db_path}")
        db.create_tables()
        
        df = sample_ohlcv_dataframe.head(10)
        db.save_ohlcv(df, "binance", "BTC/USDT", "1h")
        db.save_ohlcv(df, "dydx", "BTC-USD", "1h")
        
        available = db.get_available_data()
        
        assert isinstance(available, pd.DataFrame)
        assert len(available) >= 2  # Co najmniej 2 kombinacje exchange:symbol:timeframe

