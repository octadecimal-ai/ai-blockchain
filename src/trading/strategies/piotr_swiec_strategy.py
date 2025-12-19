"""
Strategia Piotra Święsa
========================
Strategia oparta na impulsach cenowych i RSI.

Główne założenia:
- Wejście po gwałtownym ruchu (impulsie) w kierunku przeciwnym
- RSI > 70: rynek wykupiony -> preferuj SHORT
- RSI < 30: rynek wyprzedany -> preferuj LONG
- Krótkie trade'y z określonym target zysku i max stratą w USD
- Cooldown po zamknięciu pozycji

Autor: AI Assistant na podstawie strategii Piotra Święsa
Data: 2025-12-13
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType


class PiotrSwiecStrategy(BaseStrategy):
    """
    Strategia Piotra Święsa - trading na impulsach z RSI.
    
    Założenia:
    1. RSI > 70 + impuls wzrostowy -> SELL (SHORT)
    2. RSI < 30 + impuls spadkowy -> BUY (LONG)
    3. Target zysku i max straty w USD
    4. Cooldown między transakcjami
    """
    
    name = "PiotrSwiecStrategy"
    description = "Strategia impulsowa Piotra Święsa z RSI"
    timeframe = "5min"  # Krótki timeframe dla szybkich transakcji
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        
        # Parametry RSI
        self.rsi_period = self.config.get('rsi_period', 14)
        self.rsi_overbought = self.config.get('rsi_overbought', 70)  # Wykupienie
        self.rsi_oversold = self.config.get('rsi_oversold', 30)      # Wyprzedanie
        
        # Parametry ATR
        self.atr_period = self.config.get('atr_period', 14)
        
        # Parametry impulsu
        self.impulse_lookback = self.config.get('impulse_lookback', 4)  # Ile świec wstecz
        self.impulse_threshold_pct = self.config.get('impulse_threshold_pct', 0.8)  # Min % zmiany
        self.impulse_atr_mult = self.config.get('impulse_atr_mult', 2.0)  # Alternatywnie: mnożnik ATR
        self.use_atr_for_impulse = self.config.get('use_atr_for_impulse', False)  # Czy użyć ATR
        
        # Parametry zysku/straty w USD
        self.target_profit_usd = self.config.get('target_profit_usd', 500.0)
        self.max_loss_usd = self.config.get('max_loss_usd', 500.0)
        
        # Czasowe ograniczenia
        self.max_hold_seconds = self.config.get('max_hold_seconds', 900)  # 15 min
        self.cooldown_seconds = self.config.get('cooldown_seconds', 120)  # 2 min cooldown
        
        # Slippage
        self.slippage_percent = self.config.get('slippage_percent', 0.1)
        
        # Confidence
        self.min_confidence_for_trade = self.config.get('min_confidence_for_trade', 8.0)
        
        # Position sizing
        self.position_size_btc = self.config.get('position_size_btc', 0.1)  # Domyślnie 0.1 BTC
        self.use_fixed_size = self.config.get('use_fixed_size', True)
        
        # Tracking
        self.last_close_time: Optional[datetime] = None
        self.paper_trading_engine = None
        
        logger.info(f"Strategia {self.name} zainicjalizowana:")
        logger.info(f"   RSI period: {self.rsi_period}, Overbought: {self.rsi_overbought}, Oversold: {self.rsi_oversold}")
        logger.info(f"   Impulse: lookback={self.impulse_lookback}, threshold={self.impulse_threshold_pct}%")
        logger.info(f"   Target: ${self.target_profit_usd}, Max Loss: ${self.max_loss_usd}")
        logger.info(f"   Max hold: {self.max_hold_seconds}s, Cooldown: {self.cooldown_seconds}s")
    
    def set_paper_trading_engine(self, engine):
        """Ustawia referencję do paper trading engine."""
        self.paper_trading_engine = engine
        logger.debug("Paper trading engine ustawiony")
    
    # ========================================
    # OBLICZANIE WSKAŹNIKÓW
    # ========================================
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Oblicza RSI (Relative Strength Index)."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        # Unikaj dzielenia przez zero
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)  # Domyślnie neutralne RSI
    
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
    
    def _detect_impulse(self, df: pd.DataFrame, atr: Optional[pd.Series] = None) -> Dict[str, Any]:
        """
        Wykrywa impuls cenowy.
        
        Impuls to gwałtowny ruch w jedną stronę.
        
        Returns:
            {
                'detected': bool,
                'direction': 'up' | 'down' | None,
                'magnitude_pct': float,
                'magnitude_atr': float
            }
        """
        if len(df) < self.impulse_lookback + 1:
            return {'detected': False, 'direction': None, 'magnitude_pct': 0, 'magnitude_atr': 0}
        
        close = df['close']
        current_close = float(close.iloc[-1])
        lookback_close = float(close.iloc[-self.impulse_lookback - 1])
        
        # Oblicz zmianę procentową
        price_change_pct = ((current_close - lookback_close) / lookback_close) * 100
        
        # Oblicz zmianę w ATR (jeśli dostępne)
        magnitude_atr = 0
        if atr is not None and not atr.empty:
            current_atr = float(atr.iloc[-1])
            if current_atr > 0:
                magnitude_atr = abs(current_close - lookback_close) / current_atr
        
        # Sprawdź czy wykryto impuls
        detected = False
        direction = None
        
        if self.use_atr_for_impulse and magnitude_atr > 0:
            # Użyj ATR do wykrycia impulsu
            if magnitude_atr >= self.impulse_atr_mult:
                detected = True
                direction = 'up' if price_change_pct > 0 else 'down'
        else:
            # Użyj procentu do wykrycia impulsu
            if abs(price_change_pct) >= self.impulse_threshold_pct:
                detected = True
                direction = 'up' if price_change_pct > 0 else 'down'
        
        return {
            'detected': detected,
            'direction': direction,
            'magnitude_pct': round(price_change_pct, 3),
            'magnitude_atr': round(magnitude_atr, 2)
        }
    
    # ========================================
    # SPRAWDZANIE POZYCJI
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
        seconds_open = (datetime.now() - position.opened_at).total_seconds()
        
        # Oblicz PnL w USD (przybliżenie na podstawie size i leverage)
        position_value = position.size * current_price
        pnl_usd = pnl  # pnl już jest w USD
        
        return {
            'position': position,
            'side': position.side.value,  # 'long' lub 'short'
            'entry_price': position.entry_price,
            'current_price': current_price,
            'size': position.size,
            'pnl': pnl,
            'pnl_usd': pnl_usd,
            'pnl_percent': pnl_percent,
            'seconds_open': seconds_open,
            'stop_loss': position.stop_loss,
            'take_profit': position.take_profit
        }
    
    def _is_in_cooldown(self) -> bool:
        """Sprawdza czy jesteśmy w okresie cooldown."""
        if self.last_close_time is None:
            return False
        
        elapsed = (datetime.now() - self.last_close_time).total_seconds()
        return elapsed < self.cooldown_seconds
    
    # ========================================
    # OBLICZANIE STOP LOSS / TAKE PROFIT
    # ========================================
    
    def _calculate_sl_tp(self, current_price: float, side: str, size: float) -> Dict[str, float]:
        """
        Oblicza Stop Loss i Take Profit na podstawie target USD i max loss USD.
        
        Uwzględnia slippage.
        """
        # Oblicz zmianę ceny potrzebną do osiągnięcia target/loss
        # PnL = size * (exit_price - entry_price) dla LONG
        # PnL = size * (entry_price - exit_price) dla SHORT
        
        if size <= 0:
            size = self.position_size_btc
        
        # Uwzględnij slippage
        slippage_factor = 1 + (self.slippage_percent / 100)
        
        if side.lower() == 'long':
            # LONG: TP wyżej, SL niżej
            tp_price_change = self.target_profit_usd / size
            sl_price_change = self.max_loss_usd / size
            
            take_profit = current_price + tp_price_change / slippage_factor  # Mniej ambitny TP
            stop_loss = current_price - sl_price_change * slippage_factor    # Bliższy SL
        else:
            # SHORT: TP niżej, SL wyżej
            tp_price_change = self.target_profit_usd / size
            sl_price_change = self.max_loss_usd / size
            
            take_profit = current_price - tp_price_change / slippage_factor
            stop_loss = current_price + sl_price_change * slippage_factor
        
        return {
            'take_profit': round(take_profit, 2),
            'stop_loss': round(stop_loss, 2)
        }
    
    # ========================================
    # GŁÓWNA ANALIZA
    # ========================================
    
    def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD") -> Optional[TradingSignal]:
        """
        Analizuje dane i generuje sygnał.
        
        Logika:
        1. Jeśli mamy otwartą pozycję -> sprawdź warunki wyjścia
        2. Jeśli nie mamy pozycji i nie jesteśmy w cooldown -> szukaj wejścia
        """
        if df is None or df.empty:
            logger.warning(f"Brak danych dla {symbol}")
            return None
        
        if len(df) < max(self.rsi_period, self.atr_period, self.impulse_lookback) + 5:
            logger.debug(f"Za mało danych ({len(df)} świec)")
            return None
        
        # Oblicz wskaźniki
        close = df['close']
        current_price = float(close.iloc[-1])
        
        rsi = self._calculate_rsi(close, self.rsi_period)
        current_rsi = float(rsi.iloc[-1])
        
        atr = self._calculate_atr(df, self.atr_period)
        current_atr = float(atr.iloc[-1]) if not atr.empty else 0
        
        impulse = self._detect_impulse(df, atr)
        
        # Log stanu
        logger.debug(
            f"[{self.name}] {symbol}: RSI={current_rsi:.1f}, "
            f"ATR=${current_atr:.2f}, "
            f"Impulse={impulse['detected']} ({impulse['direction']}, {impulse['magnitude_pct']:.2f}%)"
        )
        
        # Sprawdź czy mamy otwartą pozycję
        position_info = self._get_current_position(symbol)
        
        if position_info:
            # Mamy pozycję - sprawdź warunki wyjścia
            return self._check_exit_conditions(position_info, current_price, current_rsi, symbol)
        else:
            # Nie mamy pozycji - sprawdź warunki wejścia
            return self._check_entry_conditions(
                symbol, current_price, current_rsi, impulse, current_atr
            )
    
    def _check_entry_conditions(
        self,
        symbol: str,
        current_price: float,
        current_rsi: float,
        impulse: Dict[str, Any],
        current_atr: float
    ) -> Optional[TradingSignal]:
        """Sprawdza warunki wejścia w pozycję."""
        
        # Sprawdź cooldown
        if self._is_in_cooldown():
            remaining = self.cooldown_seconds - (datetime.now() - self.last_close_time).total_seconds()
            logger.debug(f"W cooldown, pozostało {remaining:.0f}s")
            return None
        
        # Sprawdź czy wykryto impuls
        if not impulse['detected']:
            logger.debug("Brak impulsu - HOLD")
            return None
        
        signal_type = None
        reason = ""
        
        # RSI > 70 + impuls wzrostowy -> SELL (SHORT)
        # Logika: po impulsie wzrostowym przy wykupionym rynku, spodziewamy się korekty
        if current_rsi > self.rsi_overbought and impulse['direction'] == 'up':
            signal_type = SignalType.SELL
            reason = f"RSI={current_rsi:.1f} > {self.rsi_overbought} (wykupiony) + impuls UP ({impulse['magnitude_pct']:.2f}%) -> SHORT"
        
        # RSI < 30 + impuls spadkowy -> BUY (LONG)
        # Logika: po impulsie spadkowym przy wyprzedanym rynku, spodziewamy się odbicia
        elif current_rsi < self.rsi_oversold and impulse['direction'] == 'down':
            signal_type = SignalType.BUY
            reason = f"RSI={current_rsi:.1f} < {self.rsi_oversold} (wyprzedany) + impuls DOWN ({impulse['magnitude_pct']:.2f}%) -> LONG"
        
        if signal_type is None:
            logger.debug(f"Brak sygnału: RSI={current_rsi:.1f}, Impulse={impulse['direction']}")
            return None
        
        # Oblicz SL/TP
        side = 'long' if signal_type == SignalType.BUY else 'short'
        sl_tp = self._calculate_sl_tp(current_price, side, self.position_size_btc)
        
        # Log decyzję
        logger.info(f"🎯 [{self.name}] SYGNAŁ: {signal_type.value.upper()}")
        logger.info(f"   RSI: {current_rsi:.1f}, Impuls: {impulse['direction']} ({impulse['magnitude_pct']:.2f}%)")
        logger.info(f"   Cena: ${current_price:,.2f}")
        logger.info(f"   TP: ${sl_tp['take_profit']:,.2f} (+${self.target_profit_usd})")
        logger.info(f"   SL: ${sl_tp['stop_loss']:,.2f} (-${self.max_loss_usd})")
        logger.info(f"   Powód: {reason}")
        
        return TradingSignal(
            signal_type=signal_type,
            symbol=symbol,
            confidence=self.min_confidence_for_trade,
            price=current_price,
            stop_loss=sl_tp['stop_loss'],
            take_profit=sl_tp['take_profit'],
            size_percent=15.0,  # Lub można obliczyć na podstawie position_size_btc
            reason=reason,
            strategy=self.name
        )
    
    def _check_exit_conditions(
        self,
        position_info: Dict[str, Any],
        current_price: float,
        current_rsi: float,
        symbol: str
    ) -> Optional[TradingSignal]:
        """Sprawdza warunki wyjścia z pozycji."""
        
        pnl_usd = position_info['pnl_usd']
        seconds_open = position_info['seconds_open']
        side = position_info['side']
        
        # 1. Take Profit - osiągnięto target zysku
        if pnl_usd >= self.target_profit_usd:
            self.last_close_time = datetime.now()
            reason = f"TARGET PROFIT: +${pnl_usd:.2f} >= ${self.target_profit_usd}"
            logger.success(f"🎉 [{self.name}] {reason}")
            
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=current_price,
                reason=reason,
                strategy=self.name
            )
        
        # 2. Stop Loss - przekroczono max stratę
        if pnl_usd <= -self.max_loss_usd:
            self.last_close_time = datetime.now()
            reason = f"STOP LOSS: ${pnl_usd:.2f} <= -${self.max_loss_usd}"
            logger.warning(f"🛑 [{self.name}] {reason}")
            
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=current_price,
                reason=reason,
                strategy=self.name
            )
        
        # 3. Timeout + brak zysku (sideways exit)
        if seconds_open >= self.max_hold_seconds:
            # Zamknij tylko jeśli PnL jest blisko zera lub ujemny
            if pnl_usd < self.target_profit_usd * 0.3:  # Mniej niż 30% target
                self.last_close_time = datetime.now()
                reason = f"TIMEOUT: {seconds_open:.0f}s >= {self.max_hold_seconds}s, PnL=${pnl_usd:.2f} (sideways)"
                logger.info(f"⏰ [{self.name}] {reason}")
                
                return TradingSignal(
                    signal_type=SignalType.CLOSE,
                    symbol=symbol,
                    confidence=8.0,
                    price=current_price,
                    reason=reason,
                    strategy=self.name
                )
        
        # 4. RSI reversal - opcjonalne wyjście gdy RSI się odwraca
        # LONG przy RSI > 70 -> zamknij
        if side == 'long' and current_rsi > self.rsi_overbought and pnl_usd > 0:
            self.last_close_time = datetime.now()
            reason = f"RSI REVERSAL: LONG przy RSI={current_rsi:.1f} > {self.rsi_overbought}, PnL=${pnl_usd:.2f}"
            logger.info(f"📊 [{self.name}] {reason}")
            
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=7.0,
                price=current_price,
                reason=reason,
                strategy=self.name
            )
        
        # SHORT przy RSI < 30 -> zamknij
        if side == 'short' and current_rsi < self.rsi_oversold and pnl_usd > 0:
            self.last_close_time = datetime.now()
            reason = f"RSI REVERSAL: SHORT przy RSI={current_rsi:.1f} < {self.rsi_oversold}, PnL=${pnl_usd:.2f}"
            logger.info(f"📊 [{self.name}] {reason}")
            
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=7.0,
                price=current_price,
                reason=reason,
                strategy=self.name
            )
        
        # Brak sygnału zamknięcia - HOLD
        logger.debug(
            f"[{self.name}] HOLD: {side.upper()} PnL=${pnl_usd:.2f}, "
            f"open {seconds_open:.0f}s, RSI={current_rsi:.1f}"
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
        Metoda wywoływana przez TradingBot do sprawdzenia wyjścia.
        
        Deleguje do _check_exit_conditions jeśli mamy pozycję.
        """
        if df is None or df.empty:
            return None
        
        symbol = getattr(self, '_current_symbol', 'BTC-USD')
        current_price = float(df['close'].iloc[-1])
        
        position_info = self._get_current_position(symbol)
        if not position_info:
            return None
        
        # Oblicz RSI
        rsi = self._calculate_rsi(df['close'], self.rsi_period)
        current_rsi = float(rsi.iloc[-1])
        
        return self._check_exit_conditions(position_info, current_price, current_rsi, symbol)


# ========================================
# TESTY
# ========================================

if __name__ == "__main__":
    """Prosty test strategii."""
    import sys
    from loguru import logger
    
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")
    
    # Utwórz strategię z domyślnymi parametrami
    strategy = PiotrSwiecStrategy({
        'rsi_period': 14,
        'impulse_lookback': 4,
        'impulse_threshold_pct': 0.8,
        'target_profit_usd': 500,
        'max_loss_usd': 500
    })
    
    # Symulowane dane
    # Test 1: RSI > 70 + impuls UP -> powinien być SELL
    print("\n=== TEST 1: RSI > 70 + impuls UP ===")
    df_test1 = pd.DataFrame({
        'open': [100000, 100100, 100200, 100300, 100500, 100800, 101200, 101600, 102000],
        'high': [100150, 100200, 100350, 100500, 100700, 101000, 101400, 101800, 102200],
        'low': [99900, 100000, 100100, 100200, 100400, 100700, 101100, 101500, 101900],
        'close': [100100, 100200, 100300, 100500, 100600, 100900, 101300, 101700, 102100],
        'volume': [100] * 9
    })
    # Symuluj wysokie RSI (dodając więcej wzrostów)
    for i in range(10):
        df_test1 = pd.concat([df_test1, pd.DataFrame({
            'open': [102100 + i*100],
            'high': [102200 + i*100],
            'low': [102000 + i*100],
            'close': [102150 + i*100],
            'volume': [100]
        })], ignore_index=True)
    
    signal = strategy.analyze(df_test1, "BTC-USD")
    if signal:
        print(f"Sygnał: {signal.signal_type.value.upper()}, Powód: {signal.reason}")
    else:
        print("Brak sygnału (może brakować danych do RSI/impulsu)")
    
    print("\n=== TEST 2: RSI < 30 + impuls DOWN ===")
    # Symulowane dane dla spadku
    df_test2 = pd.DataFrame({
        'open': [100000, 99900, 99700, 99500, 99200, 98900, 98500, 98100, 97700],
        'high': [100100, 100000, 99800, 99600, 99300, 99000, 98600, 98200, 97800],
        'low': [99800, 99700, 99500, 99300, 99000, 98700, 98300, 97900, 97500],
        'close': [99900, 99700, 99500, 99200, 98900, 98500, 98100, 97700, 97300],
        'volume': [100] * 9
    })
    for i in range(10):
        df_test2 = pd.concat([df_test2, pd.DataFrame({
            'open': [97300 - i*100],
            'high': [97400 - i*100],
            'low': [97200 - i*100],
            'close': [97250 - i*100],
            'volume': [100]
        })], ignore_index=True)
    
    signal = strategy.analyze(df_test2, "BTC-USD")
    if signal:
        print(f"Sygnał: {signal.signal_type.value.upper()}, Powód: {signal.reason}")
    else:
        print("Brak sygnału (może brakować danych do RSI/impulsu)")
    
    print("\n✅ Testy zakończone")

