"""
Testy dla strategii Propagacji Sentymentu
==========================================
Testy jednostkowe i integracyjne dla strategii SentimentPropagationStrategy.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.trading.strategies.sentiment_propagation_strategy import SentimentPropagationStrategy
from src.trading.strategies.base_strategy import TradingSignal, SignalType


class TestSentimentPropagationStrategy:
    """Testy dla strategii Propagacji Sentymentu."""
    
    @pytest.fixture
    def strategy(self):
        """Tworzy instancję strategii z domyślną konfiguracją."""
        return SentimentPropagationStrategy({
            'query': 'bitcoin OR cryptocurrency',
            'countries': ['US', 'CN', 'JP'],
            'days_back': 7,
            'min_wave_strength': 0.5,
            'min_confidence': 6.0,
            'recent_wave_hours': 24,
            'target_profit_percent': 2.0,
            'stop_loss_percent': 1.5,
            'max_hold_hours': 48,
            '_backtest_mode': True
        })
    
    @pytest.fixture
    def strategy_conservative(self):
        """Tworzy instancję strategii z konserwatywną konfiguracją."""
        return SentimentPropagationStrategy({
            'query': 'bitcoin',
            'countries': ['US', 'GB'],
            'days_back': 3,
            'min_wave_strength': 0.7,
            'min_confidence': 8.0,
            'recent_wave_hours': 12,
            'target_profit_percent': 1.5,
            'stop_loss_percent': 1.0,
            'max_hold_hours': 24,
            '_backtest_mode': True
        })
    
    @pytest.fixture
    def sample_data(self):
        """Tworzy przykładowe dane OHLCV."""
        dates = pd.date_range('2024-01-01', periods=100, freq='1H')
        data = {
            'open': [40000 + i * 10 for i in range(100)],
            'high': [40100 + i * 10 for i in range(100)],
            'low': [39900 + i * 10 for i in range(100)],
            'close': [40050 + i * 10 for i in range(100)],
            'volume': [1000 + i * 5 for i in range(100)]
        }
        df = pd.DataFrame(data, index=dates)
        df.index.name = 'timestamp'
        return df
    
    @pytest.fixture
    def mock_analysis_results(self):
        """Tworzy mock wyników analizy propagacji sentymentu."""
        return {
            'query': 'bitcoin OR cryptocurrency',
            'countries': ['US', 'CN', 'JP'],
            'days_back': 7,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'sentiment_data': None,
            'lag_matrix': {
                'US-CN': {
                    'lag_hours': -6.0,
                    'correlation': 0.85,
                    'direction': 'leads',
                    'confidence': 0.9
                },
                'US-JP': {
                    'lag_hours': -3.0,
                    'correlation': 0.88,
                    'direction': 'leads',
                    'confidence': 0.85
                }
            },
            'leader_region': {
                'region': 'US',
                'avg_lead_hours': 4.5
            },
            'waves': [
                {
                    'origin': 'US',
                    'time': (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                    'affected_regions': ['US', 'JP', 'CN'],
                    'arrival_times': {'US': 0.0, 'JP': 3.0, 'CN': 6.0},
                    'sentiment_change': 5.2,
                    'strength': 0.75
                }
            ],
            'price_correlations': {
                'US': {
                    'optimal_lag': -2,
                    'correlation': 0.65
                }
            },
            'summary': {
                'total_data_points': 168,
                'countries_analyzed': 3,
                'significant_lags': 2,
                'waves_detected': 1,
                'leader_region': 'US',
                'trading_signals': [
                    {
                        'type': 'bullish',
                        'origin': 'US',
                        'strength': 0.75,
                        'expected_propagation': ['JP', 'CN'],
                        'message': 'Fala pozytywna z US. Oczekiwana propagacja do JP, CN w ciągu 6.0h.'
                    }
                ]
            }
        }
    
    def test_strategy_initialization(self, strategy):
        """Test inicjalizacji strategii."""
        assert strategy.name == "SentimentPropagationStrategy"
        assert strategy.description == "Strategia oparta na propagacji sentymentu między regionami"
        assert strategy.timeframe == "1h"
        assert strategy.query == 'bitcoin OR cryptocurrency'
        assert strategy.countries == ['US', 'CN', 'JP']
        assert strategy.days_back == 7
        assert strategy.min_wave_strength == 0.5
        assert strategy.min_confidence == 6.0
    
    def test_should_refresh_analysis(self, strategy, sample_data):
        """Test sprawdzania czy należy odświeżyć analizę."""
        current_time = sample_data.index[-1]
        
        # Pierwsze wywołanie - powinno zwrócić True
        assert strategy._should_refresh_analysis(current_time) == True
        
        # Ustaw cache
        strategy._last_analysis = {}
        strategy._last_analysis_time = current_time
        
        # To samo wywołanie - powinno zwrócić False (cache jeszcze ważny)
        assert strategy._should_refresh_analysis(current_time) == False
        
        # Czas późniejszy o 2 godziny - powinno zwrócić True
        future_time = current_time + pd.Timedelta(hours=2)
        assert strategy._should_refresh_analysis(future_time) == True
    
    @patch('src.trading.strategies.sentiment_propagation_strategy.SentimentWaveTracker')
    def test_analyze_with_bullish_signal(self, mock_tracker_class, strategy, sample_data, mock_analysis_results):
        """Test analizy z sygnałem bullish."""
        # Mock tracker'a
        mock_tracker = Mock()
        mock_tracker.run_full_analysis.return_value = mock_analysis_results
        strategy.tracker = mock_tracker
        
        # Wywołaj analyze
        signal = strategy.analyze(sample_data, "BTC-USD")
        
        # Sprawdź czy tracker został wywołany
        mock_tracker.run_full_analysis.assert_called_once()
        
        # Sprawdź sygnał
        assert signal is not None
        assert signal.signal_type == SignalType.BUY
        assert signal.symbol == "BTC-USD"
        assert signal.confidence >= strategy.min_confidence
        assert signal.stop_loss is not None
        assert signal.take_profit is not None
        assert signal.reason != ""
        assert signal.strategy == strategy.name
    
    @patch('src.trading.strategies.sentiment_propagation_strategy.SentimentWaveTracker')
    def test_analyze_with_bearish_signal(self, mock_tracker_class, strategy, sample_data):
        """Test analizy z sygnałem bearish."""
        # Mock wyników z bearish signal
        mock_results = {
            'summary': {
                'trading_signals': [
                    {
                        'type': 'bearish',
                        'origin': 'US',
                        'strength': 0.8,
                        'expected_propagation': ['JP', 'CN'],
                        'message': 'Fala negatywna z US.'
                    }
                ]
            },
            'leader_region': {'region': 'US', 'avg_lead_hours': 4.5}
        }
        
        mock_tracker = Mock()
        mock_tracker.run_full_analysis.return_value = mock_results
        strategy.tracker = mock_tracker
        
        signal = strategy.analyze(sample_data, "BTC-USD")
        
        assert signal is not None
        assert signal.signal_type == SignalType.SELL
    
    @patch('src.trading.strategies.sentiment_propagation_strategy.SentimentWaveTracker')
    def test_analyze_with_weak_signal(self, mock_tracker_class, strategy, sample_data):
        """Test analizy z za słabym sygnałem."""
        # Mock wyników z za słabym sygnałem
        mock_results = {
            'summary': {
                'trading_signals': [
                    {
                        'type': 'bullish',
                        'origin': 'US',
                        'strength': 0.3,  # Za słabe (< 0.5)
                        'expected_propagation': [],
                        'message': 'Słaba fala'
                    }
                ]
            },
            'leader_region': {'region': 'US'}
        }
        
        mock_tracker = Mock()
        mock_tracker.run_full_analysis.return_value = mock_results
        strategy.tracker = mock_tracker
        
        signal = strategy.analyze(sample_data, "BTC-USD")
        
        # Powinno zwrócić None (za słaby sygnał)
        assert signal is None
    
    @patch('src.trading.strategies.sentiment_propagation_strategy.SentimentWaveTracker')
    def test_analyze_with_low_confidence(self, mock_tracker_class, strategy, sample_data):
        """Test analizy z niską confidence."""
        # Mock wyników z niską confidence
        mock_results = {
            'summary': {
                'trading_signals': [
                    {
                        'type': 'bullish',
                        'origin': 'US',
                        'strength': 0.6,
                        'expected_propagation': [],  # Brak propagacji -> niska confidence
                        'message': 'Fala bez propagacji'
                    }
                ]
            },
            'leader_region': {'region': 'CN'}  # US nie jest liderem -> brak bonusu
        }
        
        mock_tracker = Mock()
        mock_tracker.run_full_analysis.return_value = mock_results
        strategy.tracker = mock_tracker
        
        signal = strategy.analyze(sample_data, "BTC-USD")
        
        # Confidence powinno być niskie (brak propagacji + brak lidera)
        # Może zwrócić None jeśli confidence < min_confidence
        if signal is None:
            # To jest OK - za niska confidence
            assert True
        else:
            # Jeśli zwróci sygnał, confidence powinno być niskie
            assert signal.confidence < strategy.min_confidence
    
    @patch('src.trading.strategies.sentiment_propagation_strategy.SentimentWaveTracker')
    def test_analyze_with_no_signals(self, mock_tracker_class, strategy, sample_data):
        """Test analizy bez sygnałów."""
        mock_results = {
            'summary': {
                'trading_signals': []
            }
        }
        
        mock_tracker = Mock()
        mock_tracker.run_full_analysis.return_value = mock_results
        strategy.tracker = mock_tracker
        
        signal = strategy.analyze(sample_data, "BTC-USD")
        
        assert signal is None
    
    @patch('src.trading.strategies.sentiment_propagation_strategy.SentimentWaveTracker')
    def test_analyze_uses_cache(self, mock_tracker_class, strategy, sample_data, mock_analysis_results):
        """Test używania cache'u."""
        mock_tracker = Mock()
        mock_tracker.run_full_analysis.return_value = mock_analysis_results
        strategy.tracker = mock_tracker
        
        # Pierwsze wywołanie - powinno wywołać tracker
        signal1 = strategy.analyze(sample_data, "BTC-USD")
        assert mock_tracker.run_full_analysis.call_count == 1
        
        # Drugie wywołanie w krótkim czasie - powinno użyć cache
        signal2 = strategy.analyze(sample_data, "BTC-USD")
        assert mock_tracker.run_full_analysis.call_count == 1  # Nie zwiększyło się
    
    def test_should_close_position_on_profit_target(self, strategy, sample_data):
        """Test zamykania pozycji przy osiągnięciu target zysku."""
        entry_price = 40000.0
        current_price = 40800.0  # +2% (target_profit_percent = 2.0)
        current_pnl = 2.0
        
        signal = strategy.should_close_position(
            sample_data,
            entry_price,
            "long",
            current_pnl
        )
        
        assert signal is not None
        assert signal.signal_type == SignalType.CLOSE
        assert "target zysku" in signal.reason.lower()
    
    def test_should_close_position_on_stop_loss(self, strategy, sample_data):
        """Test zamykania pozycji przy osiągnięciu stop loss."""
        entry_price = 40000.0
        current_price = 39400.0  # -1.5% (stop_loss_percent = 1.5)
        current_pnl = -1.5
        
        signal = strategy.should_close_position(
            sample_data,
            entry_price,
            "long",
            current_pnl
        )
        
        assert signal is not None
        assert signal.signal_type == SignalType.CLOSE
        assert "stop loss" in signal.reason.lower()
    
    def test_should_close_position_on_max_hold_time(self, strategy):
        """Test zamykania pozycji przy przekroczeniu maksymalnego czasu trzymania."""
        dates = pd.date_range('2024-01-01', periods=50, freq='1H')
        data = {
            'open': [40000] * 50,
            'high': [40100] * 50,
            'low': [39900] * 50,
            'close': [40050] * 50,
            'volume': [1000] * 50
        }
        df = pd.DataFrame(data, index=dates)
        
        entry_price = 40000.0
        current_pnl = 0.5  # Mały zysk, ale minęło > 48h
        
        signal = strategy.should_close_position(
            df,
            entry_price,
            "long",
            current_pnl
        )
        
        # Powinno zwrócić sygnał CLOSE (przekroczono max_hold_hours)
        assert signal is not None
        assert signal.signal_type == SignalType.CLOSE
        assert "czas trzymania" in signal.reason.lower()
    
    @patch('src.trading.strategies.sentiment_propagation_strategy.SentimentWaveTracker')
    def test_should_close_position_on_sentiment_reversal(self, mock_tracker_class, strategy):
        """Test zamykania pozycji przy odwróceniu fali sentymentu."""
        # Utwórz dane z krótkim zakresem czasowym (mniej niż max_hold_hours)
        # żeby nie przekroczyć max_hold_hours przed sprawdzeniem odwrócenia fali
        dates = pd.date_range('2024-01-01', periods=24, freq='1H')  # 24 godziny (< 48h)
        data = {
            'open': [40000] * 24,
            'high': [40100] * 24,
            'low': [39900] * 24,
            'close': [40050] * 24,
            'volume': [1000] * 24
        }
        df = pd.DataFrame(data, index=dates)
        
        # Mock wyników z odwróconą falą
        mock_results = {
            'summary': {
                'trading_signals': [
                    {
                        'type': 'bearish',  # Odwrócona fala (była long)
                        'origin': 'US',
                        'strength': 0.7,
                        'expected_propagation': ['JP'],
                        'message': 'Fala negatywna'
                    }
                ]
            }
        }
        
        strategy._last_analysis = mock_results
        
        entry_price = 40000.0
        current_pnl = 0.5
        
        signal = strategy.should_close_position(
            df,
            entry_price,
            "long",  # Mamy long, ale fala jest bearish
            current_pnl
        )
        
        assert signal is not None
        assert signal.signal_type == SignalType.CLOSE
        assert "odwrócenie fali" in signal.reason.lower() or "bearish" in signal.reason.lower()
    
    def test_should_close_position_no_reason(self, strategy):
        """Test że pozycja nie jest zamykana bez powodu."""
        # Utwórz dane z krótkim zakresem czasowym (mniej niż max_hold_hours)
        dates = pd.date_range('2024-01-01', periods=24, freq='1H')  # 24 godziny (< 48h)
        data = {
            'open': [40000] * 24,
            'high': [40100] * 24,
            'low': [39900] * 24,
            'close': [40050] * 24,
            'volume': [1000] * 24
        }
        df = pd.DataFrame(data, index=dates)
        
        entry_price = 40000.0
        current_price = 40100.0  # +0.25% (poniżej target i stop loss)
        current_pnl = 0.25
        
        # Upewnij się, że nie ma analizy sentymentu
        strategy._last_analysis = None
        
        signal = strategy.should_close_position(
            df,
            entry_price,
            "long",
            current_pnl
        )
        
        # Nie powinno być sygnału zamykania
        assert signal is None
    
    def test_calculate_position_size(self, strategy):
        """Test obliczania rozmiaru pozycji."""
        account_balance = 10000.0
        price = 40000.0
        risk_percent = 2.0
        
        size = strategy.calculate_position_size(account_balance, price, risk_percent)
        
        # Powinno użyć 2% kapitału = 200 USD
        # Rozmiar = 200 / 40000 = 0.005 BTC
        expected_size = (account_balance * risk_percent / 100) / price
        assert abs(size - expected_size) < 0.0001


class TestSentimentPropagationStrategyIntegration:
    """Testy integracyjne dla strategii Propagacji Sentymentu."""
    
    @pytest.fixture
    def strategy(self):
        """Tworzy instancję strategii dla testów integracyjnych."""
        return SentimentPropagationStrategy({
            'query': 'bitcoin',
            'countries': ['US', 'CN', 'JP'],
            'days_back': 3,
            'min_wave_strength': 0.5,
            'min_confidence': 6.0,
            '_backtest_mode': False  # Dla testu integracyjnego z GDELT używamy rzeczywistego API
        })
    
    @pytest.fixture
    def sample_ohlcv_data(self):
        """Tworzy przykładowe dane OHLCV dla testów integracyjnych."""
        dates = pd.date_range('2024-01-01', periods=168, freq='1H')  # 7 dni
        np.random.seed(42)
        
        base_price = 40000
        prices = []
        for i in range(168):
            change = np.random.randn() * 100
            base_price += change
            prices.append(base_price)
        
        data = {
            'open': prices,
            'high': [p * 1.01 for p in prices],
            'low': [p * 0.99 for p in prices],
            'close': prices,
            'volume': [1000 + np.random.randint(-100, 100) for _ in range(168)]
        }
        
        df = pd.DataFrame(data, index=dates)
        df.index.name = 'timestamp'
        return df
    
    def test_integration_with_gdelt(self, strategy, sample_ohlcv_data):
        """
        Test integracji z GDELT API (wymaga połączenia internetowego).
        
        Test sprawdza czy strategia może pobrać rzeczywiste dane z GDELT API
        i wygenerować sygnał tradingowy na ich podstawie.
        """
        # Upewnij się, że strategia nie jest w trybie backtestingu
        strategy._backtest_mode = False
        
        signal = strategy.analyze(sample_ohlcv_data, "BTC-USD")
        
        # Jeśli GDELT zwróci dane, powinno być sygnał lub None
        # (w zależności od aktualnego sentymentu)
        assert signal is None or isinstance(signal, TradingSignal)
        
        # Jeśli jest sygnał, sprawdź czy ma poprawne pola
        if signal is not None:
            assert signal.signal_type in [SignalType.BUY, SignalType.SELL]
            assert signal.confidence >= 0
            assert signal.confidence <= 10
            assert signal.price > 0
            assert signal.reason != ""
    
    def test_strategy_with_empty_data(self, strategy):
        """Test strategii z pustymi danymi."""
        empty_df = pd.DataFrame()
        
        signal = strategy.analyze(empty_df, "BTC-USD")
        
        assert signal is None
    
    def test_strategy_with_single_row(self, strategy):
        """Test strategii z pojedynczym wierszem danych."""
        dates = pd.date_range('2024-01-01', periods=1, freq='1H')
        data = {
            'open': [40000],
            'high': [40100],
            'low': [39900],
            'close': [40050],
            'volume': [1000]
        }
        df = pd.DataFrame(data, index=dates)
        
        # Powinno działać bez błędów
        signal = strategy.analyze(df, "BTC-USD")
        
        # Może zwrócić None (brak wystarczających danych) lub sygnał
        assert signal is None or isinstance(signal, TradingSignal)

