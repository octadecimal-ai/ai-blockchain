from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType
from src.collectors.exchange.dydx_collector import DydxCollector


class UnderhumanStrategyV11(BaseStrategy):
    """
    UNDERHUMAN STRATEGY v1.1 - Ulepszona wersja z:
    - ATR-based dynamic SL/TP
    - Trend filtering (nie handluj przeciwko silnym trendom)
    - Trailing stop loss
    - Wyższy próg pewności
    - Ochrona przed max drawdown
    """

    name = "UnderhumanStrategyV11"
    description = "Strategia zmiany stanu rynku + anomalie (UNDERHUMAN v1.1)"
    timeframe = "5min"

    def __init__(self, config: dict = None):
        super().__init__(config)

        # === RSI tylko jako czujnik przegrzania ===
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

        # Reaction delay
        self.delay_threshold = self.config.get("delay_threshold", 1.35)

        # Money/risk - ULEPSZONE
        self.target_profit_usd_min = self.config.get("target_profit_usd_min", 400.0)
        self.target_profit_usd_max = self.config.get("target_profit_usd_max", 1000.0)
        self.max_loss_usd = self.config.get("max_loss_usd", 500.0)

        self.max_hold_seconds = self.config.get("max_hold_seconds", 900)
        self.cooldown_seconds = self.config.get("cooldown_seconds", 120)

        self.slippage_percent = self.config.get("slippage_percent", 0.1)
        # WYŻSZY próg pewności (było 7.0, teraz 8.0)
        self.min_confidence_for_trade = self.config.get("min_confidence_for_trade", 8.0)

        self.position_size_btc = self.config.get("position_size_btc", 0.1)
        self.last_close_time: Optional[datetime] = None
        self.paper_trading_engine = None
        
        # NOWE: ATR dla dynamicznego SL/TP
        self.atr_period = self.config.get("atr_period", 14)
        self.atr_sl_multiplier = self.config.get("atr_sl_multiplier", 2.0)  # SL = entry ± (ATR * 2.0)
        self.atr_tp_multiplier = self.config.get("atr_tp_multiplier", 3.0)  # TP = entry ± (ATR * 3.0)
        self.min_sl_percent = self.config.get("min_sl_percent", 2.0)  # Minimalny SL 2%
        self.min_tp_percent = self.config.get("min_tp_percent", 3.0)  # Minimalny TP 3%
        
        # NOWE: Trend filtering
        self.trend_ema_fast = self.config.get("trend_ema_fast", 20)
        self.trend_ema_slow = self.config.get("trend_ema_slow", 50)
        self.trend_strength_threshold = self.config.get("trend_strength_threshold", 0.5)  # 0.5% różnicy
        
        # NOWE: Trailing stop
        self.trailing_stop_activation_pnl = self.config.get("trailing_stop_activation_pnl", 200.0)  # Aktywuj przy $200 zysku
        self.trailing_stop_atr_multiplier = self.config.get("trailing_stop_atr_multiplier", 1.5)
        
        # NOWE: Max drawdown protection
        self.max_drawdown_percent = self.config.get("max_drawdown_percent", 20.0)  # Zatrzymaj handel przy 20% drawdown
        self.initial_balance = None
        self.peak_balance = None
        
        # Tryb backtestingu
        self._backtest_mode = self.config.get("_backtest_mode", False)
        
        if not self._backtest_mode:
            try:
                self.dydx_collector = DydxCollector(testnet=False)
                logger.info("DydxCollector zainicjalizowany dla UNDERHUMAN v1.1")
            except Exception as e:
                logger.warning(f"Nie udało się zainicjalizować DydxCollector: {e}")
                self.dydx_collector = None
        else:
            self.dydx_collector = None
            logger.info("Tryb backtestingu - pomijam inicjalizację DydxCollector")

        logger.info(f"Strategia {self.name} zainicjalizowana (UNDERHUMAN v1.1).")

    def set_paper_trading_engine(self, engine):
        self.paper_trading_engine = engine
        if engine and hasattr(engine, 'balance'):
            self.initial_balance = engine.balance
            self.peak_balance = engine.balance

    # =========================
    # INDICATORS / FEATURES
    # =========================

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Oblicza ATR (Average True Range) dla dynamicznego SL/TP."""
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def _detect_trend(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Wykrywa trend używając EMA.
        
        Returns:
            {
                'direction': 'up' | 'down' | 'sideways',
                'strength': float (0-1),
                'ema_fast': float,
                'ema_slow': float
            }
        """
        if len(df) < self.trend_ema_slow:
            return {'direction': 'sideways', 'strength': 0.0, 'ema_fast': 0.0, 'ema_slow': 0.0}
        
        close = df['close']
        ema_fast = close.ewm(span=self.trend_ema_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.trend_ema_slow, adjust=False).mean()
        
        current_fast = float(ema_fast.iloc[-1])
        current_slow = float(ema_slow.iloc[-1])
        current_price = float(close.iloc[-1])
        
        # Różnica procentowa między EMA
        diff_pct = abs(current_fast - current_slow) / current_slow * 100
        
        if diff_pct < self.trend_strength_threshold:
            return {'direction': 'sideways', 'strength': diff_pct / self.trend_strength_threshold, 
                   'ema_fast': current_fast, 'ema_slow': current_slow}
        
        if current_fast > current_slow:
            strength = min(1.0, diff_pct / (self.trend_strength_threshold * 2))
            return {'direction': 'up', 'strength': strength, 'ema_fast': current_fast, 'ema_slow': current_slow}
        else:
            strength = min(1.0, diff_pct / (self.trend_strength_threshold * 2))
            return {'direction': 'down', 'strength': strength, 'ema_fast': current_fast, 'ema_slow': current_slow}

    def _check_max_drawdown(self) -> bool:
        """Sprawdza czy przekroczono max drawdown."""
        if self.paper_trading_engine is None or self.peak_balance is None:
            return False
        
        current_balance = self.paper_trading_engine.balance
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
        
        drawdown = (self.peak_balance - current_balance) / self.peak_balance * 100
        return drawdown >= self.max_drawdown_percent

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
            logger.warning(f"Błąd wzbogacania danych rynkowych: {e}")
        return df_enriched

    def _get_orderbook(self, symbol: str) -> Optional[Dict[str, Any]]:
        if self.dydx_collector is None:
            return None
        try:
            orderbook = self.dydx_collector.get_orderbook(symbol)
            return {'bids': orderbook.get('bids', []), 'asks': orderbook.get('asks', [])}
        except Exception as e:
            logger.warning(f"Nie udało się pobrać orderbook: {e}")
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

    def _calculate_sl_tp(self, entry_price: float, side: str, size_btc: float, confidence: float) -> Dict[str, float]:
        """
        ULEPSZONA: Oblicza SL/TP używając ATR zamiast stałych procentów.
        """
        # To będzie nadpisane przez ATR w analyze()
        return {
            "stop_loss": entry_price * (0.98 if side == "long" else 1.02),
            "take_profit": entry_price * (1.03 if side == "long" else 0.97)
        }

    def _calculate_sl_tp_atr(self, entry_price: float, side: str, atr_value: float) -> Dict[str, float]:
        """
        NOWA: Oblicza SL/TP używając ATR.
        """
        if side == "long":
            sl_atr = entry_price - (atr_value * self.atr_sl_multiplier)
            tp_atr = entry_price + (atr_value * self.atr_tp_multiplier)
            sl_percent = (entry_price - sl_atr) / entry_price * 100
            tp_percent = (tp_atr - entry_price) / entry_price * 100
            
            # Upewnij się że SL/TP są nie mniejsze niż minimum
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

    def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD", market_ctx: Optional[Dict[str, Any]] = None) -> Optional[TradingSignal]:
        if df is None or df.empty:
            return None

        min_bars = max(self.rsi_period, self.lookback_state, self.lookback_short, self.lookback_impulse, self.trend_ema_slow) + 5
        if len(df) < min_bars:
            return None
        
        # NOWE: Sprawdź max drawdown
        if self._check_max_drawdown():
            logger.warning(f"[{self.name}] Max drawdown przekroczony - zatrzymuję handel")
            return None
        
        df = self._enrich_df_with_market_data(df, symbol)
        
        if market_ctx is None:
            market_ctx = {}
        
        if 'orderbook' not in market_ctx:
            market_ctx['orderbook'] = self._get_orderbook(symbol)
        
        try:
            if self.dydx_collector:
                ticker_data = self.dydx_collector.get_ticker(symbol)
                market_ctx['open_interest'] = float(ticker_data.get('open_interest', 0))
                funding_rates = self.dydx_collector.get_funding_rates(symbol, limit=1)
                if not funding_rates.empty:
                    market_ctx['funding_rate'] = float(funding_rates['funding_rate'].iloc[-1])
        except Exception as e:
            logger.debug(f"Nie udało się pobrać aktualnych danych rynkowych: {e}")

        close = df["close"]
        current_price = float(close.iloc[-1])

        rsi = self._calculate_rsi(close, self.rsi_period)
        current_rsi = float(rsi.iloc[-1])

        # NOWE: Oblicz ATR
        atr = self._calculate_atr(df, self.atr_period)
        current_atr = float(atr.iloc[-1]) if not atr.empty and not pd.isna(atr.iloc[-1]) else current_price * 0.02

        # NOWE: Wykryj trend
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
        if ob_imb is not None:
            if abs(ob_imb) >= self.imbalance_threshold:
                ob_bias = float(ob_imb)

        anomalies_str = ", ".join([f"{k}={v}" for k, v in anomalies.items()])
        ob_imb_str = f"{ob_imb:.3f}" if ob_imb is not None else "None"
        logger.info(
            f"[{self.name}] {symbol} state={state}, RSI={current_rsi:.1f}, "
            f"trend={trend['direction']}({trend['strength']:.2f}), "
            f"anomalies={anomaly_count}/{len(anomalies)} ({anomalies_str}), ob_imb={ob_imb_str}"
        )

        pos = self._get_current_position(symbol)
        if pos:
            return self._check_exit(pos, df, state, anomalies, symbol, current_atr, trend)

        if self._is_in_cooldown():
            return None

        if anomaly_count < self.min_anomalies_to_trade:
            return None

        # NOWE: Filtrowanie trendu - nie handluj przeciwko silnym trendom
        action = None
        reason = []

        # SHORT: OVEREXTENDED/EXHAUSTION
        if state in ("OVEREXTENDED", "EXHAUSTION"):
            # NOWE: Sprawdź czy trend nie jest zbyt silny w górę
            if trend['direction'] == 'up' and trend['strength'] > 0.7:
                logger.info(f"[{self.name}] Odrzucono SHORT - zbyt silny trend wzrostowy ({trend['strength']:.2f})")
                return None
            action = SignalType.SELL
            reason.append(f"state={state} + anomalies={anomaly_count}")

        # LONG: PANIC/CHAOS/EXHAUSTION
        if state in ("PANIC", "CHAOS"):
            # NOWE: Sprawdź czy trend nie jest zbyt silny w dół
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
                    # NOWE: Sprawdź trend przed SHORT
                    if trend['direction'] == 'up' and trend['strength'] > 0.7:
                        return None
                    action = SignalType.SELL
                    reason.append("impulse detected -> fade (mean reversion)")
                elif imp["detected"] and imp["direction"] == "down":
                    # NOWE: Sprawdź trend przed LONG
                    if trend['direction'] == 'down' and trend['strength'] > 0.7:
                        return None
                    action = SignalType.BUY
                    reason.append("impulse detected -> fade (mean reversion)")
                else:
                    return None

        confidence = 5.0
        confidence += 1.2 * anomaly_count
        if anomalies["impulse_failure"]:
            confidence += 1.0
        if anomalies["energy_divergence"]:
            confidence += 1.0
        if ob_imb is not None and abs(ob_imb) >= self.imbalance_threshold:
            confidence += 0.8

        if action == SignalType.SELL and current_rsi > 60:
            confidence += 0.4
        if action == SignalType.BUY and current_rsi < 40:
            confidence += 0.4

        # NOWE: Bonus za zgodność z trendem
        if action == SignalType.BUY and trend['direction'] == 'up':
            confidence += 0.5
        elif action == SignalType.SELL and trend['direction'] == 'down':
            confidence += 0.5
        # Kary za handel przeciwko trendowi
        elif action == SignalType.BUY and trend['direction'] == 'down' and trend['strength'] > 0.5:
            confidence -= 1.0
        elif action == SignalType.SELL and trend['direction'] == 'up' and trend['strength'] > 0.5:
            confidence -= 1.0

        confidence = float(max(1.0, min(10.0, confidence)))
        if confidence < self.min_confidence_for_trade:
            return None

        side = "long" if action == SignalType.BUY else "short"
        # NOWE: Użyj ATR do SL/TP
        sltp = self._calculate_sl_tp_atr(current_price, side, current_atr)

        reason_str = (
            f"{' / '.join(reason)} | "
            f"anom={anomalies} | "
            f"trend={trend['direction']}({trend['strength']:.2f}) | "
            f"ATR={current_atr:.2f} | "
            f"RSI={current_rsi:.1f} | "
            f"ob_imb={None if ob_imb is None else round(ob_imb, 3)}"
        )

        logger.info(f"🎯 [{self.name}] ENTRY {action.value.upper()} conf={confidence:.1f} {reason_str}")

        return TradingSignal(
            signal_type=action,
            symbol=symbol,
            confidence=confidence,
            price=current_price,
            stop_loss=sltp["stop_loss"],
            take_profit=sltp["take_profit"],
            size_percent=15.0,
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
        trend: Dict[str, Any]
    ) -> Optional[TradingSignal]:
        pnl = float(position_info["pnl_usd"])
        seconds_open = float(position_info["seconds_open"])
        side = position_info["side"]
        entry_price = float(position_info.get("entry_price", 0))
        current_price = float(df["close"].iloc[-1])

        # NOWE: Trailing stop loss
        if pnl >= self.trailing_stop_activation_pnl:
            if side == "long":
                trailing_stop = current_price - (current_atr * self.trailing_stop_atr_multiplier)
                if current_price <= trailing_stop:
                    self.last_close_time = datetime.now()
                    return TradingSignal(
                        signal_type=SignalType.CLOSE,
                        symbol=symbol,
                        confidence=10.0,
                        price=current_price,
                        reason=f"TRAILING STOP hit pnl={pnl:.2f}",
                        strategy=self.name
                    )
            else:  # short
                trailing_stop = current_price + (current_atr * self.trailing_stop_atr_multiplier)
                if current_price >= trailing_stop:
                    self.last_close_time = datetime.now()
                    return TradingSignal(
                        signal_type=SignalType.CLOSE,
                        symbol=symbol,
                        confidence=10.0,
                        price=current_price,
                        reason=f"TRAILING STOP hit pnl={pnl:.2f}",
                        strategy=self.name
                    )

        if pnl <= -self.max_loss_usd:
            self.last_close_time = datetime.now()
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=current_price,
                reason=f"STOP LOSS hit pnl={pnl:.2f}",
                strategy=self.name
            )

        anomaly_count = sum(1 for v in anomalies.values() if v)
        if anomaly_count == 0:
            self.last_close_time = datetime.now()
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=8.5,
                price=current_price,
                reason=f"STRUCTURE NORMALIZED (anomalies vanished) pnl={pnl:.2f}",
                strategy=self.name
            )

        if seconds_open >= self.max_hold_seconds and pnl < 0.3 * self.target_profit_usd_max:
            self.last_close_time = datetime.now()
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=8.0,
                price=current_price,
                reason=f"TIMEOUT {seconds_open:.0f}s pnl={pnl:.2f} state={state}",
                strategy=self.name
            )

        return None

