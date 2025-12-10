"""
Base Strategy
=============
Bazowa klasa dla wszystkich strategii tradingowych.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import pandas as pd


class SignalType(Enum):
    """Typ sygnału."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"


@dataclass
class TradingSignal:
    """
    Sygnał tradingowy.
    """
    signal_type: SignalType
    symbol: str
    confidence: float  # 0-10
    price: float
    
    # Opcjonalne
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    size_percent: float = 10.0  # % kapitału do użycia
    
    reason: str = ""
    strategy: str = ""
    
    def __repr__(self):
        return f"<Signal {self.signal_type.value.upper()} {self.symbol} @ {self.price:.2f} (conf: {self.confidence}/10)>"


class BaseStrategy(ABC):
    """
    Bazowa klasa strategii.
    
    Każda strategia musi implementować:
    - analyze() - analiza danych i generowanie sygnałów
    """
    
    name: str = "BaseStrategy"
    description: str = "Bazowa strategia"
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Inicjalizacja strategii.
        
        Args:
            config: Konfiguracja strategii
        """
        self.config = config or {}
    
    @abstractmethod
    def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD") -> Optional[TradingSignal]:
        """
        Analizuje dane i generuje sygnał.
        
        Args:
            df: DataFrame z danymi OHLCV
            symbol: Symbol pary
            
        Returns:
            TradingSignal lub None
        """
        pass
    
    def should_close_position(
        self,
        df: pd.DataFrame,
        entry_price: float,
        side: str,
        current_pnl_percent: float
    ) -> Optional[TradingSignal]:
        """
        Sprawdza czy należy zamknąć pozycję.
        
        Args:
            df: DataFrame z danymi OHLCV
            entry_price: Cena wejścia
            side: "long" lub "short"
            current_pnl_percent: Aktualny PnL w %
            
        Returns:
            TradingSignal (CLOSE) lub None
        """
        return None
    
    def calculate_position_size(
        self,
        account_balance: float,
        price: float,
        risk_percent: float = 2.0
    ) -> float:
        """
        Oblicza rozmiar pozycji na podstawie kapitału i ryzyka.
        
        Args:
            account_balance: Saldo konta
            price: Aktualna cena
            risk_percent: Procent kapitału do zaryzykowania
            
        Returns:
            Rozmiar pozycji w jednostkach bazowych
        """
        capital_to_use = account_balance * (risk_percent / 100)
        size = capital_to_use / price
        return size

