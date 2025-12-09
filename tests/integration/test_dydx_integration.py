"""
Testy integracyjne dla DydxCollector.

UWAGA: dYdX v4 API jest publiczne i nie wymaga API keys dla podstawowych endpointów.
"""

import pytest
from datetime import datetime, timedelta

from src.collectors.exchange.dydx_collector import DydxCollector


@pytest.mark.integration
class TestDydxIntegration:
    """Testy integracyjne z API dYdX."""
    
    @pytest.fixture
    def collector(self):
        """Inicjalizacja kolektora."""
        return DydxCollector(testnet=False)
    
    def test_get_markets_real(self, collector):
        """Test pobierania rzeczywistych rynków."""
        df = collector.get_markets()
        
        assert len(df) > 0
        assert 'ticker' in df.columns
        assert 'BTC-USD' in df['ticker'].values
    
    def test_get_ticker_real(self, collector):
        """Test pobierania rzeczywistego tickera."""
        ticker = collector.get_ticker("BTC-USD")
        
        assert ticker['ticker'] == 'BTC-USD'
        assert ticker['oracle_price'] > 0
        assert 'next_funding_rate' in ticker
    
    def test_fetch_candles_real(self, collector):
        """Test pobierania rzeczywistych świec."""
        df = collector.fetch_candles("BTC-USD", "1HOUR", limit=10)
        
        assert len(df) > 0
        assert 'close' in df.columns
        assert df['close'].iloc[-1] > 0
    
    def test_get_funding_rates_real(self, collector):
        """Test pobierania rzeczywistych funding rates."""
        df = collector.get_funding_rates("BTC-USD", limit=10)
        
        assert len(df) > 0
        assert 'funding_rate' in df.columns
        # timestamp może być w index lub columns
        assert 'timestamp' in df.columns or df.index.name == 'timestamp'
    
    def test_compare_with_cex_real(self, collector):
        """Test porównania z CEX (wymaga mocka ceny CEX)."""
        # Używamy przykładowej ceny CEX
        cex_price = 50000.0
        
        result = collector.compare_with_cex("BTC-USD", cex_price=cex_price)
        
        assert 'dydx_price' in result
        assert 'cex_price' in result
        assert 'spread_percent' in result
        assert result['cex_price'] == cex_price

