"""
Funding Rate Arbitrage Strategy
================================
Strategia arbitrażu stopy finansowania dla kontraktów wieczystych (perpetual futures).

Zasada działania:
1. Monitorowanie stóp finansowania (funding rates) na dYdX
2. Gdy stopa finansowania jest dodatnia i wystarczająco wysoka:
   - Kupno aktywa na rynku spot (lub symulacja)
   - Zajęcie krótkiej pozycji na kontraktach wieczystych
3. Otrzymywanie płatności z tytułu stopy finansowania (co 8h)
4. Pozycja jest neutralna rynkowo (hedged)

Źródła:
- https://blog.biqutex.com/funding-rate-arbitrage/
- https://airdropalert.com/blogs/funding-rate-arbitrage-farming/
- https://sharpe.ai/blog/funding-rate-arbitrage
"""

from typing import Optional, Dict, List
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType


class FundingRateArbitrageStrategy(BaseStrategy):
    """
    Strategia arbitrażu stopy finansowania.
    
    Wykorzystuje dodatnie stopy finansowania kontraktów wieczystych
    do generowania zysków przy zerowym ryzyku rynkowym poprzez
    zajęcie pozycji neutralnej (long spot + short perpetual).
    
    Konfiguracja:
    - min_funding_rate: Minimalna stopa finansowania do otwarcia pozycji (% na 8h) - default 0.01%
    - target_funding_rate: Docelowa stopa finansowania (wysoka atrakcyjność) - default 0.05%
    - max_position_size: Maksymalny rozmiar pozycji jako % kapitału - default 50%
    - funding_interval_hours: Interwał płatności funding rate - default 8
    - min_holding_hours: Minimalny czas trzymania pozycji - default 24
    - use_spot_hedge: Czy hedgować pozycję na rynku spot - default True
    - max_leverage: Maksymalna dźwignia - default 2.0
    """
    
    name = "FundingRateArbitrage"
    description = "Arbitraż stopy finansowania kontraktów wieczystych"
    timeframe = "1h"  # Sprawdzanie co godzinę
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        
        # Domyślna konfiguracja
        self.min_funding_rate = self.config.get('min_funding_rate', 0.01)  # 0.01% na 8h
        self.target_funding_rate = self.config.get('target_funding_rate', 0.05)  # 0.05% na 8h
        self.max_position_size = self.config.get('max_position_size', 50.0)  # 50% kapitału
        self.funding_interval_hours = self.config.get('funding_interval_hours', 8)
        self.min_holding_hours = self.config.get('min_holding_hours', 24)
        self.use_spot_hedge = self.config.get('use_spot_hedge', True)
        self.max_leverage = self.config.get('max_leverage', 2.0)
        
        # DydxCollector do pobierania rzeczywistych funding rates (opcjonalnie)
        self.dydx_collector = self.config.get('dydx_collector', None)
        self.use_real_funding_rate = self.config.get('use_real_funding_rate', True) if self.dydx_collector else False
        
        logger.info(f"Strategia {self.name} zainicjalizowana z konfiguracją: {self.config}")
    
    def _calculate_annual_return(self, funding_rate: float) -> float:
        """
        Oblicza roczny zwrot na podstawie stopy finansowania.
        
        Args:
            funding_rate: Stopa finansowania w % (na jeden interwał, np. 8h)
        
        Returns:
            Szacowany roczny zwrot w %
        """
        # Liczba interwałów w roku
        intervals_per_year = (365 * 24) / self.funding_interval_hours
        
        # Prosty zwrot roczny (zakładając stałą stopę)
        annual_return = funding_rate * intervals_per_year
        
        return annual_return
    
    def _get_funding_rate(self, df: pd.DataFrame, symbol: str = "BTC-USD") -> Optional[float]:
        """
        Pobiera aktualną stopę finansowania.
        
        Próbuje pobrać rzeczywisty funding rate z dYdX API.
        Zgodnie z zasadą projektu: NIE używamy symulowanych danych.
        Jeśli nie ma rzeczywistych danych, zwraca None.
        
        Args:
            df: DataFrame z danymi OHLCV
            symbol: Symbol instrumentu
        
        Returns:
            Stopa finansowania w % (lub None jeśli niedostępna)
        """
        # Próba pobrania rzeczywistego funding rate z dYdX
        if self.use_real_funding_rate and self.dydx_collector:
            try:
                ticker_data = self.dydx_collector.get_ticker(symbol)
                next_funding_rate = ticker_data.get('next_funding_rate', None)
                
                if next_funding_rate is not None:
                    # Funding rate z dYdX jest w formacie dziesiętnym (np. 0.0001 = 0.01%)
                    # Konwertuj na procent
                    funding_rate_percent = float(next_funding_rate) * 100
                    logger.debug(f"[FUNDING] Rzeczywisty funding rate z dYdX: {funding_rate_percent:.4f}%")
                    return funding_rate_percent
            except Exception as e:
                logger.warning(f"[FUNDING] Nie udało się pobrać funding rate z dYdX: {e}")
        
        # Zgodnie z zasadą projektu: NIE używamy symulowanych danych
        # Jeśli nie mamy rzeczywistych danych, zwracamy None
        logger.warning("[FUNDING] Brak rzeczywistych danych funding rate - zwracam None (zgodnie z zasadą projektu)")
        return None
    
    def _calculate_position_confidence(
        self,
        funding_rate: float,
        volatility: float,
        liquidity_score: float = 1.0
    ) -> float:
        """
        Oblicza pewność sygnału (0-10) na podstawie różnych czynników.
        
        Args:
            funding_rate: Stopa finansowania w %
            volatility: Zmienność rynku w %
            liquidity_score: Wskaźnik płynności (0-1)
        
        Returns:
            Confidence (0-10)
        """
        confidence = 0.0
        
        # Funding rate (0-5 punktów)
        # Im wyższy funding rate, tym lepiej
        if funding_rate >= self.target_funding_rate:
            confidence += 5.0
        elif funding_rate >= self.min_funding_rate:
            # Liniowa skala między min a target
            ratio = (funding_rate - self.min_funding_rate) / (self.target_funding_rate - self.min_funding_rate)
            confidence += 2.5 + (ratio * 2.5)
        
        # Volatility (0-2 punkty)
        # Preferuj niską zmienność (mniejsze ryzyko)
        if volatility < 1.0:
            confidence += 2.0
        elif volatility < 2.0:
            confidence += 1.0
        elif volatility < 3.0:
            confidence += 0.5
        
        # Liquidity (0-3 punkty)
        confidence += liquidity_score * 3.0
        
        return min(10.0, confidence)
    
    def _calculate_volatility(self, df: pd.DataFrame, period: int = 24) -> float:
        """
        Oblicza zmienność (volatility) jako odchylenie standardowe zmian cen.
        
        Args:
            df: DataFrame z danymi OHLCV
            period: Okres do obliczenia zmienności
        
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
    
    def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD") -> Optional[TradingSignal]:
        """
        Analizuje dane i generuje sygnały arbitrażowe.
        
        Sygnał LONG (BUY) = Otwórz pozycję arbitrażową (short perp + long spot)
        Sygnał SHORT (SELL) = Zamknij pozycję arbitrażową
        
        Args:
            df: DataFrame z danymi OHLCV
            symbol: Symbol instrumentu
        
        Returns:
            TradingSignal lub None
        """
        if len(df) < 50:
            logger.debug(f"[FUNDING] Za mało danych: {len(df)} < 50")
            return None
        
        current_price = float(df['close'].iloc[-1])
        
        # Pobierz funding rate
        funding_rate = self._get_funding_rate(df, symbol)
        
        if funding_rate is None:
            logger.debug(f"[FUNDING] Brak danych o funding rate")
            return None
        
        logger.debug(f"[FUNDING] Funding rate: {funding_rate:.4f}% na {self.funding_interval_hours}h")
        
        # Oblicz roczny zwrot
        annual_return = self._calculate_annual_return(funding_rate)
        logger.debug(f"[FUNDING] Szacowany roczny zwrot: {annual_return:.2f}%")
        
        # Sprawdź czy funding rate jest wystarczająco wysoki
        if funding_rate < self.min_funding_rate:
            logger.debug(
                f"[FUNDING] Funding rate {funding_rate:.4f}% < min {self.min_funding_rate:.4f}%"
            )
            return None
        
        # Oblicz metryki
        volatility = self._calculate_volatility(df)
        liquidity_score = 1.0  # W rzeczywistości należy pobrać z API
        
        # Oblicz confidence
        confidence = self._calculate_position_confidence(
            funding_rate, volatility, liquidity_score
        )
        
        logger.debug(
            f"[FUNDING] Confidence: {confidence:.1f}, Volatility: {volatility:.2f}%, "
            f"Funding: {funding_rate:.4f}%"
        )
        
        # Generuj sygnał jeśli confidence jest wystarczający
        if confidence >= 3.0:
            # Oblicz rozmiar pozycji
            # W rzeczywistej implementacji należy uwzględnić dostępny kapitał
            position_size_pct = min(self.max_position_size, confidence * 5)
            
            # Oblicz stop loss i take profit
            # Dla strategii arbitrażowej nie ma klasycznego SL/TP
            # Zamykamy pozycję gdy funding rate spada poniżej minimum
            # lub po osiągnięciu minimalnego czasu trzymania
            
            # Stop loss: zamknij gdy funding rate spadnie poniżej 50% minimum
            # (chronienie przed ujemnym funding rate)
            stop_loss = None  # Nie ma tradycyjnego SL w tej strategii
            
            # Take profit: zamknij gdy funding rate spadnie znacząco
            # lub po określonym czasie
            take_profit = None  # Nie ma tradycyjnego TP w tej strategii
            
            reason = (
                f"Funding Rate Arbitrage: {funding_rate:.4f}% na {self.funding_interval_hours}h "
                f"(~{annual_return:.1f}% rocznie), volatility: {volatility:.2f}%, "
                f"position_size: {position_size_pct:.1f}%"
            )
            
            # Sygnał BUY oznacza: otwórz pozycję arbitrażową
            # (w praktyce: short perp + long spot)
            return TradingSignal(
                signal_type=SignalType.BUY,
                symbol=symbol,
                confidence=float(round(confidence, 1)),
                price=float(current_price),
                stop_loss=float(current_price * 0.95) if stop_loss is None else stop_loss,  # Safety stop
                take_profit=float(current_price * 1.05) if take_profit is None else take_profit,  # Safety target
                reason=reason,
                strategy=self.name
            )
        
        return None
    
    def should_close_position(
        self,
        df: pd.DataFrame,
        entry_price: float,
        side: str,
        current_pnl_percent: float,
        entry_time: Optional[datetime] = None
    ) -> Optional[TradingSignal]:
        """
        Sprawdza czy należy zamknąć pozycję arbitrażową.
        
        Zamykamy pozycję gdy:
        1. Funding rate spadł poniżej minimum
        2. Minął minimalny czas trzymania i funding rate się pogorszył
        3. Wystąpiło duże odchylenie ceny (ryzyko likwidacji)
        
        Args:
            df: DataFrame z danymi OHLCV
            entry_price: Cena wejścia
            side: Strona pozycji ("long" lub "short")
            current_pnl_percent: Aktualny PnL w %
            entry_time: Czas otwarcia pozycji
        
        Returns:
            TradingSignal typu CLOSE lub None
        """
        if len(df) < 20:
            return None
        
        current_price = float(df['close'].iloc[-1])
        
        # Pobierz aktualny funding rate
        funding_rate = self._get_funding_rate(df)
        
        if funding_rate is None:
            return None
        
        # Sprawdź czas trzymania pozycji
        holding_hours = 0
        if entry_time:
            holding_hours = (datetime.now() - entry_time).total_seconds() / 3600
        
        # Powody zamknięcia:
        
        # 1. Funding rate spadł poniżej 50% minimum
        if funding_rate < self.min_funding_rate * 0.5:
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol="",
                confidence=8.0,
                price=float(current_price),
                reason=f"Funding rate spadł do {funding_rate:.4f}% (< {self.min_funding_rate * 0.5:.4f}%)",
                strategy=self.name
            )
        
        # 2. Funding rate stał się ujemny (płacimy zamiast otrzymywać)
        if funding_rate < 0:
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol="",
                confidence=9.0,
                price=float(current_price),
                reason=f"Funding rate ujemny: {funding_rate:.4f}%",
                strategy=self.name
            )
        
        # 3. Minął minimalny czas i funding rate się pogorszył
        if holding_hours >= self.min_holding_hours:
            if funding_rate < self.min_funding_rate:
                return TradingSignal(
                    signal_type=SignalType.CLOSE,
                    symbol="",
                    confidence=7.0,
                    price=float(current_price),
                    reason=f"Minął min. czas ({holding_hours:.1f}h) i funding rate spadł do {funding_rate:.4f}%",
                    strategy=self.name
                )
        
        # 4. Duże odchylenie ceny (ryzyko likwidacji pozycji short perp)
        # Dla pozycji arbitrażowej, odchylenia cenowe są hedgowane,
        # ale ekstremalne ruchy mogą powodować problemy z marginem
        price_change_pct = abs((current_price - entry_price) / entry_price * 100)
        if price_change_pct > 10.0:  # 10% odchylenie
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol="",
                confidence=9.0,
                price=float(current_price),
                reason=f"Duże odchylenie ceny: {price_change_pct:.1f}% (ryzyko likwidacji)",
                strategy=self.name
            )
        
        return None


# Przykład użycia
if __name__ == "__main__":
    strategy = FundingRateArbitrageStrategy({
        'min_funding_rate': 0.01,  # 0.01% na 8h
        'target_funding_rate': 0.05,  # 0.05% na 8h
        'max_position_size': 50.0,  # 50% kapitału
        'funding_interval_hours': 8,
        'min_holding_hours': 24
    })
    print(f"Strategia: {strategy.name}")
    print(f"Opis: {strategy.description}")
    print(f"\nPrzykładowe zwroty:")
    for rate in [0.01, 0.03, 0.05, 0.10]:
        annual = strategy._calculate_annual_return(rate)
        print(f"  {rate:.2f}% na 8h → {annual:.1f}% rocznie")

