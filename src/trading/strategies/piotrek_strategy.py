"""
Piotrek Breakout Strategy
=========================
Strategia oparta na breakoutach z exit na konsolidacji.

Zasady wejścia:
1. Identyfikuj poziomy oporu (lokalne maksima)
2. Wchodź LONG gdy cena przebija opór z impetem
3. Ustaw stop loss poniżej ostatniego wsparcia

Zasady wyjścia:
1. Zamknij gdy cena się "wypłaszcza" (konsolidacja)
2. Zamknij gdy osiągnięty take profit
3. "Dalej to loteria" - nie czekaj na idealne szczyty

Źródło: Analiza transakcji Piotrka na dYdX (2024-12-09)
"""

from typing import Optional, List, Tuple
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType


class PiotrekBreakoutStrategy(BaseStrategy):
    """
    Strategia breakout w stylu Piotrka.
    
    Konfiguracja:
    - breakout_threshold: Minimalne przebicie poziomu (%) - default 1.0%
    - consolidation_threshold: Próg wykrycia konsolidacji (%) - default 0.5%
    - consolidation_candles: Liczba świec do wykrycia konsolidacji - default 3
    - lookback_period: Okres do identyfikacji poziomów - default 20
    - min_confidence: Minimalna pewność sygnału - default 6
    - risk_reward_ratio: Stosunek zysku do ryzyka - default 2.0
    """
    
    name = "PiotrekBreakout"
    description = "Breakout z exit na konsolidacji (styl Piotrka)"
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        
        # Domyślna konfiguracja
        self.breakout_threshold = self.config.get('breakout_threshold', 1.0)
        self.consolidation_threshold = self.config.get('consolidation_threshold', 0.5)
        self.consolidation_candles = self.config.get('consolidation_candles', 3)
        self.lookback_period = self.config.get('lookback_period', 20)
        self.min_confidence = self.config.get('min_confidence', 6)
        self.risk_reward_ratio = self.config.get('risk_reward_ratio', 2.0)
        
        logger.info(f"Strategia {self.name} zainicjalizowana z konfiguracją: {self.config}")
    
    def find_support_resistance_levels(
        self,
        df: pd.DataFrame,
        lookback: int = None
    ) -> Tuple[List[float], List[float]]:
        """
        Znajduje poziomy wsparcia i oporu.
        
        Args:
            df: DataFrame z danymi OHLCV
            lookback: Okres do analizy
            
        Returns:
            (support_levels, resistance_levels)
        """
        lookback = lookback or self.lookback_period
        recent_data = df.tail(lookback)
        
        if len(recent_data) < 5:
            return [], []
        
        highs = recent_data['high'].values
        lows = recent_data['low'].values
        
        # Znajdź lokalne maksima (opory)
        resistance_levels = []
        for i in range(2, len(highs) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                resistance_levels.append(highs[i])
        
        # Znajdź lokalne minima (wsparcia)
        support_levels = []
        for i in range(2, len(lows) - 2):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                support_levels.append(lows[i])
        
        # Sortuj i usuń duplikaty (w przybliżeniu)
        resistance_levels = self._cluster_levels(resistance_levels)
        support_levels = self._cluster_levels(support_levels)
        
        return sorted(support_levels), sorted(resistance_levels)
    
    def _cluster_levels(self, levels: List[float], tolerance: float = 0.005) -> List[float]:
        """Grupuje podobne poziomy cenowe."""
        if not levels:
            return []
        
        levels = sorted(levels)
        clustered = [levels[0]]
        
        for level in levels[1:]:
            # Jeśli poziom jest zbliżony do ostatniego, uśrednij
            if abs(level - clustered[-1]) / clustered[-1] < tolerance:
                clustered[-1] = (clustered[-1] + level) / 2
            else:
                clustered.append(level)
        
        return clustered
    
    def detect_breakout(
        self,
        df: pd.DataFrame,
        resistance_levels: List[float]
    ) -> Tuple[bool, float, float]:
        """
        Wykrywa przebicie poziomu oporu.
        
        Args:
            df: DataFrame z danymi OHLCV
            resistance_levels: Lista poziomów oporu
            
        Returns:
            (is_breakout, breakout_strength, broken_level)
        """
        if len(df) < 2 or not resistance_levels:
            return False, 0.0, 0.0
        
        current_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        current_high = df['high'].iloc[-1]
        
        for resistance in resistance_levels:
            # Breakout: poprzednia świeca pod oporem, aktualna nad oporem
            if prev_close < resistance and current_close > resistance:
                breakout_strength = ((current_close - resistance) / resistance) * 100
                
                if breakout_strength >= self.breakout_threshold:
                    logger.info(
                        f"🚀 BREAKOUT wykryty! Poziom ${resistance:.2f} przebity "
                        f"z siłą {breakout_strength:.2f}%"
                    )
                    return True, breakout_strength, resistance
        
        return False, 0.0, 0.0
    
    def detect_consolidation(self, df: pd.DataFrame) -> Tuple[bool, float]:
        """
        Wykrywa konsolidację (wypłaszczenie).
        
        Args:
            df: DataFrame z danymi OHLCV
            
        Returns:
            (is_consolidating, consolidation_percent)
        """
        if len(df) < self.consolidation_candles:
            return False, 0.0
        
        recent = df.tail(self.consolidation_candles)
        
        # Oblicz zakres ruchów
        price_range = recent['high'].max() - recent['low'].min()
        avg_price = recent['close'].mean()
        range_percent = (price_range / avg_price) * 100
        
        is_consolidating = bool(range_percent < self.consolidation_threshold)
        
        if is_consolidating:
            logger.info(
                f"📊 Konsolidacja wykryta! Zakres {range_percent:.2f}% "
                f"(próg: {self.consolidation_threshold}%)"
            )
        
        return is_consolidating, range_percent
    
    def calculate_momentum(self, df: pd.DataFrame, period: int = 5) -> float:
        """
        Oblicza momentum cenowe.
        
        Args:
            df: DataFrame z danymi OHLCV
            period: Okres do obliczenia momentum
            
        Returns:
            Momentum jako procent zmiany
        """
        if len(df) < period:
            return 0.0
        
        current_price = df['close'].iloc[-1]
        past_price = df['close'].iloc[-period]
        
        momentum = ((current_price - past_price) / past_price) * 100
        return momentum
    
    def calculate_volume_confirmation(self, df: pd.DataFrame) -> float:
        """
        Sprawdza potwierdzenie wolumenem.
        
        Args:
            df: DataFrame z danymi OHLCV
            
        Returns:
            Współczynnik wolumenu (1.0 = średni, >1.0 = powyżej średniej)
        """
        if len(df) < 20 or 'volume' not in df.columns:
            return 1.0
        
        avg_volume = df['volume'].iloc[-20:].mean()
        current_volume = df['volume'].iloc[-1]
        
        if avg_volume == 0:
            return 1.0
        
        return current_volume / avg_volume
    
    def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD") -> Optional[TradingSignal]:
        """
        Analizuje dane i generuje sygnał.
        
        Args:
            df: DataFrame z danymi OHLCV (minimum 20 świec)
            symbol: Symbol pary
            
        Returns:
            TradingSignal lub None
        """
        if len(df) < self.lookback_period:
            logger.warning(f"Za mało danych: {len(df)} < {self.lookback_period}")
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Znajdź poziomy
        supports, resistances = self.find_support_resistance_levels(df)
        
        logger.debug(f"Poziomy S/R: Support={supports}, Resistance={resistances}")
        
        # Sprawdź breakout
        is_breakout, breakout_strength, broken_level = self.detect_breakout(df, resistances)
        
        if is_breakout:
            # Oblicz dodatkowe metryki
            momentum = self.calculate_momentum(df)
            volume_ratio = self.calculate_volume_confirmation(df)
            
            # Oblicz confidence (0-10)
            confidence = min(10, (
                (breakout_strength / self.breakout_threshold) * 3 +  # Siła breakoutu
                (momentum / 2) +  # Momentum
                (volume_ratio * 2)  # Wolumen
            ))
            
            if confidence >= self.min_confidence:
                # Oblicz stop loss (poniżej najbliższego wsparcia lub -2%)
                if supports:
                    stop_loss = max(supports[-1], current_price * 0.98)
                else:
                    stop_loss = current_price * 0.98
                
                # Oblicz take profit na podstawie risk/reward
                risk = current_price - stop_loss
                take_profit = current_price + (risk * self.risk_reward_ratio)
                
                return TradingSignal(
                    signal_type=SignalType.BUY,
                    symbol=symbol,
                    confidence=round(confidence, 1),
                    price=current_price,
                    stop_loss=round(stop_loss, 2),
                    take_profit=round(take_profit, 2),
                    reason=f"Breakout powyżej ${broken_level:.2f} z siłą {breakout_strength:.1f}%",
                    strategy=self.name
                )
        
        return None
    
    def should_close_position(
        self,
        df: pd.DataFrame,
        entry_price: float,
        side: str,
        current_pnl_percent: float
    ) -> Optional[TradingSignal]:
        """
        Sprawdza czy należy zamknąć pozycję.
        
        Zasady Piotrka:
        1. Zamknij gdy cena się "wypłaszcza"
        2. "Dalej to loteria" - nie czekaj na idealne szczyty
        
        Args:
            df: DataFrame z danymi OHLCV
            entry_price: Cena wejścia
            side: "long" lub "short"
            current_pnl_percent: Aktualny PnL w %
            
        Returns:
            TradingSignal (CLOSE) lub None
        """
        if len(df) < self.consolidation_candles:
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Sprawdź konsolidację
        is_consolidating, range_percent = self.detect_consolidation(df)
        
        # Jeśli jesteśmy w zysku i cena się wypłaszcza - zamykamy
        if is_consolidating and current_pnl_percent > 0.5:
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol="",  # Będzie uzupełnione
                confidence=7,
                price=current_price,
                reason=f"Konsolidacja przy PnL +{current_pnl_percent:.1f}% - 'dalej to loteria'",
                strategy=self.name
            )
        
        # Sprawdź utratę momentum
        momentum = self.calculate_momentum(df, period=3)
        
        # Dla LONG: jeśli momentum spada poniżej 0 przy zysku
        if side.lower() == "long" and momentum < -0.5 and current_pnl_percent > 1.0:
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol="",
                confidence=6,
                price=current_price,
                reason=f"Momentum spadające ({momentum:.1f}%) przy zysku - zamykam",
                strategy=self.name
            )
        
        return None


# Przykład użycia
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/Users/piotradamczyk/Projects/Octadecimal/ai-blockchain')
    
    from src.collectors.exchange.dydx_collector import DydxCollector
    
    # Pobierz dane
    collector = DydxCollector()
    df = collector.fetch_candles("BTC-USD", "1h", limit=50)
    
    # Analizuj
    strategy = PiotrekBreakoutStrategy({
        'breakout_threshold': 0.5,
        'min_confidence': 5
    })
    
    signal = strategy.analyze(df, "BTC-USD")
    
    if signal:
        print(f"\n🎯 SYGNAŁ: {signal}")
        print(f"   Powód: {signal.reason}")
        print(f"   SL: ${signal.stop_loss}, TP: ${signal.take_profit}")
    else:
        print("\n⏳ Brak sygnału - HOLD")

