"""
Prompt Strategy v1.2
====================
Ulepszona strategia tradingowa oparta na analizie LLM.

Ulepszenia względem v1.1:
- Automatyczne zamykanie pozycji przy progach PnL (nawet gdy LLM nie decyduje)
- Wymuszanie CLOSE gdy LLM zwraca BUY przy otwartej LONG (i odwrotnie)
- Śledzenie dużych transakcji na rynku (whale tracking)
- Bardziej agresywne zarządzanie pozycjami
- Lepsza integracja informacji o pozycjach z promptem
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import json
import os
import time
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType
from src.analysis.llm.market_analyzer import MarketAnalyzerLLM
from src.utils.api_logger import get_api_logger


class PromptStrategyV12(BaseStrategy):
    """
    Strategia tradingowa v1.2 oparta na analizie LLM z ulepszonym zarządzaniem pozycjami.
    
    Kluczowe ulepszenia względem v1.1:
    - Automatyczne CLOSE przy progach PnL (bez czekania na LLM)
    - Wymuszanie poprawnych akcji (nie BUY przy otwartym LONG)
    - Śledzenie dużych transakcji (whale tracking)
    - Bardziej agresywne progi zamykania
    """
    
    name = "PromptStrategyV12"
    description = "Ulepszona strategia LLM v1.2 z agresywnym zarządzaniem pozycjami"
    timeframe = "15min"  # Domyślnie 15min dla dynamicznego tradingu
    
    # Progi automatycznego zamykania pozycji
    AUTO_TAKE_PROFIT_PERCENT = 2.0  # Automatyczne zamknięcie przy +2%
    AUTO_STOP_LOSS_PERCENT = -1.5   # Automatyczne zamknięcie przy -1.5%
    MAX_HOLD_HOURS = 4.0            # Maksymalny czas trzymania pozycji
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        
        # Wczytaj prompt
        self.prompt_file = self.config.get('prompt_file')
        if not self.prompt_file:
            raise ValueError("prompt_file jest wymagany w konfiguracji")
        
        prompt_path = Path(self.prompt_file)
        if not prompt_path.exists():
            raise FileNotFoundError(f"Plik promptu nie istnieje: {self.prompt_file}")
        
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.prompt_template = f.read()
        
        # Konfiguracja LLM
        self.provider = self.config.get('provider', 'anthropic')
        self.model = self.config.get('model', 'claude-3-5-haiku-20241022')
        self.api_key = self.config.get('api_key')
        self.max_history_candles = self.config.get('max_history_candles', 50)
        
        # Parametry wskaźników technicznych
        self.rsi_period = self.config.get('rsi_period', 14)
        self.macd_fast = self.config.get('macd_fast', 12)
        self.macd_slow = self.config.get('macd_slow', 26)
        self.macd_signal = self.config.get('macd_signal', 9)
        self.bb_period = self.config.get('bb_period', 20)
        self.bb_std = self.config.get('bb_std', 2.0)
        self.atr_period = self.config.get('atr_period', 14)
        
        # Progi automatycznego zamykania
        self.auto_take_profit = self.config.get('auto_take_profit_percent', self.AUTO_TAKE_PROFIT_PERCENT)
        self.auto_stop_loss = self.config.get('auto_stop_loss_percent', self.AUTO_STOP_LOSS_PERCENT)
        self.max_hold_hours = self.config.get('max_hold_hours', self.MAX_HOLD_HOURS)
        
        # Trailing stop loss
        self.trailing_stop_enabled = self.config.get('trailing_stop_enabled', True)
        self.trailing_stop_atr_multiplier = self.config.get('trailing_stop_atr_multiplier', 2.0)
        self.trailing_stop_percent = self.config.get('trailing_stop_percent', 2.0)
        
        # Dynamiczny trading - agresywne parametry
        self.min_confidence_for_trade = self.config.get('min_confidence_for_trade', 6.0)
        self.force_close_on_reversal = self.config.get('force_close_on_reversal', True)
        self.max_hold_candles = self.config.get('max_hold_candles', 24)  # Max 24 świec (6h dla 15min)
        
        # Whale tracking
        self.whale_tracking_enabled = self.config.get('whale_tracking_enabled', True)
        self.whale_trade_threshold = self.config.get('whale_trade_threshold', 10.0)  # BTC
        
        # Inicjalizuj LLM
        try:
            self.llm_analyzer = MarketAnalyzerLLM(
                provider=self.provider,
                model=self.model,
                api_key=self.api_key
            )
            logger.info(f"LLM zainicjalizowany: {self.provider}/{self.model}")
        except Exception as e:
            logger.error(f"Błąd inicjalizacji LLM: {e}")
            raise
        
        # Inicjalizuj API logger
        self.api_logger = get_api_logger()
        
        # Historia i kontekst
        self.price_history: Dict[str, pd.DataFrame] = {}
        self.session_context: Dict[str, Any] = {}
        self.decision_history: List[Dict[str, Any]] = []
        self.paper_trading_engine = None
        
        # Cache dla wskaźników technicznych
        self.indicators_cache: Dict[str, Dict[str, Any]] = {}
        self.indicators_cache_time: Dict[str, datetime] = {}
        
        # Trailing stop tracking
        self.trailing_stops: Dict[str, Dict[str, float]] = {}
        
        # Whale trades cache
        self.recent_whale_trades: List[Dict[str, Any]] = []
        
        logger.info(f"Strategia {self.name} zainicjalizowana z promptem: {self.prompt_file}")
        logger.info(f"   Auto Take Profit: +{self.auto_take_profit}%")
        logger.info(f"   Auto Stop Loss: {self.auto_stop_loss}%")
        logger.info(f"   Max Hold: {self.max_hold_hours}h")
    
    def set_session_context(self, context: Dict[str, Any]):
        """Ustawia kontekst sesji."""
        self.session_context = context
        logger.debug(f"Kontekst sesji ustawiony: {context}")
    
    def set_paper_trading_engine(self, engine):
        """Ustawia referencję do paper trading engine."""
        self.paper_trading_engine = engine
        logger.debug("Paper trading engine ustawiony")
    
    def update_price_history(self, symbol: str, df: pd.DataFrame):
        """Aktualizuje historię cen dla symbolu."""
        if df is None or df.empty:
            return
        
        # Upewnij się, że timestamp jest kolumną
        if df.index.name == 'timestamp' or isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
        
        if 'timestamp' not in df.columns:
            logger.warning(f"Brak kolumny 'timestamp' w DataFrame dla {symbol}")
            return
        
        # Usuń duplikaty i ogranicz
        df = df.drop_duplicates(subset=['timestamp'], keep='last')
        df = df.sort_values('timestamp')
        
        if len(df) > self.max_history_candles:
            df = df.tail(self.max_history_candles)
        
        self.price_history[symbol] = df
    
    # ========================================
    # AUTOMATYCZNE ZARZĄDZANIE POZYCJAMI
    # ========================================
    
    def _check_auto_close_conditions(self, symbol: str, current_price: float) -> Optional[TradingSignal]:
        """
        Sprawdza czy pozycja powinna być automatycznie zamknięta.
        
        Zamyka automatycznie gdy:
        1. PnL >= auto_take_profit (domyślnie +2%)
        2. PnL <= auto_stop_loss (domyślnie -1.5%)
        3. Pozycja otwarta > max_hold_hours
        """
        if not self.paper_trading_engine:
            return None
        
        open_positions = self.paper_trading_engine.get_open_positions()
        position = next((p for p in open_positions if p.symbol == symbol), None)
        
        if not position:
            return None
        
        # Oblicz PnL
        pnl, pnl_percent = position.calculate_pnl(current_price)
        
        # Oblicz czas od otwarcia (pole w modelu to 'opened_at')
        hours_open = (datetime.now() - position.opened_at).total_seconds() / 3600
        
        # Sprawdź Take Profit
        if pnl_percent >= self.auto_take_profit:
            logger.info(f"🎯 AUTO TAKE PROFIT: {symbol} +{pnl_percent:.2f}% (próg: +{self.auto_take_profit}%)")
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=current_price,
                reason=f"AUTO TAKE PROFIT: +{pnl_percent:.2f}% >= +{self.auto_take_profit}%",
                strategy=self.name
            )
        
        # Sprawdź Stop Loss
        if pnl_percent <= self.auto_stop_loss:
            logger.info(f"🛑 AUTO STOP LOSS: {symbol} {pnl_percent:.2f}% (próg: {self.auto_stop_loss}%)")
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=current_price,
                reason=f"AUTO STOP LOSS: {pnl_percent:.2f}% <= {self.auto_stop_loss}%",
                strategy=self.name
            )
        
        # Sprawdź maksymalny czas trzymania
        if hours_open >= self.max_hold_hours and pnl_percent < 0.5:
            logger.info(f"⏰ AUTO TIMEOUT: {symbol} otwarta {hours_open:.1f}h (max: {self.max_hold_hours}h)")
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=8.0,
                price=current_price,
                reason=f"AUTO TIMEOUT: pozycja otwarta {hours_open:.1f}h z PnL {pnl_percent:+.2f}%",
                strategy=self.name
            )
        
        return None
    
    def _get_current_position_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Pobiera informacje o aktualnej pozycji."""
        if not self.paper_trading_engine:
            return None
        
        open_positions = self.paper_trading_engine.get_open_positions()
        position = next((p for p in open_positions if p.symbol == symbol), None)
        
        if not position:
            return None
        
        current_price = self.paper_trading_engine.get_current_price(symbol)
        pnl, pnl_percent = position.calculate_pnl(current_price)
        hours_open = (datetime.now() - position.opened_at).total_seconds() / 3600
        
        return {
            'side': position.side.value,  # 'long' lub 'short'
            'entry_price': position.entry_price,
            'current_price': current_price,
            'size': position.size,
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'hours_open': hours_open,
            'stop_loss': position.stop_loss,
            'take_profit': position.take_profit
        }
    
    def _validate_llm_action(self, llm_action: str, position_info: Optional[Dict]) -> str:
        """
        Waliduje akcję LLM i wymusza poprawną odpowiedź.
        
        Jeśli LLM zwraca BUY przy otwartym LONG -> wymusza CLOSE
        Jeśli LLM zwraca SELL przy otwartym SHORT -> wymusza CLOSE
        """
        if not position_info:
            # Brak pozycji - wszystkie akcje dozwolone
            return llm_action
        
        current_side = position_info['side'].upper()
        
        # Mamy pozycję - waliduj akcję
        if current_side == 'LONG' and llm_action == 'BUY':
            logger.warning(f"⚠️ LLM zwrócił BUY przy otwartym LONG - wymuszam CLOSE (PnL: {position_info['pnl_percent']:+.2f}%)")
            return 'CLOSE'
        
        if current_side == 'SHORT' and llm_action == 'SELL':
            logger.warning(f"⚠️ LLM zwrócił SELL przy otwartym SHORT - wymuszam CLOSE (PnL: {position_info['pnl_percent']:+.2f}%)")
            return 'CLOSE'
        
        # Akcja jest poprawna
        return llm_action
    
    # ========================================
    # WHALE TRACKING
    # ========================================
    
    def _fetch_whale_trades(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Pobiera duże transakcje (whale trades) z rynku.
        
        Whale trades to transakcje powyżej określonego progu (np. 10 BTC).
        """
        if not self.whale_tracking_enabled:
            return []
        
        try:
            # Pobierz ostatnie transakcje z dYdX
            if self.paper_trading_engine and hasattr(self.paper_trading_engine, 'dydx_collector'):
                dydx = self.paper_trading_engine.dydx_collector
                trades_df = dydx.get_trades(symbol, limit=100)
                
                if trades_df.empty:
                    return []
                
                # Filtruj duże transakcje
                whale_trades = []
                for _, trade in trades_df.iterrows():
                    if trade['size'] >= self.whale_trade_threshold:
                        whale_trades.append({
                            'timestamp': trade.name,  # index jest timestamp
                            'side': trade['side'],
                            'price': trade['price'],
                            'size': trade['size']
                        })
                
                self.recent_whale_trades = whale_trades[-10:]  # Ostatnie 10 whale trades
                return self.recent_whale_trades
                
        except Exception as e:
            logger.debug(f"Błąd pobierania whale trades: {e}")
        
        return []
    
    def _format_whale_trades(self, whale_trades: List[Dict[str, Any]]) -> str:
        """Formatuje whale trades dla promptu."""
        if not whale_trades:
            return "\n=== WHALE TRADES ===\nBrak dużych transakcji w ostatnim czasie"
        
        lines = ["\n=== WHALE TRADES (transakcje > 10 BTC) ==="]
        
        buy_volume = sum(t['size'] for t in whale_trades if t['side'].upper() == 'BUY')
        sell_volume = sum(t['size'] for t in whale_trades if t['side'].upper() == 'SELL')
        
        lines.append(f"📊 Wolumen BUY: {buy_volume:.2f} BTC | SELL: {sell_volume:.2f} BTC")
        
        if buy_volume > sell_volume * 1.5:
            lines.append(f"🐋 WHALE BIAS: BULLISH (kupujący dominują)")
        elif sell_volume > buy_volume * 1.5:
            lines.append(f"🐋 WHALE BIAS: BEARISH (sprzedający dominują)")
        else:
            lines.append(f"🐋 WHALE BIAS: NEUTRAL")
        
        lines.append("\nOstatnie duże transakcje:")
        for trade in whale_trades[-5:]:
            emoji = "🟢" if trade['side'].upper() == 'BUY' else "🔴"
            lines.append(f"  {emoji} {trade['side'].upper()} {trade['size']:.2f} BTC @ ${trade['price']:,.2f}")
        
        return "\n".join(lines)
    
    # ========================================
    # WSKAŹNIKI TECHNICZNE
    # ========================================
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Oblicza RSI (Relative Strength Index)."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Oblicza MACD (Moving Average Convergence Divergence)."""
        exp1 = prices.ewm(span=self.macd_fast, adjust=False).mean()
        exp2 = prices.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def _calculate_bollinger_bands(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Oblicza Bollinger Bands."""
        sma = prices.rolling(window=self.bb_period).mean()
        std = prices.rolling(window=self.bb_period).std()
        upper = sma + (self.bb_std * std)
        lower = sma - (self.bb_std * std)
        return upper, sma, lower
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Oblicza ATR (Average True Range)."""
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    def _calculate_all_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Oblicza wszystkie wskaźniki techniczne."""
        if df is None or len(df) < 30:
            return {}
        
        close = df['close']
        
        # RSI
        rsi = self._calculate_rsi(close, self.rsi_period)
        current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
        
        # MACD
        macd_line, signal_line, histogram = self._calculate_macd(close)
        current_macd = float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else 0.0
        current_signal = float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else 0.0
        current_histogram = float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else 0.0
        prev_histogram = float(histogram.iloc[-2]) if len(histogram) > 1 and not pd.isna(histogram.iloc[-2]) else 0.0
        
        # Bollinger Bands
        bb_upper, bb_mid, bb_lower = self._calculate_bollinger_bands(close)
        current_bb_upper = float(bb_upper.iloc[-1]) if not pd.isna(bb_upper.iloc[-1]) else 0.0
        current_bb_mid = float(bb_mid.iloc[-1]) if not pd.isna(bb_mid.iloc[-1]) else 0.0
        current_bb_lower = float(bb_lower.iloc[-1]) if not pd.isna(bb_lower.iloc[-1]) else 0.0
        
        # ATR
        atr = self._calculate_atr(df, self.atr_period)
        current_atr = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
        
        # SMA
        sma_20 = float(close.rolling(20).mean().iloc[-1])
        sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(df) >= 50 else sma_20
        
        # EMA
        ema_9 = float(close.ewm(span=9, adjust=False).mean().iloc[-1])
        ema_21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
        
        # Trend
        current_price = float(close.iloc[-1])
        trend = "bullish" if current_price > sma_20 and ema_9 > ema_21 else "bearish" if current_price < sma_20 and ema_9 < ema_21 else "neutral"
        
        # Zmienność
        volatility = (current_atr / current_price) * 100 if current_price > 0 else 0.0
        
        # Momentum direction
        macd_momentum = "rising" if current_histogram > prev_histogram else "falling"
        
        return {
            'rsi': round(current_rsi, 2),
            'rsi_signal': "oversold" if current_rsi < 30 else "overbought" if current_rsi > 70 else "neutral",
            'macd_line': round(current_macd, 2),
            'macd_signal': round(current_signal, 2),
            'macd_histogram': round(current_histogram, 2),
            'macd_trend': "bullish" if current_macd > current_signal else "bearish",
            'macd_momentum': macd_momentum,
            'bb_upper': round(current_bb_upper, 2),
            'bb_mid': round(current_bb_mid, 2),
            'bb_lower': round(current_bb_lower, 2),
            'bb_position': "above_upper" if current_price > current_bb_upper else "below_lower" if current_price < current_bb_lower else "inside",
            'atr': round(current_atr, 2),
            'atr_percent': round(volatility, 2),
            'sma_20': round(sma_20, 2),
            'sma_50': round(sma_50, 2),
            'ema_9': round(ema_9, 2),
            'ema_21': round(ema_21, 2),
            'trend': trend,
            'volatility': "high" if volatility > 3.0 else "low" if volatility < 1.0 else "normal"
        }
    
    # ========================================
    # FORMATOWANIE PROMPTU
    # ========================================
    
    def _format_open_positions(self, position_info: Optional[Dict[str, Any]]) -> str:
        """Formatuje informacje o otwartych pozycjach."""
        if not position_info:
            return """
=== OTWARTE POZYCJE ===
📭 Brak otwartych pozycji - możesz otworzyć nową (BUY lub SELL)!
⚡ Możliwe akcje: BUY, SELL, HOLD"""
        
        side_emoji = "📈" if position_info['side'] == 'long' else "📉"
        pnl_emoji = "🟢" if position_info['pnl'] > 0 else "🔴"
        
        # Rekomendacja na podstawie PnL
        recommendation = ""
        if position_info['pnl_percent'] >= 2.0:
            recommendation = "💡 REKOMENDACJA: CLOSE - cel zysku osiągnięty!"
        elif position_info['pnl_percent'] <= -1.5:
            recommendation = "⚠️ REKOMENDACJA: CLOSE - utnij stratę!"
        elif position_info['hours_open'] > 3:
            recommendation = f"⏰ UWAGA: Pozycja otwarta {position_info['hours_open']:.1f}h - rozważ zamknięcie"
        
        return f"""
=== OTWARTE POZYCJE ===
{side_emoji} {position_info['side'].upper()} pozycja
   Rozmiar: {position_info['size']:.6f}
   Cena wejścia: ${position_info['entry_price']:,.2f}
   Cena aktualna: ${position_info['current_price']:,.2f}
   {pnl_emoji} PnL: ${position_info['pnl']:+,.2f} ({position_info['pnl_percent']:+.2f}%)
   ⏱️ Czas otwarcia: {position_info['hours_open']:.1f}h
   
{recommendation}

⚡ Możliwe akcje: CLOSE lub HOLD
❌ NIE MOŻESZ: BUY ani SELL (masz już pozycję!)"""
    
    def _format_indicators(self, indicators: Dict[str, Any]) -> str:
        """Formatuje wskaźniki techniczne dla prompta."""
        if not indicators:
            return "\n=== WSKAŹNIKI TECHNICZNE ===\nBrak wystarczających danych do obliczenia wskaźników"
        
        lines = ["\n=== WSKAŹNIKI TECHNICZNE ==="]
        
        # RSI
        rsi = indicators.get('rsi', 50)
        rsi_signal = indicators.get('rsi_signal', 'neutral')
        rsi_emoji = "🟢" if rsi < 30 else "🔴" if rsi > 70 else "⚪"
        lines.append(f"\n📊 RSI({self.rsi_period}): {rsi} {rsi_emoji} [{rsi_signal.upper()}]")
        
        # MACD
        macd_line = indicators.get('macd_line', 0)
        macd_signal = indicators.get('macd_signal', 0)
        macd_hist = indicators.get('macd_histogram', 0)
        macd_trend = indicators.get('macd_trend', 'neutral')
        macd_momentum = indicators.get('macd_momentum', 'neutral')
        macd_emoji = "🟢" if macd_trend == "bullish" else "🔴"
        lines.append(f"📈 MACD: {macd_line} | Signal: {macd_signal} | Histogram: {macd_hist} {macd_emoji}")
        lines.append(f"   Momentum: {macd_momentum.upper()}")
        
        # Bollinger Bands
        bb_upper = indicators.get('bb_upper', 0)
        bb_mid = indicators.get('bb_mid', 0)
        bb_lower = indicators.get('bb_lower', 0)
        bb_pos = indicators.get('bb_position', 'inside')
        bb_emoji = "🔴" if bb_pos == "above_upper" else "🟢" if bb_pos == "below_lower" else "⚪"
        lines.append(f"📏 Bollinger Bands: Upper: ${bb_upper:,.2f} | Mid: ${bb_mid:,.2f} | Lower: ${bb_lower:,.2f}")
        lines.append(f"   Pozycja ceny: {bb_pos.upper()} {bb_emoji}")
        
        # ATR i zmienność
        atr = indicators.get('atr', 0)
        atr_pct = indicators.get('atr_percent', 0)
        vol = indicators.get('volatility', 'normal')
        vol_emoji = "🔥" if vol == "high" else "❄️" if vol == "low" else "⚖️"
        lines.append(f"📉 ATR({self.atr_period}): ${atr:,.2f} ({atr_pct:.2f}%) - Zmienność: {vol.upper()} {vol_emoji}")
        
        # Trend
        trend = indicators.get('trend', 'neutral')
        trend_emoji = "📈" if trend == "bullish" else "📉" if trend == "bearish" else "➡️"
        sma_20 = indicators.get('sma_20', 0)
        ema_9 = indicators.get('ema_9', 0)
        ema_21 = indicators.get('ema_21', 0)
        lines.append(f"\n🎯 TREND: {trend.upper()} {trend_emoji}")
        lines.append(f"   SMA(20): ${sma_20:,.2f} | EMA(9): ${ema_9:,.2f} | EMA(21): ${ema_21:,.2f}")
        
        return "\n".join(lines)
    
    def _format_price_history(self, symbol: str) -> str:
        """Formatuje historię cen do tekstu dla LLM."""
        if symbol not in self.price_history or self.price_history[symbol].empty:
            return "Brak danych historycznych"
        
        df = self.price_history[symbol]
        
        lines = [f"\n=== HISTORIA CEN {symbol} (ostatnie 15 świec) ==="]
        lines.append(f"{'Timestamp':<20} {'Open':<12} {'High':<12} {'Low':<12} {'Close':<12} {'Volume':<10}")
        lines.append("-" * 80)
        
        # Pokaż ostatnie 15 świec
        display_df = df.tail(15)
        
        for _, row in display_df.iterrows():
            timestamp = str(row.get('timestamp', ''))[:16]
            lines.append(f"{timestamp:<20} {row.get('open', 0):>11.2f} {row.get('high', 0):>11.2f} {row.get('low', 0):>11.2f} {row.get('close', 0):>11.2f} {row.get('volume', 0):>9.0f}")
        
        # Statystyki
        current_price = float(df['close'].iloc[-1])
        price_start = float(df['close'].iloc[0])
        change = ((current_price - price_start) / price_start) * 100
        
        lines.append(f"\n📊 Statystyki:")
        lines.append(f"   Cena aktualna: ${current_price:,.2f}")
        lines.append(f"   Zmiana w okresie: {change:+.2f}%")
        lines.append(f"   Min: ${float(df['low'].min()):,.2f}")
        lines.append(f"   Max: ${float(df['high'].max()):,.2f}")
        
        return "\n".join(lines)
    
    def _format_decision_history(self) -> str:
        """Formatuje historię decyzji."""
        if not self.decision_history:
            return "\n=== HISTORIA DECYZJI ===\nBrak poprzednich decyzji w tej sesji"
        
        lines = ["\n=== HISTORIA DECYZJI (ostatnie 10) ==="]
        
        for decision in self.decision_history[-10:]:
            action = decision.get('action', 'N/A')
            price = decision.get('price', 0)
            conf = decision.get('confidence', 0)
            reason = decision.get('reason', '')[:50]
            timestamp = decision.get('timestamp', '')[:16]
            
            emoji = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "🔚" if action == "CLOSE" else "⏸️"
            lines.append(f"{emoji} {timestamp} | {action} @ ${price:,.2f} | Conf: {conf}/10 | {reason}")
        
        return "\n".join(lines)
    
    def _build_prompt(self, symbol: str, current_price: float, indicators: Dict[str, Any], 
                      position_info: Optional[Dict[str, Any]], whale_trades: List[Dict[str, Any]]) -> str:
        """Buduje pełny prompt dla LLM."""
        # Kontekst sesji
        context_text = f"""
=== KONTEKST SESJI ===
💰 Kapitał: ${self.session_context.get('balance', 0):,.2f}
⏱️ Limit czasu: {self.session_context.get('time_limit', 'N/A')}
🛑 Max strata: ${self.session_context.get('max_loss', 0):,.2f}
📝 Tryb: {self.session_context.get('mode', 'paper').upper()}
"""
        
        # Otwarte pozycje
        positions_text = self._format_open_positions(position_info)
        
        # Wskaźniki techniczne
        indicators_text = self._format_indicators(indicators)
        
        # Whale trades
        whale_text = self._format_whale_trades(whale_trades)
        
        # Historia cen
        price_history_text = self._format_price_history(symbol)
        
        # Historia decyzji
        decision_history_text = self._format_decision_history()
        
        # Możliwe akcje
        if position_info:
            possible_actions = '"CLOSE" | "HOLD"'
            action_note = f"UWAGA: Masz otwartą pozycję {position_info['side'].upper()} - możesz tylko CLOSE lub HOLD!"
        else:
            possible_actions = '"BUY" | "SELL" | "HOLD"'
            action_note = "Brak pozycji - możesz otworzyć nową (BUY/SELL) lub czekać (HOLD)"
        
        # Pełny prompt
        full_prompt = f"""{self.prompt_template}

{context_text}

{positions_text}

{indicators_text}

{whale_text}

{price_history_text}

{decision_history_text}

=== AKTUALNA SYTUACJA ===
Symbol: {symbol}
Cena aktualna: ${current_price:,.2f}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

=== FORMAT ODPOWIEDZI ===
{action_note}

Odpowiedz TYLKO w formacie JSON:
{{
    "action": {possible_actions},
    "confidence": 0.0-10.0,
    "price": {current_price},
    "stop_loss": <cena stop loss lub null>,
    "take_profit": <cena take profit lub null>,
    "size_percent": <procent kapitału 15-20>,
    "trailing_stop_percent": <opcjonalnie: trailing stop w % lub null>,
    "observations": "<szczegółowa analiza wskaźników i rynku>",
    "reason": "<krótkie uzasadnienie decyzji>"
}}

KRYTYCZNE ZASADY:
- Jeśli masz OTWARTĄ POZYCJĘ - zdecyduj CLOSE lub HOLD (NIE BUY/SELL!)
- CLOSE gdy PnL >= +2% lub PnL <= -1.5%
- Confidence >= 6 dla otwarcia nowej pozycji
- Zawsze ustaw stop_loss i take_profit dla nowych pozycji
"""
        
        return full_prompt
    
    def _parse_llm_response(self, response: str, symbol: str, current_price: float, 
                            position_info: Optional[Dict[str, Any]]) -> Optional[TradingSignal]:
        """Parsuje odpowiedź LLM i tworzy sygnał tradingowy."""
        try:
            # Wyciągnij JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.error(f"Nie znaleziono JSON w odpowiedzi LLM")
                return None
            
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            # Pobierz akcję i waliduj
            action_str = data.get('action', 'HOLD').upper()
            validated_action = self._validate_llm_action(action_str, position_info)
            
            if validated_action != action_str:
                logger.info(f"🔄 Akcja skorygowana: {action_str} → {validated_action}")
                data['action'] = validated_action
                data['reason'] = f"[AUTO-KOREKTA] {data.get('reason', '')}"
            
            # Mapuj action na SignalType
            action_map = {
                'BUY': SignalType.BUY,
                'SELL': SignalType.SELL,
                'HOLD': SignalType.HOLD,
                'CLOSE': SignalType.CLOSE
            }
            
            signal_type = action_map.get(validated_action, SignalType.HOLD)
            
            # Wyświetl decyzję
            self._display_decision(data, symbol, current_price, position_info)
            
            # Dla HOLD nie generuj sygnału
            if signal_type == SignalType.HOLD:
                logger.info(f"LLM zdecydował: HOLD - brak sygnału")
                return None
            
            # Utwórz sygnał
            signal = TradingSignal(
                signal_type=signal_type,
                symbol=symbol,
                confidence=float(data.get('confidence', 5.0)),
                price=float(data.get('price', current_price)),
                stop_loss=float(data.get('stop_loss')) if data.get('stop_loss') else None,
                take_profit=float(data.get('take_profit')) if data.get('take_profit') else None,
                size_percent=float(data.get('size_percent', 15.0)),
                reason=data.get('reason', 'Decyzja LLM'),
                strategy=self.name,
                observations=data.get('observations', '')
            )
            
            # Zapisz trailing stop jeśli podany
            if data.get('trailing_stop_percent'):
                self.trailing_stops[symbol] = {
                    'percent': float(data.get('trailing_stop_percent')),
                    'high_water_mark': current_price if signal_type == SignalType.BUY else None,
                    'low_water_mark': current_price if signal_type == SignalType.SELL else None
                }
            
            return signal
            
        except json.JSONDecodeError as e:
            logger.error(f"Błąd parsowania JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Błąd parsowania odpowiedzi: {e}")
            return None
    
    def _display_decision(self, data: Dict[str, Any], symbol: str, current_price: float,
                          position_info: Optional[Dict[str, Any]]):
        """Wyświetla decyzję LLM."""
        action = data.get('action', 'HOLD')
        emoji_map = {
            'BUY': '🟢 KUPNO (LONG)',
            'SELL': '🔴 SPRZEDAŻ (SHORT)',
            'HOLD': '⏸️ CZEKANIE',
            'CLOSE': '🔚 ZAMKNIĘCIE'
        }
        
        logger.info("")
        logger.info("=" * 70)
        logger.info(f"🤖 DECYZJA LLM v1.2 dla {symbol}: {emoji_map.get(action, action)}")
        logger.info("=" * 70)
        logger.info(f"Pewność: {data.get('confidence', 0)}/10")
        logger.info(f"Cena: ${current_price:,.2f}")
        
        if position_info:
            logger.info(f"Pozycja: {position_info['side'].upper()} | PnL: {position_info['pnl_percent']:+.2f}%")
        
        if data.get('stop_loss'):
            logger.info(f"Stop Loss: ${data.get('stop_loss'):,.2f}")
        if data.get('take_profit'):
            logger.info(f"Take Profit: ${data.get('take_profit'):,.2f}")
        if data.get('size_percent'):
            logger.info(f"Rozmiar: {data.get('size_percent')}% kapitału")
        
        if data.get('reason'):
            logger.info(f"\n📋 Uzasadnienie: {data.get('reason')}")
        
        if data.get('observations'):
            logger.info(f"\n🔍 Obserwacje: {data.get('observations')[:200]}...")
        
        logger.info("=" * 70)
    
    def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD") -> Optional[TradingSignal]:
        """
        Analizuje dane rynkowe używając LLM z ulepszoną logiką.
        
        1. Najpierw sprawdza automatyczne warunki zamknięcia (PnL, timeout)
        2. Pobiera informacje o aktualnej pozycji
        3. Pobiera whale trades
        4. Wysyła prompt do LLM
        5. Waliduje odpowiedź LLM
        """
        if df is None or df.empty:
            logger.warning(f"Brak danych dla {symbol}")
            return None
        
        # Zapisz symbol
        self._current_symbol = symbol
        
        # Aktualizuj historię
        self.update_price_history(symbol, df)
        
        # Pobierz aktualną cenę
        current_price = float(df['close'].iloc[-1])
        
        # 1. SPRAWDŹ AUTOMATYCZNE ZAMKNIĘCIE
        auto_close_signal = self._check_auto_close_conditions(symbol, current_price)
        if auto_close_signal:
            # Zapisz decyzję w historii
            self.decision_history.append({
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'action': 'CLOSE',
                'price': current_price,
                'confidence': 10.0,
                'reason': auto_close_signal.reason
            })
            return auto_close_signal
        
        # 2. POBIERZ INFORMACJE O POZYCJI
        position_info = self._get_current_position_info(symbol)
        
        # 3. OBLICZ WSKAŹNIKI
        indicators = self._calculate_all_indicators(df)
        
        # 4. POBIERZ WHALE TRADES
        whale_trades = self._fetch_whale_trades(symbol)
        
        # 5. ZBUDUJ PROMPT
        prompt = self._build_prompt(symbol, current_price, indicators, position_info, whale_trades)
        
        # 6. WYŚLIJ DO LLM
        try:
            from langchain.schema import HumanMessage, SystemMessage
            
            system_message = """Jesteś AGRESYWNYM traderem kryptowalut. Podejmujesz SZYBKIE i ZDECYDOWANE decyzje.

KRYTYCZNE ZASADY:
1. Jeśli masz OTWARTĄ POZYCJĘ - możesz tylko CLOSE lub HOLD (NIE BUY/SELL!)
2. CLOSE gdy zysk >= +2% lub strata >= -1.5%
3. Jeśli NIE masz pozycji - szukaj okazji (BUY/SELL przy dobrych sygnałach)
4. ZAWSZE ustaw stop loss i take profit dla nowych pozycji
5. Confidence >= 6 dla otwarcia pozycji

Odpowiadaj TYLKO w formacie JSON."""
            
            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=prompt)
            ]
            
            # Log request
            messages_for_log = [{"role": "system", "content": system_message}, {"role": "human", "content": prompt}]
            self.api_logger.log_request(
                provider=self.provider,
                model=self.model,
                messages=messages_for_log,
                temperature=0.3,
                max_tokens=2048,
                metadata={"method": "analyze", "strategy": self.name, "symbol": symbol}
            )
            
            # Wykonaj request
            start_time = time.time()
            response = self.llm_analyzer.llm.invoke(messages)
            response_time_ms = (time.time() - start_time) * 1000
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Log response
            input_tokens = None
            output_tokens = None
            if hasattr(response, 'response_metadata'):
                usage = response.response_metadata.get('usage', {}) if response.response_metadata else {}
                input_tokens = usage.get('input_tokens')
                output_tokens = usage.get('output_tokens')
            
            self.api_logger.log_response(
                provider=self.provider,
                model=self.model,
                response_text=response_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                response_time_ms=response_time_ms,
                metadata={"method": "analyze", "strategy": self.name, "symbol": symbol}
            )
            
            # Parsuj odpowiedź z walidacją
            signal = self._parse_llm_response(response_text, symbol, current_price, position_info)
            
            # Zapisz decyzję w historii
            if signal:
                decision = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': symbol,
                    'action': signal.signal_type.value.upper(),
                    'price': signal.price,
                    'confidence': signal.confidence,
                    'stop_loss': signal.stop_loss,
                    'take_profit': signal.take_profit,
                    'reason': signal.reason
                }
                self.decision_history.append(decision)
            
            return signal
            
        except Exception as e:
            logger.error(f"Błąd analizy LLM: {e}")
            return None
    
    def should_close_position(
        self,
        df: pd.DataFrame,
        entry_price: float,
        side: str,
        current_pnl_percent: float
    ) -> Optional[TradingSignal]:
        """Sprawdza czy pozycja powinna zostać zamknięta (trailing stop)."""
        if df is None or df.empty:
            return None
        
        symbol = getattr(self, '_current_symbol', 'BTC-USD')
        current_price = float(df['close'].iloc[-1])
        
        # Automatyczne progi
        if current_pnl_percent >= self.auto_take_profit:
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=current_price,
                reason=f"Auto Take Profit: +{current_pnl_percent:.2f}%",
                strategy=self.name
            )
        
        if current_pnl_percent <= self.auto_stop_loss:
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=current_price,
                reason=f"Auto Stop Loss: {current_pnl_percent:.2f}%",
                strategy=self.name
            )
        
        # Trailing stop
        if self.trailing_stop_enabled and symbol in self.trailing_stops:
            ts = self.trailing_stops[symbol]
            
            if side.lower() == 'long' and ts.get('high_water_mark'):
                # Aktualizuj high water mark
                if current_price > ts['high_water_mark']:
                    ts['high_water_mark'] = current_price
                
                # Sprawdź trailing stop
                stop_price = ts['high_water_mark'] * (1 - ts['percent'] / 100)
                if current_price <= stop_price:
                    del self.trailing_stops[symbol]
                    return TradingSignal(
                        signal_type=SignalType.CLOSE,
                        symbol=symbol,
                        confidence=10.0,
                        price=current_price,
                        reason=f"Trailing stop ({ts['percent']}% od max ${ts['high_water_mark']:,.2f})",
                        strategy=self.name
                    )
            
            elif side.lower() == 'short' and ts.get('low_water_mark'):
                # Aktualizuj low water mark
                if current_price < ts['low_water_mark']:
                    ts['low_water_mark'] = current_price
                
                # Sprawdź trailing stop
                stop_price = ts['low_water_mark'] * (1 + ts['percent'] / 100)
                if current_price >= stop_price:
                    del self.trailing_stops[symbol]
                    return TradingSignal(
                        signal_type=SignalType.CLOSE,
                        symbol=symbol,
                        confidence=10.0,
                        price=current_price,
                        reason=f"Trailing stop ({ts['percent']}% od min ${ts['low_water_mark']:,.2f})",
                        strategy=self.name
                    )
        
        return None

