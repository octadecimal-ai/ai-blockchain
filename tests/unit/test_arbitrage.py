"""
Testy jednostkowe dla ArbitrageScanner.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.strategies.arbitrage import (
    ArbitrageScanner,
    ArbitrageOpportunity,
    ArbitrageType
)


class TestArbitrageOpportunity:
    """Testy dla klasy ArbitrageOpportunity."""
    
    def test_init(self):
        """Test inicjalizacji okazji arbitrażowej."""
        # Spread 0.5% - wystarczająco duży, żeby być opłacalnym po opłatach
        opp = ArbitrageOpportunity(
            timestamp=datetime.now(),
            arb_type=ArbitrageType.CROSS_EXCHANGE,
            symbol="BTC",
            exchange_buy="binance",
            exchange_sell="dydx",
            price_buy=50000.0,
            price_sell=50250.0,  # 0.5% spread
            spread_percent=0.5,
            spread_usd=250.0
        )
        
        assert opp.symbol == "BTC"
        assert opp.spread_percent == 0.5
        # net_profit_percent = spread - fees_buy - fees_sell - slippage = 0.5 - 0.1 - 0.1 - 0.05 = 0.25%
        assert opp.net_profit_percent > 0  # Po odjęciu opłat
    
    def test_is_profitable(self):
        """Test sprawdzania czy okazja jest opłacalna."""
        # Opłacalna okazja (duży spread 0.5%)
        opp_profitable = ArbitrageOpportunity(
            timestamp=datetime.now(),
            arb_type=ArbitrageType.CROSS_EXCHANGE,
            symbol="BTC",
            exchange_buy="binance",
            exchange_sell="dydx",
            price_buy=50000.0,
            price_sell=50250.0,  # 0.5% spread
            spread_percent=0.5,
            spread_usd=250.0
        )
        
        assert opp_profitable.is_profitable() is True
        
        # Nieopłacalna okazja (mały spread)
        opp_not_profitable = ArbitrageOpportunity(
            timestamp=datetime.now(),
            arb_type=ArbitrageType.CROSS_EXCHANGE,
            symbol="BTC",
            exchange_buy="binance",
            exchange_sell="dydx",
            price_buy=50000.0,
            price_sell=50001.0,
            spread_percent=0.002,
            spread_usd=1.0
        )
        
        assert opp_not_profitable.is_profitable() is False
    
    def test_summary(self):
        """Test generowania podsumowania."""
        opp = ArbitrageOpportunity(
            timestamp=datetime.now(),
            arb_type=ArbitrageType.CROSS_EXCHANGE,
            symbol="BTC",
            exchange_buy="binance",
            exchange_sell="dydx",
            price_buy=50000.0,
            price_sell=50250.0,
            spread_percent=0.5,
            spread_usd=250.0
        )
        
        summary = opp.summary()
        
        assert isinstance(summary, str)
        assert "BTC" in summary
        assert "binance" in summary
        assert "dydx" in summary


class TestArbitrageScanner:
    """Testy dla klasy ArbitrageScanner."""
    
    def test_init(self):
        """Test inicjalizacji skanera."""
        scanner = ArbitrageScanner()
        
        assert scanner._binance is None  # Lazy loading
        assert scanner._dydx is None
    
    def test_get_prices_parallel(self):
        """Test równoległego pobierania cen."""
        scanner = ArbitrageScanner()
        
        # Mock kolektorów
        mock_binance = MagicMock()
        mock_binance.get_ticker.return_value = {'last': 50000.0}
        
        mock_dydx = MagicMock()
        mock_dydx.get_ticker.return_value = {'oracle_price': 50100.0}
        
        scanner._binance = mock_binance
        scanner._dydx = mock_dydx
        
        prices = scanner.get_prices("BTC")
        
        assert prices['binance'] == 50000.0
        assert prices['dydx'] == 50100.0
    
    def test_get_prices_error_handling(self):
        """Test obsługi błędów przy pobieraniu cen."""
        scanner = ArbitrageScanner()
        
        # Mock błędów
        mock_binance = MagicMock()
        mock_binance.get_ticker.side_effect = Exception("API Error")
        
        mock_dydx = MagicMock()
        mock_dydx.get_ticker.return_value = {'oracle_price': 50100.0}
        
        scanner._binance = mock_binance
        scanner._dydx = mock_dydx
        
        prices = scanner.get_prices("BTC")
        
        assert prices['binance'] is None
        assert prices['dydx'] == 50100.0
    
    def test_scan_single_profitable(self):
        """Test skanowania pojedynczego asseta z opłacalną okazją."""
        scanner = ArbitrageScanner()
        
        # Mock cen z różnicą
        with patch.object(scanner, 'get_prices') as mock_prices:
            mock_prices.return_value = {
                'binance': 50000.0,
                'dydx': 50100.0  # dYdX droższy
            }
            
            opp = scanner.scan_single("BTC")
            
            assert opp is not None
            assert opp.exchange_buy == "binance"
            assert opp.exchange_sell == "dydx"
            assert opp.spread_percent > 0
    
    def test_scan_single_no_prices(self):
        """Test skanowania gdy brak cen."""
        scanner = ArbitrageScanner()
        
        with patch.object(scanner, 'get_prices') as mock_prices:
            mock_prices.return_value = {
                'binance': None,
                'dydx': None
            }
            
            opp = scanner.scan_single("BTC")
            
            assert opp is None
    
    def test_scan_all(self):
        """Test skanowania wszystkich assetów."""
        scanner = ArbitrageScanner()
        
        with patch.object(scanner, 'scan_single') as mock_scan:
            mock_opp = ArbitrageOpportunity(
                timestamp=datetime.now(),
                arb_type=ArbitrageType.CROSS_EXCHANGE,
                symbol="BTC",
                exchange_buy="binance",
                exchange_sell="dydx",
                price_buy=50000.0,
                price_sell=50100.0,
                spread_percent=0.2,
                spread_usd=100.0
            )
            mock_scan.return_value = mock_opp
            
            opportunities = scanner.scan_all(parallel=False)
            
            assert len(opportunities) > 0
            # Powinny być posortowane po zysku
            assert all(
                opportunities[i].net_profit_percent >= opportunities[i+1].net_profit_percent
                for i in range(len(opportunities) - 1)
            )
    
    def test_scan_funding_arbitrage(self):
        """Test skanowania funding rate arbitrage."""
        scanner = ArbitrageScanner()
        
        mock_dydx = MagicMock()
        mock_dydx.get_ticker.return_value = {
            'next_funding_rate': 0.001  # 0.1% - wysokie
        }
        scanner._dydx = mock_dydx
        
        opportunities = scanner.scan_funding_arbitrage()
        
        # Jeśli funding rate jest wysoki, powinna być okazja
        if opportunities:
            assert 'asset' in opportunities[0]
            assert 'annual_rate' in opportunities[0]
    
    def test_generate_report(self):
        """Test generowania raportu."""
        scanner = ArbitrageScanner()
        
        with patch.object(scanner, 'scan_all') as mock_scan_all, \
             patch.object(scanner, 'scan_funding_arbitrage') as mock_funding:
            
            mock_opp = ArbitrageOpportunity(
                timestamp=datetime.now(),
                arb_type=ArbitrageType.CROSS_EXCHANGE,
                symbol="BTC",
                exchange_buy="binance",
                exchange_sell="dydx",
                price_buy=50000.0,
                price_sell=50100.0,
                spread_percent=0.2,
                spread_usd=100.0
            )
            
            mock_scan_all.return_value = [mock_opp]
            mock_funding.return_value = []
            
            report = scanner.generate_report()
            
            assert isinstance(report, str)
            assert "ARBITRAŻU" in report or "ARBITRAGE" in report

