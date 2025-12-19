"""
Strategia Propagacji Sentymentu
================================
Strategia oparta na wykrywaniu propagacji sentymentu między regionami świata.

Główne założenia:
- Informacje o kryptowalutach rozprzestrzeniają się z opóźnieniem między regionami
- US/GB zazwyczaj reagują pierwsze (główne źródła newsów EN)
- Europa (DE) opóźniona o ~2h
- Azja (JP, KR) opóźniona o ~3-4h
- Chiny (CN) opóźnione o ~6h
- Wykrycie tego opóźnienia może dać przewagę tradingową

Strategia:
- Monitoruje sentyment z regionu lidera (zazwyczaj US)
- Wykrywa "fale" sentymentu propagujące się między regionami
- Generuje sygnały BUY/SELL na podstawie wykrytych fal
- Koreluje sentyment z cenami BTC

Autor: AI Assistant
Data: 2025-12-18
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType
from src.collectors.sentiment import (
    SentimentWaveTracker,
    SentimentPropagationAnalyzer,
    PropagationDirection
)


class SentimentPropagationStrategy(BaseStrategy):
    """
    Strategia propagacji sentymentu między regionami.
    
    Wykorzystuje:
    - GDELT do pobierania sentymentu z mediów z różnych krajów
    - Cross-correlation do wykrywania lag-ów między regionami
    - Wykrywanie "fal" sentymentu propagujących się globalnie
    - Korelację z cenami BTC
    """
    
    name = "SentimentPropagationStrategy"
    description = "Strategia oparta na propagacji sentymentu między regionami"
    timeframe = "1h"  # Używamy danych godzinowych
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        
        # Parametry strategii
        self.query = self.config.get("query", "bitcoin OR cryptocurrency")
        self.countries = self.config.get(
            "countries", 
            ["US", "CN", "JP", "KR", "DE", "GB"]
        )
        self.days_back = self.config.get("days_back", 7)
        
        # Parametry wykrywania fal
        self.min_wave_strength = self.config.get("min_wave_strength", 0.5)
        self.min_confidence = self.config.get("min_confidence", 6.0)
        self.recent_wave_hours = self.config.get("recent_wave_hours", 24)
        
        # Parametry tradingowe
        self.target_profit_percent = self.config.get("target_profit_percent", 2.0)
        self.stop_loss_percent = self.config.get("stop_loss_percent", 1.5)
        self.max_hold_hours = self.config.get("max_hold_hours", 48)
        
        # Symbol dla danych LLM (można przekazać w config)
        # Normalizuj symbol: BTC-USD -> BTC/USDC (zgodnie z formatem używanym w bazie)
        symbol_raw = self.config.get("symbol", "BTC/USDC")
        # Konwertuj BTC-USD na BTC/USDC (format używany w llm_sentiment_analysis)
        if symbol_raw and "-" in symbol_raw:
            # BTC-USD -> BTC/USDC
            base, quote = symbol_raw.split("-", 1)
            if quote == "USD":
                self.symbol = f"{base}/USDC"  # Używamy USDC zamiast USD dla zgodności z bazą
            else:
                self.symbol = f"{base}/{quote}"
        else:
            self.symbol = symbol_raw
        
        # Źródło danych sentymentu (llm lub gdelt)
        use_llm_data = self.config.get("use_llm_data", True)  # Domyślnie LLM
        
        # Inicjalizacja tracker'a
        if use_llm_data:
            logger.info("Używam danych z llm_sentiment_analysis jako źródła sentymentu")
        else:
            logger.info("Używam danych z GDELT API jako źródła sentymentu")
        
        self.tracker = SentimentWaveTracker(
            cache_dir=None,  # Użyj domyślnego
            use_database=True,  # Użyj bazy danych
            use_llm_data=use_llm_data  # Użyj danych z llm_sentiment_analysis lub GDELT
        )
        
        # Cache dla wyników analizy
        self._last_analysis: Optional[Dict[str, Any]] = None
        self._last_analysis_time: Optional[datetime] = None
        self._analysis_cache_hours = 1  # Cache na 1 godzinę
        
        # Tryb backtestingu
        self._backtest_mode = self.config.get("_backtest_mode", False)
        
        logger.info(f"Strategia {self.name} zainicjalizowana")
        logger.info(f"Kraje: {self.countries}, Query: {self.query}")
    
    def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD") -> Optional[TradingSignal]:
        """
        Analizuje dane i generuje sygnał na podstawie propagacji sentymentu.
        
        Args:
            df: DataFrame z danymi OHLCV
            symbol: Symbol pary (może być w formacie BTC-USD, ale używamy self.symbol dla LLM)
            
        Returns:
            TradingSignal lub None
        """
        if df.empty:
            logger.warning("Brak danych OHLCV")
            return None
        
        # Pobierz aktualną cenę
        current_price = float(df["close"].iloc[-1])
        current_time = df.index[-1]
        
        # Sprawdź cache
        if self._should_refresh_analysis(current_time):
            logger.info("Aktualizuję analizę propagacji sentymentu...")
            
            try:
                # Uruchom pełną analizę (używa danych z llm_sentiment_analysis)
                # Używamy self.symbol (znormalizowany, np. BTC/USDC) zamiast symbol z parametru (może być BTC-USD)
                logger.debug(f"Przekazuję symbol do tracker.run_full_analysis: '{self.symbol}' (długość: {len(self.symbol)})")
                results = self.tracker.run_full_analysis(
                    query=self.query,  # Używane tylko jako fallback do GDELT
                    countries=self.countries,
                    days_back=self.days_back,
                    include_price_correlation=True,
                    symbol=self.symbol  # Używamy znormalizowanego symbolu (BTC/USDC) dla danych LLM
                )
                
                self._last_analysis = results
                self._last_analysis_time = current_time
                
            except Exception as e:
                logger.error(f"Błąd podczas analizy propagacji sentymentu: {e}")
                # Użyj cache jeśli dostępny
                if self._last_analysis is None:
                    return None
        else:
            logger.debug("Używam cache'owanej analizy")
            results = self._last_analysis
        
        if not results or not results.get("summary"):
            logger.warning("Brak wyników analizy")
            return None
        
        # Sprawdź sygnały tradingowe
        signals = results.get("summary", {}).get("trading_signals", [])
        
        if not signals:
            logger.debug("Brak aktywnych sygnałów tradingowych")
            return None
        
        # Weź najnowszy sygnał
        latest_signal = signals[0]
        
        # Sprawdź czy sygnał jest wystarczająco silny
        if latest_signal.get("strength", 0) < self.min_wave_strength:
            logger.debug(f"Sygnał za słaby: {latest_signal.get('strength')} < {self.min_wave_strength}")
            return None
        
        # Określ typ sygnału
        signal_type = SignalType.BUY if latest_signal.get("type") == "bullish" else SignalType.SELL
        
        # Oblicz confidence na podstawie siły fali i liczby dotkniętych regionów
        wave_strength = latest_signal.get("strength", 0)
        affected_regions = len(latest_signal.get("expected_propagation", []))
        
        # Confidence: 0-10
        # Bazowa confidence z siły fali (0-5)
        base_confidence = wave_strength * 5
        
        # Bonus za propagację do wielu regionów (0-3)
        propagation_bonus = min(3.0, affected_regions * 0.5)
        
        # Bonus za region lidera (0-2)
        leader_bonus = 0
        if results.get("leader_region"):
            leader = results["leader_region"].get("region", "")
            if latest_signal.get("origin") == leader:
                leader_bonus = 2.0
        
        confidence = min(10.0, base_confidence + propagation_bonus + leader_bonus)
        
        if confidence < self.min_confidence:
            logger.debug(f"Confidence za niska: {confidence} < {self.min_confidence}")
            return None
        
        # Oblicz stop loss i take profit
        if signal_type == SignalType.BUY:
            stop_loss = current_price * (1 - self.stop_loss_percent / 100)
            take_profit = current_price * (1 + self.target_profit_percent / 100)
        else:  # SELL
            stop_loss = current_price * (1 + self.stop_loss_percent / 100)
            take_profit = current_price * (1 - self.target_profit_percent / 100)
        
        # Przygotuj reason
        reason = latest_signal.get("message", "")
        if not reason:
            direction = "pozytywna" if signal_type == SignalType.BUY else "negatywna"
            reason = f"Fala {direction} sentymentu z {latest_signal.get('origin', 'nieznany')}"
        
        # Używamy symbol z parametru (może być BTC-USD) dla sygnału tradingowego
        # ale self.symbol (BTC/USDC) jest używany do pobierania danych LLM
        signal = TradingSignal(
            signal_type=signal_type,
            symbol=symbol,  # Symbol z parametru (format używany przez trading bot)
            confidence=confidence,
            price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason,
            strategy=self.name
        )
        
        logger.info(f"Wygenerowano sygnał: {signal}")
        return signal
    
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
        if df.empty:
            return None
        
        current_price = float(df["close"].iloc[-1])
        entry_time = df.index[0]  # Założenie: entry_time to pierwszy timestamp
        
        # Sprawdź czy osiągnięto target zysku
        if side == "long" and current_pnl_percent >= self.target_profit_percent:
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=df.get("symbol", "BTC-USD"),
                confidence=10.0,
                price=current_price,
                reason=f"Osiągnięto target zysku: {current_pnl_percent:.2f}%",
                strategy=self.name
            )
        
        if side == "short" and current_pnl_percent >= self.target_profit_percent:
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=df.get("symbol", "BTC-USD"),
                confidence=10.0,
                price=current_price,
                reason=f"Osiągnięto target zysku: {current_pnl_percent:.2f}%",
                strategy=self.name
            )
        
        # Sprawdź czy osiągnięto stop loss
        if abs(current_pnl_percent) >= self.stop_loss_percent:
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=df.get("symbol", "BTC-USD"),
                confidence=10.0,
                price=current_price,
                reason=f"Osiągnięto stop loss: {current_pnl_percent:.2f}%",
                strategy=self.name
            )
        
        # Sprawdź czy fala sentymentu się odwróciła (ważniejsze niż czas)
        # To powinno być sprawdzane przed max_hold_hours, bo odwrócenie fali
        # jest ważniejszym sygnałem do zamknięcia pozycji
        if self._last_analysis:
            signals = self._last_analysis.get("summary", {}).get("trading_signals", [])
            if signals:
                latest_signal = signals[0]
                # Jeśli nowa fala ma przeciwny kierunek, zamknij pozycję
                if side == "long" and latest_signal.get("type") == "bearish":
                    return TradingSignal(
                        signal_type=SignalType.CLOSE,
                        symbol=df.get("symbol", "BTC-USD"),
                        confidence=7.0,
                        price=current_price,
                        reason="Wykryto odwrócenie fali sentymentu (bearish)",
                        strategy=self.name
                    )
                elif side == "short" and latest_signal.get("type") == "bullish":
                    return TradingSignal(
                        signal_type=SignalType.CLOSE,
                        symbol=df.get("symbol", "BTC-USD"),
                        confidence=7.0,
                        price=current_price,
                        reason="Wykryto odwrócenie fali sentymentu (bullish)",
                        strategy=self.name
                    )
        
        # Sprawdź czy minął maksymalny czas trzymania (na końcu, po sprawdzeniu innych warunków)
        if isinstance(entry_time, pd.Timestamp):
            hold_hours = (df.index[-1] - entry_time).total_seconds() / 3600
            if hold_hours >= self.max_hold_hours:
                return TradingSignal(
                    signal_type=SignalType.CLOSE,
                    symbol=df.get("symbol", "BTC-USD"),
                    confidence=8.0,
                    price=current_price,
                    reason=f"Przekroczono maksymalny czas trzymania: {hold_hours:.1f}h",
                    strategy=self.name
                )
        
        return None
    
    def _should_refresh_analysis(self, current_time: pd.Timestamp) -> bool:
        """Sprawdza czy należy odświeżyć analizę."""
        if self._last_analysis_time is None:
            return True
        
        if isinstance(current_time, pd.Timestamp):
            time_diff = (current_time - self._last_analysis_time).total_seconds() / 3600
            return time_diff >= self._analysis_cache_hours
        
        return True

