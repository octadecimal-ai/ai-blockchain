"""
UNDERHUMAN Strategy Version 2.0 dla BTC/USDT 1h
================================================

Strategia AI wykorzystująca detekcję anomalii i filtrowanie reżimu rynkowego.

Kluczowe cechy:
- **Detekcja reżimu:** Klasyfikuje rynek jako bull, bear, neutral lub sideways 
  używając EMA i volatility bazującej na ATR.
- **Dynamiczne SL/TP:** Stop-loss i take-profit bazujące na ATR i typie reżimu
- **Anomalie strukturalne:** Wykrywa anomalie kierunkowe:
    - *Impulse failure* (silny ruch który nie kontynuuje)
    - *Asymmetric response* (osłabienie kupujących/sprzedających)
    - *Energy divergence* (wolumen rośnie podczas stagnacji ceny)
    - *Reaction delay* (wysoki wolumen przy małym ruchu ceny)
- **Scoring pewności:** Każda anomalia dodaje do score pewności (1-10)
- **Bias kierunkowy i filtry:** Generalnie handluje w kierunku trendu. 
  Pozycje counter-trend tylko przy silnych sygnałach odwrócenia (≥3 anomalie).
- **Risk management:** Cooldown po stop-loss, regime lock przed zmianą kierunku.
- **Offline capability:** Używa tylko danych OHLCV.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType


class UnderhumanStrategyV2(BaseStrategy):
    """
    UNDERHUMAN Strategy Version 2.0 dla BTC/USDT 1h.
    
    Wykorzystuje AI-driven anomaly detection i regime filtering do generowania
    sygnałów. Wykrywa reżim rynkowy (bull, bear, neutral, sideways) używając
    EMA trend i volatility, następnie identyfikuje anomalie strukturalne.
    """

    name = "UnderhumanStrategyV2"
    description = "Strategia AI z detekcją anomalii i filtrami reżimu rynkowego (v2.0)"
    timeframe = "1h"

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # === Parametry strategii ===
        # EMA do detekcji trendu
        self.ema_fast_period = self.config.get('ema_fast_period', 50)
        self.ema_slow_period = self.config.get('ema_slow_period', 200)
        
        # ATR dla SL/TP i kalkulacji volatility
        self.atr_period = self.config.get('atr_period', 14)
        self.atr_long_period = self.config.get('atr_long_period', 50)
        
        # RSI dla momentum
        self.rsi_period = self.config.get('rsi_period', 14)
        
        # Wolumen MA dla anomalii wolumenu
        self.vol_ma_period = self.config.get('vol_ma_period', 20)
        
        # === Progi i mnożniki ===
        self.impulse_thr_atr_mult = self.config.get('impulse_thr_atr_mult', 2.0)
        self.vol_spike_mult = self.config.get('vol_spike_mult', 2.0)
        self.small_body_ratio = self.config.get('small_body_ratio', 0.3)
        self.volatility_high_thr = self.config.get('volatility_high_thr', 1.2)
        self.volatility_low_thr = self.config.get('volatility_low_thr', 0.8)
        
        # === SL/TP mnożniki ===
        self.sl_trend_atr_mult = self.config.get('sl_trend_atr_mult', 1.0)
        self.tp_trend_atr_mult = self.config.get('tp_trend_atr_mult', 2.0)
        self.sl_range_atr_mult = self.config.get('sl_range_atr_mult', 1.0)
        self.tp_range_atr_mult = self.config.get('tp_range_atr_mult', 1.0)
        
        # === Filtry anomalii ===
        self.counter_anomaly_threshold = self.config.get('counter_anomaly_threshold', 3)
        self.pro_trend_min_anomaly = self.config.get('pro_trend_min_anomaly', 1)
        self.range_min_anomaly = self.config.get('range_min_anomaly', 2)
        
        # === Anti-whipsaw ===
        self.cooldown_bars = self.config.get('cooldown_bars', 3)
        self.regime_lock_bars = self.config.get('regime_lock_bars', 3)
        
        # === Egzekucja ===
        self.slippage_percent = self.config.get('slippage_percent', 0.1)
        self.min_confidence_for_trade = self.config.get('min_confidence_for_trade', 7.0)
        
        # === Stan wewnętrzny (resetowany przy każdej analizie jeśli _backtest_mode) ===
        self._backtest_mode = self.config.get('_backtest_mode', False)
        self._last_trade_dir: Optional[str] = None
        self._last_trade_exit_idx: int = -1
        self._cooldown_until: int = -1
        self._last_trend: Optional[str] = None

    def _calculate_ema(self, series: pd.Series, period: int) -> pd.Series:
        """Oblicza Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()

    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Oblicza Average True Range."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        return atr

    def _calculate_rsi(self, series: pd.Series, period: int) -> pd.Series:
        """Oblicza Relative Strength Index."""
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        
        # Wilder's smoothing po inicjalizacji
        for i in range(period, len(series)):
            avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
            avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
        
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def _detect_regime(
        self, 
        ema_fast: float, 
        ema_slow: float, 
        atr_short: float, 
        atr_long: float
    ) -> str:
        """
        Określa aktualny reżim rynkowy.
        
        Returns:
            'bull', 'bear', 'sideways', lub 'neutral'
        """
        # Trend direction
        diff = ema_fast - ema_slow
        threshold = atr_long if atr_long > 0 else 0.0
        
        if diff > threshold:
            trend_dir = 'bull'
        elif diff < -threshold:
            trend_dir = 'bear'
        else:
            trend_dir = None
        
        # Volatility state
        if atr_long > 0:
            vol_ratio = atr_short / atr_long
            if vol_ratio > self.volatility_high_thr:
                vol_state = 'high'
            elif vol_ratio < self.volatility_low_thr:
                vol_state = 'low'
            else:
                vol_state = 'moderate'
        else:
            vol_state = 'moderate'
        
        # Final regime
        if trend_dir == 'bull':
            return 'bull'
        elif trend_dir == 'bear':
            return 'bear'
        else:
            return 'sideways' if vol_state == 'low' else 'neutral'

    def _detect_anomalies(
        self,
        df: pd.DataFrame,
        regime: str,
        atr_val: float,
        rsi_val: float,
        vol_ma: float
    ) -> tuple[int, int]:
        """
        Wykrywa anomalie strukturalne na ostatniej świecy.
        
        Returns:
            (bull_signals, bear_signals)
        """
        bull_signals = 0
        bear_signals = 0
        
        if len(df) < 2:
            return bull_signals, bear_signals
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # === Impulse Failure ===
        impulse_threshold = self.impulse_thr_atr_mult * atr_val if atr_val else 0
        
        # Bullish impulse failure: poprzednia świeca duża czerwona, aktualna zamyka powyżej połowy
        prev_body_down = prev['open'] - prev['close']
        if prev_body_down > impulse_threshold:
            mid_body = prev['close'] + prev_body_down / 2.0
            if current['close'] > mid_body:
                bull_signals += 1
        
        # Bearish impulse failure: poprzednia świeca duża zielona, aktualna zamyka poniżej połowy
        prev_body_up = prev['close'] - prev['open']
        if prev_body_up > impulse_threshold:
            mid_body = prev['open'] + prev_body_up / 2.0
            if current['close'] < mid_body:
                bear_signals += 1
        
        # === Asymmetric Response (RSI) ===
        if regime == 'bull' and rsi_val is not None and rsi_val < 50.0:
            bear_signals += 1  # Słabnący bull
        if regime == 'bear' and rsi_val is not None and rsi_val > 50.0:
            bull_signals += 1  # Słabnący bear
        
        # === Energy Divergence ===
        if regime == 'sideways' and vol_ma > 0:
            if current['volume'] > vol_ma * 1.3:
                if self._last_trend == 'bull':
                    bear_signals += 1  # Dystrybucja
                elif self._last_trend == 'bear':
                    bull_signals += 1  # Akumulacja
        
        # === Reaction Delay (absorpcja) ===
        if vol_ma > 0 and current['volume'] > vol_ma * self.vol_spike_mult:
            body_size = abs(current['close'] - current['open'])
            range_size = current['high'] - current['low']
            body_vs_range = (body_size / range_size) if range_size > 0 else 0
            small_move_thr = (atr_val * 0.5) if atr_val else 0
            
            if body_vs_range < self.small_body_ratio or body_size < small_move_thr:
                if regime == 'bull':
                    bear_signals += 1
                elif regime == 'bear':
                    bull_signals += 1
        
        return bull_signals, bear_signals

    def _calculate_confidence(self, signal_count: int) -> float:
        """
        Konwertuje liczbę sygnałów na score pewności (1-10).
        """
        if signal_count >= 5:
            return 10.0
        elif signal_count == 4:
            return 9.0
        elif signal_count == 3:
            return 8.0
        elif signal_count == 2:
            return 7.0
        elif signal_count == 1:
            return 5.0
        else:
            return 0.0

    def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD") -> Optional[TradingSignal]:
        """
        Analizuje dane OHLCV i generuje sygnał tradingowy.
        
        Args:
            df: DataFrame z danymi OHLCV (posortowane chronologicznie)
            symbol: Symbol pary
            
        Returns:
            TradingSignal lub None
        """
        min_required = max(self.ema_slow_period, self.atr_long_period) + 10
        if len(df) < min_required:
            return None
        
        # === Oblicz wskaźniki ===
        close = df['close']
        
        ema_fast = self._calculate_ema(close, self.ema_fast_period)
        ema_slow = self._calculate_ema(close, self.ema_slow_period)
        atr_short = self._calculate_atr(df, self.atr_period)
        atr_long = self._calculate_atr(df, self.atr_long_period)
        rsi = self._calculate_rsi(close, self.rsi_period)
        vol_ma = df['volume'].rolling(window=self.vol_ma_period).mean()
        
        # Ostatnie wartości
        current_price = float(close.iloc[-1])
        ema_fast_val = float(ema_fast.iloc[-1])
        ema_slow_val = float(ema_slow.iloc[-1])
        atr_short_val = float(atr_short.iloc[-1]) if not pd.isna(atr_short.iloc[-1]) else 0
        atr_long_val = float(atr_long.iloc[-1]) if not pd.isna(atr_long.iloc[-1]) else 0
        rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
        vol_ma_val = float(vol_ma.iloc[-1]) if not pd.isna(vol_ma.iloc[-1]) else 0
        
        # Indeks do filtrów czasowych
        current_idx = len(df) - 1
        
        # === Sprawdź cooldown ===
        if current_idx <= self._cooldown_until:
            return None
        
        # === Określ reżim ===
        regime = self._detect_regime(ema_fast_val, ema_slow_val, atr_short_val, atr_long_val)
        
        # Aktualizuj pamięć trendu
        if regime in ('bull', 'bear'):
            self._last_trend = regime
        
        # === Wykryj anomalie ===
        bull_signals, bear_signals = self._detect_anomalies(
            df, regime, atr_short_val, rsi_val, vol_ma_val
        )
        
        # Dodaj bias trendu
        if regime == 'bull':
            bull_signals += 1
        elif regime == 'bear':
            bear_signals += 1
        
        # === Określ kierunek transakcji ===
        trade_dir: Optional[str] = None
        confidence_signals = 0
        
        if regime == 'bull':
            if bear_signals >= self.counter_anomaly_threshold:
                trade_dir = 'short'
                confidence_signals = bear_signals
            elif bull_signals >= (self.pro_trend_min_anomaly + 1):
                trade_dir = 'long'
                confidence_signals = bull_signals
        elif regime == 'bear':
            if bull_signals >= self.counter_anomaly_threshold:
                trade_dir = 'long'
                confidence_signals = bull_signals
            elif bear_signals >= (self.pro_trend_min_anomaly + 1):
                trade_dir = 'short'
                confidence_signals = bear_signals
        elif regime in ('neutral', 'sideways'):
            if bull_signals >= self.range_min_anomaly or bear_signals >= self.range_min_anomaly:
                if bull_signals > bear_signals and bull_signals >= self.range_min_anomaly:
                    trade_dir = 'long'
                    confidence_signals = bull_signals
                elif bear_signals > bull_signals and bear_signals >= self.range_min_anomaly:
                    trade_dir = 'short'
                    confidence_signals = bear_signals
        
        # === Regime lock - unikaj szybkiej zmiany kierunku ===
        if trade_dir and self._last_trade_dir:
            if trade_dir != self._last_trade_dir:
                if (current_idx - self._last_trade_exit_idx) <= self.regime_lock_bars:
                    return None
        
        # Brak sygnału
        if trade_dir is None:
            return None
        
        # === Oblicz confidence ===
        confidence = self._calculate_confidence(confidence_signals)
        
        if confidence < self.min_confidence_for_trade:
            return None
        
        # === Oblicz SL/TP ===
        if regime in ('bull', 'bear'):
            sl_dist = atr_short_val * self.sl_trend_atr_mult
            tp_dist = atr_short_val * self.tp_trend_atr_mult
        else:
            sl_dist = atr_short_val * self.sl_range_atr_mult
            tp_dist = atr_short_val * self.tp_range_atr_mult
        
        if trade_dir == 'long':
            stop_loss = current_price - sl_dist
            take_profit = current_price + tp_dist
            signal_type = SignalType.BUY
        else:
            stop_loss = current_price + sl_dist
            take_profit = current_price - tp_dist
            signal_type = SignalType.SELL
        
        # Przygotuj reason
        reason = f"Regime: {regime}, Anomalies: bull={bull_signals}, bear={bear_signals}"
        
        return TradingSignal(
            signal_type=signal_type,
            symbol=symbol,
            confidence=confidence,
            price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            size_percent=15.0,
            reason=reason,
            strategy=self.name,
            observations=f"ATR={atr_short_val:.2f}, RSI={rsi_val:.1f}"
        )

    def should_close_position(
        self,
        df: pd.DataFrame,
        entry_price: float,
        side: str,
        current_pnl_percent: float
    ) -> Optional[TradingSignal]:
        """
        Sprawdza czy należy zamknąć pozycję.
        Dla V2 polegamy głównie na SL/TP, ale można dodać dodatkowe warunki.
        """
        # V2 polega na dynamicznych SL/TP ustawionych przy wejściu
        # Nie dodajemy dodatkowej logiki wyjścia
        return None

    def update_trade_state(self, trade_dir: str, exit_idx: int, was_stopped: bool = False):
        """
        Aktualizuje stan po zamknięciu transakcji.
        Wywoływane przez BacktestEngine po zamknięciu pozycji.
        """
        self._last_trade_dir = trade_dir
        self._last_trade_exit_idx = exit_idx
        if was_stopped:
            self._cooldown_until = exit_idx + self.cooldown_bars

