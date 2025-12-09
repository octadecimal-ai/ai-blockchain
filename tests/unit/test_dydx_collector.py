"""
Testy jednostkowe dla DydxCollector.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime

from src.collectors.exchange.dydx_collector import DydxCollector


class TestDydxCollector:
    """Testy dla klasy DydxCollector."""
    
    def test_init_testnet(self):
        """Test inicjalizacji w trybie testnet."""
        with patch('src.collectors.exchange.dydx_collector.requests') as mock_requests:
            collector = DydxCollector(testnet=True)
            
            assert collector.testnet is True
            assert "testnet" in collector.base_url.lower()
    
    def test_init_mainnet(self):
        """Test inicjalizacji w trybie mainnet."""
        with patch('src.collectors.exchange.dydx_collector.requests') as mock_requests:
            collector = DydxCollector(testnet=False)
            
            assert collector.testnet is False
            assert "testnet" not in collector.base_url.lower()
    
    def test_make_request_success(self):
        """Test pomyślnego requestu do API."""
        with patch('src.collectors.exchange.dydx_collector.requests') as mock_requests:
            mock_response = MagicMock()
            mock_response.json.return_value = {'data': 'test'}
            mock_response.raise_for_status = Mock()
            mock_requests.Session.return_value.get.return_value = mock_response
            
            collector = DydxCollector()
            result = collector._make_request("/test")
            
            assert result == {'data': 'test'}
    
    def test_make_request_retry(self):
        """Test retry logic przy błędach."""
        import requests as real_requests
        
        with patch.object(DydxCollector, '__init__', lambda self, testnet=False: None):
            collector = DydxCollector()
            collector.base_url = "https://test.api"
            collector.testnet = False
            collector.session = MagicMock()
            
            # Pierwsze 2 próby fail, trzecia sukces
            mock_response = MagicMock()
            mock_response.json.return_value = {'data': 'success'}
            mock_response.raise_for_status = Mock()
            
            collector.session.get.side_effect = [
                real_requests.exceptions.RequestException("Error 1"),
                real_requests.exceptions.RequestException("Error 2"),
                mock_response
            ]
            
            result = collector._make_request("/test", max_retries=3)
            
            assert result == {'data': 'success'}
            assert collector.session.get.call_count == 3
    
    def test_get_markets(self):
        """Test pobierania listy rynków."""
        with patch.object(DydxCollector, '_make_request') as mock_request:
            mock_request.return_value = {
                'markets': {
                    'BTC-USD': {
                        'status': 'ACTIVE',
                        'baseAsset': 'BTC',
                        'oraclePrice': '50000'
                    }
                }
            }
            
            collector = DydxCollector()
            df = collector.get_markets()
            
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 1
            assert df.iloc[0]['ticker'] == 'BTC-USD'
    
    def test_get_ticker(self):
        """Test pobierania tickera."""
        with patch.object(DydxCollector, '_make_request') as mock_request:
            mock_request.return_value = {
                'markets': {
                    'BTC-USD': {
                        'oraclePrice': '50000',
                        'priceChange24H': '0.05',
                        'volume24H': '1000000',
                        'nextFundingRate': '0.0001'
                    }
                }
            }
            
            collector = DydxCollector()
            ticker = collector.get_ticker("BTC-USD")
            
            assert ticker['ticker'] == 'BTC-USD'
            assert ticker['oracle_price'] == 50000.0
            assert ticker['next_funding_rate'] == 0.0001
    
    def test_fetch_candles(self):
        """Test pobierania świec."""
        with patch.object(DydxCollector, '_make_request') as mock_request:
            mock_request.return_value = {
                'candles': [
                    {
                        'startedAt': '2024-01-01T00:00:00Z',
                        'open': '50000',
                        'high': '51000',
                        'low': '49000',
                        'close': '50500',
                        'baseTokenVolume': '1000',
                        'usdVolume': '50000000',
                        'trades': '100'
                    }
                ]
            }
            
            collector = DydxCollector()
            df = collector.fetch_candles("BTC-USD", "1h", limit=1)
            
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 1
            assert 'open' in df.columns
            assert 'close' in df.columns
    
    def test_get_funding_rates(self):
        """Test pobierania funding rates."""
        with patch.object(DydxCollector, '_make_request') as mock_request:
            mock_request.return_value = {
                'historicalFunding': [
                    {
                        'effectiveAt': '2024-01-01T00:00:00Z',
                        'rate': '0.0001',
                        'price': '50000'
                    }
                ]
            }
            
            collector = DydxCollector()
            df = collector.get_funding_rates("BTC-USD", limit=1)
            
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 1
            assert 'funding_rate' in df.columns
    
    def test_compare_with_cex(self):
        """Test porównania z CEX."""
        with patch.object(DydxCollector, 'get_ticker') as mock_ticker:
            mock_ticker.return_value = {
                'oracle_price': 50000.0,
                'next_funding_rate': 0.0001
            }
            
            collector = DydxCollector()
            result = collector.compare_with_cex("BTC-USD", cex_price=49900.0)
            
            assert result['dydx_price'] == 50000.0
            assert result['cex_price'] == 49900.0
            assert result['spread_percent'] > 0  # dYdX droższy
            assert 'opportunity' in result

