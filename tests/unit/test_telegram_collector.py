"""
Testy jednostkowe dla TelegramCollector.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.collectors.sentiment.telegram_collector import TelegramCollector


class TestTelegramCollector:
    """Testy dla klasy TelegramCollector."""
    
    def test_init_with_credentials(self):
        """Test inicjalizacji z credentials."""
        collector = TelegramCollector(
            bot_token="test_token",
            chat_id="test_chat_id"
        )
        
        assert collector.bot_token == "test_token"
        assert collector.chat_id == "test_chat_id"
        assert collector.api_url is not None
    
    def test_init_without_credentials(self, monkeypatch):
        """Test inicjalizacji bez credentials."""
        monkeypatch.delenv('TELEGRAM_BOT_TOKEN', raising=False)
        monkeypatch.delenv('TELEGRAM_CHAT_ID', raising=False)
        
        collector = TelegramCollector()
        
        assert collector.bot_token is None
        assert collector.api_url is None
    
    def test_init_from_env(self, monkeypatch):
        """Test inicjalizacji z zmiennych środowiskowych."""
        monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'env_token')
        monkeypatch.setenv('TELEGRAM_CHAT_ID', 'env_chat_id')
        
        collector = TelegramCollector()
        
        assert collector.bot_token == 'env_token'
        assert collector.chat_id == 'env_chat_id'
    
    def test_send_message_success(self):
        """Test pomyślnego wysyłania wiadomości."""
        collector = TelegramCollector(
            bot_token="test_token",
            chat_id="test_chat_id"
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'ok': True, 'result': {'message_id': 123}}
        mock_response.raise_for_status = Mock()
        
        with patch('src.collectors.sentiment.telegram_collector.requests.post', return_value=mock_response):
            result = collector.send_message("Test message")
            
            assert result is not None
            assert result['ok'] is True
    
    def test_send_message_error_handling(self):
        """Test obsługi błędów przy wysyłaniu."""
        collector = TelegramCollector(
            bot_token="test_token",
            chat_id="test_chat_id"
        )
        
        with patch('src.collectors.sentiment.telegram_collector.requests.post', side_effect=Exception("API Error")):
            result = collector.send_message("Test message")
            
            assert result is None
    
    def test_send_message_without_token(self):
        """Test wysyłania bez tokenu."""
        collector = TelegramCollector()
        
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            collector.send_message("Test")
    
    def test_send_message_without_chat_id(self):
        """Test wysyłania bez chat_id."""
        collector = TelegramCollector(bot_token="test_token")
        
        with pytest.raises(ValueError, match="chat_id"):
            collector.send_message("Test")
    
    def test_send_signal_alert(self):
        """Test wysyłania alertu o sygnale."""
        collector = TelegramCollector(
            bot_token="test_token",
            chat_id="test_chat_id"
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'ok': True}
        mock_response.raise_for_status = Mock()
        
        with patch.object(collector, 'send_message', return_value={'ok': True}):
            result = collector.send_signal_alert(
                symbol="BTC/USDT",
                signal_type="buy",
                price=50000.0,
                strategy="test_strategy"
            )
            
            assert result is not None
    
    def test_send_signal_alert_with_info(self):
        """Test wysyłania alertu z dodatkowymi informacjami."""
        collector = TelegramCollector(
            bot_token="test_token",
            chat_id="test_chat_id"
        )
        
        with patch.object(collector, 'send_message', return_value={'ok': True}) as mock_send:
            collector.send_signal_alert(
                symbol="BTC/USDT",
                signal_type="sell",
                price=51000.0,
                strategy="test_strategy",
                additional_info="RSI overbought"
            )
            
            # Sprawdź czy wiadomość zawiera dodatkowe info
            call_args = mock_send.call_args[0][0]
            assert "RSI overbought" in call_args
    
    def test_send_market_report(self):
        """Test wysyłania raportu rynkowego."""
        collector = TelegramCollector(
            bot_token="test_token",
            chat_id="test_chat_id"
        )
        
        report = "Market is bullish. BTC up 5%."
        
        with patch.object(collector, 'send_message', return_value={'ok': True}) as mock_send:
            result = collector.send_market_report(report)
            
            assert result is not None
            # Sprawdź czy raport jest w wiadomości
            call_args = mock_send.call_args[0][0]
            assert "Raport Rynkowy" in call_args
            assert "Market is bullish" in call_args
    
    def test_send_market_report_long_text(self):
        """Test wysyłania długiego raportu (obcięcie do 4000 znaków)."""
        collector = TelegramCollector(
            bot_token="test_token",
            chat_id="test_chat_id"
        )
        
        long_report = "A" * 5000  # 5000 znaków
        
        with patch.object(collector, 'send_message', return_value={'ok': True}) as mock_send:
            collector.send_market_report(long_report)
            
            call_args = mock_send.call_args[0][0]
            # Sprawdź czy został obcięty
            assert len(call_args) <= 4100  # Tytuł + obcięty tekst
    
    def test_get_updates(self):
        """Test pobierania wiadomości."""
        collector = TelegramCollector(bot_token="test_token")
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'ok': True,
            'result': [
                {'update_id': 1, 'message': {'text': 'Hello'}},
                {'update_id': 2, 'message': {'text': 'World'}}
            ]
        }
        mock_response.raise_for_status = Mock()
        
        with patch('src.collectors.sentiment.telegram_collector.requests.get', return_value=mock_response):
            updates = collector.get_updates()
            
            assert len(updates) == 2
            assert updates[0]['update_id'] == 1
    
    def test_get_me(self):
        """Test pobierania informacji o bocie."""
        collector = TelegramCollector(bot_token="test_token")
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'ok': True,
            'result': {
                'id': 123456,
                'username': 'test_bot',
                'first_name': 'Test Bot'
            }
        }
        mock_response.raise_for_status = Mock()
        
        with patch('src.collectors.sentiment.telegram_collector.requests.get', return_value=mock_response):
            bot_info = collector.get_me()
            
            assert bot_info is not None
            assert bot_info['username'] == 'test_bot'

