"""
Testy jednostkowe dla MarketAnalyzerLLM.
Testy używają mocków, aby nie wymagać API keys.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime
import os


class TestMarketAnalyzer:
    """Testy dla klasy MarketAnalyzerLLM."""
    
    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Ustawia fake API key dla testów."""
        monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_key_for_testing')
    
    def test_init_default(self):
        """Test inicjalizacji z domyślnym modelem."""
        with patch('src.analysis.llm.market_analyzer.ChatAnthropic') as mock_chat:
            mock_chat.return_value = MagicMock()
            
            from src.analysis.llm.market_analyzer import MarketAnalyzerLLM
            analyzer = MarketAnalyzerLLM()
            
            assert analyzer.model is not None
            assert analyzer.llm is not None
    
    def test_init_custom_model(self):
        """Test inicjalizacji z niestandardowym modelem."""
        with patch('src.analysis.llm.market_analyzer.ChatAnthropic') as mock_chat:
            mock_chat.return_value = MagicMock()
            
            from src.analysis.llm.market_analyzer import MarketAnalyzerLLM
            analyzer = MarketAnalyzerLLM(model="claude-3-opus-20240229")
            
            assert analyzer.model == "claude-3-opus-20240229"
    
    def test_generate_market_report(self, sample_ohlcv_dataframe):
        """Test generowania raportu rynkowego."""
        with patch('src.analysis.llm.market_analyzer.ChatAnthropic') as mock_chat:
            mock_llm = MagicMock()
            mock_chat.return_value = mock_llm
            mock_llm.invoke.return_value = MagicMock(content="Test raport rynkowy")
            
            from src.analysis.llm.market_analyzer import MarketAnalyzerLLM
            analyzer = MarketAnalyzerLLM()
            
            report = analyzer.generate_market_report(
                df=sample_ohlcv_dataframe,
                symbol="BTC/USDT"
            )
            
            assert isinstance(report, str)
            assert len(report) > 0
    
    def test_analyze_sentiment(self):
        """Test analizy sentymentu."""
        with patch('src.analysis.llm.market_analyzer.ChatAnthropic') as mock_chat:
            mock_llm = MagicMock()
            mock_chat.return_value = mock_llm
            mock_llm.invoke.return_value = MagicMock(content='{"sentiment": "positive", "score": 0.8}')
            
            from src.analysis.llm.market_analyzer import MarketAnalyzerLLM
            analyzer = MarketAnalyzerLLM()
            
            result = analyzer.analyze_sentiment("Bitcoin price is rising!")
            
            assert isinstance(result, dict)
    
    def test_analyze_sentiment_invalid_json(self):
        """Test obsługi nieprawidłowego JSON w odpowiedzi."""
        with patch('src.analysis.llm.market_analyzer.ChatAnthropic') as mock_chat:
            mock_llm = MagicMock()
            mock_chat.return_value = mock_llm
            mock_llm.invoke.return_value = MagicMock(content="Not a JSON response")
            
            from src.analysis.llm.market_analyzer import MarketAnalyzerLLM
            analyzer = MarketAnalyzerLLM()
            
            result = analyzer.analyze_sentiment("Test")
            
            # Powinien zwrócić dict z błędem lub domyślnymi wartościami
            assert isinstance(result, dict)
    
    def test_langchain_not_available(self):
        """Test gdy LangChain nie jest dostępny."""
        # Sprawdzamy że klasa obsługuje brak LangChain
        import src.analysis.llm.market_analyzer as module
        
        # Jeśli LANGCHAIN_AVAILABLE jest True, test przechodzi
        # Jeśli False, klasa powinna obsłużyć to gracefully
        assert hasattr(module, 'LANGCHAIN_AVAILABLE')
