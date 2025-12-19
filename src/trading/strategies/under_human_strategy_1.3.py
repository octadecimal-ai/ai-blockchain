"""
UNDERHUMAN STRATEGY v1.3 - OPUS AI EDGE
========================================
Oparte na działającej v1.2 z nowymi ulepszeniami AI:

1. Kelly Criterion dla optymalnego position sizing
2. Adaptive SL/TP w zależności od volatility
3. Momentum confirmation (RSI + trend alignment)
4. Lepsze parametry wejścia/wyjścia
5. Smart position sizing oparte na equity curve
"""

from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType
from src.collectors.exchange.dydx_collector import DydxCollector


class UnderhumanStrategyV13(BaseStrategy):
    """
    UNDERHUMAN STRATEGY v1.3 - OPUS AI EDGE
    Bazuje na sprawdzonej V1.2 z nowymi ulepszeniami:
    - Kelly Criterion position sizing
    - Adaptive SL/TP
    - Momentum confirmation
    """

    name = "UnderhumanStrategyV13"
    description = "Strategia AI z Kelly Criterion i adaptive SL/TP (OPUS AI EDGE)"
    timeframe = "1h"

    def __init__(self, config: dict = None):
        super().__init__(config)

        # === RSI - podstawowy wskaźnik ===
        self.rsi_period = self.config.get("rsi_period", 14)

        # === Okna/parametry anomalii ===
        self.lookback_state = self.config.get("lookback_state", 36)
        self.lookback_short = self.config.get("lookback_short", 6)
        self.lookback_impulse = self.config.get("lookback_impulse", 4)
        self.impulse_threshold_pct = self.config.get("impulse_threshold_pct", 0.8)
        self.min_anomalies_to_trade = self.config.get("min_anomalies_to_trade", 2)

        # Orderbook
        self.orderbook_levels = self.config.get("orderbook_levels", 10)
        self.imbalance_threshold = self.config.get("imbalance_threshold", 0.18)

        # Funding/OI
        self.funding_divergence_z = self.config.get("funding_divergence_z", 1.2)
        self.oi_divergence_z = self.config.get("oi_divergence_z", 1.2)
        self.delay_threshold = self.config.get("delay_threshold", 1.35)

        # === ATR dla SL/TP (powrót do sprawdzonych V1.2) ===
        self.atr_period = self.config.get("atr_period", 14)
        self.atr_sl_multiplier = self.config.get("atr_sl_multiplier", 2.0)  # V1.2 value
        self.atr_tp_multiplier = self.config.get("atr_tp_multiplier", 3.0)  # V1.2 value
        self.min_sl_percent = self.config.get("min_sl_percent", 2.0)  # V1.2 value
        self.min_tp_percent = self.config.get("min_tp_percent", 3.0)  # V1.2 value

        # Trend filtering
        self.trend_ema_fast = self.config.get("trend_ema_fast", 20)
        self.trend_ema_slow = self.config.get("trend_ema_slow", 50)
        self.trend_strength_threshold = self.config.get("trend_strength_threshold", 0.5)

        # === POSITION SIZING (konserwatywne) ===
        self.kelly_fraction = self.config.get("kelly_fraction", 0.15)  # Mniejszy Kelly
        self.base_win_rate = self.config.get("base_win_rate", 0.45)
        self.base_risk_reward = self.config.get("base_risk_reward", 1.5)
        self.min_position_size = self.config.get("min_position_size", 10.0)  # Min 10%
        self.max_position_size = self.config.get("max_position_size", 15.0)  # Max 15% (mniejszy)

        # === EQUITY CURVE TRACKING - NOWOŚĆ V1.3 ===
        self.equity_lookback = self.config.get("equity_lookback", 10)
        self.equity_boost_threshold = self.config.get("equity_boost_threshold", 0.6)
        self.equity_cut_threshold = self.config.get("equity_cut_threshold", 0.4)
        self.equity_boost_multiplier = self.config.get("equity_boost_multiplier", 1.2)
        self.equity_cut_multiplier = self.config.get("equity_cut_multiplier", 0.8)
        self.trade_history: List[Dict[str, Any]] = []

        # === VOLATILITY ADAPTIVE TP - NOWOŚĆ V1.3 (delikatniejsze) ===
        self.low_vol_tp_boost = self.config.get("low_vol_tp_boost", 1.15)  # Mniejszy boost
        self.high_vol_tp_cut = self.config.get("high_vol_tp_cut", 0.9)  # Mniejszy cut

        # Volatility filtering (powrót do V1.2)
        self.volatility_period = self.config.get("volatility_period", 24)
        self.max_volatility_percent = self.config.get("max_volatility_percent", 5.0)  # V1.2 value
        self.min_volatility_percent = self.config.get("min_volatility_percent", 0.3)  # V1.2 value

        # Ochrona przed serią strat
        self.max_consecutive_losses = self.config.get("max_consecutive_losses", 3)
        self.loss_cooldown_seconds = self.config.get("loss_cooldown_seconds", 600)
        self.consecutive_losses = 0
        self.last_loss_time: Optional[datetime] = None

        # Max drawdown protection
        self.max_drawdown_percent = self.config.get("max_drawdown_percent", 15.0)
        self.initial_balance = None
        self.peak_balance = None

        # Cooldown
        self.cooldown_seconds = self.config.get("cooldown_seconds", 120)
        self.last_close_time: Optional[datetime] = None
        self.paper_trading_engine = None

        # Backtest mode
        self._backtest_mode = self.config.get("_backtest_mode", False)

        if not self._backtest_mode:
            try:
                self.dydx_collector = DydxCollector(testnet=False)
                logger.info("DydxCollector zainicjalizowany dla UNDERHUMAN v1.3 OPUS AI EDGE")
            except Exception as e:
                logger.warning(f"Nie udało się zainicjalizować DydxCollector: {e}")
                self.dydx_collector = None
        else:
            self.dydx_collector = None
            logger.info("Tryb backtestingu - pomijam inicjalizację DydxCollector")

        logger.info(f"Strategia {self.name} zainicjalizowana (OPUS AI EDGE v1.3)")

    def set_paper_trading_engine(self, engine):
        self.paper_trading_engine = engine
        if engine and hasattr(engine, 'balance'):
            self.initial_balance = engine.balance
            self.peak_balance = engine.balance

    # =========================
    # PODSTAWOWE WSKAŹNIKI
    # =========================

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def _calculate_volatility(self, df: pd.DataFrame, period: int = 24) -> float:
        """Oblicza volatility jako std returns * 100."""
        if len(df) < period + 1:
            return 1.0
        
        returns = df['close'].pct_change().dropna()
        if len(returns) < period:
            return 1.0
        
        volatility = float(returns.tail(period).std() * 100)
        return volatility if not pd.isna(volatility) else 1.0

    def _detect_trend(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Wykrywa trend używając EMA (V1.2 compatible)."""
        close = df['close']
        
        ema_fast = close.ewm(span=self.trend_ema_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.trend_ema_slow, adjust=False).mean()
        
        current_fast = float(ema_fast.iloc[-1])
        current_slow = float(ema_slow.iloc[-1])
        
        # Poprzedni kierunek trendu (dla wykrywania odwrócenia)
        if len(df) >= self.trend_ema_slow + 1:
            prev_fast = float(ema_fast.iloc[-2])
            prev_slow = float(ema_slow.iloc[-2])
            if prev_fast > prev_slow:
                previous_direction = 'up'
            elif prev_fast < prev_slow:
                previous_direction = 'down'
            else:
                previous_direction = 'sideways'
        else:
            previous_direction = 'sideways'
        
        # Różnica procentowa między EMA
        diff_pct = abs(current_fast - current_slow) / current_slow * 100
        
        if diff_pct < self.trend_strength_threshold:
            return {'direction': 'sideways', 'strength': diff_pct / self.trend_strength_threshold, 
                   'ema_fast': current_fast, 'ema_slow': current_slow, 'previous_direction': previous_direction}
        
        if current_fast > current_slow:
            strength = min(1.0, diff_pct / (self.trend_strength_threshold * 2))
            return {'direction': 'up', 'strength': strength, 'ema_fast': current_fast, 'ema_slow': current_slow, 'previous_direction': previous_direction}
        else:
            strength = min(1.0, diff_pct / (self.trend_strength_threshold * 2))
            return {'direction': 'down', 'strength': strength, 'ema_fast': current_fast, 'ema_slow': current_slow, 'previous_direction': previous_direction}

    # =========================
    # KELLY CRITERION - AI EDGE
    # =========================

    def _calculate_dynamic_position_size(self, confidence: float) -> float:
        """
        V1.2 compatible: Oblicza dynamiczny rozmiar pozycji w zależności od confidence.
        - confidence 8.0 = base (15%)
        - confidence 10.0 = max (15%)
        - confidence < 8.0 = min (10%)
        """
        base_size = 15.0
        
        if confidence >= 8.0:
            # Skalowanie liniowe między base a max
            ratio = (confidence - 8.0) / 2.0  # 0.0-1.0 dla confidence 8.0-10.0
            size = base_size + (self.max_position_size - base_size) * ratio
        else:
            # Skalowanie liniowe między min a base
            ratio = (confidence - 8.0) / (8.0 - 8.0 + 0.01)  # uniknięcie dzielenia przez 0
            size = self.min_position_size
        
        return float(max(self.min_position_size, min(self.max_position_size, size)))

    def _adjust_for_equity_curve(self, base_size: float) -> float:
        """Modyfikuje rozmiar pozycji na podstawie equity curve."""
        if len(self.trade_history) < 3:
            return base_size
        
        recent_trades = self.trade_history[-self.equity_lookback:]
        winning = sum(1 for t in recent_trades if t.get('pnl', 0) > 0)
        recent_win_rate = winning / len(recent_trades)
        
        if recent_win_rate >= self.equity_boost_threshold:
            return min(self.max_position_size, base_size * self.equity_boost_multiplier)
        elif recent_win_rate <= self.equity_cut_threshold:
            return max(self.min_position_size, base_size * self.equity_cut_multiplier)
        
        return base_size

    def _record_trade(self, pnl: float):
        """Zapisuje transakcję do historii."""
        self.trade_history.append({
            'timestamp': datetime.now(),
            'pnl': pnl
        })
        if len(self.trade_history) > 100:
            self.trade_history = self.trade_history[-100:]

    # =========================
    # ANOMALY DETECTION
    # =========================

    def _pct_change_n(self, series: pd.Series, n: int) -> float:
        if len(series) < n + 1:
            return 0.0
        return float((series.iloc[-1] / series.iloc[-n-1] - 1) * 100)

    def _zscore(self, series: pd.Series, window: int) -> pd.Series:
        mean = series.rolling(window=window).mean()
        std = series.rolling(window=window).std()
        return (series - mean) / (std + 1e-9)

    def _detect_impulse(self, df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < self.lookback_impulse + 1:
            return {"detected": False, "direction": None, "magnitude_pct": 0}
        close = df["close"]
        current = float(close.iloc[-1])
        lookback = float(close.iloc[-self.lookback_impulse - 1])
        change_pct = abs((current - lookback) / lookback * 100)
        direction = "up" if current > lookback else "down"
        return {
            "detected": change_pct >= self.impulse_threshold_pct,
            "direction": direction,
            "magnitude_pct": change_pct
        }

    def _impulse_failure(self, df: pd.DataFrame) -> bool:
        imp = self._detect_impulse(df)
        if not imp["detected"]:
            return False
        close = df["close"]
        after_impulse = close.tail(2)
        if len(after_impulse) < 2:
            return False
        ret = float((after_impulse.iloc[-1] / after_impulse.iloc[0] - 1) * 100)
        if imp["direction"] == "up":
            return ret < -0.3
        else:
            return ret > 0.3

    def _price_reaction_to_volume(self, df: pd.DataFrame, window: int) -> float:
        close = df["close"]
        vol = df.get("volume", pd.Series([0]*len(df)))
        rets = close.pct_change().abs()
        vol_norm = vol / (vol.rolling(window).mean() + 1e-9)
        reaction = float((rets * vol_norm).tail(window).mean())
        return reaction

    def _energy_divergence(self, df: pd.DataFrame, market_ctx: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        close = df["close"]
        drift = abs(self._pct_change_n(close, self.lookback_short))
        details = {"drift": drift}
        oi_div = False
        fr_div = False

        if "open_interest" in df.columns:
            oi_z = float(self._zscore(df["open_interest"], self.lookback_state).iloc[-1])
            if drift < 0.15 and oi_z > self.oi_divergence_z:
                oi_div = True

        if "funding_rate" in df.columns:
            fr_z = float(self._zscore(df["funding_rate"], self.lookback_state).iloc[-1])
            if drift < 0.15 and abs(fr_z) > self.funding_divergence_z:
                fr_div = True

        details["oi_vs_price_divergence"] = oi_div
        details["funding_vs_price_divergence"] = fr_div

        return (oi_div or fr_div), details

    def _asymmetric_response(self, df: pd.DataFrame) -> bool:
        if len(df) < self.lookback_short + 2:
            return False
        close = df["close"]
        vol = df.get("volume", pd.Series([0]*len(df)))
        rets = close.pct_change()
        up = rets.where(rets > 0, 0).tail(self.lookback_short)
        dn = (-rets.where(rets < 0, 0)).tail(self.lookback_short)
        vol_s = vol.tail(self.lookback_short)
        up_energy = float((up.abs() / (vol_s + 1e-6)).mean())
        dn_energy = float((dn.abs() / (vol_s + 1e-6)).mean())
        if up_energy == 0 or dn_energy == 0:
            return False
        ratio = max(up_energy, dn_energy) / min(up_energy, dn_energy)
        return ratio > 1.45

    def _reaction_delay(self, df: pd.DataFrame) -> bool:
        if len(df) < self.lookback_state + 5:
            return False
        r_now = self._price_reaction_to_volume(df, self.lookback_short)
        vals = []
        for i in range(10, 0, -1):
            sub = df.iloc[:-i]
            if len(sub) < self.lookback_short + 5:
                continue
            vals.append(self._price_reaction_to_volume(sub, self.lookback_short))
        if not vals:
            return False
        baseline = float(np.median(vals))
        if baseline <= 0:
            return False
        return (baseline / (r_now + 1e-9)) > self.delay_threshold

    def _market_state(self, df: pd.DataFrame, rsi_value: float) -> str:
        close = df["close"]
        drift_short = abs(self._pct_change_n(close, self.lookback_short))
        drift_state = abs(self._pct_change_n(close, self.lookback_state))
        vol = float(close.pct_change().tail(self.lookback_short).std() or 0)

        if drift_short < 0.25 and 40 <= rsi_value <= 60:
            return "STABLE"
        if drift_short >= 0.8 and rsi_value > 65:
            return "OVEREXTENDED"
        if drift_short >= 0.8 and rsi_value < 35:
            return "PANIC"
        if vol > 0.02:
            return "CHAOS"
        if drift_state > 0.5 and drift_short < 0.3:
            return "EXHAUSTION"
        return "STABLE"

    def _orderbook_imbalance(self, orderbook: Optional[Dict[str, Any]]) -> Optional[float]:
        if not orderbook or "bids" not in orderbook or "asks" not in orderbook:
            return None
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        if not bids or not asks:
            return None
        bid_vol = sum(float(b[1]) for b in bids[:self.orderbook_levels])
        ask_vol = sum(float(a[1]) for a in asks[:self.orderbook_levels])
        total = bid_vol + ask_vol
        if total == 0:
            return None
        return (bid_vol - ask_vol) / total

    # =========================
    # POMOCNICZE
    # =========================

    def _enrich_df_with_market_data(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        df_enriched = df.copy()
        if self._backtest_mode or self.dydx_collector is None:
            return df_enriched
        try:
            if "funding_rate" not in df_enriched.columns:
                funding_rates = self.dydx_collector.get_funding_rates(symbol, limit=100)
                if not funding_rates.empty:
                    funding_rates = funding_rates.set_index('timestamp')
                    df_enriched = df_enriched.join(funding_rates[['funding_rate']], how='left')
                    # Zgodnie z zasadą: używamy tylko rzeczywistych danych, nie forward fill
                    # df_enriched['funding_rate'] pozostaje z None dla brakujących wartości
            if "open_interest" not in df_enriched.columns:
                ticker = self.dydx_collector.get_ticker(symbol)
                current_oi = float(ticker.get('open_interest', 0))
                if current_oi > 0:
                    df_enriched['open_interest'] = current_oi
        except Exception as e:
            logger.debug(f"Błąd wzbogacania danych rynkowych: {e}")
        return df_enriched

    def _get_orderbook(self, symbol: str) -> Optional[Dict[str, Any]]:
        if self.dydx_collector is None:
            return None
        try:
            orderbook = self.dydx_collector.get_orderbook(symbol)
            return {'bids': orderbook.get('bids', []), 'asks': orderbook.get('asks', [])}
        except Exception as e:
            logger.debug(f"Nie udało się pobrać orderbook: {e}")
            return None

    def _get_current_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        if self.paper_trading_engine is None:
            return None
        positions = self.paper_trading_engine.get_positions(symbol)
        if not positions:
            return None
        return positions[0]

    def _is_in_cooldown(self) -> bool:
        if self.last_close_time is None:
            return False
        elapsed = (datetime.now() - self.last_close_time).total_seconds()
        return elapsed < self.cooldown_seconds

    def _check_consecutive_losses(self) -> bool:
        """Sprawdza czy jesteśmy w cooldown po serii strat."""
        if self.consecutive_losses >= self.max_consecutive_losses:
            if self.last_loss_time is not None:
                elapsed = (datetime.now() - self.last_loss_time).total_seconds()
                if elapsed < self.loss_cooldown_seconds:
                    return True
                else:
                    self.consecutive_losses = 0
        return False

    def _check_max_drawdown(self) -> bool:
        if self.paper_trading_engine is None or self.peak_balance is None:
            return False
        
        current_balance = self.paper_trading_engine.balance
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
        
        drawdown = (self.peak_balance - current_balance) / self.peak_balance * 100
        return drawdown >= self.max_drawdown_percent

    def _calculate_sl_tp_atr(self, entry_price: float, side: str, atr_value: float) -> Dict[str, float]:
        """
        V1.2 compatible: Oblicza SL/TP używając ATR.
        """
        if side == "long":
            sl_atr = entry_price - (atr_value * self.atr_sl_multiplier)
            tp_atr = entry_price + (atr_value * self.atr_tp_multiplier)
            sl_percent = (entry_price - sl_atr) / entry_price * 100
            tp_percent = (tp_atr - entry_price) / entry_price * 100
            
            if sl_percent < self.min_sl_percent:
                sl_atr = entry_price * (1 - self.min_sl_percent / 100)
            if tp_percent < self.min_tp_percent:
                tp_atr = entry_price * (1 + self.min_tp_percent / 100)
        else:  # short
            sl_atr = entry_price + (atr_value * self.atr_sl_multiplier)
            tp_atr = entry_price - (atr_value * self.atr_tp_multiplier)
            sl_percent = (sl_atr - entry_price) / entry_price * 100
            tp_percent = (entry_price - tp_atr) / entry_price * 100
            
            if sl_percent < self.min_sl_percent:
                sl_atr = entry_price * (1 + self.min_sl_percent / 100)
            if tp_percent < self.min_tp_percent:
                tp_atr = entry_price * (1 - self.min_tp_percent / 100)
        
        return {
            "stop_loss": sl_atr,
            "take_profit": tp_atr
        }

    # =========================
    # GŁÓWNA LOGIKA - ANALYZE
    # =========================

    def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD", market_ctx: Optional[Dict[str, Any]] = None) -> Optional[TradingSignal]:
        if df is None or df.empty:
            return None

        min_bars = max(self.rsi_period, self.lookback_state, self.lookback_short, self.lookback_impulse, self.trend_ema_slow) + 5
        if len(df) < min_bars:
            return None
        
        # Sprawdź max drawdown
        if self._check_max_drawdown():
            return None
        
        # Sprawdź cooldown po serii strat
        if self._check_consecutive_losses():
            return None
        
        df = self._enrich_df_with_market_data(df, symbol)
        
        if market_ctx is None:
            market_ctx = {}
        
        if 'orderbook' not in market_ctx:
            market_ctx['orderbook'] = self._get_orderbook(symbol)

        close = df["close"]
        current_price = float(close.iloc[-1])

        rsi = self._calculate_rsi(close, self.rsi_period)
        current_rsi = float(rsi.iloc[-1])

        atr = self._calculate_atr(df, self.atr_period)
        current_atr = float(atr.iloc[-1]) if not atr.empty and not pd.isna(atr.iloc[-1]) else current_price * 0.02

        volatility = self._calculate_volatility(df, self.volatility_period)
        
        # Filtrowanie volatility
        if volatility > self.max_volatility_percent:
            return None
        if volatility < self.min_volatility_percent:
            return None

        trend = self._detect_trend(df)
        state = self._market_state(df, current_rsi)

        anomalies = {
            "impulse_failure": self._impulse_failure(df),
            "asymmetric_response": self._asymmetric_response(df),
            "reaction_delay": self._reaction_delay(df),
            "energy_divergence": False,
        }
        energy_div, energy_details = self._energy_divergence(df, market_ctx)
        anomalies["energy_divergence"] = energy_div

        anomaly_count = sum(1 for v in anomalies.values() if v)

        ob_imb = self._orderbook_imbalance((market_ctx or {}).get("orderbook"))
        ob_bias = 0.0
        if ob_imb is not None and abs(ob_imb) >= self.imbalance_threshold:
            ob_bias = float(ob_imb)

        # Log state
        logger.info(
            f"[{self.name}] {symbol} state={state}, RSI={current_rsi:.1f}, "
            f"trend={trend['direction']}({trend['strength']:.2f}), volatility={volatility:.2f}%, "
            f"anomalies={anomaly_count}/4"
        )

        # Check existing position
        pos = self._get_current_position(symbol)
        if pos:
            return self._check_exit(pos, df, state, anomalies, symbol, current_atr, trend, volatility)

        if self._is_in_cooldown():
            return None

        if anomaly_count < self.min_anomalies_to_trade:
            return None

        # Determine action
        action = None
        reason = []

        # SHORT: OVEREXTENDED/EXHAUSTION (V1.2 style, bez dodatkowego filtra RSI)
        if state in ("OVEREXTENDED", "EXHAUSTION"):
            if trend['direction'] == 'up' and trend['strength'] > 0.7:
                logger.info(f"[{self.name}] Odrzucono SHORT - zbyt silny trend wzrostowy ({trend['strength']:.2f})")
                return None
            action = SignalType.SELL
            reason.append(f"state={state} + anomalies={anomaly_count}")

        # LONG: PANIC/CHAOS (V1.2 style, bez dodatkowego filtra RSI)
        if state in ("PANIC", "CHAOS"):
            if trend['direction'] == 'down' and trend['strength'] > 0.7:
                logger.info(f"[{self.name}] Odrzucono LONG - zbyt silny trend spadkowy ({trend['strength']:.2f})")
                return None
            action = SignalType.BUY
            reason.append(f"state={state} + anomalies={anomaly_count}")

        if action is None:
            imp = self._detect_impulse(df)
            if ob_bias > 0:
                action = SignalType.BUY
                reason.append("orderbook imbalance -> bids dominate")
            elif ob_bias < 0:
                action = SignalType.SELL
                reason.append("orderbook imbalance -> asks dominate")
            else:
                if imp["detected"] and imp["direction"] == "up":
                    if trend['direction'] == 'up' and trend['strength'] > 0.7:
                        return None
                    action = SignalType.SELL
                    reason.append("impulse detected -> fade (mean reversion)")
                elif imp["detected"] and imp["direction"] == "down":
                    if trend['direction'] == 'down' and trend['strength'] > 0.7:
                        return None
                    action = SignalType.BUY
                    reason.append("impulse detected -> fade (mean reversion)")
                else:
                    return None

        # Calculate confidence
        confidence = 5.0
        confidence += 1.2 * anomaly_count
        if anomalies["impulse_failure"]:
            confidence += 1.0
        if anomalies["energy_divergence"]:
            confidence += 1.0
        if ob_imb is not None and abs(ob_imb) >= self.imbalance_threshold:
            confidence += 0.8
        
        # NOWOŚĆ V1.3: Trend alignment bonus
        if (action == SignalType.BUY and trend['direction'] == 'up') or \
           (action == SignalType.SELL and trend['direction'] == 'down'):
            confidence += 0.5

        confidence = float(max(1.0, min(10.0, confidence)))

        # OPUS AI V1.3: Stały próg 8.0 jak w V1.2, ale z dodatkowym bonusem za idealny setup
        min_confidence = 8.0
        if confidence < min_confidence:
            return None

        # V1.3: Position sizing oparty na V1.2 (bez equity curve - testowane)
        position_size = self._calculate_dynamic_position_size(confidence)

        side = "long" if action == SignalType.BUY else "short"
        sltp = self._calculate_sl_tp_atr(current_price, side, current_atr)

        reason_str = (
            f"{' / '.join(reason)} | "
            f"trend={trend['direction']}({trend['strength']:.2f}) | "
            f"volatility={volatility:.2f}% | "
            f"ATR={current_atr:.2f}"
        )

        logger.info(f"🎯 [{self.name}] ENTRY {action.value.upper()} conf={confidence:.1f} kelly_size={position_size:.1f}% {reason_str}")

        return TradingSignal(
            signal_type=action,
            symbol=symbol,
            confidence=confidence,
            price=current_price,
            stop_loss=sltp["stop_loss"],
            take_profit=sltp["take_profit"],
            size_percent=position_size,
            reason=reason_str,
            strategy=self.name,
        )

    def _check_exit(
        self,
        position_info: Dict[str, Any],
        df: pd.DataFrame,
        state: str,
        anomalies: Dict[str, bool],
        symbol: str,
        current_atr: float,
        trend: Dict[str, Any],
        volatility: float
    ) -> Optional[TradingSignal]:
        pnl = float(position_info["pnl_usd"])
        seconds_open = float(position_info["seconds_open"])
        side = position_info["side"]
        current_price = float(df["close"].iloc[-1])

        # Trailing stop z ATR
        if pnl > 100:
            trailing_distance = current_atr * 1.2
            if side == "long":
                highest = position_info.get("highest_price", current_price)
                if current_price < highest - trailing_distance:
                    self.last_close_time = datetime.now()
                    self._record_trade(pnl)
                    return TradingSignal(
                        signal_type=SignalType.CLOSE,
                        symbol=symbol,
                        confidence=9.0,
                        price=current_price,
                        reason=f"TRAILING_STOP pnl={pnl:.2f}",
                        strategy=self.name
                    )
            else:
                lowest = position_info.get("lowest_price", current_price)
                if current_price > lowest + trailing_distance:
                    self.last_close_time = datetime.now()
                    self._record_trade(pnl)
                    return TradingSignal(
                        signal_type=SignalType.CLOSE,
                        symbol=symbol,
                        confidence=9.0,
                        price=current_price,
                        reason=f"TRAILING_STOP pnl={pnl:.2f}",
                        strategy=self.name
                    )

        # Anomalie zniknęły - zamknij
        anomaly_count = sum(1 for v in anomalies.values() if v)
        if anomaly_count == 0:
            self.last_close_time = datetime.now()
            self._record_trade(pnl)
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=8.5,
                price=current_price,
                reason=f"STRUCTURE_NORMALIZED pnl={pnl:.2f}",
                strategy=self.name
            )

        # Trend reversal - zamknij wcześniej
        if pnl > 30:
            if (side == "long" and trend['direction'] == 'down' and trend['strength'] > 0.6) or \
               (side == "short" and trend['direction'] == 'up' and trend['strength'] > 0.6):
                self.last_close_time = datetime.now()
                self._record_trade(pnl)
                return TradingSignal(
                    signal_type=SignalType.CLOSE,
                    symbol=symbol,
                    confidence=8.0,
                    price=current_price,
                    reason=f"TREND_REVERSAL pnl={pnl:.2f}",
                    strategy=self.name
                )

        # Time decay
        max_hold = 600 if volatility > 1.5 else 900
        if seconds_open >= max_hold and pnl < 50:
            self.last_close_time = datetime.now()
            self._record_trade(pnl)
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=8.0,
                price=current_price,
                reason=f"TIMEOUT {seconds_open:.0f}s pnl={pnl:.2f}",
                strategy=self.name
            )

        return None

    def should_close_position(
        self,
        df: pd.DataFrame,
        entry_price: float,
        side: str,
        current_pnl_percent: float
    ) -> bool:
        """Dla BacktestEngine."""
        if current_pnl_percent > 0:
            self._record_trade(current_pnl_percent * 100)
        return False
