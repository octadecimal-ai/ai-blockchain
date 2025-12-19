"""
Prompt Strategy v1.1
====================
Ulepszona strategia tradingowa oparta na analizie LLM.

Ulepszenia względem v1.0:
- Dodanie informacji o aktualnych pozycjach do prompta
- Obliczanie i przekazywanie wskaźników technicznych (RSI, MACD, Bollinger Bands)
- Trailing stop loss na podstawie ATR
- Agresywniejsze zarządzanie pozycjami
- Optymalizacja dla dynamicznego tradingu (częste transakcje)
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


class PromptStrategyV11(BaseStrategy):
    """
    Strategia tradingowa v1.1 oparta na analizie LLM z ulepszoną analityką.
    
    Kluczowe ulepszenia:
    - Informacja o otwartych pozycjach w promptcie
    - Wskaźniki techniczne (RSI, MACD, Bollinger Bands, ATR)
    - Trailing stop loss
    - Dynamiczne zarządzanie ryzykiem
    """
    
    name = "PromptStrategyV11"
    description = "Ulepszona strategia LLM v1.1 z wskaźnikami technicznymi i trailing stop"
    timeframe = "15min"  # Domyślnie 15min dla dynamicznego tradingu
    
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
        
        # Trailing stop loss
        self.trailing_stop_enabled = self.config.get('trailing_stop_enabled', True)
        self.trailing_stop_atr_multiplier = self.config.get('trailing_stop_atr_multiplier', 2.0)
        self.trailing_stop_percent = self.config.get('trailing_stop_percent', 3.0)  # 3% trailing stop
        
        # Dynamiczny trading - agresywne parametry
        self.min_confidence_for_trade = self.config.get('min_confidence_for_trade', 5.0)
        self.force_close_on_reversal = self.config.get('force_close_on_reversal', True)
        self.max_hold_candles = self.config.get('max_hold_candles', 48)  # Max 48 świec (12h dla 15min)
        
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
        
        logger.info(f"Strategia {self.name} zainicjalizowana z promptem: {self.prompt_file}")
    
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
        
        return {
            'rsi': round(current_rsi, 2),
            'rsi_signal': "oversold" if current_rsi < 30 else "overbought" if current_rsi > 70 else "neutral",
            'macd_line': round(current_macd, 2),
            'macd_signal': round(current_signal, 2),
            'macd_histogram': round(current_histogram, 2),
            'macd_trend': "bullish" if current_macd > current_signal else "bearish",
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
    
    def _format_open_positions(self) -> str:
        """Formatuje informacje o otwartych pozycjach."""
        if not self.paper_trading_engine:
            return "\n=== OTWARTE POZYCJE ===\nBrak informacji o pozycjach (paper trading engine nie ustawiony)"
        
        try:
            open_positions = self.paper_trading_engine.get_open_positions()
            
            if not open_positions:
                return "\n=== OTWARTE POZYCJE ===\n📭 Brak otwartych pozycji - możesz otworzyć nową!"
            
            lines = ["\n=== OTWARTE POZYCJE ==="]
            for pos in open_positions:
                current_price = self.paper_trading_engine.get_current_price(pos.symbol)
                pnl, pnl_pct = pos.calculate_pnl(current_price)
                
                emoji = "🟢" if pnl > 0 else "🔴"
                side_emoji = "📈" if pos.side.value == "long" else "📉"
                
                # Oblicz czas od otwarcia
                time_open = (datetime.now() - pos.opened_at).total_seconds() / 3600  # w godzinach
                
                lines.append(f"\n{side_emoji} {pos.symbol} - {pos.side.value.upper()}")
                lines.append(f"   Rozmiar: {pos.size:.6f}")
                lines.append(f"   Cena wejścia: ${pos.entry_price:,.2f}")
                lines.append(f"   Cena aktualna: ${current_price:,.2f}")
                lines.append(f"   {emoji} PnL: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")
                lines.append(f"   ⏱️ Czas otwarcia: {time_open:.1f}h")
                
                if pos.stop_loss:
                    lines.append(f"   🛡️ Stop Loss: ${pos.stop_loss:,.2f}")
                if pos.take_profit:
                    lines.append(f"   🎯 Take Profit: ${pos.take_profit:,.2f}")
                
                # Rekomendacja działania na podstawie PnL
                if pnl_pct <= -5.0:
                    lines.append(f"   ⚠️ UWAGA: Rozważ CLOSE - znaczna strata!")
                elif pnl_pct >= 5.0:
                    lines.append(f"   💡 SUGESTIA: Rozważ CLOSE lub trailing stop - dobry zysk!")
                elif time_open > 12:
                    lines.append(f"   ⏰ UWAGA: Pozycja otwarta > 12h - rozważ zamknięcie")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.warning(f"Błąd pobierania otwartych pozycji: {e}")
            return "\n=== OTWARTE POZYCJE ===\nBłąd pobierania pozycji"
    
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
        macd_emoji = "🟢" if macd_trend == "bullish" else "🔴"
        lines.append(f"📈 MACD: {macd_line} | Signal: {macd_signal} | Histogram: {macd_hist} {macd_emoji}")
        
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
    
    def _build_prompt(self, symbol: str, current_price: float, indicators: Dict[str, Any]) -> str:
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
        positions_text = self._format_open_positions()
        
        # Wskaźniki techniczne
        indicators_text = self._format_indicators(indicators)
        
        # Historia cen
        price_history_text = self._format_price_history(symbol)
        
        # Historia decyzji
        decision_history_text = self._format_decision_history()
        
        # Pełny prompt
        full_prompt = f"""{self.prompt_template}

{context_text}

{positions_text}

{indicators_text}

{price_history_text}

{decision_history_text}

=== AKTUALNA SYTUACJA ===
Symbol: {symbol}
Cena aktualna: ${current_price:,.2f}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

=== FORMAT ODPOWIEDZI ===
Odpowiedz TYLKO w formacie JSON:
{{
    "action": "BUY" | "SELL" | "HOLD" | "CLOSE",
    "confidence": 0.0-10.0,
    "price": {current_price},
    "stop_loss": <cena stop loss lub null>,
    "take_profit": <cena take profit lub null>,
    "size_percent": <procent kapitału 5-30>,
    "trailing_stop_percent": <opcjonalnie: trailing stop w % lub null>,
    "observations": "<szczegółowa analiza wskaźników i rynku>",
    "reason": "<krótkie uzasadnienie decyzji>"
}}

WAŻNE:
- Jeśli masz OTWARTĄ POZYCJĘ - zdecyduj czy CLOSE czy HOLD (nie możesz BUY/SELL w tym samym kierunku!)
- Jeśli NIE masz pozycji - możesz BUY, SELL lub HOLD
- Confidence >= 5 dla otwarcia nowej pozycji
- Zawsze ustaw stop_loss i take_profit dla nowych pozycji
"""
        
        return full_prompt
    
    def _parse_llm_response(self, response: str, symbol: str, current_price: float) -> Optional[TradingSignal]:
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
            
            # Mapuj action na SignalType
            action_map = {
                'BUY': SignalType.BUY,
                'SELL': SignalType.SELL,
                'HOLD': SignalType.HOLD,
                'CLOSE': SignalType.CLOSE
            }
            
            action_str = data.get('action', 'HOLD').upper()
            signal_type = action_map.get(action_str, SignalType.HOLD)
            
            # Wyświetl decyzję
            self._display_decision(data, symbol, current_price)
            
            # Dla HOLD nie generuj sygnału
            if signal_type == SignalType.HOLD:
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
    
    def _display_decision(self, data: Dict[str, Any], symbol: str, current_price: float):
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
        logger.info(f"🤖 DECYZJA LLM v1.1 dla {symbol}: {emoji_map.get(action, action)}")
        logger.info("=" * 70)
        logger.info(f"Pewność: {data.get('confidence', 0)}/10")
        logger.info(f"Cena: ${current_price:,.2f}")
        
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
        """Analizuje dane rynkowe używając LLM z wskaźnikami technicznymi."""
        if df is None or df.empty:
            logger.warning(f"Brak danych dla {symbol}")
            return None
        
        # Zapisz symbol
        self._current_symbol = symbol
        
        # Aktualizuj historię
        self.update_price_history(symbol, df)
        
        # Pobierz aktualną cenę
        current_price = float(df['close'].iloc[-1])
        
        # Oblicz wskaźniki techniczne
        indicators = self._calculate_all_indicators(df)
        
        # Zbuduj prompt
        prompt = self._build_prompt(symbol, current_price, indicators)
        
        # Wyślij do LLM
        try:
            from langchain.schema import HumanMessage, SystemMessage
            
            system_message = """Jesteś profesjonalnym traderem kryptowalut. Podejmujesz szybkie i zdecydowane decyzje tradingowe.

ZASADY:
1. DZIAŁAJ AGRESYWNIE - rynek kryptowalut wymaga szybkich decyzji
2. Jeśli masz OTWARTĄ POZYCJĘ - zarządzaj nią aktywnie (CLOSE przy zysku >3% lub stracie >-2%)
3. Jeśli NIE masz pozycji - szukaj okazji (BUY/SELL przy dobrych sygnałach)
4. Używaj wskaźników technicznych do potwierdzenia decyzji
5. Zawsze ustaw stop loss i take profit

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
            
            # Parsuj odpowiedź
            signal = self._parse_llm_response(response_text, symbol, current_price)
            
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
        
        # Stop loss / take profit (backup)
        if current_pnl_percent <= -self.trailing_stop_percent:
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=current_price,
                reason=f"Stop loss ({current_pnl_percent:.2f}%)",
                strategy=self.name
            )
        
        if current_pnl_percent >= 10.0:  # 10% take profit
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=current_price,
                reason=f"Take profit ({current_pnl_percent:.2f}%)",
                strategy=self.name
            )
        
        return None
