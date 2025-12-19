"""
Improved Breakout Strategy
=========================
Poprawiona strategia breakout na bazie analizy wyników optymalizacji.

Główne poprawki:
1. Lepsze filtrowanie sygnałów (wolumen, zmienność, trend)
2. Dynamiczne zarządzanie ryzykiem (ATR-based stop loss)
3. Trailing stop loss
4. Lepsze wykrywanie breakoutów (potwierdzenie wolumenem)
5. Filtrowanie fałszywych sygnałów
6. Lepsze zamykanie pozycji (częściowe zamykanie, trailing stop)

Źródło: Analiza wyników optymalizacji (2025-12-11)
"""

from typing import Optional, List, Tuple
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType
from src.analysis.technical.indicators import TechnicalAnalyzer


class ImprovedBreakoutStrategy(BaseStrategy):
    """
    Poprawiona strategia breakout z lepszymi filtrami i zarządzaniem ryzykiem.
    
    Konfiguracja:
    - breakout_threshold: Minimalne przebicie poziomu (%) - default 0.5%
    - min_confidence: Minimalna pewność sygnału - default 4.0
    - risk_reward_ratio: Stosunek zysku do ryzyka - default 2.0
    - atr_multiplier: Mnożnik ATR dla stop loss - default 2.0
    - min_volume_ratio: Minimalny stosunek wolumenu do średniej - default 1.5
    - use_trend_filter: Czy używać filtru trendu - default True
    - use_volume_filter: Czy używać filtru wolumenu - default True
    - trailing_stop_enabled: Czy używać trailing stop - default True
    - trailing_stop_atr_multiplier: Mnożnik ATR dla trailing stop - default 1.5
    """
    
    name = "ImprovedBreakout"
    description = "Poprawiona strategia breakout z lepszymi filtrami i zarządzaniem ryzykiem"
    timeframe = "1h"
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        
        # Domyślna konfiguracja
        self.breakout_threshold = self.config.get('breakout_threshold', 0.5)
        self.min_confidence = self.config.get('min_confidence', 4.0)
        self.risk_reward_ratio = self.config.get('risk_reward_ratio', 2.0)
        self.atr_multiplier = self.config.get('atr_multiplier', 2.0)
        self.min_volume_ratio = self.config.get('min_volume_ratio', 1.5)
        self.use_trend_filter = self.config.get('use_trend_filter', True)
        self.use_volume_filter = self.config.get('use_volume_filter', True)
        self.trailing_stop_enabled = self.config.get('trailing_stop_enabled', True)
        self.trailing_stop_atr_multiplier = self.config.get('trailing_stop_atr_multiplier', 1.5)
        
        # RSI konfiguracja
        self.use_rsi = self.config.get('use_rsi', True)
        self.rsi_period = self.config.get('rsi_period', 14)
        self.rsi_oversold = self.config.get('rsi_oversold', 35)
        self.rsi_overbought = self.config.get('rsi_overbought', 65)
        
        # Trend konfiguracja
        self.trend_sma_period = self.config.get('trend_sma_period', 50)
        self.trend_ema_period = self.config.get('trend_ema_period', 20)
        
        logger.info(f"Strategia {self.name} zainicjalizowana z konfiguracją: {self.config}")
    
    def _detect_trend(self, df: pd.DataFrame) -> str:
        """
        Wykrywa trend rynkowy używając SMA i EMA.
        
        Returns:
            "up" - trend wzrostowy
            "down" - trend spadkowy
            "sideways" - brak wyraźnego trendu
        """
        if len(df) < self.trend_sma_period:
            return "sideways"
        
        try:
            analyzer = TechnicalAnalyzer(df)
            analyzer.add_sma(periods=[self.trend_sma_period])
            analyzer.add_ema(periods=[self.trend_ema_period])
            df = analyzer.df
            
            sma_col = f'sma_{self.trend_sma_period}'
            ema_col = f'ema_{self.trend_ema_period}'
            
            if sma_col not in df.columns or ema_col not in df.columns:
                return "sideways"
            
            if df[sma_col].isna().iloc[-1] or df[ema_col].isna().iloc[-1]:
                return "sideways"
            
            current_price = float(df['close'].iloc[-1])
            sma_value = float(df[sma_col].iloc[-1])
            ema_value = float(df[ema_col].iloc[-1])
            
            # Trend wzrostowy: cena > SMA > EMA
            if current_price > sma_value * 1.01 and sma_value > ema_value * 1.005:
                return "up"
            # Trend spadkowy: cena < SMA < EMA
            elif current_price < sma_value * 0.99 and sma_value < ema_value * 0.995:
                return "down"
            else:
                return "sideways"
        except Exception as e:
            logger.debug(f"Błąd wykrywania trendu: {e}")
            return "sideways"
    
    def _calculate_volume_confirmation(self, df: pd.DataFrame, period: int = 20) -> float:
        """
        Oblicza stosunek aktualnego wolumenu do średniej.
        
        Returns:
            Stosunek wolumenu (1.0 = średnia, 1.5 = 50% powyżej średniej)
        """
        if len(df) < period:
            return 1.0
        
        try:
            current_volume = float(df['volume'].iloc[-1])
            avg_volume = float(df['volume'].tail(period).mean())
            
            if avg_volume == 0:
                return 1.0
            
            return current_volume / avg_volume
        except Exception:
            return 1.0
    
    def _calculate_volatility(self, df: pd.DataFrame, period: int = 20) -> float:
        """
        Oblicza zmienność (volatility) jako odchylenie standardowe zmian cen.
        
        Returns:
            Volatility w %
        """
        if len(df) < period:
            return 0.0
        
        try:
            price_changes = df['close'].pct_change().tail(period)
            volatility = float(price_changes.std() * 100)
            return volatility
        except Exception:
            return 0.0
    
    def _find_support_resistance_levels(
        self,
        df: pd.DataFrame,
        lookback: int = 30
    ) -> Tuple[List[float], List[float]]:
        """
        Znajduje poziomy wsparcia i oporu używając lokalnych ekstremów.
        """
        if len(df) < lookback:
            return [], []
        
        recent_data = df.tail(lookback)
        
        highs = recent_data['high'].values
        lows = recent_data['low'].values
        
        # Znajdź lokalne maksima (opory) - szukaj w oknie 5 świec
        resistance_levels = []
        for i in range(5, len(highs) - 5):
            if highs[i] == max(highs[i-5:i+6]):
                resistance_levels.append(highs[i])
        
        # Znajdź lokalne minima (wsparcia) - szukaj w oknie 5 świec
        support_levels = []
        for i in range(5, len(lows) - 5):
            if lows[i] == min(lows[i-5:i+6]):
                support_levels.append(lows[i])
        
        # Usuń duplikaty i sortuj
        resistance_levels = sorted(set(resistance_levels), reverse=True)[:5]
        support_levels = sorted(set(support_levels))[:5]
        
        return support_levels, resistance_levels
    
    def _detect_breakout(
        self,
        df: pd.DataFrame,
        resistance_levels: List[float],
        current_price: float
    ) -> Tuple[bool, float, Optional[float]]:
        """
        Wykrywa breakout powyżej oporu z potwierdzeniem wolumenem.
        
        Sprawdza czy cena właśnie przebiła opór (była poniżej, teraz jest powyżej).
        Używa podejścia podobnego do PiotrekBreakoutStrategy.
        
        Returns:
            (is_breakout, strength_percent, broken_level)
        """
        if not resistance_levels or len(df) < 3:
            return False, 0.0, None
        
        # Znajdź najbliższy opór poniżej ceny (który został przebity)
        nearest_resistance = None
        for resistance in sorted(resistance_levels, reverse=True):
            if resistance < current_price:
                nearest_resistance = resistance
                break
        
        if nearest_resistance is None:
            return False, 0.0, None
        
        # Sprawdź czy w ostatnich 3 świecach cena była poniżej oporu
        lookback = min(3, len(df) - 1)
        was_below = False
        
        for i in range(max(0, len(df) - lookback - 1), len(df) - 1):
            prev_high = float(df['high'].iloc[i])
            prev_close = float(df['close'].iloc[i])
            
            # Jeśli wcześniej cena była poniżej oporu
            if prev_high < nearest_resistance or prev_close < nearest_resistance:
                was_below = True
                break
        
        # Jeśli cena była poniżej oporu i teraz jest powyżej = breakout
        if was_below and current_price > nearest_resistance:
            breakout_strength = ((current_price - nearest_resistance) / nearest_resistance) * 100
            
            if breakout_strength >= self.breakout_threshold:
                # Potwierdź wolumenem
                volume_ratio = self._calculate_volume_confirmation(df)
                if volume_ratio >= self.min_volume_ratio:
                    return True, breakout_strength, nearest_resistance
        
        return False, 0.0, None
    
    def _detect_breakdown(
        self,
        df: pd.DataFrame,
        support_levels: List[float],
        current_price: float
    ) -> Tuple[bool, float, Optional[float]]:
        """
        Wykrywa breakdown poniżej wsparcia z potwierdzeniem wolumenem.
        
        Sprawdza czy cena właśnie przebiła wsparcie w dół (była powyżej, teraz jest poniżej).
        Używa podejścia podobnego do PiotrekBreakoutStrategy.
        
        Returns:
            (is_breakdown, strength_percent, broken_level)
        """
        if not support_levels or len(df) < 3:
            return False, 0.0, None
        
        # Znajdź najbliższe wsparcie powyżej ceny (które zostało przebite)
        nearest_support = None
        for support in sorted(support_levels, reverse=True):
            if support > current_price:
                nearest_support = support
                break
        
        if nearest_support is None:
            return False, 0.0, None
        
        # Sprawdź czy w ostatnich 3 świecach cena była powyżej wsparcia
        lookback = min(3, len(df) - 1)
        was_above = False
        
        for i in range(max(0, len(df) - lookback - 1), len(df) - 1):
            prev_low = float(df['low'].iloc[i])
            prev_close = float(df['close'].iloc[i])
            
            # Jeśli wcześniej cena była powyżej wsparcia
            if prev_low > nearest_support or prev_close > nearest_support:
                was_above = True
                break
        
        # Jeśli cena była powyżej wsparcia i teraz jest poniżej = breakdown
        if was_above and current_price < nearest_support:
            breakdown_strength = ((nearest_support - current_price) / nearest_support) * 100
            
            if breakdown_strength >= self.breakout_threshold:
                # Potwierdź wolumenem
                volume_ratio = self._calculate_volume_confirmation(df)
                if volume_ratio >= self.min_volume_ratio:
                    return True, breakdown_strength, nearest_support
        
        return False, 0.0, None
    
    def _calculate_signal_confidence(
        self,
        df: pd.DataFrame,
        breakout_strength: float,
        volume_ratio: float,
        rsi_value: float,
        rsi_signal: str,
        trend: str,
        volatility: float
    ) -> float:
        """
        Oblicza confidence sygnału (0-10) na podstawie wielu czynników.
        """
        confidence = 0.0
        
        # Siła breakoutu (0-3)
        confidence += min(3.0, (breakout_strength / self.breakout_threshold) * 1.5)
        
        # Potwierdzenie wolumenem (0-2)
        if volume_ratio >= self.min_volume_ratio:
            confidence += min(2.0, (volume_ratio - 1.0) * 2.0)
        
        # RSI (0-2)
        if self.use_rsi:
            if rsi_signal == "LONG" and rsi_value < self.rsi_oversold:
                confidence += 2.0
            elif rsi_signal == "SHORT" and rsi_value > self.rsi_overbought:
                confidence += 2.0
            elif rsi_signal == "LONG" and rsi_value < 50:
                confidence += 1.0
            elif rsi_signal == "SHORT" and rsi_value > 50:
                confidence += 1.0
        
        # Trend (0-1.5)
        if self.use_trend_filter:
            if trend == "up":
                confidence += 1.5  # Bonus za trend wzrostowy
            elif trend == "sideways":
                confidence += 0.5
        
        # Volatility (0-1.5) - preferuj umiarkowaną zmienność
        if 0.5 <= volatility <= 3.0:
            confidence += 1.5
        elif 0.3 <= volatility <= 5.0:
            confidence += 0.5
        
        return min(10.0, confidence)
    
    def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD") -> Optional[TradingSignal]:
        """
        Analizuje dane i generuje sygnały tradingowe.
        """
        if len(df) < 50:
            return None
        
        # Dodaj wskaźniki techniczne
        try:
            analyzer = TechnicalAnalyzer(df)
            analyzer.add_rsi(period=self.rsi_period)
            analyzer.add_atr(period=14)
            analyzer.add_sma(periods=[self.trend_sma_period])
            analyzer.add_ema(periods=[self.trend_ema_period])
            df = analyzer.df  # Pobierz zaktualizowany DataFrame
        except Exception as e:
            logger.debug(f"Błąd dodawania wskaźników: {e}")
            return None
        
        current_price = float(df['close'].iloc[-1])
        
        # Oblicz metryki
        trend = self._detect_trend(df) if self.use_trend_filter else "sideways"
        volume_ratio = self._calculate_volume_confirmation(df)
        volatility = self._calculate_volatility(df)
        
        # RSI
        rsi_value = float(df['rsi'].iloc[-1]) if 'rsi' in df.columns else 50.0
        rsi_signal = None
        if self.use_rsi:
            if rsi_value < self.rsi_oversold:
                rsi_signal = "LONG"
            elif rsi_value > self.rsi_overbought:
                rsi_signal = "SHORT"
        
        # Znajdź poziomy S/R
        supports, resistances = self._find_support_resistance_levels(df)
        
        # LONG: Breakout powyżej oporu
        is_breakout, breakout_strength, broken_level = self._detect_breakout(
            df, resistances, current_price
        )
        
        if is_breakout and (rsi_signal == "LONG" or not self.use_rsi) and trend != "down":
            # Filtruj wolumenem
            if self.use_volume_filter and volume_ratio < self.min_volume_ratio:
                logger.debug(f"[IMPROVED] Odrzucono LONG: za niski wolumen ({volume_ratio:.2f}x)")
                return None
            
            # Oblicz confidence
            confidence = self._calculate_signal_confidence(
                df, breakout_strength, volume_ratio, rsi_value, rsi_signal, trend, volatility
            )
            
            if confidence >= self.min_confidence:
                # Oblicz stop loss używając ATR
                atr_value = float(df['atr'].iloc[-1]) if 'atr' in df.columns else current_price * 0.02
                stop_loss = current_price - (atr_value * self.atr_multiplier)
                
                # Upewnij się, że stop loss nie jest zbyt blisko (min 2%)
                stop_loss = min(stop_loss, current_price * 0.98)
                
                # Oblicz take profit
                risk = current_price - stop_loss
                take_profit = current_price + (risk * self.risk_reward_ratio)
                
                reason = (
                    f"Breakout powyżej ${broken_level:.2f} (siła: {breakout_strength:.1f}%) "
                    f"+ wolumen {volume_ratio:.1f}x + trend {trend}"
                )
                
                return TradingSignal(
                    signal_type=SignalType.BUY,
                    symbol=symbol,
                    confidence=float(round(confidence, 1)),
                    price=float(current_price),
                    stop_loss=float(round(stop_loss, 2)),
                    take_profit=float(round(take_profit, 2)),
                    reason=reason,
                    strategy=self.name
                )
        
        # SHORT: Breakdown poniżej wsparcia
        is_breakdown, breakdown_strength, broken_level = self._detect_breakdown(
            df, supports, current_price
        )
        
        if is_breakdown and (rsi_signal == "SHORT" or not self.use_rsi) and trend != "up":
            # Filtruj wolumenem
            if self.use_volume_filter and volume_ratio < self.min_volume_ratio:
                logger.debug(f"[IMPROVED] Odrzucono SHORT: za niski wolumen ({volume_ratio:.2f}x)")
                return None
            
            # Oblicz confidence
            confidence = self._calculate_signal_confidence(
                df, breakdown_strength, volume_ratio, rsi_value, rsi_signal, trend, volatility
            )
            
            if confidence >= self.min_confidence:
                # Oblicz stop loss używając ATR
                atr_value = float(df['atr'].iloc[-1]) if 'atr' in df.columns else current_price * 0.02
                stop_loss = current_price + (atr_value * self.atr_multiplier)
                
                # Upewnij się, że stop loss nie jest zbyt blisko (min 2%)
                stop_loss = max(stop_loss, current_price * 1.02)
                
                # Oblicz take profit
                risk = stop_loss - current_price
                take_profit = current_price - (risk * self.risk_reward_ratio)
                
                reason = (
                    f"Breakdown poniżej ${broken_level:.2f} (siła: {breakdown_strength:.1f}%) "
                    f"+ wolumen {volume_ratio:.1f}x + trend {trend}"
                )
                
                return TradingSignal(
                    signal_type=SignalType.SELL,
                    symbol=symbol,
                    confidence=float(round(confidence, 1)),
                    price=float(current_price),
                    stop_loss=float(round(stop_loss, 2)),
                    take_profit=float(round(take_profit, 2)),
                    reason=reason,
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
        
        Używa trailing stop loss i innych sygnałów wyjścia.
        """
        if len(df) < 20:
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Trailing stop loss
        if self.trailing_stop_enabled and current_pnl_percent > 1.0:
            try:
                analyzer = TechnicalAnalyzer(df)
                analyzer.add_atr(period=14)
                df = analyzer.df
                atr_value = float(df['atr'].iloc[-1]) if 'atr' in df.columns else current_price * 0.01
                
                if side.lower() == "long":
                    # Trailing stop: cena - (ATR * multiplier)
                    trailing_stop = current_price - (atr_value * self.trailing_stop_atr_multiplier)
                    # Jeśli cena spadła poniżej trailing stop
                    if current_price < trailing_stop:
                        return TradingSignal(
                            signal_type=SignalType.CLOSE,
                            symbol="",
                            confidence=8.0,
                            price=float(current_price),
                            reason=f"Trailing stop loss (PnL: {current_pnl_percent:.1f}%)",
                            strategy=self.name
                        )
                elif side.lower() == "short":
                    # Trailing stop: cena + (ATR * multiplier)
                    trailing_stop = current_price + (atr_value * self.trailing_stop_atr_multiplier)
                    # Jeśli cena wzrosła powyżej trailing stop
                    if current_price > trailing_stop:
                        return TradingSignal(
                            signal_type=SignalType.CLOSE,
                            symbol="",
                            confidence=8.0,
                            price=float(current_price),
                            reason=f"Trailing stop loss (PnL: {current_pnl_percent:.1f}%)",
                            strategy=self.name
                        )
            except Exception as e:
                logger.debug(f"Błąd trailing stop: {e}")
        
        # Sprawdź utratę momentum
        try:
            analyzer = TechnicalAnalyzer(df)
            analyzer.add_rsi(period=self.rsi_period)
            df = analyzer.df
            rsi_value = float(df['rsi'].iloc[-1]) if 'rsi' in df.columns else 50.0
            
            if side.lower() == "long":
                # Zamknij LONG jeśli RSI > 70 (overbought) i jesteśmy w zysku
                if rsi_value > 70 and current_pnl_percent > 2.0:
                    return TradingSignal(
                        signal_type=SignalType.CLOSE,
                        symbol="",
                        confidence=7.0,
                        price=float(current_price),
                        reason=f"RSI overbought ({rsi_value:.1f}) przy zysku {current_pnl_percent:.1f}%",
                        strategy=self.name
                    )
            elif side.lower() == "short":
                # Zamknij SHORT jeśli RSI < 30 (oversold) i jesteśmy w zysku
                if rsi_value < 30 and current_pnl_percent > 2.0:
                    return TradingSignal(
                        signal_type=SignalType.CLOSE,
                        symbol="",
                        confidence=7.0,
                        price=float(current_price),
                        reason=f"RSI oversold ({rsi_value:.1f}) przy zysku {current_pnl_percent:.1f}%",
                        strategy=self.name
                    )
        except Exception:
            pass
        
        return None


# Przykład użycia
if __name__ == "__main__":
    strategy = ImprovedBreakoutStrategy({
        'breakout_threshold': 0.5,
        'min_confidence': 4.0,
        'risk_reward_ratio': 2.0,
        'atr_multiplier': 2.0,
        'min_volume_ratio': 1.5,
        'use_trend_filter': True,
        'use_volume_filter': True,
        'trailing_stop_enabled': True
    })
    print(f"Strategia: {strategy.name}")
    print(f"Opis: {strategy.description}")

