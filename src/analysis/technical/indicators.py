"""
Technical Indicators
====================
Moduł do obliczania wskaźników analizy technicznej.
Wykorzystuje bibliotekę 'ta' oraz własne implementacje.
"""

import pandas as pd
import numpy as np
from typing import Optional
from loguru import logger

# Próba importu biblioteki 'ta', jeśli nie ma - użyjemy własnych funkcji
try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logger.warning("Biblioteka 'ta' nie jest zainstalowana. Używam własnych implementacji.")


class TechnicalAnalyzer:
    """
    Klasa do obliczania wskaźników technicznych.
    
    Obsługuje:
    - Średnie kroczące (SMA, EMA)
    - Oscylatory (RSI, MACD, Stochastic)
    - Wskaźniki zmienności (Bollinger Bands, ATR)
    - Wskaźniki wolumenu (OBV, VWAP)
    """
    
    def __init__(self, df: pd.DataFrame):
        """
        Inicjalizacja z danymi OHLCV.
        
        Args:
            df: DataFrame z kolumnami open, high, low, close, volume
        """
        self.df = df.copy()
        self._validate_columns()
    
    def _validate_columns(self):
        """Sprawdza czy DataFrame ma wymagane kolumny."""
        required = ['open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required if col not in self.df.columns]
        if missing:
            raise ValueError(f"Brakujące kolumny: {missing}")
    
    # === Średnie Kroczące ===
    
    def add_sma(self, periods: list[int] = [20, 50, 200]) -> 'TechnicalAnalyzer':
        """Dodaje Simple Moving Average."""
        for period in periods:
            self.df[f'sma_{period}'] = self.df['close'].rolling(window=period).mean()
        logger.debug(f"Dodano SMA dla okresów: {periods}")
        return self
    
    def add_ema(self, periods: list[int] = [9, 21, 55]) -> 'TechnicalAnalyzer':
        """Dodaje Exponential Moving Average."""
        for period in periods:
            self.df[f'ema_{period}'] = self.df['close'].ewm(span=period, adjust=False).mean()
        logger.debug(f"Dodano EMA dla okresów: {periods}")
        return self
    
    # === Oscylatory ===
    
    def add_rsi(self, period: int = 14) -> 'TechnicalAnalyzer':
        """Dodaje Relative Strength Index."""
        if TA_AVAILABLE:
            self.df['rsi'] = ta.momentum.RSIIndicator(self.df['close'], window=period).rsi()
        else:
            # Własna implementacja RSI
            delta = self.df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            self.df['rsi'] = 100 - (100 / (1 + rs))
        logger.debug(f"Dodano RSI({period})")
        return self
    
    def add_macd(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> 'TechnicalAnalyzer':
        """Dodaje MACD (Moving Average Convergence Divergence)."""
        if TA_AVAILABLE:
            macd_ind = ta.trend.MACD(self.df['close'], window_fast=fast, window_slow=slow, window_sign=signal)
            self.df['MACD_12_26_9'] = macd_ind.macd()
            self.df['MACDs_12_26_9'] = macd_ind.macd_signal()
            self.df['MACDh_12_26_9'] = macd_ind.macd_diff()
        else:
            # Własna implementacja MACD
            ema_fast = self.df['close'].ewm(span=fast, adjust=False).mean()
            ema_slow = self.df['close'].ewm(span=slow, adjust=False).mean()
            self.df['MACD_12_26_9'] = ema_fast - ema_slow
            self.df['MACDs_12_26_9'] = self.df['MACD_12_26_9'].ewm(span=signal, adjust=False).mean()
            self.df['MACDh_12_26_9'] = self.df['MACD_12_26_9'] - self.df['MACDs_12_26_9']
        logger.debug(f"Dodano MACD({fast}, {slow}, {signal})")
        return self
    
    def add_stochastic(
        self,
        k: int = 14,
        d: int = 3,
        smooth_k: int = 3
    ) -> 'TechnicalAnalyzer':
        """Dodaje Stochastic Oscillator."""
        if TA_AVAILABLE:
            stoch_ind = ta.momentum.StochasticOscillator(
                self.df['high'], self.df['low'], self.df['close'],
                window=k, smooth_window=d
            )
            self.df['STOCHk_14_3_3'] = stoch_ind.stoch()
            self.df['STOCHd_14_3_3'] = stoch_ind.stoch_signal()
        else:
            # Własna implementacja Stochastic
            low_min = self.df['low'].rolling(window=k).min()
            high_max = self.df['high'].rolling(window=k).max()
            stoch_k = 100 * ((self.df['close'] - low_min) / (high_max - low_min))
            self.df['STOCHk_14_3_3'] = stoch_k.rolling(window=smooth_k).mean()
            self.df['STOCHd_14_3_3'] = self.df['STOCHk_14_3_3'].rolling(window=d).mean()
        logger.debug(f"Dodano Stochastic({k}, {d})")
        return self
    
    # === Wskaźniki Zmienności ===
    
    def add_bollinger_bands(
        self,
        period: int = 20,
        std_dev: float = 2.0
    ) -> 'TechnicalAnalyzer':
        """Dodaje Bollinger Bands."""
        if TA_AVAILABLE:
            bbands = ta.volatility.BollingerBands(self.df['close'], window=period, window_dev=std_dev)
            self.df['BBM_20_2.0'] = bbands.bollinger_mavg()
            self.df['BBU_20_2.0'] = bbands.bollinger_hband()
            self.df['BBL_20_2.0'] = bbands.bollinger_lband()
        else:
            # Własna implementacja Bollinger Bands
            sma = self.df['close'].rolling(window=period).mean()
            std = self.df['close'].rolling(window=period).std()
            self.df['BBM_20_2.0'] = sma
            self.df['BBU_20_2.0'] = sma + (std * std_dev)
            self.df['BBL_20_2.0'] = sma - (std * std_dev)
        logger.debug(f"Dodano Bollinger Bands({period}, {std_dev})")
        return self
    
    def add_atr(self, period: int = 14) -> 'TechnicalAnalyzer':
        """Dodaje Average True Range."""
        if TA_AVAILABLE:
            atr_ind = ta.volatility.AverageTrueRange(
                self.df['high'], self.df['low'], self.df['close'], window=period
            )
            self.df['atr'] = atr_ind.average_true_range()
        else:
            # Własna implementacja ATR
            high_low = self.df['high'] - self.df['low']
            high_close = np.abs(self.df['high'] - self.df['close'].shift())
            low_close = np.abs(self.df['low'] - self.df['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            self.df['atr'] = true_range.rolling(window=period).mean()
        logger.debug(f"Dodano ATR({period})")
        return self
    
    # === Wskaźniki Wolumenu ===
    
    def add_obv(self) -> 'TechnicalAnalyzer':
        """Dodaje On-Balance Volume."""
        if TA_AVAILABLE:
            self.df['obv'] = ta.volume.OnBalanceVolumeIndicator(
                self.df['close'], self.df['volume']
            ).on_balance_volume()
        else:
            # Własna implementacja OBV
            obv = (np.sign(self.df['close'].diff()) * self.df['volume']).fillna(0).cumsum()
            self.df['obv'] = obv
        logger.debug("Dodano OBV")
        return self
    
    def add_vwap(self) -> 'TechnicalAnalyzer':
        """Dodaje Volume Weighted Average Price."""
        if TA_AVAILABLE:
            self.df['vwap'] = ta.volume.VolumeWeightedAveragePrice(
                self.df['high'], self.df['low'], self.df['close'], self.df['volume']
            ).volume_weighted_average_price()
        else:
            # Własna implementacja VWAP
            typical_price = (self.df['high'] + self.df['low'] + self.df['close']) / 3
            self.df['vwap'] = (typical_price * self.df['volume']).cumsum() / self.df['volume'].cumsum()
        logger.debug("Dodano VWAP")
        return self
    
    # === Metody Pomocnicze ===
    
    def add_all_indicators(self) -> 'TechnicalAnalyzer':
        """Dodaje wszystkie podstawowe wskaźniki."""
        return (
            self
            .add_sma()
            .add_ema()
            .add_rsi()
            .add_macd()
            .add_bollinger_bands()
            .add_atr()
            .add_obv()
        )
    
    def get_signals(self) -> dict:
        """
        Generuje sygnały kupna/sprzedaży na podstawie wskaźników.
        
        Returns:
            Słownik z sygnałami dla różnych wskaźników
        """
        if self.df.empty:
            return {}
        
        latest = self.df.iloc[-1]
        signals = {}
        
        # RSI
        if 'rsi' in self.df.columns:
            rsi_val = latest.get('rsi', 50)
            if rsi_val < 30:
                signals['rsi'] = 'OVERSOLD (kupuj)'
            elif rsi_val > 70:
                signals['rsi'] = 'OVERBOUGHT (sprzedaj)'
            else:
                signals['rsi'] = 'NEUTRAL'
        
        # MACD
        if 'MACD_12_26_9' in self.df.columns and 'MACDs_12_26_9' in self.df.columns:
            macd = latest.get('MACD_12_26_9', 0)
            signal = latest.get('MACDs_12_26_9', 0)
            if macd > signal:
                signals['macd'] = 'BULLISH'
            else:
                signals['macd'] = 'BEARISH'
        
        # SMA Cross
        if 'sma_20' in self.df.columns and 'sma_50' in self.df.columns:
            if latest['sma_20'] > latest['sma_50']:
                signals['sma_cross'] = 'GOLDEN CROSS (bullish)'
            else:
                signals['sma_cross'] = 'DEATH CROSS (bearish)'
        
        # Bollinger Bands
        if 'BBL_20_2.0' in self.df.columns and 'BBU_20_2.0' in self.df.columns:
            close = latest['close']
            lower = latest.get('BBL_20_2.0', close)
            upper = latest.get('BBU_20_2.0', close)
            
            if close < lower:
                signals['bbands'] = 'BELOW LOWER (oversold)'
            elif close > upper:
                signals['bbands'] = 'ABOVE UPPER (overbought)'
            else:
                signals['bbands'] = 'WITHIN BANDS (neutral)'
        
        return signals
    
    def get_dataframe(self) -> pd.DataFrame:
        """Zwraca DataFrame z wszystkimi wskaźnikami."""
        return self.df
    
    def summary(self) -> str:
        """Generuje podsumowanie analizy technicznej."""
        if self.df.empty:
            return "Brak danych do analizy"
        
        latest = self.df.iloc[-1]
        signals = self.get_signals()
        
        summary = [
            "=" * 50,
            "📊 PODSUMOWANIE ANALIZY TECHNICZNEJ",
            "=" * 50,
            f"Cena: ${latest['close']:,.2f}",
            f"Zmiana 24h: {((latest['close'] / self.df.iloc[-24]['close'] - 1) * 100):.2f}%" if len(self.df) >= 24 else "",
            "",
            "📈 SYGNAŁY:",
        ]
        
        for indicator, signal in signals.items():
            summary.append(f"  • {indicator.upper()}: {signal}")
        
        summary.append("=" * 50)
        return "\n".join(summary)


# === Przykład użycia ===
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    
    from src.collectors.exchange.binance_collector import BinanceCollector
    from pathlib import Path
    
    # Pobierz dane
    collector = BinanceCollector()
    df = collector.fetch_ohlcv("BTC/USDT", "1h", limit=200)
    
    # Analiza techniczna
    analyzer = TechnicalAnalyzer(df)
    analyzer.add_all_indicators()
    
    # Wyświetl podsumowanie
    print(analyzer.summary())
    
    # Wyświetl ostatnie dane
    print("\nOstatnie dane ze wskaźnikami:")
    print(analyzer.get_dataframe().tail())

