"""
Testy integracyjne dla BinanceCollector.

WYMAGANE: BINANCE_API_KEY i BINANCE_SECRET w .env
Instrukcje: docs/setup/binance_api_setup.md
"""

import pytest
import os
from datetime import datetime, timedelta

from src.collectors.exchange.binance_collector import BinanceCollector


@pytest.mark.integration
class TestBinanceIntegration:
    """Testy integracyjne z API Binance."""
    
    @pytest.fixture
    def collector(self):
        """Inicjalizacja kolektora w trybie sandbox (nie wymaga API keys)."""
        # Binance sandbox nie wymaga API keys dla publicznych endpointów
        return BinanceCollector(sandbox=True)
    
    @pytest.fixture
    def collector_production(self):
        """Inicjalizacja kolektora produkcyjnego (wymaga API keys)."""
        api_key = os.getenv('BINANCE_API_KEY')
        secret = os.getenv('BINANCE_SECRET')
        
        if not api_key or not secret:
            pytest.skip("Brak BINANCE_API_KEY lub BINANCE_SECRET w .env")
        
        return BinanceCollector(
            sandbox=False,
            api_key=api_key,
            secret=secret
        )
    
    def test_fetch_ohlcv_sandbox(self, collector):
        """Test pobierania danych OHLCV z sandbox."""
        df = collector.fetch_ohlcv("BTC/USDT", "1h", limit=10)
        
        assert len(df) > 0
        assert 'close' in df.columns
        assert df['close'].iloc[-1] > 0
    
    def test_get_ticker_sandbox(self, collector):
        """Test pobierania tickera z sandbox."""
        ticker = collector.get_ticker("BTC/USDT")
        
        assert 'last' in ticker
        assert ticker['last'] > 0
        assert 'bid' in ticker
        assert 'ask' in ticker
    
    def test_get_available_symbols_sandbox(self, collector):
        """Test pobierania dostępnych symboli z sandbox."""
        symbols = collector.get_available_symbols()
        
        assert len(symbols) > 0
        assert "BTC/USDT" in symbols
    
    def test_fetch_historical_sandbox(self, collector):
        """Test pobierania danych historycznych z sandbox."""
        start = datetime.now() - timedelta(days=7)
        end = datetime.now()
        
        df = collector.fetch_historical("BTC/USDT", "1h", start, end)
        
        assert len(df) > 0
        assert df.index[0] <= start
        assert df.index[-1] <= end
    
    def test_fetch_ohlcv_real(self, collector_production):
        """Test pobierania rzeczywistych danych OHLCV (produkcja)."""
        df = collector_production.fetch_ohlcv("BTC/USDT", "1h", limit=10)
        
        assert len(df) > 0
        assert 'close' in df.columns
        assert df['close'].iloc[-1] > 0
    
    def test_get_ticker_real(self, collector_production):
        """Test pobierania rzeczywistego tickera (produkcja)."""
        ticker = collector_production.get_ticker("BTC/USDT")
        
        assert 'last' in ticker
        assert ticker['last'] > 0
        assert 'bid' in ticker
        assert 'ask' in ticker

