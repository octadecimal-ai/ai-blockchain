"""
Testy jednostkowe dla Paper Trading Engine.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.trading.models import (
    Base, PaperAccount, PaperPosition, PaperOrder, PaperTrade,
    OrderSide, OrderType, OrderStatus, PositionStatus
)
from src.trading.paper_trading import PaperTradingEngine
from src.trading.strategies.piotrek_strategy import PiotrekBreakoutStrategy
from src.trading.strategies.base_strategy import TradingSignal, SignalType


@pytest.fixture
def db_session():
    """Tworzy tymczasową bazę danych w pamięci."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def mock_dydx():
    """Mock dla DydxCollector."""
    mock = MagicMock()
    mock.get_ticker.return_value = {'oracle_price': 50000.0}
    return mock


@pytest.fixture
def paper_engine(db_session, mock_dydx):
    """Tworzy Paper Trading Engine z mockami."""
    engine = PaperTradingEngine(
        session=db_session,
        account_name="test_account",
        dydx_collector=mock_dydx
    )
    return engine


class TestPaperAccount:
    """Testy dla modelu PaperAccount."""
    
    def test_create_account(self, db_session):
        """Test tworzenia konta."""
        account = PaperAccount(
            name="test",
            initial_balance=10000.0,
            current_balance=10000.0
        )
        db_session.add(account)
        db_session.commit()
        
        assert account.id is not None
        assert account.name == "test"
        assert account.initial_balance == 10000.0
    
    def test_win_rate(self, db_session):
        """Test obliczania win rate."""
        account = PaperAccount(
            name="test_winrate",
            total_trades=10,
            winning_trades=7,
            losing_trades=3
        )
        
        assert account.win_rate == 70.0
    
    def test_roi(self, db_session):
        """Test obliczania ROI."""
        account = PaperAccount(
            name="test_roi",
            initial_balance=10000.0,
            current_balance=12000.0
        )
        
        assert account.roi == 20.0


class TestPaperPosition:
    """Testy dla modelu PaperPosition."""
    
    def test_calculate_pnl_long(self, db_session):
        """Test obliczania PnL dla pozycji LONG."""
        position = PaperPosition(
            account_id=1,
            symbol="BTC-USD",
            side=OrderSide.LONG,
            size=0.1,
            entry_price=50000.0,
            leverage=1.0,
            margin_used=5000.0
        )
        
        # Cena wzrosła o 10%
        pnl, pnl_percent = position.calculate_pnl(55000.0)
        
        assert pnl == 500.0  # 0.1 * 5000 = 500
        assert pnl_percent == 10.0
    
    def test_calculate_pnl_short(self, db_session):
        """Test obliczania PnL dla pozycji SHORT."""
        position = PaperPosition(
            account_id=1,
            symbol="BTC-USD",
            side=OrderSide.SHORT,
            size=0.1,
            entry_price=50000.0,
            leverage=1.0,
            margin_used=5000.0
        )
        
        # Cena spadła o 10%
        pnl, pnl_percent = position.calculate_pnl(45000.0)
        
        assert pnl == 500.0  # 0.1 * 5000 = 500
        assert pnl_percent == 10.0
    
    def test_calculate_pnl_with_leverage(self, db_session):
        """Test obliczania PnL z dźwignią."""
        position = PaperPosition(
            account_id=1,
            symbol="BTC-USD",
            side=OrderSide.LONG,
            size=0.1,
            entry_price=50000.0,
            leverage=5.0,
            margin_used=1000.0
        )
        
        # Cena wzrosła o 2%
        pnl, pnl_percent = position.calculate_pnl(51000.0)
        
        assert pnl == 500.0  # 0.1 * 1000 * 5 = 500
        assert pnl_percent == 10.0  # 2% * 5x = 10%
    
    def test_is_liquidated(self, db_session):
        """Test wykrywania likwidacji."""
        position = PaperPosition(
            account_id=1,
            symbol="BTC-USD",
            side=OrderSide.LONG,
            size=0.1,
            entry_price=50000.0,
            leverage=10.0,
            margin_used=500.0
        )
        
        # Cena spadła o 10% = -100% przy 10x leverage
        assert position.is_liquidated(45000.0) is True
        
        # Cena spadła o 5% = -50% przy 10x leverage
        assert position.is_liquidated(47500.0) is False


class TestPaperTradingEngine:
    """Testy dla Paper Trading Engine."""
    
    def test_get_or_create_account(self, paper_engine):
        """Test tworzenia konta."""
        assert paper_engine.account is not None
        assert paper_engine.account.name == "test_account"
        assert paper_engine.account.initial_balance == 10000.0
    
    def test_get_current_price(self, paper_engine, mock_dydx):
        """Test pobierania aktualnej ceny."""
        price = paper_engine.get_current_price("BTC-USD")
        
        assert price == 50000.0
        mock_dydx.get_ticker.assert_called_with("BTC-USD")
    
    def test_open_position_long(self, paper_engine, mock_dydx):
        """Test otwierania pozycji LONG."""
        position = paper_engine.open_position(
            symbol="BTC-USD",
            side="long",
            size=0.1,
            leverage=2.0,
            stop_loss=48000.0,
            take_profit=55000.0,
            strategy="test_strategy"
        )
        
        assert position is not None
        assert position.symbol == "BTC-USD"
        assert position.side == OrderSide.LONG
        assert position.size == 0.1
        assert position.leverage == 2.0
        assert position.stop_loss == 48000.0
        assert position.take_profit == 55000.0
    
    def test_open_position_insufficient_funds(self, paper_engine, mock_dydx):
        """Test otwierania pozycji przy braku środków."""
        # Próba otwarcia pozycji większej niż saldo
        position = paper_engine.open_position(
            symbol="BTC-USD",
            side="long",
            size=100,  # 100 BTC = $5,000,000 przy $50,000/BTC
            leverage=1.0
        )
        
        assert position is None
    
    def test_close_position(self, paper_engine, mock_dydx):
        """Test zamykania pozycji."""
        # Otwórz pozycję
        position = paper_engine.open_position(
            symbol="BTC-USD",
            side="long",
            size=0.1,
            leverage=1.0
        )
        
        # Zmień cenę na wyższą
        mock_dydx.get_ticker.return_value = {'oracle_price': 55000.0}
        
        # Zamknij pozycję
        trade = paper_engine.close_position(
            position.id,
            exit_reason="manual"
        )
        
        assert trade is not None
        assert trade.exit_price == 55000.0
        assert trade.pnl > 0  # Zysk
    
    def test_check_stop_loss(self, paper_engine, mock_dydx):
        """Test sprawdzania Stop Loss."""
        # Otwórz pozycję ze SL
        position = paper_engine.open_position(
            symbol="BTC-USD",
            side="long",
            size=0.1,
            leverage=1.0,
            stop_loss=45000.0
        )
        
        # Cena spada poniżej SL
        mock_dydx.get_ticker.return_value = {'oracle_price': 44000.0}
        
        # Sprawdź SL/TP
        closed_trades = paper_engine.check_stop_loss_take_profit()
        
        assert len(closed_trades) == 1
        assert closed_trades[0].exit_reason == "stop_loss"
    
    def test_check_take_profit(self, paper_engine, mock_dydx):
        """Test sprawdzania Take Profit."""
        # Otwórz pozycję z TP
        position = paper_engine.open_position(
            symbol="BTC-USD",
            side="long",
            size=0.1,
            leverage=1.0,
            take_profit=55000.0
        )
        
        # Cena rośnie powyżej TP
        mock_dydx.get_ticker.return_value = {'oracle_price': 56000.0}
        
        # Sprawdź SL/TP
        closed_trades = paper_engine.check_stop_loss_take_profit()
        
        assert len(closed_trades) == 1
        assert closed_trades[0].exit_reason == "take_profit"
    
    def test_get_account_summary(self, paper_engine):
        """Test pobierania podsumowania konta."""
        summary = paper_engine.get_account_summary()
        
        assert 'current_balance' in summary
        assert 'equity' in summary
        assert 'open_positions' in summary
        assert summary['open_positions'] == 0
    
    def test_performance_stats(self, paper_engine, mock_dydx):
        """Test statystyk wydajności."""
        # Wykonaj kilka transakcji
        for i in range(3):
            pos = paper_engine.open_position(
                symbol="BTC-USD",
                side="long",
                size=0.01,
                leverage=1.0
            )
            
            # Zamknij z różnymi wynikami
            if i % 2 == 0:
                mock_dydx.get_ticker.return_value = {'oracle_price': 51000.0}  # Zysk
            else:
                mock_dydx.get_ticker.return_value = {'oracle_price': 49000.0}  # Strata
            
            paper_engine.close_position(pos.id, exit_reason="test")
            mock_dydx.get_ticker.return_value = {'oracle_price': 50000.0}
        
        stats = paper_engine.get_performance_stats()
        
        assert stats['total_trades'] == 3
        assert 'win_rate' in stats
        assert 'profit_factor' in stats


class TestPiotrekStrategy:
    """Testy dla strategii Piotrka."""
    
    @pytest.fixture
    def sample_df(self):
        """Generuje przykładowe dane OHLCV."""
        dates = pd.date_range(start='2024-01-01', periods=50, freq='h')
        
        # Symulacja trendu z breakoutem
        base_price = 50000
        prices = []
        
        for i in range(50):
            if i < 40:
                # Konsolidacja
                price = base_price + np.random.uniform(-100, 100)
            else:
                # Breakout
                price = base_price + (i - 40) * 100 + np.random.uniform(-50, 50)
            prices.append(price)
        
        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': [p + np.random.uniform(0, 50) for p in prices],
            'low': [p - np.random.uniform(0, 50) for p in prices],
            'close': prices,
            'volume': [np.random.uniform(100, 1000) for _ in range(50)]
        })
        df.set_index('timestamp', inplace=True)
        
        return df
    
    def test_strategy_init(self):
        """Test inicjalizacji strategii."""
        strategy = PiotrekBreakoutStrategy({
            'breakout_threshold': 1.5,
            'min_confidence': 7
        })
        
        assert strategy.name == "PiotrekBreakout"
        assert strategy.breakout_threshold == 1.5
        assert strategy.min_confidence == 7
    
    def test_find_support_resistance(self, sample_df):
        """Test znajdowania poziomów S/R."""
        strategy = PiotrekBreakoutStrategy()
        
        supports, resistances = strategy.find_support_resistance_levels(sample_df)
        
        assert isinstance(supports, list)
        assert isinstance(resistances, list)
    
    def test_detect_consolidation(self, sample_df):
        """Test wykrywania konsolidacji."""
        strategy = PiotrekBreakoutStrategy({
            'consolidation_threshold': 5.0  # Wysoki próg
        })
        
        # Z wysokim progiem powinno wykryć konsolidację
        is_consolidating, range_percent = strategy.detect_consolidation(sample_df)
        
        assert isinstance(is_consolidating, bool)
        assert isinstance(range_percent, float)
    
    def test_calculate_momentum(self, sample_df):
        """Test obliczania momentum."""
        strategy = PiotrekBreakoutStrategy()
        
        momentum = strategy.calculate_momentum(sample_df, period=5)
        
        assert isinstance(momentum, float)
    
    def test_should_close_position(self, sample_df):
        """Test sygnału zamknięcia pozycji."""
        strategy = PiotrekBreakoutStrategy({
            'consolidation_threshold': 5.0
        })
        
        signal = strategy.should_close_position(
            df=sample_df,
            entry_price=49000.0,
            side="long",
            current_pnl_percent=5.0  # 5% zysku
        )
        
        # Może zwrócić sygnał lub None
        if signal:
            assert signal.signal_type == SignalType.CLOSE


class TestTradingSignal:
    """Testy dla TradingSignal."""
    
    def test_signal_creation(self):
        """Test tworzenia sygnału."""
        signal = TradingSignal(
            signal_type=SignalType.BUY,
            symbol="BTC-USD",
            confidence=8.5,
            price=50000.0,
            stop_loss=48000.0,
            take_profit=55000.0,
            reason="Breakout detected"
        )
        
        assert signal.signal_type == SignalType.BUY
        assert signal.confidence == 8.5
        assert signal.stop_loss == 48000.0

