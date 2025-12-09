"""
Pytest configuration i shared fixtures.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# Dodaj ścieżkę projektu do PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def sample_ohlcv_data():
    """Przykładowe dane OHLCV do testów."""
    dates = pd.date_range(
        start=datetime.now() - timedelta(days=30),
        end=datetime.now(),
        freq='1h'
    )
    
    # Generuj realistyczne dane cenowe
    np.random.seed(42)
    base_price = 50000.0
    prices = base_price + np.cumsum(np.random.randn(len(dates)) * 100)
    
    return pd.DataFrame({
        'open': prices + np.random.randn(len(dates)) * 10,
        'high': prices + np.abs(np.random.randn(len(dates)) * 50),
        'low': prices - np.abs(np.random.randn(len(dates)) * 50),
        'close': prices,
        'volume': np.random.uniform(100, 1000, len(dates))
    }, index=dates)


@pytest.fixture
def sample_ohlcv_dataframe(sample_ohlcv_data):
    """DataFrame z danymi OHLCV."""
    return sample_ohlcv_data.copy()


@pytest.fixture
def temp_db_path(tmp_path):
    """Ścieżka do tymczasowej bazy danych SQLite."""
    return tmp_path / "test_ai_blockchain.db"


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock zmiennych środowiskowych."""
    monkeypatch.setenv('BINANCE_API_KEY', 'test_key')
    monkeypatch.setenv('BINANCE_SECRET', 'test_secret')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test_anthropic_key')
    monkeypatch.setenv('OPENAI_API_KEY', 'test_openai_key')


@pytest.fixture
def skip_if_no_api_key():
    """Skip test jeśli brak API key."""
    def _skip_if_no_key(key_name: str):
        if not os.getenv(key_name):
            pytest.skip(f"Brak {key_name} - pomijam test integracyjny")
    return _skip_if_no_key

