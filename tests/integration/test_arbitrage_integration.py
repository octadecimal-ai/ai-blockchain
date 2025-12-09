"""
Testy integracyjne dla ArbitrageScanner.

WYMAGANE: BINANCE_API_KEY i BINANCE_SECRET w .env (opcjonalnie)
Instrukcje: docs/setup/binance_api_setup.md
"""

import pytest
import os

from src.strategies.arbitrage import ArbitrageScanner


@pytest.mark.integration
class TestArbitrageIntegration:
    """Testy integracyjne dla skanera arbitrażu."""
    
    @pytest.fixture
    def scanner(self):
        """Inicjalizacja skanera."""
        scanner = ArbitrageScanner()
        
        # Opcjonalnie ustaw API keys dla Binance
        api_key = os.getenv('BINANCE_API_KEY')
        secret = os.getenv('BINANCE_SECRET')
        
        if api_key and secret:
            from src.collectors.exchange.binance_collector import BinanceCollector
            scanner._binance = BinanceCollector(
                sandbox=False,
                api_key=api_key,
                secret=secret
            )
        
        return scanner
    
    def test_scan_single_real(self, scanner):
        """Test skanowania pojedynczego asseta z rzeczywistymi danymi."""
        opp = scanner.scan_single("BTC")
        
        # Może zwrócić None jeśli brak okazji lub błędów API
        if opp is not None:
            assert opp.symbol == "BTC"
            assert opp.exchange_buy in ["binance", "dydx"]
            assert opp.exchange_sell in ["binance", "dydx"]
            assert opp.exchange_buy != opp.exchange_sell
    
    def test_scan_all_real(self, scanner):
        """Test skanowania wszystkich assetów."""
        opportunities = scanner.scan_all(parallel=False)
        
        # Sprawdź czy zwrócono listę (może być pusta)
        assert isinstance(opportunities, list)
        
        if opportunities:
            # Sprawdź czy są posortowane
            assert all(
                opportunities[i].net_profit_percent >= opportunities[i+1].net_profit_percent
                for i in range(len(opportunities) - 1)
            )
    
    def test_scan_funding_arbitrage_real(self, scanner):
        """Test skanowania funding rate arbitrage."""
        opportunities = scanner.scan_funding_arbitrage()
        
        assert isinstance(opportunities, list)
        
        if opportunities:
            assert 'asset' in opportunities[0]
            assert 'annual_rate' in opportunities[0]

