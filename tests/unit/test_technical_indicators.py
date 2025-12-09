"""
Testy jednostkowe dla TechnicalAnalyzer.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.analysis.technical.indicators import TechnicalAnalyzer


class TestTechnicalAnalyzer:
    """Testy dla klasy TechnicalAnalyzer."""
    
    def test_init_valid_dataframe(self, sample_ohlcv_dataframe):
        """Test inicjalizacji z poprawnym DataFrame."""
        analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
        assert analyzer.df is not None
        assert len(analyzer.df) == len(sample_ohlcv_dataframe)
    
    def test_init_missing_columns(self):
        """Test inicjalizacji z brakującymi kolumnami."""
        df = pd.DataFrame({'close': [100, 101, 102]})
        
        with pytest.raises(ValueError, match="Brakujące kolumny"):
            TechnicalAnalyzer(df)
    
    def test_add_sma(self, sample_ohlcv_dataframe):
        """Test dodawania Simple Moving Average."""
        analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
        analyzer.add_sma(periods=[20])
        
        assert 'sma_20' in analyzer.df.columns
        assert analyzer.df['sma_20'].iloc[-1] is not None
    
    def test_add_sma_default_periods(self, sample_ohlcv_dataframe):
        """Test domyślnych okresów SMA."""
        analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
        analyzer.add_sma()
        
        assert 'sma_20' in analyzer.df.columns
        assert 'sma_50' in analyzer.df.columns
        assert 'sma_200' in analyzer.df.columns
    
    def test_add_ema(self, sample_ohlcv_dataframe):
        """Test dodawania Exponential Moving Average."""
        analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
        analyzer.add_ema(periods=[9])
        
        assert 'ema_9' in analyzer.df.columns
    
    def test_add_rsi(self, sample_ohlcv_dataframe):
        """Test dodawania RSI."""
        analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
        analyzer.add_rsi(period=14)
        
        assert 'rsi' in analyzer.df.columns
        # RSI powinien być w zakresie 0-100
        rsi_values = analyzer.df['rsi'].dropna()
        if len(rsi_values) > 0:
            assert (rsi_values >= 0).all()
            assert (rsi_values <= 100).all()
    
    def test_add_macd(self, sample_ohlcv_dataframe):
        """Test dodawania MACD."""
        analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
        analyzer.add_macd()
        
        assert 'MACD_12_26_9' in analyzer.df.columns
        assert 'MACDs_12_26_9' in analyzer.df.columns
        assert 'MACDh_12_26_9' in analyzer.df.columns
    
    def test_add_bollinger_bands(self, sample_ohlcv_dataframe):
        """Test dodawania Bollinger Bands."""
        analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
        analyzer.add_bollinger_bands()
        
        assert 'BBM_20_2.0' in analyzer.df.columns
        assert 'BBU_20_2.0' in analyzer.df.columns
        assert 'BBL_20_2.0' in analyzer.df.columns
        
        # Upper band powinien być wyższy niż lower
        latest = analyzer.df.iloc[-1]
        if pd.notna(latest['BBU_20_2.0']) and pd.notna(latest['BBL_20_2.0']):
            assert latest['BBU_20_2.0'] > latest['BBL_20_2.0']
    
    def test_add_atr(self, sample_ohlcv_dataframe):
        """Test dodawania ATR."""
        analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
        analyzer.add_atr()
        
        assert 'atr' in analyzer.df.columns
        # ATR powinien być dodatni (pomijamy pierwsze 14 wartości - rolling window)
        atr_values = analyzer.df['atr'].dropna()
        # Bierzemy tylko wartości po okresie rozgrzewki (pierwsze 14 mogą być 0)
        atr_values_after_warmup = atr_values.iloc[14:]
        if len(atr_values_after_warmup) > 0:
            assert (atr_values_after_warmup > 0).all()
    
    def test_add_obv(self, sample_ohlcv_dataframe):
        """Test dodawania OBV."""
        analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
        analyzer.add_obv()
        
        assert 'obv' in analyzer.df.columns
    
    def test_add_all_indicators(self, sample_ohlcv_dataframe):
        """Test dodawania wszystkich wskaźników."""
        analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
        analyzer.add_all_indicators()
        
        # Sprawdź czy wszystkie podstawowe wskaźniki są dodane
        assert 'sma_20' in analyzer.df.columns
        assert 'ema_9' in analyzer.df.columns
        assert 'rsi' in analyzer.df.columns
        assert 'MACD_12_26_9' in analyzer.df.columns
        assert 'BBM_20_2.0' in analyzer.df.columns
        assert 'atr' in analyzer.df.columns
        assert 'obv' in analyzer.df.columns
    
    def test_get_signals(self, sample_ohlcv_dataframe):
        """Test generowania sygnałów."""
        analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
        analyzer.add_all_indicators()
        
        signals = analyzer.get_signals()
        
        assert isinstance(signals, dict)
        # Sprawdź czy są jakieś sygnały
        assert len(signals) > 0
    
    def test_get_signals_empty_dataframe(self):
        """Test sygnałów dla pustego DataFrame."""
        df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        analyzer = TechnicalAnalyzer(df)
        
        signals = analyzer.get_signals()
        assert signals == {}
    
    def test_get_dataframe(self, sample_ohlcv_dataframe):
        """Test zwracania DataFrame."""
        analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
        analyzer.add_sma()
        
        df = analyzer.get_dataframe()
        
        assert isinstance(df, pd.DataFrame)
        assert 'sma_20' in df.columns
    
    def test_summary(self, sample_ohlcv_dataframe):
        """Test generowania podsumowania."""
        analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
        analyzer.add_all_indicators()
        
        summary = analyzer.summary()
        
        assert isinstance(summary, str)
        assert "ANALIZY TECHNICZNEJ" in summary or "SYGNAŁY" in summary
    
    def test_method_chaining(self, sample_ohlcv_dataframe):
        """Test method chaining (fluent API)."""
        analyzer = (
            TechnicalAnalyzer(sample_ohlcv_dataframe)
            .add_sma()
            .add_ema()
            .add_rsi()
        )
        
        assert 'sma_20' in analyzer.df.columns
        assert 'ema_9' in analyzer.df.columns
        assert 'rsi' in analyzer.df.columns

