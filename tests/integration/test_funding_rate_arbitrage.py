"""
Testy dla strategii Funding Rate Arbitrage
==========================================
Testy jednostkowe i integracyjne dla strategii Funding Rate Arbitrage
na danych historycznych z 2022 i 2023 roku.
"""

import pytest
import pandas as pd
from datetime import datetime
from pathlib import Path

from src.trading.strategies.funding_rate_arbitrage_strategy import FundingRateArbitrageStrategy
from src.trading.strategies.base_strategy import TradingSignal, SignalType


class TestFundingRateArbitrageStrategy:
    """Testy dla strategii Funding Rate Arbitrage."""
    
    @pytest.fixture
    def strategy(self):
        """Tworzy instancję strategii z domyślną konfiguracją."""
        return FundingRateArbitrageStrategy({
            'min_funding_rate': 0.01,
            'target_funding_rate': 0.05,
            'max_position_size': 50.0,
            'funding_interval_hours': 8,
            'min_holding_hours': 24
        })
    
    @pytest.fixture
    def strategy_conservative(self):
        """Tworzy instancję strategii z konserwatywną konfiguracją."""
        return FundingRateArbitrageStrategy({
            'min_funding_rate': 0.03,
            'target_funding_rate': 0.08,
            'max_position_size': 30.0,
            'funding_interval_hours': 8,
            'min_holding_hours': 48
        })
    
    @pytest.fixture
    def strategy_aggressive(self):
        """Tworzy instancję strategii z agresywną konfiguracją."""
        return FundingRateArbitrageStrategy({
            'min_funding_rate': 0.005,
            'target_funding_rate': 0.03,
            'max_position_size': 70.0,
            'funding_interval_hours': 8,
            'min_holding_hours': 12
        })
    
    @pytest.fixture
    def sample_data(self):
        """Tworzy przykładowe dane OHLCV."""
        dates = pd.date_range('2023-01-01', periods=100, freq='1H')
        data = {
            'open': [20000 + i * 10 for i in range(100)],
            'high': [20100 + i * 10 for i in range(100)],
            'low': [19900 + i * 10 for i in range(100)],
            'close': [20050 + i * 10 for i in range(100)],
            'volume': [1000 + i * 5 for i in range(100)]
        }
        df = pd.DataFrame(data, index=dates)
        df.index.name = 'timestamp'
        return df
    
    def test_strategy_initialization(self, strategy):
        """Test inicjalizacji strategii."""
        assert strategy.name == "FundingRateArbitrage"
        assert strategy.description == "Arbitraż stopy finansowania kontraktów wieczystych"
        assert strategy.timeframe == "1h"
        assert strategy.min_funding_rate == 0.01
        assert strategy.target_funding_rate == 0.05
        assert strategy.max_position_size == 50.0
    
    def test_calculate_annual_return(self, strategy):
        """Test obliczania rocznego zwrotu."""
        # Test dla różnych stóp finansowania
        test_cases = [
            (0.01, 10.95),  # 0.01% na 8h -> ~11% rocznie
            (0.03, 32.85),  # 0.03% na 8h -> ~33% rocznie
            (0.05, 54.75),  # 0.05% na 8h -> ~55% rocznie
            (0.10, 109.5),  # 0.10% na 8h -> ~110% rocznie
        ]
        
        for funding_rate, expected_annual in test_cases:
            annual = strategy._calculate_annual_return(funding_rate)
            assert abs(annual - expected_annual) < 1.0, \
                f"Funding rate {funding_rate}% -> expected ~{expected_annual}%, got {annual}%"
    
    def test_get_funding_rate_simulation(self, strategy, sample_data):
        """Test symulacji funding rate na podstawie RSI."""
        funding_rate = strategy._get_funding_rate(sample_data, "BTC-USD")
        
        # Funding rate powinien być obliczony (symulowany na podstawie RSI)
        assert funding_rate is not None
        assert isinstance(funding_rate, (int, float))
        # Funding rate powinien być w rozsądnym zakresie (-0.1% do 0.2%)
        assert -0.1 <= funding_rate <= 0.2
    
    def test_calculate_volatility(self, strategy, sample_data):
        """Test obliczania zmienności."""
        volatility = strategy._calculate_volatility(sample_data, period=24)
        
        assert isinstance(volatility, (int, float))
        assert volatility >= 0
        # Dla stabilnych danych volatility powinna być niska
        assert volatility < 10.0
    
    def test_calculate_position_confidence(self, strategy):
        """Test obliczania confidence."""
        # Test dla wysokiego funding rate
        confidence_high = strategy._calculate_position_confidence(
            funding_rate=0.05,
            volatility=1.0,
            liquidity_score=1.0
        )
        assert confidence_high >= 5.0
        assert confidence_high <= 10.0
        
        # Test dla niskiego funding rate
        confidence_low = strategy._calculate_position_confidence(
            funding_rate=0.01,
            volatility=3.0,
            liquidity_score=0.5
        )
        assert confidence_low >= 0.0
        assert confidence_low < confidence_high
    
    def test_analyze_no_signal_insufficient_data(self, strategy):
        """Test że strategia nie generuje sygnału przy zbyt małej ilości danych."""
        df = pd.DataFrame({
            'open': [20000],
            'high': [20100],
            'low': [19900],
            'close': [20050],
            'volume': [1000]
        })
        
        signal = strategy.analyze(df, "BTC-USD")
        assert signal is None
    
    def test_analyze_generates_signal(self, strategy, sample_data):
        """Test generowania sygnału."""
        signal = strategy.analyze(sample_data, "BTC-USD")
        
        # Sygnał może być None (jeśli funding rate za niski) lub TradingSignal
        if signal is not None:
            assert isinstance(signal, TradingSignal)
            assert signal.signal_type in [SignalType.BUY, SignalType.SELL]
            assert signal.confidence >= 3.0
            assert signal.price > 0
            assert signal.strategy == "FundingRateArbitrage"
    
    def test_should_close_position_funding_rate_drop(self, strategy, sample_data):
        """Test zamykania pozycji gdy funding rate spadł."""
        entry_price = 20000.0
        entry_time = datetime.now()
        
        # Symuluj sytuację gdzie funding rate spadł poniżej 50% minimum
        # (w rzeczywistości _get_funding_rate zwróci niski funding rate)
        signal = strategy.should_close_position(
            df=sample_data,
            entry_price=entry_price,
            side="long",
            current_pnl_percent=0.0,
            entry_time=entry_time
        )
        
        # Sygnał może być None lub CLOSE (w zależności od symulowanego funding rate)
        if signal is not None:
            assert signal.signal_type == SignalType.CLOSE
            assert "funding rate" in signal.reason.lower()
    
    def test_should_close_position_large_price_deviation(self, strategy, sample_data):
        """Test zamykania pozycji przy dużym odchyleniu ceny."""
        entry_price = 20000.0
        current_price = 22000.0  # 10% odchylenie
        
        # Modyfikuj dane aby odzwierciedlić duże odchylenie
        sample_data_modified = sample_data.copy()
        sample_data_modified['close'].iloc[-1] = current_price
        
        signal = strategy.should_close_position(
            df=sample_data_modified,
            entry_price=entry_price,
            side="long",
            current_pnl_percent=10.0,
            entry_time=datetime.now()
        )
        
        # Powinien być sygnał CLOSE z powodu dużego odchylenia
        if signal is not None:
            assert signal.signal_type == SignalType.CLOSE
            assert "odchylenie" in signal.reason.lower() or "deviation" in signal.reason.lower()


class TestFundingRateArbitrageBacktest:
    """Testy backtestingu strategii na danych historycznych."""
    
    @pytest.fixture
    def data_2022(self):
        """Wczytuje dane z 2022 roku."""
        csv_path = Path("data/backtest_periods/binance/BTCUSDT_2022_1h.csv")
        if not csv_path.exists():
            pytest.skip(f"Plik {csv_path} nie istnieje")
        
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        df = df.sort_index()
        return df
    
    @pytest.fixture
    def data_2023(self):
        """Wczytuje dane z 2023 roku."""
        csv_path = Path("data/backtest_periods/binance/BTCUSDT_2023_1h.csv")
        if not csv_path.exists():
            pytest.skip(f"Plik {csv_path} nie istnieje")
        
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        df = df.sort_index()
        return df
    
    def test_backtest_2022_default_config(self, data_2022):
        """Test backtestingu na danych z 2022 z domyślną konfiguracją."""
        from src.trading.backtesting import BacktestEngine
        
        strategy = FundingRateArbitrageStrategy({
            'min_funding_rate': 0.01,
            'target_funding_rate': 0.05,
            'max_position_size': 50.0
        })
        
        engine = BacktestEngine(
            initial_balance=10000.0
        )
        
        result = engine.run_backtest(
            df=data_2022,
            strategy=strategy,
            symbol="BTC/USDT"
        )
        
        assert result is not None
        assert result.trades >= 0
        assert result.return_ >= -100.0  # Nie więcej niż -100% straty
        assert result.max_dd >= 0.0
        
        print(f"\n📊 Backtest 2022 (default):")
        print(f"   Zwrot: {result.return_:.2f}%")
        print(f"   Transakcje: {result.trades}")
        print(f"   Win Rate: {result.win_rate:.1f}%")
        print(f"   Max Drawdown: {result.max_dd:.2f}%")
    
    def test_backtest_2023_default_config(self, data_2023):
        """Test backtestingu na danych z 2023 z domyślną konfiguracją."""
        from src.trading.backtesting import BacktestEngine
        
        strategy = FundingRateArbitrageStrategy({
            'min_funding_rate': 0.01,
            'target_funding_rate': 0.05,
            'max_position_size': 50.0
        })
        
        engine = BacktestEngine(
            initial_balance=10000.0
        )
        
        result = engine.run_backtest(
            df=data_2023,
            strategy=strategy,
            symbol="BTC/USDT"
        )
        
        assert result is not None
        assert result.trades >= 0
        assert result.return_ >= -100.0
        assert result.max_dd >= 0.0
        
        print(f"\n📊 Backtest 2023 (default):")
        print(f"   Zwrot: {result.return_:.2f}%")
        print(f"   Transakcje: {result.trades}")
        print(f"   Win Rate: {result.win_rate:.1f}%")
        print(f"   Max Drawdown: {result.max_dd:.2f}%")
    
    def test_backtest_2022_conservative(self, data_2022):
        """Test backtestingu na danych z 2022 z konserwatywną konfiguracją."""
        from src.trading.backtesting import BacktestEngine
        
        strategy = FundingRateArbitrageStrategy({
            'min_funding_rate': 0.03,
            'target_funding_rate': 0.08,
            'max_position_size': 30.0,
            'min_holding_hours': 48
        })
        
        engine = BacktestEngine(
            initial_balance=10000.0
        )
        
        result = engine.run_backtest(
            df=data_2022,
            strategy=strategy,
            symbol="BTC/USDT"
        )
        
        assert result is not None
        print(f"\n📊 Backtest 2022 (conservative):")
        print(f"   Zwrot: {result.return_:.2f}%")
        print(f"   Transakcje: {result.trades}")
        print(f"   Win Rate: {result.win_rate:.1f}%")
    
    def test_backtest_2023_conservative(self, data_2023):
        """Test backtestingu na danych z 2023 z konserwatywną konfiguracją."""
        from src.trading.backtesting import BacktestEngine
        
        strategy = FundingRateArbitrageStrategy({
            'min_funding_rate': 0.03,
            'target_funding_rate': 0.08,
            'max_position_size': 30.0,
            'min_holding_hours': 48
        })
        
        engine = BacktestEngine(
            initial_balance=10000.0
        )
        
        result = engine.run_backtest(
            df=data_2023,
            strategy=strategy,
            symbol="BTC/USDT"
        )
        
        assert result is not None
        print(f"\n📊 Backtest 2023 (conservative):")
        print(f"   Zwrot: {result.return_:.2f}%")
        print(f"   Transakcje: {result.trades}")
        print(f"   Win Rate: {result.win_rate:.1f}%")
    
    def test_backtest_2022_aggressive(self, data_2022):
        """Test backtestingu na danych z 2022 z agresywną konfiguracją."""
        from src.trading.backtesting import BacktestEngine
        
        strategy = FundingRateArbitrageStrategy({
            'min_funding_rate': 0.005,
            'target_funding_rate': 0.03,
            'max_position_size': 70.0,
            'min_holding_hours': 12
        })
        
        engine = BacktestEngine(
            initial_balance=10000.0
        )
        
        result = engine.run_backtest(
            df=data_2022,
            strategy=strategy,
            symbol="BTC/USDT"
        )
        
        assert result is not None
        print(f"\n📊 Backtest 2022 (aggressive):")
        print(f"   Zwrot: {result.return_:.2f}%")
        print(f"   Transakcje: {result.trades}")
        print(f"   Win Rate: {result.win_rate:.1f}%")
    
    def test_backtest_2023_aggressive(self, data_2023):
        """Test backtestingu na danych z 2023 z agresywną konfiguracją."""
        from src.trading.backtesting import BacktestEngine
        
        strategy = FundingRateArbitrageStrategy({
            'min_funding_rate': 0.005,
            'target_funding_rate': 0.03,
            'max_position_size': 70.0,
            'min_holding_hours': 12
        })
        
        engine = BacktestEngine(
            initial_balance=10000.0
        )
        
        result = engine.run_backtest(
            df=data_2023,
            strategy=strategy,
            symbol="BTC/USDT"
        )
        
        assert result is not None
        print(f"\n📊 Backtest 2023 (aggressive):")
        print(f"   Zwrot: {result.return_:.2f}%")
        print(f"   Transakcje: {result.trades}")
        print(f"   Win Rate: {result.win_rate:.1f}%")
    
    def test_compare_2022_vs_2023(self, data_2022, data_2023):
        """Porównanie wyników między 2022 a 2023."""
        from src.trading.backtesting import BacktestEngine
        
        strategy = FundingRateArbitrageStrategy({
            'min_funding_rate': 0.01,
            'target_funding_rate': 0.05,
            'max_position_size': 50.0
        })
        
        engine = BacktestEngine(
            initial_balance=10000.0
        )
        
        result_2022 = engine.run_backtest(
            df=data_2022,
            strategy=strategy,
            symbol="BTC/USDT"
        )
        
        result_2023 = engine.run_backtest(
            df=data_2023,
            strategy=strategy,
            symbol="BTC/USDT"
        )
        
        print(f"\n📊 Porównanie 2022 vs 2023:")
        print(f"   2022: Zwrot={result_2022.return_:.2f}%, Trades={result_2022.trades}, WR={result_2022.win_rate:.1f}%")
        print(f"   2023: Zwrot={result_2023.return_:.2f}%, Trades={result_2023.trades}, WR={result_2023.win_rate:.1f}%")
        
        assert result_2022 is not None
        assert result_2023 is not None

