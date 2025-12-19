"""
Scalping Strategy
=================
Strategia scalpingowa dla bardzo szybkich transakcji.
Działa na krótkich interwałach (1-5 min) i generuje wiele małych zysków.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType
from src.analysis.technical.indicators import TechnicalAnalyzer


class ScalpingStrategy(BaseStrategy):
    """
    Strategia scalpingowa - szybkie transakcje na małych ruchach cenowych.
    
    Zasady:
    1. Działa na bardzo krótkich interwałach (1-5 min)
    2. Wykrywa małe ruchy cenowe (0.1-0.5%)
    3. Szybko zamyka pozycje (małe zyski, ale częste)
    4. Używa RSI, MACD, ATR dla szybkich sygnałów
    5. Bardzo ciasne stop loss i take profit
    """
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        
        self.name = "scalping_strategy"
        self.display_name = "Scalping Strategy"
        self.version = "1.0.0"
        
        # Konfiguracja domyślna
        default_config = {
            # Szybkość sygnałów
            'min_price_change': 0.1,  # Minimalna zmiana ceny w % do sygnału
            'max_price_change': 0.5,  # Maksymalna zmiana ceny w % (zamykamy)
            'min_confidence': 4.0,  # Niższy próg niż breakout (szybsze sygnały)
            
            # RSI dla scalping
            'rsi_period': 7,  # Krótszy okres dla szybszych sygnałów
            'rsi_oversold': 25,  # Bardziej agresywne wartości
            'rsi_overbought': 75,
            'rsi_momentum_threshold': 3.0,
            
            # MACD dla momentum
            'macd_fast': 8,  # Szybsze parametry MACD
            'macd_slow': 21,
            'macd_signal': 5,
            
            # ATR dla volatility i stop loss
            'atr_period': 7,
            'atr_multiplier': 1.5,  # Stop loss = entry ± ATR * multiplier
            'atr_take_profit': 2.0,  # Take profit = entry ± ATR * multiplier
            
            # Volume
            'min_volume_ratio': 1.2,  # Minimalny stosunek wolumenu do średniej
            'volume_period': 10,  # Okres dla średniej wolumenu
            
            # Time in position
            'max_hold_seconds': 300,  # Maksymalny czas trzymania pozycji (5 min)
            'min_hold_seconds': 30,  # Minimalny czas przed zamknięciem
            
            # Risk/Reward
            'risk_reward_ratio': 1.5,  # Mniejszy niż breakout (szybsze zyski)
            
            # Slippage
            'slippage_percent': 0.1,  # Mniejszy slippage dla szybkich transakcji
        }
        
        self.config = {**default_config, **(config or {})}
        
        # Timeframe dla scalping (krótkie interwały)
        self.timeframe = self.config.get('timeframe', '1min')  # Domyślnie 1 minuta dla scalping
        
        # Parametry strategii
        self.min_price_change = float(self.config.get('min_price_change', 0.1))
        self.max_price_change = float(self.config.get('max_price_change', 0.5))
        self.min_confidence = float(self.config.get('min_confidence', 4.0))
        
        # RSI
        self.rsi_period = int(self.config.get('rsi_period', 7))
        self.rsi_oversold = float(self.config.get('rsi_oversold', 25))
        self.rsi_overbought = float(self.config.get('rsi_overbought', 75))
        self.rsi_momentum_threshold = float(self.config.get('rsi_momentum_threshold', 3.0))
        
        # MACD
        self.macd_fast = int(self.config.get('macd_fast', 8))
        self.macd_slow = int(self.config.get('macd_slow', 21))
        self.macd_signal = int(self.config.get('macd_signal', 5))
        
        # ATR
        self.atr_period = int(self.config.get('atr_period', 7))
        self.atr_multiplier = float(self.config.get('atr_multiplier', 1.5))
        self.atr_take_profit = float(self.config.get('atr_take_profit', 2.0))
        
        # Volume
        self.min_volume_ratio = float(self.config.get('min_volume_ratio', 1.2))
        self.volume_period = int(self.config.get('volume_period', 10))
        
        # Time limits
        self.max_hold_seconds = int(self.config.get('max_hold_seconds', 300))
        self.min_hold_seconds = int(self.config.get('min_hold_seconds', 30))
        
        # Risk/Reward
        self.risk_reward_ratio = float(self.config.get('risk_reward_ratio', 1.5))
        
        # Slippage
        self.slippage_percent = float(self.config.get('slippage_percent', 0.1))
        
        logger.info(f"Strategia {self.display_name} zainicjalizowana z konfiguracją: {self.config}")
    
    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Oblicza Average True Range (ATR) dla volatility."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR jako średnia krocząca
        atr = tr.rolling(window=self.atr_period).mean()
        
        return atr
    
    def calculate_macd(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Oblicza MACD z szybkimi parametrami."""
        close = df['close']
        
        # EMA szybka i wolna
        ema_fast = close.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.macd_slow, adjust=False).mean()
        
        # MACD line
        macd_line = ema_fast - ema_slow
        
        # Signal line
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        
        # Histogram
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    def detect_quick_momentum(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Wykrywa szybki momentum dla scalping.
        
        Zwraca:
        - direction: "LONG", "SHORT", lub None
        - strength: siła momentum (0-10)
        - price_change: zmiana ceny w %
        """
        if len(df) < max(self.macd_slow, self.rsi_period, self.atr_period) + 5:
            return {'direction': None, 'strength': 0, 'price_change': 0}
        
        current_price = float(df['close'].iloc[-1])
        price_5_candles_ago = float(df['close'].iloc[-6]) if len(df) >= 6 else current_price
        price_change = ((current_price - price_5_candles_ago) / price_5_candles_ago) * 100
        
        # RSI - oblicz bezpośrednio
        analyzer = TechnicalAnalyzer(df.copy())
        analyzer.add_rsi(period=self.rsi_period)
        rsi = float(analyzer.df['rsi'].iloc[-1]) if 'rsi' in analyzer.df.columns and not analyzer.df['rsi'].isna().iloc[-1] else 50.0
        
        # MACD
        macd_data = self.calculate_macd(df)
        macd = macd_data['macd'].iloc[-1] if not macd_data['macd'].empty else 0.0
        signal = macd_data['signal'].iloc[-1] if not macd_data['signal'].empty else 0.0
        histogram = macd_data['histogram'].iloc[-1] if not macd_data['histogram'].empty else 0.0
        
        # Volume
        current_volume = float(df['volume'].iloc[-1])
        avg_volume = float(df['volume'].tail(self.volume_period).mean())
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # ATR dla volatility
        atr = self.calculate_atr(df)
        current_atr = float(atr.iloc[-1]) if not atr.empty else current_price * 0.01
        atr_percent = (current_atr / current_price) * 100 if current_price > 0 else 0
        
        # Oblicz siłę sygnału
        strength = 0.0
        direction = None
        
        # LONG sygnał
        if (rsi < self.rsi_oversold and 
            macd > signal and 
            histogram > 0 and 
            price_change > self.min_price_change and
            volume_ratio >= self.min_volume_ratio):
            
            direction = "LONG"
            strength = (
                (abs(rsi - self.rsi_oversold) / 10) * 2 +  # RSI bonus
                (abs(histogram) / (current_price * 0.001)) * 1.5 +  # MACD momentum
                (min(price_change, self.max_price_change) / self.max_price_change) * 2 +  # Price change
                (min(volume_ratio, 3.0) / 3.0) * 1.5 +  # Volume
                (1.0 if atr_percent < 2.0 else 0.5)  # Low volatility bonus
            )
            strength = min(10.0, strength)
        
        # SHORT sygnał
        elif (rsi > self.rsi_overbought and 
              macd < signal and 
              histogram < 0 and 
              price_change < -self.min_price_change and
              volume_ratio >= self.min_volume_ratio):
            
            direction = "SHORT"
            strength = (
                (abs(rsi - self.rsi_overbought) / 10) * 2 +  # RSI bonus
                (abs(histogram) / (current_price * 0.001)) * 1.5 +  # MACD momentum
                (min(abs(price_change), self.max_price_change) / self.max_price_change) * 2 +  # Price change
                (min(volume_ratio, 3.0) / 3.0) * 1.5 +  # Volume
                (1.0 if atr_percent < 2.0 else 0.5)  # Low volatility bonus
            )
            strength = min(10.0, strength)
        
        return {
            'direction': direction,
            'strength': float(strength),
            'price_change': float(price_change),
            'rsi': float(rsi),
            'macd_histogram': float(histogram),
            'volume_ratio': float(volume_ratio),
            'atr_percent': float(atr_percent)
        }
    
    def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD") -> Optional[TradingSignal]:
        """
        Analizuje rynek i generuje sygnały scalpingowe.
        
        Scalping wymaga:
        - Szybkich sygnałów (RSI, MACD)
        - Potwierdzenia wolumenem
        - Małych ruchów cenowych
        - Niskiej volatility (ATR)
        """
        min_required = max(self.macd_slow, self.rsi_period, self.atr_period) + 10
        if len(df) < min_required:
            logger.debug(f"[SCALPING] Za mało danych: {len(df)} < {min_required}")
            return None
        
        current_price = float(df['close'].iloc[-1])
        
        # Wykryj momentum
        momentum = self.detect_quick_momentum(df)
        
        if not momentum['direction']:
            logger.debug(f"[SCALPING] Brak kierunku momentum (RSI: {momentum.get('rsi', 0):.1f}, MACD: {momentum.get('macd_histogram', 0):.4f})")
            return None
        
        if momentum['strength'] < self.min_confidence:
            logger.debug(f"[SCALPING] Siła sygnału za niska: {momentum['strength']:.1f} < {self.min_confidence} (kierunek: {momentum['direction']})")
            return None
        
        logger.debug(f"[SCALPING] Wykryto momentum {momentum['direction']} z siłą {momentum['strength']:.1f}/10")
        
        # Oblicz ATR dla stop loss i take profit
        atr = self.calculate_atr(df)
        current_atr = float(atr.iloc[-1]) if not atr.empty else current_price * 0.01
        
        # LONG sygnał
        if momentum['direction'] == "LONG":
            # Stop loss poniżej ceny (entry - ATR * multiplier)
            stop_loss = float(current_price - (current_atr * self.atr_multiplier))
            # Take profit powyżej ceny (entry + ATR * take_profit_multiplier)
            take_profit = float(current_price + (current_atr * self.atr_take_profit))
            
            # Upewnij się, że risk/reward jest OK
            risk = current_price - stop_loss
            if risk > 0:
                potential_reward = take_profit - current_price
                if potential_reward / risk < self.risk_reward_ratio:
                    # Skoryguj take profit
                    take_profit = float(current_price + (risk * self.risk_reward_ratio))
            
            reason = (
                f"Scalping LONG: RSI={momentum['rsi']:.1f} < {self.rsi_oversold}, "
                f"MACD↑, zmiana +{momentum['price_change']:.2f}%, "
                f"vol={momentum['volume_ratio']:.1f}x"
            )
            
            return TradingSignal(
                signal_type=SignalType.BUY,
                symbol=symbol,
                confidence=float(round(momentum['strength'], 1)),
                price=current_price,
                stop_loss=float(round(stop_loss, 2)),
                take_profit=float(round(take_profit, 2)),
                reason=reason,
                strategy=self.name
            )
        
        # SHORT sygnał
        elif momentum['direction'] == "SHORT":
            # Stop loss powyżej ceny (entry + ATR * multiplier)
            stop_loss = float(current_price + (current_atr * self.atr_multiplier))
            # Take profit poniżej ceny (entry - ATR * take_profit_multiplier)
            take_profit = float(current_price - (current_atr * self.atr_take_profit))
            
            # Upewnij się, że risk/reward jest OK
            risk = stop_loss - current_price
            if risk > 0:
                potential_reward = current_price - take_profit
                if potential_reward / risk < self.risk_reward_ratio:
                    # Skoryguj take profit
                    take_profit = float(current_price - (risk * self.risk_reward_ratio))
            
            reason = (
                f"Scalping SHORT: RSI={momentum['rsi']:.1f} > {self.rsi_overbought}, "
                f"MACD↓, zmiana {momentum['price_change']:.2f}%, "
                f"vol={momentum['volume_ratio']:.1f}x"
            )
            
            return TradingSignal(
                signal_type=SignalType.SELL,
                symbol=symbol,
                confidence=float(round(momentum['strength'], 1)),
                price=current_price,
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
        Decyduje czy zamknąć pozycję scalpingową.
        
        Scalping zamyka szybko gdy:
        - Osiągnięty mały zysk (0.2-0.5%)
        - Momentum się odwraca
        - Przekroczony maksymalny czas trzymania
        - Stop loss / Take profit
        """
        if len(df) < 5:
            return None
        
        current_price = float(df['close'].iloc[-1])
        
        # Szybkie zamknięcie przy małym zysku
        if current_pnl_percent >= self.max_price_change:
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol="",
                confidence=9.0,
                price=current_price,
                reason=f"Scalping: osiągnięty max zysk {current_pnl_percent:.2f}%",
                strategy=self.name
            )
        
        # Zamknięcie przy małym zysku (0.2%+) jeśli momentum się odwraca
        if current_pnl_percent >= 0.2:
            momentum = self.detect_quick_momentum(df)
            
            # LONG - zamknij jeśli momentum się odwraca
            if side.lower() == "long" and momentum['direction'] == "SHORT":
                return TradingSignal(
                    signal_type=SignalType.CLOSE,
                    symbol="",
                    confidence=7.0,
                    price=current_price,
                    reason=f"Scalping: momentum odwrócony przy zysku {current_pnl_percent:.2f}%",
                    strategy=self.name
                )
            
            # SHORT - zamknij jeśli momentum się odwraca
            elif side.lower() == "short" and momentum['direction'] == "LONG":
                return TradingSignal(
                    signal_type=SignalType.CLOSE,
                    symbol="",
                    confidence=7.0,
                    price=current_price,
                    reason=f"Scalping: momentum odwrócony przy zysku {current_pnl_percent:.2f}%",
                    strategy=self.name
                )
        
        # Zamknięcie przy małej zmianie ceny (konsolidacja)
        price_change = abs((current_price - entry_price) / entry_price * 100)
        if price_change < self.min_price_change and current_pnl_percent > 0:
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol="",
                confidence=6.0,
                price=current_price,
                reason=f"Scalping: konsolidacja przy małej zmianie {price_change:.2f}%",
                strategy=self.name
            )
        
        return None

