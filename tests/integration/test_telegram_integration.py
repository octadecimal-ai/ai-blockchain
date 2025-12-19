"""
Testy integracyjne dla TelegramCollector.

UWAGA: Telegram nie ma sandbox/testnet, ale można użyć testowego bota.
Testy wymagają TELEGRAM_BOT_TOKEN i TELEGRAM_CHAT_ID w .env.
Jeśli brak - testy są pomijane.
"""

import pytest
import os

from src.collectors.sentiment.telegram_collector import TelegramCollector


@pytest.mark.integration
class TestTelegramIntegration:
    """Testy integracyjne z Telegram Bot API."""
    
    @pytest.fixture
    def collector(self):
        """Inicjalizacja kolektora."""
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not bot_token or not chat_id:
            pytest.skip("Brak TELEGRAM_BOT_TOKEN lub TELEGRAM_CHAT_ID w .env")
        
        return TelegramCollector(bot_token=bot_token, chat_id=chat_id)
    
    def test_get_me_real(self, collector):
        """Test pobierania informacji o bocie."""
        bot_info = collector.get_me()
        
        assert bot_info is not None
        assert 'id' in bot_info
        assert 'username' in bot_info or 'first_name' in bot_info
    
    def test_send_message_real(self, collector):
        """Test wysyłania rzeczywistej wiadomości."""
        # Użyj timestamp aby uniknąć duplikatów
        test_message = f"Test message from AI Blockchain - {os.getpid()}"
        
        result = collector.send_message(test_message)
        
        assert result is not None
        assert result.get('ok') is True
        assert 'result' in result
    
    def test_send_signal_alert_real(self, collector):
        """Test wysyłania alertu o sygnale."""
        result = collector.send_signal_alert(
            symbol="BTC/USDT",
            signal_type="buy",
            price=50000.0,
            strategy="test_strategy",
            additional_info="Test integration"
        )
        
        assert result is not None
        assert result.get('ok') is True
    
    def test_send_market_report_real(self, collector):
        """Test wysyłania raportu rynkowego."""
        report = """
        Market Analysis:
        - BTC: $50,000 (+5%)
        - ETH: $3,000 (+3%)
        - Market sentiment: Bullish
        """
        
        result = collector.send_market_report(report, title="📊 Test Raport")
        
        assert result is not None
        assert result.get('ok') is True
    
    def test_get_updates_real(self, collector):
        """Test pobierania wiadomości."""
        updates = collector.get_updates(limit=10)
        
        assert isinstance(updates, list)
        # Może być puste jeśli brak nowych wiadomości

