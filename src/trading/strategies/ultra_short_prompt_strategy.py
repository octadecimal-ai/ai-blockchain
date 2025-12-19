"""
Ultra Short Strategy - VWAP Fakeout Strategy
============================================
Strategia oparta na VWAP fakeoutach (mean reversion).

Główne założenia:
- SHORT: Cena wybija powyżej VWAP (≥+0.5-1.0%), brak kontynuacji, powrót pod VWAP
- LONG: Cena spada poniżej VWAP (≥-0.5-1.0%), brak kontynuacji, powrót nad VWAP
- RSI jako filtr (SHORT: ≥65, LONG: ≤35)
- Mean reversion - oczekiwanie powrotu do VWAP
- Krótkie timeframe (5-15 minut)
- Parametry pozycji w USD (300-800 profit, 300-500 loss)

Autor: AI Assistant
Data: 2025-12-16
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import json
import time
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType
from src.analysis.llm.market_analyzer import MarketAnalyzerLLM
from src.utils.api_logger import get_api_logger
from src.collectors.exchange.dydx_collector import DydxCollector
from src.analysis.technical.indicators import TechnicalAnalyzer


class UltraShortPromptStrategy(BaseStrategy):
    """
    Strategia Ultra Short oparta na VWAP fakeoutach z LLM.
    
    Kluczowe cechy:
    - Wykrywa fakeouty VWAP (fałszywe wybicia)
    - Mean reversion - oczekiwanie powrotu do średniej
    - RSI jako filtr wejścia
    - Parametry pozycji w USD
    - Krótkie timeframe (5-15 minut)
    """
    
    name = "UltraShortPromptStrategy"
    description = "VWAP Fakeout Strategy - Mean Reversion z LLM"
    timeframe = "5min"  # Krótki timeframe dla szybkich decyzji
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        
        # Ścieżka do promptu
        self.prompt_file = self.config.get('prompt_file', 'prompts/trading/ultra_short_strategy_prompt.txt')
        prompt_path = Path(self.prompt_file)
        if not prompt_path.exists():
            raise FileNotFoundError(f"Plik promptu nie istnieje: {self.prompt_file}")
        
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.prompt_template = f.read()
        
        # Konfiguracja LLM
        self.provider = self.config.get('provider', 'anthropic')
        self.model = self.config.get('model', 'claude-3-5-haiku-20241022')
        self.api_key = self.config.get('api_key')
        
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
        
        # API logger
        self.api_logger = get_api_logger()
        
        # Inicjalizuj DydxCollector dla danych rynkowych
        try:
            self.dydx_collector = DydxCollector()
            logger.info("DydxCollector zainicjalizowany")
        except Exception as e:
            logger.warning(f"Nie udało się zainicjalizować DydxCollector: {e}")
            self.dydx_collector = None
        
        # Parametry RSI
        self.rsi_period = self.config.get('rsi_period', 14)
        self.rsi_short_threshold = self.config.get('rsi_short_threshold', 65)  # Filtr dla SHORT
        self.rsi_long_threshold = self.config.get('rsi_long_threshold', 35)  # Filtr dla LONG
        
        # Parametry VWAP fakeout
        self.vwap_fakeout_min_percent = self.config.get('vwap_fakeout_min_percent', 0.5)  # Min wybicie w %
        self.vwap_fakeout_max_percent = self.config.get('vwap_fakeout_max_percent', 1.0)  # Max wybicie w %
        
        # Parametry pozycji
        self.target_profit_usd_min = self.config.get('target_profit_usd_min', 300.0)
        self.target_profit_usd_max = self.config.get('target_profit_usd_max', 800.0)
        self.max_loss_usd_min = self.config.get('max_loss_usd_min', 300.0)
        self.max_loss_usd_max = self.config.get('max_loss_usd_max', 500.0)
        self.position_size_percent_min = self.config.get('position_size_percent_min', 10.0)
        self.position_size_percent_max = self.config.get('position_size_percent_max', 20.0)
        
        # Parametry czasowe
        self.max_hold_minutes = self.config.get('max_hold_minutes', 15)
        self.min_hold_minutes = self.config.get('min_hold_minutes', 10)
        self.cooldown_minutes = self.config.get('cooldown_minutes', 2)
        
        # Tracking
        self.last_close_time: Optional[datetime] = None
        self.paper_trading_engine = None
        
        # Kontekst sesji
        self.session_context: Dict[str, Any] = {}
        
        logger.info(f"UltraShortPromptStrategy zainicjalizowana")
        logger.info(f"  Prompt: {self.prompt_file}")
        logger.info(f"  LLM: {self.provider}/{self.model}")
        logger.info(f"  RSI: {self.rsi_period} (SHORT≥{self.rsi_short_threshold}, LONG≤{self.rsi_long_threshold})")
        logger.info(f"  VWAP fakeout: {self.vwap_fakeout_min_percent}%-{self.vwap_fakeout_max_percent}%")
        logger.info(f"  Profit: ${self.target_profit_usd_min}-${self.target_profit_usd_max}")
        logger.info(f"  Loss: ${self.max_loss_usd_min}-${self.max_loss_usd_max}")
    
    # ========================================
    # KONTEKST SESJI
    # ========================================
    
    def set_session_context(self, context: Dict[str, Any]):
        """Ustawia kontekst sesji."""
        self.session_context = context
        logger.debug(f"Kontekst sesji ustawiony: {context}")
    
    def set_paper_trading_engine(self, engine):
        """Ustawia referencję do paper trading engine."""
        self.paper_trading_engine = engine
        logger.debug("Paper trading engine ustawiony")
    
    # ========================================
    # ANALIZA RSI
    # ========================================
    
    def _calculate_rsi(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Oblicza RSI i analizuje warunki dla strategii.
        
        Returns:
            Dict z danymi RSI i analizą
        """
        if len(df) < self.rsi_period + 1:
            return {
                'current_rsi': 50.0,
                'previous_rsi': 50.0,
                'crossed_threshold': False,
                'threshold_crossed': None,
                'candles_since_cross': 0,
                'candles_above_70': 0,
                'candles_below_30': 0,
                'was_above_70_long': False,
                'was_below_30_long': False
            }
        
        try:
            analyzer = TechnicalAnalyzer(df.copy())
            analyzer.add_rsi(period=self.rsi_period)
            
            if 'rsi' not in analyzer.df.columns:
                return {
                    'current_rsi': 50.0,
                    'previous_rsi': 50.0,
                    'crossed_threshold': False,
                    'threshold_crossed': None,
                    'candles_since_cross': 0,
                    'candles_above_70': 0,
                    'candles_below_30': 0,
                    'was_above_70_long': False,
                    'was_below_30_long': False
                }
            
            rsi_series = analyzer.df['rsi']
            current_rsi = float(rsi_series.iloc[-1])
            previous_rsi = float(rsi_series.iloc[-2]) if len(rsi_series) >= 2 else current_rsi
            
            # Sprawdź ostatnie 10 świec dla analizy trendu
            recent_rsi = rsi_series.tail(10)
            candles_above_70 = int((recent_rsi > 70).sum())
            candles_below_30 = int((recent_rsi < 30).sum())
            
            # Sprawdź czy był >70 przez >5 świec (dla SHORT - nie chcemy silnego trendu)
            was_above_70_long = candles_above_70 > 5
            
            # Sprawdź czy był <30 przez >5 świec (dla LONG - nie chcemy silnego trendu)
            was_below_30_long = candles_below_30 > 5
            
            # Sprawdź przekroczenie progów
            crossed_threshold = False
            threshold_crossed = None
            candles_since_cross = 0
            
            # Sprawdź czy przekroczył 70 (dla SHORT)
            if current_rsi >= 70 and previous_rsi < 70:
                crossed_threshold = True
                threshold_crossed = 70
                candles_since_cross = 0
            # Sprawdź czy przekroczył 30 (dla LONG)
            elif current_rsi <= 30 and previous_rsi > 30:
                crossed_threshold = True
                threshold_crossed = 30
                candles_since_cross = 0
            else:
                # Sprawdź ile świec od ostatniego przekroczenia
                if current_rsi >= 70:
                    # Szukaj kiedy ostatnio był <70
                    for i in range(len(rsi_series) - 1, -1, -1):
                        if rsi_series.iloc[i] < 70:
                            candles_since_cross = len(rsi_series) - 1 - i
                            threshold_crossed = 70
                            break
                elif current_rsi <= 30:
                    # Szukaj kiedy ostatnio był >30
                    for i in range(len(rsi_series) - 1, -1, -1):
                        if rsi_series.iloc[i] > 30:
                            candles_since_cross = len(rsi_series) - 1 - i
                            threshold_crossed = 30
                            break
            
            return {
                'current_rsi': round(current_rsi, 2),
                'previous_rsi': round(previous_rsi, 2),
                'crossed_threshold': crossed_threshold,
                'threshold_crossed': threshold_crossed,
                'candles_since_cross': candles_since_cross,
                'candles_above_70': candles_above_70,
                'candles_below_30': candles_below_30,
                'was_above_70_long': was_above_70_long,
                'was_below_30_long': was_below_30_long
            }
        except Exception as e:
            logger.warning(f"Błąd obliczania RSI: {e}")
            return {
                'current_rsi': 50.0,
                'previous_rsi': 50.0,
                'crossed_threshold': False,
                'threshold_crossed': None,
                'candles_since_cross': 0,
                'candles_above_70': 0,
                'candles_below_30': 0,
                'was_above_70_long': False,
                'was_below_30_long': False
            }
    
    # ========================================
    # ANALIZA VWAP
    # ========================================
    
    def _calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """
        Oblicza VWAP (Volume Weighted Average Price).
        
        Args:
            df: DataFrame z danymi OHLCV
            
        Returns:
            Series z wartościami VWAP
        """
        try:
            analyzer = TechnicalAnalyzer(df.copy())
            analyzer.add_vwap()
            
            if 'vwap' in analyzer.df.columns:
                return analyzer.df['vwap']
            else:
                # Fallback - własna implementacja
                typical_price = (df['high'] + df['low'] + df['close']) / 3
                vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
                return vwap
        except Exception as e:
            logger.warning(f"Błąd obliczania VWAP: {e}")
            # Fallback
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
            return vwap
    
    def _analyze_vwap_fakeout(self, df: pd.DataFrame, vwap: pd.Series) -> Dict[str, Any]:
        """
        Analizuje fakeout VWAP (fałszywe wybicie).
        
        Returns:
            Dict z analizą fakeoutu
        """
        if len(df) < 5:
            return {
                'has_fakeout': False,
                'fakeout_type': None,
                'price_vs_vwap_percent': 0.0,
                'fakeout_strength': 0.0,
                'continuation_failed': False,
                'returning_to_vwap': False
            }
        
        try:
            current_price = float(df['close'].iloc[-1])
            current_vwap = float(vwap.iloc[-1])
            
            # Oblicz odchylenie od VWAP w %
            price_vs_vwap_percent = ((current_price - current_vwap) / current_vwap) * 100
            
            # Sprawdź ostatnie 3-5 świec dla wykrycia fakeoutu
            lookback = min(5, len(df))
            recent_df = df.tail(lookback)
            recent_vwap = vwap.tail(lookback)
            
            # Sprawdź czy nastąpiło wybicie
            has_breakout_up = False
            has_breakout_down = False
            continuation_failed = False
            returning_to_vwap = False
            
            # Sprawdź wybicie w górę (dla SHORT)
            if price_vs_vwap_percent >= self.vwap_fakeout_min_percent:
                # Sprawdź czy cena wybiła powyżej VWAP w ostatnich świecach
                for i in range(len(recent_df) - 1, -1, -1):
                    price_at_i = float(recent_df['close'].iloc[i])
                    vwap_at_i = float(recent_vwap.iloc[i])
                    if price_at_i > vwap_at_i * (1 + self.vwap_fakeout_min_percent / 100):
                        has_breakout_up = True
                        break
                
                # Sprawdź brak kontynuacji (kolejna świeca nie robi higher high)
                if has_breakout_up and len(recent_df) >= 2:
                    max_high_after_breakout = float(recent_df['high'].iloc[-1])
                    max_high_before = float(recent_df['high'].iloc[-2])
                    if max_high_after_breakout <= max_high_before:
                        continuation_failed = True
                    
                    # Sprawdź czy cena wraca pod VWAP
                    if current_price < current_vwap:
                        returning_to_vwap = True
            
            # Sprawdź wybicie w dół (dla LONG)
            elif price_vs_vwap_percent <= -self.vwap_fakeout_min_percent:
                # Sprawdź czy cena wybiła poniżej VWAP w ostatnich świecach
                for i in range(len(recent_df) - 1, -1, -1):
                    price_at_i = float(recent_df['close'].iloc[i])
                    vwap_at_i = float(recent_vwap.iloc[i])
                    if price_at_i < vwap_at_i * (1 - self.vwap_fakeout_min_percent / 100):
                        has_breakout_down = True
                        break
                
                # Sprawdź brak kontynuacji (kolejna świeca nie robi lower low)
                if has_breakout_down and len(recent_df) >= 2:
                    min_low_after_breakout = float(recent_df['low'].iloc[-1])
                    min_low_before = float(recent_df['low'].iloc[-2])
                    if min_low_after_breakout >= min_low_before:
                        continuation_failed = True
                    
                    # Sprawdź czy cena wraca nad VWAP
                    if current_price > current_vwap:
                        returning_to_vwap = True
            
            # Określ typ fakeoutu
            fakeout_type = None
            if has_breakout_up and (continuation_failed or returning_to_vwap):
                fakeout_type = 'UP'  # Fakeout w górę -> sygnał SHORT
            elif has_breakout_down and (continuation_failed or returning_to_vwap):
                fakeout_type = 'DOWN'  # Fakeout w dół -> sygnał LONG
            
            has_fakeout = fakeout_type is not None
            
            # Siła fakeoutu (0-1)
            fakeout_strength = 0.0
            if has_fakeout:
                abs_deviation = abs(price_vs_vwap_percent)
                fakeout_strength = min(1.0, abs_deviation / self.vwap_fakeout_max_percent)
            
            return {
                'has_fakeout': has_fakeout,
                'fakeout_type': fakeout_type,
                'price_vs_vwap_percent': round(price_vs_vwap_percent, 2),
                'fakeout_strength': round(fakeout_strength, 2),
                'continuation_failed': continuation_failed,
                'returning_to_vwap': returning_to_vwap
            }
        except Exception as e:
            logger.warning(f"Błąd analizy VWAP fakeout: {e}")
            return {
                'has_fakeout': False,
                'fakeout_type': None,
                'price_vs_vwap_percent': 0.0,
                'fakeout_strength': 0.0,
                'continuation_failed': False,
                'returning_to_vwap': False
            }
    
    # ========================================
    # ANALIZA RUCHU CENY
    # ========================================
    
    def _analyze_price_movement(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analizuje ruch ceny w ostatnich świecach.
        
        Returns:
            Dict z analizą ruchu
        """
        if len(df) < 3:
            return {
                'is_sharp': False,
                'percent_change': 0.0,
                'direction': 'SIDEWAYS'
            }
        
        # Analizuj ostatnie 3-5 świec
        lookback = min(5, len(df))
        recent = df.tail(lookback)
        
        price_start = float(recent['close'].iloc[0])
        price_end = float(recent['close'].iloc[-1])
        
        percent_change = ((price_end - price_start) / price_start) * 100
        
        # Gwałtowny ruch = przekroczenie progu
        is_sharp = abs(percent_change) >= self.vwap_fakeout_min_percent
        
        if percent_change > 0.1:
            direction = 'UP'
        elif percent_change < -0.1:
            direction = 'DOWN'
        else:
            direction = 'SIDEWAYS'
        
        return {
            'is_sharp': is_sharp,
            'percent_change': round(percent_change, 2),
            'direction': direction
        }
    
    # ========================================
    # POZYCJA I PnL
    # ========================================
    
    def _get_current_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Pobiera informacje o aktualnej pozycji."""
        if not self.paper_trading_engine:
            return None
        
        open_positions = self.paper_trading_engine.get_open_positions()
        position = next((p for p in open_positions if p.symbol == symbol), None)
        
        if not position:
            return None
        
        current_price = self.paper_trading_engine.get_current_price(symbol)
        pnl, pnl_percent = position.calculate_pnl(current_price)
        
        # Oblicz czas od otwarcia
        minutes_open = (datetime.now() - position.opened_at).total_seconds() / 60
        
        return {
            'position': position,
            'side': position.side.value,
            'entry_price': position.entry_price,
            'current_price': current_price,
            'size': position.size,
            'pnl_usd': pnl,
            'pnl_percent': pnl_percent,
            'minutes_open': minutes_open
        }
    
    def _is_in_cooldown(self) -> bool:
        """Sprawdza czy jesteśmy w okresie cooldown."""
        if self.last_close_time is None:
            return False
        
        elapsed = (datetime.now() - self.last_close_time).total_seconds() / 60
        return elapsed < self.cooldown_minutes
    
    # ========================================
    # DANE Z GIEŁDY
    # ========================================
    
    def _get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Pobiera dane rynkowe z dYdX.
        
        Returns:
            Dict z danymi rynkowymi lub None
        """
        if not self.dydx_collector:
            return None
        
        try:
            ticker_data = self.dydx_collector.get_ticker(symbol)
            
            # Pobierz aktualny funding rate
            funding_rates = self.dydx_collector.get_funding_rates(symbol, limit=1)
            current_funding_rate = float(funding_rates['funding_rate'].iloc[-1]) if not funding_rates.empty else ticker_data.get('next_funding_rate', 0)
            
            # Oblicz czas do następnego funding (co 8 godzin: 00:00, 08:00, 16:00 UTC)
            from datetime import timezone
            now = datetime.now(timezone.utc)
            current_hour = now.hour
            
            funding_hours = [0, 8, 16]
            next_funding_hour = None
            
            for hour in funding_hours:
                if hour > current_hour:
                    next_funding_hour = hour
                    break
            
            if next_funding_hour is None:
                next_funding_date = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                next_funding_date = now.replace(hour=next_funding_hour, minute=0, second=0, microsecond=0)
            
            time_to_funding = next_funding_date - now
            hours_to_funding = time_to_funding.total_seconds() / 3600
            
            return {
                'oracle_price': float(ticker_data.get('oraclePrice', 0)),
                'price_change_24h': float(ticker_data.get('priceChange24H', 0)),
                'volume_24h': float(ticker_data.get('volume24H', 0)),
                'trades_24h': int(ticker_data.get('trades24H', 0)),
                'open_interest': float(ticker_data.get('openInterest', 0)),
                'funding_rate_1h': current_funding_rate * 100,  # W %
                'next_funding_time': f"{hours_to_funding:.1f}h",
                'max_leverage': float(ticker_data.get('maxLeverage', 20.0))
            }
        except Exception as e:
            logger.warning(f"Błąd pobierania danych rynkowych: {e}")
            return None
    
    def _display_market_data(self, symbol: str, current_price: float, market_data: Optional[Dict[str, Any]]):
        """Wyświetla dane rynkowe w logach."""
        if not market_data:
            return
        
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"📊 DANE RYNKOWE dYdX - {symbol}")
        logger.info("=" * 80)
        logger.info(f"Oracle Price:        ${market_data.get('oracle_price', 0):,.2f}")
        logger.info(f"Zmiana 24h:          {market_data.get('price_change_24h', 0):+.2f}%")
        logger.info(f"Wolumen 24h:         {market_data.get('volume_24h', 0):,.0f}")
        logger.info(f"Transakcje 24h:      {market_data.get('trades_24h', 0):,}")
        logger.info(f"Open Interest:       ${market_data.get('open_interest', 0):,.0f}")
        logger.info(f"Funding Rate (1h):    {market_data.get('funding_rate_1h', 0):+.4f}%")
        logger.info(f"Następny funding:     za {market_data.get('next_funding_time', 'N/A')}")
        logger.info(f"Max Leverage:        {market_data.get('max_leverage', 20.0):.1f}x")
        logger.info("=" * 80)
    
    # ========================================
    # BUDOWANIE PROMPTU
    # ========================================
    
    def _build_prompt(
        self,
        symbol: str,
        current_price: float,
        vwap: float,
        vwap_analysis: Dict[str, Any],
        rsi_data: Dict[str, Any],
        price_movement: Dict[str, Any],
        position_info: Optional[Dict[str, Any]],
        market_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Buduje prompt dla LLM z analizą VWAP fakeout.
        """
        # Kontekst sesji
        context_text = f"""
=== KONTEKST SESJI ===
Kapitał początkowy: ${self.session_context.get('balance', 10000):,.2f}
Max strata na pozycję: ${self.max_loss_usd_min}-${self.max_loss_usd_max}
Target zysku: ${self.target_profit_usd_min}-${self.target_profit_usd_max}
Rozmiar pozycji: {self.position_size_percent_min}-{self.position_size_percent_max}% kapitału
"""
        
        # Dane VWAP
        vwap_text = f"""
=== ANALIZA VWAP ===
Aktualna cena: ${current_price:,.2f}
VWAP: ${vwap:,.2f}
Odchylenie od VWAP: {vwap_analysis.get('price_vs_vwap_percent', 0):+.2f}%
Fakeout wykryty: {"TAK" if vwap_analysis.get('has_fakeout') else "NIE"}
Typ fakeoutu: {vwap_analysis.get('fakeout_type', 'BRAK')}
Siła fakeoutu: {vwap_analysis.get('fakeout_strength', 0):.2f}
Brak kontynuacji: {"TAK" if vwap_analysis.get('continuation_failed') else "NIE"}
Powrót do VWAP: {"TAK" if vwap_analysis.get('returning_to_vwap') else "NIE"}
"""
        
        # Dane RSI
        rsi_text = f"""
=== ANALIZA RSI ===
Aktualny RSI(14): {rsi_data.get('current_rsi', 50):.1f}
Przekroczył próg: {"TAK" if rsi_data.get('crossed_threshold') else "NIE"}
Próg przekroczony: {rsi_data.get('threshold_crossed', 'BRAK')}
Świec od przekroczenia: {rsi_data.get('candles_since_cross', 0)}
Świec powyżej 70 (ostatnie 10): {rsi_data.get('candles_above_70', 0)}
Świec poniżej 30 (ostatnie 10): {rsi_data.get('candles_below_30', 0)}
Był >70 przez >5 świec: {"TAK" if rsi_data.get('was_above_70_long') else "NIE"} (nie chcemy dla SHORT)
Był <30 przez >5 świec: {"TAK" if rsi_data.get('was_below_30_long') else "NIE"} (nie chcemy dla LONG)
"""
        
        # Ruch ceny
        price_text = f"""
=== ANALIZA RUCHU CENY ===
Gwałtowny ruch: {"TAK" if price_movement.get('is_sharp') else "NIE"}
Zmiana ceny: {price_movement.get('percent_change', 0):+.2f}%
Kierunek: {price_movement.get('direction', 'SIDEWAYS')}
"""
        
        # Pozycja (jeśli otwarta)
        if position_info:
            position_text = f"""
=== OTWARTA POZYCJA ===
Typ: {position_info['side'].upper()}
Cena wejścia: ${position_info['entry_price']:,.2f}
Aktualna cena: ${position_info['current_price']:,.2f}
Rozmiar: {position_info['size']:.6f} BTC
PnL: ${position_info['pnl_usd']:+,.2f} ({position_info['pnl_percent']:+.2f}%)
Otwarta od: {position_info['minutes_open']:.1f} minut

UWAGA: Masz otwartą pozycję!
- Jeśli PnL >= +${self.target_profit_usd_min} → rozważ CLOSE
- Jeśli PnL <= -${self.max_loss_usd_min} → CLOSE (stop loss!)
- Jeśli czas > {self.max_hold_minutes} min i brak zysku → rozważ CLOSE
- Jeśli reversion complete (LONG→RSI>55, SHORT→RSI<45) → rozważ CLOSE
- Jeśli 10-15 min bez ruchu w Twoją stronę → rozważ CLOSE
"""
        else:
            position_text = """
=== BRAK OTWARTEJ POZYCJI ===
Szukam sygnału do wejścia zgodnie z Ultra Short Strategy:
- SHORT: VWAP fakeout UP (wybicie ≥+0.5-1.0%, brak kontynuacji, powrót pod VWAP) + RSI≥65
- LONG: VWAP fakeout DOWN (spadek ≥-0.5-1.0%, brak kontynuacji, powrót nad VWAP) + RSI≤35
"""
        
        # Dane rynkowe (jeśli dostępne)
        market_text = ""
        if market_data:
            market_text = f"""
=== DANE RYNKOWE dYdX ===
Oracle Price: ${market_data.get('oracle_price', 0):,.2f}
Zmiana 24h: {market_data.get('price_change_24h', 0):+.2f}%
Wolumen 24h: {market_data.get('volume_24h', 0):,.0f}
Open Interest: ${market_data.get('open_interest', 0):,.0f}
Funding Rate: {market_data.get('funding_rate_1h', 0):+.4f}%
"""
        
        # Zbuduj pełny prompt
        full_prompt = f"""
{self.prompt_template}

{context_text}

{market_text}

{vwap_text}

{rsi_text}

{price_text}

{position_text}

=== ZADANIE ===
Przeanalizuj powyższe dane i podejmij decyzję zgodnie z zasadami Ultra Short Strategy.
Pamiętaj:
- To strategia MEAN REVERSION (powrót do średniej), nie trend following
- Szukamy FAKEOUTÓW (fałszywych wybić), nie prawdziwych breakoutów
- Confidence musi być ≥7 dla wejścia
- Parametry pozycji w USD (nie procentach)
- Krótkie timeframe (10-15 minut max)

Odpowiedz TYLKO w formacie JSON zgodnie z FORMAT ODPOWIEDZI.
"""
        
        return full_prompt
    
    # ========================================
    # ANALIZA I DECYZJA
    # ========================================
    
    def analyze(
        self,
        df: pd.DataFrame,
        symbol: str = "BTC-USD",
        paper_trading_engine=None
    ) -> Optional[TradingSignal]:
        """
        Analizuje rynek i zwraca sygnał handlowy.
        
        Args:
            df: DataFrame z danymi OHLCV
            symbol: Symbol rynku (np. 'BTC-USD')
            paper_trading_engine: Silnik paper trading (opcjonalnie)
            
        Returns:
            TradingSignal lub None
        """
        if paper_trading_engine:
            self.paper_trading_engine = paper_trading_engine
        
        if df is None or df.empty or len(df) < 20:
            logger.warning(f"Za mało danych dla {symbol}")
            return None
        
        # Oblicz aktualną cenę z danych
        current_price = float(df['close'].iloc[-1])
        
        # Sprawdź cooldown
        if self._is_in_cooldown():
            logger.debug(f"W okresie cooldown dla {symbol}")
            return None
        
        # Oblicz VWAP
        vwap_series = self._calculate_vwap(df)
        current_vwap = float(vwap_series.iloc[-1])
        
        # Analizuj VWAP fakeout
        vwap_analysis = self._analyze_vwap_fakeout(df, vwap_series)
        
        # Oblicz RSI
        rsi_data = self._calculate_rsi(df)
        
        # Analizuj ruch ceny
        price_movement = self._analyze_price_movement(df)
        
        # Pobierz informacje o pozycji
        position_info = self._get_current_position(symbol)
        
        # Pobierz dane rynkowe
        market_data = self._get_market_data(symbol)
        
        # Wyświetl dane rynkowe
        self._display_market_data(symbol, current_price, market_data)
        
        # Zbuduj prompt
        prompt = self._build_prompt(
            symbol=symbol,
            current_price=current_price,
            vwap=current_vwap,
            vwap_analysis=vwap_analysis,
            rsi_data=rsi_data,
            price_movement=price_movement,
            position_info=position_info,
            market_data=market_data
        )
        
        # Wyślij do LLM
        logger.info("")
        logger.info("🤖 Wysyłam zapytanie do LLM...")
        
        try:
            from langchain.schema import HumanMessage, SystemMessage
            import time
            
            messages = [
                SystemMessage(content="Jesteś traderem używającym Ultra Short Strategy (VWAP Fakeout). Analizujesz VWAP fakeouty i RSI, aby podejmować szybkie decyzje tradingowe oparte na mean reversion."),
                HumanMessage(content=prompt)
            ]
            
            # Loguj request
            messages_for_log = [
                {"role": msg.type if hasattr(msg, 'type') else str(type(msg).__name__), "content": msg.content}
                for msg in messages
            ]
            
            self.api_logger.log_request(
                provider=self.provider,
                model=self.model,
                messages=messages_for_log,
                temperature=getattr(self.llm_analyzer.llm, 'temperature', None),
                max_tokens=getattr(self.llm_analyzer.llm, 'max_tokens', None),
                metadata={"method": "analyze", "strategy": self.name, "symbol": symbol}
            )
            
            # Wykonaj request i zmierz czas
            start_time = time.time()
            response = self.llm_analyzer.llm.invoke(messages)
            response_time_ms = (time.time() - start_time) * 1000
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Pobierz usage z response jeśli dostępne
            input_tokens = None
            output_tokens = None
            if hasattr(response, 'response_metadata'):
                usage = response.response_metadata.get('usage', {}) if response.response_metadata else {}
                input_tokens = usage.get('input_tokens')
                output_tokens = usage.get('output_tokens')
            
            # Loguj response
            self.api_logger.log_response(
                provider=self.provider,
                model=self.model,
                response_text=response_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                response_time_ms=response_time_ms,
                metadata={"method": "analyze", "strategy": self.name, "symbol": symbol}
            )
            
            # Parsuj odpowiedź JSON
            signal = self._parse_llm_response(response_text, symbol, current_price, position_info)
            
            if signal:
                logger.info(f"✅ Sygnał: {signal.signal_type.value} (confidence: {signal.confidence})")
                logger.info(f"   Powód: {signal.reason}")
            else:
                logger.info("⏸️  Brak sygnału (WAIT lub błąd parsowania)")
            
            return signal
            
        except Exception as e:
            logger.error(f"Błąd podczas analizy LLM: {e}")
            return None
    
    def _parse_llm_response(
        self,
        response: str,
        symbol: str,
        current_price: float,
        position_info: Optional[Dict[str, Any]]
    ) -> Optional[TradingSignal]:
        """
        Parsuje odpowiedź LLM i zwraca TradingSignal.
        """
        try:
            # Wyciągnij JSON z odpowiedzi
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.warning("Nie znaleziono JSON w odpowiedzi LLM")
                return None
            
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            action = data.get('action', '').upper()
            confidence = int(data.get('confidence', 5))
            
            # Walidacja confidence dla wejścia
            if action in ['LONG', 'SHORT'] and confidence < 7:
                logger.warning(f"Confidence {confidence} < 7, wymuszam WAIT")
                return None
            
            # Jeśli mamy otwartą pozycję, wymuś CLOSE jeśli LLM sugeruje nową pozycję
            if position_info and action in ['LONG', 'SHORT']:
                logger.warning(f"Mamy otwartą pozycję, wymuszam CLOSE zamiast {action}")
                action = 'CLOSE'
            
            # Przygotuj parametry pozycji
            position_params = data.get('position_params', {})
            entry_price_raw = position_params.get('entry_price', current_price)
            if entry_price_raw is None:
                entry_price = current_price
            else:
                try:
                    entry_price = float(entry_price_raw)
                except (ValueError, TypeError):
                    entry_price = current_price
            
            # Obsługa None dla wartości numerycznych
            stop_loss_usd_raw = position_params.get('stop_loss_usd')
            stop_loss_usd = float(stop_loss_usd_raw) if stop_loss_usd_raw is not None else self.max_loss_usd_max
            
            take_profit_usd_raw = position_params.get('take_profit_usd')
            take_profit_usd = float(take_profit_usd_raw) if take_profit_usd_raw is not None else self.target_profit_usd_max
            
            size_percent_raw = position_params.get('size_percent')
            size_percent = float(size_percent_raw) if size_percent_raw is not None else self.position_size_percent_max
            
            # Ogranicz parametry
            stop_loss_usd = max(self.max_loss_usd_min, min(self.max_loss_usd_max, stop_loss_usd))
            take_profit_usd = max(self.target_profit_usd_min, min(self.target_profit_usd_max, take_profit_usd))
            size_percent = max(self.position_size_percent_min, min(self.position_size_percent_max, size_percent))
            
            # Powód
            reason = data.get('reason', f'{action} signal from LLM')
            
            # Utwórz sygnał
            if action == 'LONG':
                signal_type = SignalType.BUY
            elif action == 'SHORT':
                signal_type = SignalType.SELL
            elif action == 'CLOSE':
                signal_type = SignalType.CLOSE
            else:
                # WAIT lub nieznana akcja
                return None
            
            signal = TradingSignal(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=entry_price,
                confidence=confidence,
                reason=reason,
                metadata={
                    'strategy': self.name,
                    'rsi_analysis': data.get('rsi_analysis', {}),
                    'price_movement': data.get('price_movement', {}),
                    'stop_loss_usd': stop_loss_usd,
                    'take_profit_usd': take_profit_usd,
                    'size_percent': size_percent
                }
            )
            
            return signal
            
        except json.JSONDecodeError as e:
            logger.error(f"Błąd parsowania JSON: {e}")
            logger.debug(f"Odpowiedź LLM: {response[:500]}")
            return None
        except Exception as e:
            logger.error(f"Błąd parsowania odpowiedzi LLM: {e}")
            return None
    
    def on_position_closed(self, position, pnl: float, reason: str):
        """Wywoływane gdy pozycja zostaje zamknięta."""
        self.last_close_time = datetime.now()
        logger.info(f"Pozycja zamknięta: PnL=${pnl:+,.2f}, powód: {reason}")

