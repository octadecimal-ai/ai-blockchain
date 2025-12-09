"""
Testy jednostkowe dla BinanceCollector.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta

from src.collectors.exchange.binance_collector import BinanceCollector


class TestBinanceCollector:
    """Testy dla klasy BinanceCollector."""
    
    def test_init_sandbox(self):
        """Test inicjalizacji w trybie sandbox."""
        with patch('src.collectors.exchange.binance_collector.ccxt') as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.binance.return_value = mock_exchange
            
            collector = BinanceCollector(sandbox=True)
            
            assert collector.exchange == mock_exchange
            mock_exchange.set_sandbox_mode.assert_called_once_with(True)
    
    def test_init_production(self):
        """Test inicjalizacji w trybie produkcyjnym."""
        with patch('src.collectors.exchange.binance_collector.ccxt') as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.binance.return_value = mock_exchange
            
            collector = BinanceCollector(sandbox=False)
            
            assert collector.exchange == mock_exchange
            mock_exchange.set_sandbox_mode.assert_not_called()
    
    def test_init_with_api_keys(self):
        """Test inicjalizacji z API keys."""
        with patch('src.collectors.exchange.binance_collector.ccxt') as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.binance.return_value = mock_exchange
            
            collector = BinanceCollector(
                sandbox=False,
                api_key='test_key',
                secret='test_secret'
            )
            
            # Sprawdź czy API keys zostały przekazane
            call_args = mock_ccxt.binance.call_args[0][0]
            assert call_args['apiKey'] == 'test_key'
            assert call_args['secret'] == 'test_secret'
    
    def test_fetch_ohlcv_success(self, sample_ohlcv_dataframe):
        """Test pomyślnego pobrania danych OHLCV."""
        with patch('src.collectors.exchange.binance_collector.ccxt') as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.binance.return_value = mock_exchange
            
            # Mock danych OHLCV
            mock_ohlcv = [
                [1609459200000, 50000, 51000, 49000, 50500, 1000],
                [1609462800000, 50500, 51500, 49500, 51000, 1200],
            ]
            mock_exchange.fetch_ohlcv.return_value = mock_ohlcv
            
            collector = BinanceCollector()
            df = collector.fetch_ohlcv("BTC/USDT", "1h", limit=2)
            
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert 'open' in df.columns
            assert 'high' in df.columns
            assert 'low' in df.columns
            assert 'close' in df.columns
            assert 'volume' in df.columns
    
    def test_fetch_ohlcv_default_since(self):
        """Test domyślnej daty początkowej (7 dni wstecz)."""
        with patch('src.collectors.exchange.binance_collector.ccxt') as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.binance.return_value = mock_exchange
            mock_exchange.fetch_ohlcv.return_value = []
            
            collector = BinanceCollector()
            collector.fetch_ohlcv("BTC/USDT", "1h")
            
            # Sprawdź czy since jest około 7 dni wstecz
            call_args = mock_exchange.fetch_ohlcv.call_args
            since_ms = call_args[1]['since']
            since_dt = datetime.fromtimestamp(since_ms / 1000)
            days_diff = (datetime.now() - since_dt).days
            
            assert 6 <= days_diff <= 8  # Tolerancja 1 dzień
    
    def test_fetch_ohlcv_error_handling(self):
        """Test obsługi błędów przy pobieraniu danych."""
        with patch('src.collectors.exchange.binance_collector.ccxt') as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.binance.return_value = mock_exchange
            mock_exchange.fetch_ohlcv.side_effect = Exception("API Error")
            
            collector = BinanceCollector()
            
            with pytest.raises(Exception):
                collector.fetch_ohlcv("BTC/USDT", "1h")
    
    def test_fetch_historical_pagination(self):
        """Test paginacji przy pobieraniu danych historycznych."""
        with patch('src.collectors.exchange.binance_collector.ccxt') as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.binance.return_value = mock_exchange
            
            # Mock wielu stron danych
            mock_exchange.fetch_ohlcv.side_effect = [
                [[1609459200000, 50000, 51000, 49000, 50500, 1000]] * 1000,
                [[1609545600000, 50500, 51500, 49500, 51000, 1200]] * 500,
                []  # Koniec danych
            ]
            
            collector = BinanceCollector()
            start = datetime.now() - timedelta(days=10)
            end = datetime.now()
            
            df = collector.fetch_historical("BTC/USDT", "1h", start, end)
            
            # Sprawdź czy były wywołane requesty z paginacją
            assert mock_exchange.fetch_ohlcv.call_count >= 2
    
    def test_save_to_csv(self, sample_ohlcv_dataframe, tmp_path):
        """Test zapisu do CSV."""
        import os
        
        with patch('src.collectors.exchange.binance_collector.ccxt') as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.binance.return_value = mock_exchange
            
            collector = BinanceCollector()
            
            # save_to_csv dodaje prefix "data/raw/" do filename
            filename = "test_data.csv"
            result = collector.save_to_csv(sample_ohlcv_dataframe, filename)
            
            # Sprawdź czy zwrócona ścieżka istnieje
            assert result.exists()
            
            # Cleanup
            os.remove(result)
    
    def test_get_ticker(self):
        """Test pobierania tickera."""
        with patch('src.collectors.exchange.binance_collector.ccxt') as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.binance.return_value = mock_exchange
            mock_exchange.fetch_ticker.return_value = {
                'last': 50000.0,
                'bid': 49999.0,
                'ask': 50001.0
            }
            
            collector = BinanceCollector()
            ticker = collector.get_ticker("BTC/USDT")
            
            assert ticker['last'] == 50000.0
            mock_exchange.fetch_ticker.assert_called_once_with("BTC/USDT")

