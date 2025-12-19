"""
Piotr Swiec Prompt Strategy
============================
Strategia Piotra Święsa oparta na LLM.

Główne założenia:
- RSI > 70 + gwałtowny ruch UP -> SHORT
- RSI < 30 + gwałtowny ruch DOWN -> LONG
- Używa LLM do podejmowania decyzji z kontekstem RSI i ruchu ceny
- Krótki timeframe (5min) z szybkim sprawdzaniem
- Stały rozmiar pozycji i SL/TP w USD

Autor: AI Assistant na podstawie strategii Piotra Święsa
Data: 2025-12-13
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


class PiotrSwiecPromptStrategy(BaseStrategy):
    """
    Strategia Piotra Święsa oparta na LLM.
    
    Kluczowe cechy:
    - Wykrywa przekroczenie RSI progu 70/30
    - Wykrywa gwałtowne ruchy ceny
    - Wysyła kontekst do LLM który podejmuje decyzję
    - Stały rozmiar pozycji (~1 BTC lub 15-20% kapitału)
    - SL/TP w USD zamiast procentów
    """
    
    name = "PiotrSwiecPromptStrategy"
    description = "Strategia Piotra Święsa z LLM - RSI + gwałtowne ruchy"
    timeframe = "5min"  # Krótki timeframe dla szybkich decyzji
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        
        # Ścieżka do promptu
        self.prompt_file = self.config.get('prompt_file', 'prompts/trading/piotr_swiec_method.txt')
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
        
        # Parametry RSI
        self.rsi_period = self.config.get('rsi_period', 14)
        self.rsi_overbought = self.config.get('rsi_overbought', 70)
        self.rsi_oversold = self.config.get('rsi_oversold', 30)
        
        # Parametry gwałtowności ruchu
        self.sharp_move_lookback = self.config.get('sharp_move_lookback', 5)  # świec wstecz
        self.sharp_move_threshold = self.config.get('sharp_move_threshold', 0.8)  # %
        
        # Parametry pozycji
        self.target_profit_usd = self.config.get('target_profit_usd', 800.0)
        self.max_loss_usd = self.config.get('max_loss_usd', 500.0)
        self.position_size_percent = self.config.get('position_size_percent', 15.0)
        
        # Parametry czasowe
        self.max_hold_minutes = self.config.get('max_hold_minutes', 15)
        self.cooldown_minutes = self.config.get('cooldown_minutes', 2)
        
        # Tracking
        self.last_close_time: Optional[datetime] = None
        self.paper_trading_engine = None
        self.rsi_history: List[float] = []  # Historia RSI do analizy crossing
        
        # Kontekst sesji
        self.session_context: Dict[str, Any] = {}
        
        # DydX Collector do pobierania danych rynkowych
        self.dydx_collector = DydxCollector(testnet=False)
        
        logger.info(f"Strategia {self.name} zainicjalizowana:")
        logger.info(f"   Prompt: {self.prompt_file}")
        logger.info(f"   RSI: {self.rsi_period} (overbought: {self.rsi_overbought}, oversold: {self.rsi_oversold})")
        logger.info(f"   Sharp move: {self.sharp_move_threshold}% w {self.sharp_move_lookback} świecach")
        logger.info(f"   Target: ${self.target_profit_usd}, Max Loss: ${self.max_loss_usd}")
    
    def set_session_context(self, context: Dict[str, Any]):
        """Ustawia kontekst sesji."""
        self.session_context = context
        logger.debug(f"Kontekst sesji ustawiony: {context}")
    
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
        
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)
    
    def _detect_rsi_cross(self, rsi_values: pd.Series) -> Dict[str, Any]:
        """
        Wykrywa czy RSI WŁAŚNIE przekroczyło próg 70 lub 30.
        
        Returns:
            Dict z informacjami o przekroczeniu
        """
        if len(rsi_values) < 2:
            return {
                'crossed_70': False,
                'crossed_30': False,
                'currently_above_70': False,
                'currently_below_30': False,
                'candles_above_70': 0,
                'candles_below_30': 0,
                'strong_short_signal': False,
                'strong_long_signal': False
            }
        
        current = float(rsi_values.iloc[-1])
        previous = float(rsi_values.iloc[-2])
        
        # Policz ile świec RSI jest powyżej/poniżej progu
        last_10 = rsi_values.tail(10)
        candles_above_70 = int((last_10 > self.rsi_overbought).sum())
        candles_below_30 = int((last_10 < self.rsi_oversold).sum())
        
        result = {
            'current_rsi': round(current, 1),
            'previous_rsi': round(previous, 1),
            'crossed_70': current > self.rsi_overbought and previous <= self.rsi_overbought,
            'crossed_30': current < self.rsi_oversold and previous >= self.rsi_oversold,
            'currently_above_70': current > self.rsi_overbought,
            'currently_below_30': current < self.rsi_oversold,
            'candles_above_70': candles_above_70,
            'candles_below_30': candles_below_30,
        }
        
        # Sygnał jest silny tylko gdy przekroczenie było NIEDAWNO (1-3 świece)
        result['strong_short_signal'] = result['crossed_70'] or (
            result['currently_above_70'] and result['candles_above_70'] <= 3
        )
        result['strong_long_signal'] = result['crossed_30'] or (
            result['currently_below_30'] and result['candles_below_30'] <= 3
        )
        
        return result
    
    def _detect_sharp_move(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Wykrywa czy nastąpił gwałtowny ruch ceny.
        
        Returns:
            Dict z informacjami o ruchu
        """
        if len(df) < self.sharp_move_lookback:
            return {
                'is_sharp': False,
                'percent_change': 0.0,
                'direction': 'SIDEWAYS'
            }
        
        recent = df.tail(self.sharp_move_lookback)
        price_start = float(recent['open'].iloc[0])
        price_end = float(recent['close'].iloc[-1])
        
        percent_change = ((price_end - price_start) / price_start) * 100
        
        # Gwałtowny ruch = przekroczenie progu
        is_sharp = abs(percent_change) >= self.sharp_move_threshold
        
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
            'side': position.side.value,  # 'long' lub 'short'
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
    # BUDOWANIE PROMPTU
    # ========================================
    
    def _build_prompt(
        self,
        symbol: str,
        current_price: float,
        rsi_data: Dict[str, Any],
        sharp_move: Dict[str, Any],
        position_info: Optional[Dict[str, Any]],
        market_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Buduje prompt dla LLM z obliczonymi danymi RSI i sharp move.
        """
        # Kontekst sesji
        context_text = f"""
=== KONTEKST SESJI ===
Kapitał początkowy: ${self.session_context.get('balance', 10000):,.2f}
Max strata na pozycję: ${self.max_loss_usd}
Target zysku: ${self.target_profit_usd}
"""
        
        # Dane RSI
        rsi_text = f"""
=== ANALIZA RSI ===
Aktualny RSI(14): {rsi_data.get('current_rsi', 50):.1f}
Poprzedni RSI: {rsi_data.get('previous_rsi', 50):.1f}
Przekroczył 70: {"TAK" if rsi_data.get('crossed_70') else "NIE"}
Spadł poniżej 30: {"TAK" if rsi_data.get('crossed_30') else "NIE"}
Aktualnie >70: {"TAK" if rsi_data.get('currently_above_70') else "NIE"}
Aktualnie <30: {"TAK" if rsi_data.get('currently_below_30') else "NIE"}
Świec powyżej 70 (ostatnie 10): {rsi_data.get('candles_above_70', 0)}
Świec poniżej 30 (ostatnie 10): {rsi_data.get('candles_below_30', 0)}
Silny sygnał SHORT: {"TAK" if rsi_data.get('strong_short_signal') else "NIE"}
Silny sygnał LONG: {"TAK" if rsi_data.get('strong_long_signal') else "NIE"}
"""
        
        # Gwałtowność ruchu
        sharp_text = f"""
=== ANALIZA RUCHU CENY ===
Gwałtowny ruch: {"TAK" if sharp_move.get('is_sharp') else "NIE"}
Zmiana ceny: {sharp_move.get('percent_change', 0):+.2f}%
Kierunek: {sharp_move.get('direction', 'SIDEWAYS')}
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
- Jeśli PnL >= +${self.target_profit_usd} → rozważ CLOSE
- Jeśli PnL <= -${self.max_loss_usd} → CLOSE (stop loss!)
- Jeśli czas > {self.max_hold_minutes} min i brak zysku → rozważ CLOSE
- Jeśli RSI się odwraca (LONG przy RSI>60, SHORT przy RSI<40) → rozważ CLOSE
"""
        else:
            position_text = """
=== BRAK OTWARTEJ POZYCJI ===
Szukam sygnału do wejścia zgodnie z Metodą Piotra Święsa:
- SHORT: RSI > 70 + gwałtowny pump → oczekuję korekty
- LONG: RSI < 30 + gwałtowny dump → oczekuję odbicia
"""
        
        # Dane rynkowe (jeśli dostępne)
        market_text = ""
        if market_data:
            oracle_price = market_data.get('oracle_price', 0)
            change_24h = market_data.get('price_change_24h', 0)
            volume_24h = market_data.get('volume_24h', 0)
            trades_24h = market_data.get('trades_24h', 0)
            open_interest = market_data.get('open_interest', 0)
            funding_rate = market_data.get('funding_rate_1h', 0)
            next_funding_time = market_data.get('next_funding_time', 'N/A')
            max_leverage = market_data.get('max_leverage', 20.0)
            
            market_text = f"""
=== DANE RYNKOWE dYdX ===
Oracle Price: ${oracle_price:,.2f}
24h Change: {change_24h:+.2f}%
24h Volume: ${volume_24h:,.0f}
24h Trades: {trades_24h:,}
Open Interest: {open_interest:.2f} BTC
1h Funding Rate: {funding_rate*100:.5f}%
Next Funding: {next_funding_time}
Maximum Leverage: {max_leverage:.0f}×
"""
        
        # Aktualna sytuacja
        current_text = f"""
=== AKTUALNA SYTUACJA ===
Symbol: {symbol}
Aktualna cena: ${current_price:,.2f}
Czas: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        # Cooldown
        if self._is_in_cooldown():
            cooldown_text = f"\n⚠️ UWAGA: Jesteśmy w cooldown - ostatnio zamknięta pozycja. Nie wchodź w nową pozycję.\n"
        else:
            cooldown_text = ""
        
        # Połącz wszystko
        full_prompt = f"""{self.prompt_template}

{context_text}
{rsi_text}
{sharp_text}
{market_text}
{position_text}
{current_text}
{cooldown_text}

Podejmij decyzję zgodną z Metodą Piotra Święsa. Odpowiedz TYLKO w formacie JSON.
"""
        
        return full_prompt
    
    # ========================================
    # PARSOWANIE ODPOWIEDZI LLM
    # ========================================
    
    def _parse_llm_response(
        self,
        response: str,
        symbol: str,
        current_price: float,
        position_info: Optional[Dict[str, Any]]
    ) -> Optional[TradingSignal]:
        """
        Parsuje odpowiedź LLM i tworzy sygnał tradingowy.
        """
        try:
            # Wyciągnij JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.error(f"Nie znaleziono JSON w odpowiedzi LLM")
                return None
            
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            action_str = data.get('action', 'WAIT').upper()
            confidence = float(data.get('confidence', 5.0))
            reason = data.get('reason', '')
            
            # Mapuj akcje
            if action_str == 'LONG':
                signal_type = SignalType.BUY
            elif action_str == 'SHORT':
                signal_type = SignalType.SELL
            elif action_str == 'CLOSE':
                signal_type = SignalType.CLOSE
                self.last_close_time = datetime.now()
            else:  # WAIT
                # Wyświetl decyzję WAIT
                logger.info(f"🤖 [{self.name}] LLM zdecydował: WAIT (confidence: {confidence})")
                logger.info(f"   Powód: {reason}")
                return None
            
            # Pobierz parametry pozycji
            position_params = data.get('position_params') or {}
            
            # Oblicz SL/TP na podstawie USD
            stop_loss = None
            take_profit = None
            
            if signal_type in [SignalType.BUY, SignalType.SELL]:
                size_btc = (self.session_context.get('balance', 10000) * 
                           self.position_size_percent / 100) / current_price
                
                sl_usd = float(position_params.get('stop_loss_usd', self.max_loss_usd))
                tp_usd = float(position_params.get('take_profit_usd', self.target_profit_usd))
                
                if signal_type == SignalType.BUY:  # LONG
                    stop_loss = current_price - (sl_usd / size_btc)
                    take_profit = current_price + (tp_usd / size_btc)
                else:  # SHORT
                    stop_loss = current_price + (sl_usd / size_btc)
                    take_profit = current_price - (tp_usd / size_btc)
            
            # Wyświetl decyzję
            action_emoji = {"BUY": "🟢 LONG", "SELL": "🔴 SHORT", "CLOSE": "🔚 CLOSE"}.get(
                signal_type.value.upper(), signal_type.value
            )
            
            logger.info(f"")
            logger.info(f"{'='*70}")
            logger.info(f"🤖 [{self.name}] DECYZJA LLM: {action_emoji}")
            logger.info(f"{'='*70}")
            logger.info(f"Pewność: {confidence}/10")
            logger.info(f"Cena: ${current_price:,.2f}")
            if stop_loss:
                logger.info(f"Stop Loss: ${stop_loss:,.2f} (-${self.max_loss_usd})")
            if take_profit:
                logger.info(f"Take Profit: ${take_profit:,.2f} (+${self.target_profit_usd})")
            logger.info(f"Powód: {reason}")
            
            # RSI analysis z odpowiedzi
            rsi_analysis = data.get('rsi_analysis', {})
            if rsi_analysis:
                logger.info(f"RSI: {rsi_analysis.get('current_rsi', 'N/A')}")
                if rsi_analysis.get('crossed_threshold'):
                    logger.info(f"   Przekroczył próg: {rsi_analysis.get('threshold_crossed')}")
            
            # Price movement z odpowiedzi
            price_movement = data.get('price_movement', {})
            if price_movement.get('is_sharp'):
                logger.info(f"Gwałtowny ruch: {price_movement.get('direction')} ({price_movement.get('percent_change'):+.2f}%)")
            
            logger.info(f"{'='*70}")
            logger.info(f"")
            
            return TradingSignal(
                signal_type=signal_type,
                symbol=symbol,
                confidence=confidence,
                price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                size_percent=self.position_size_percent,
                reason=reason,
                strategy=self.name
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Błąd parsowania JSON z LLM: {e}")
            return None
        except Exception as e:
            logger.error(f"Błąd parsowania odpowiedzi LLM: {e}")
            return None
    
    # ========================================
    # WYKRES ASCII
    # ========================================
    
    def _generate_ascii_chart(self, df: pd.DataFrame, symbol: str, num_candles: int = 30) -> str:
        """
        Generuje wykres ASCII z ostatnimi świecami.
        
        Args:
            df: DataFrame z danymi OHLCV
            symbol: Symbol rynku
            num_candles: Liczba świec do wyświetlenia (domyślnie 30)
            
        Returns:
            String z wykresem ASCII
        """
        if df is None or df.empty or len(df) < 5:
            return "Brak danych do wyświetlenia"
        
        # Weź ostatnie świece
        recent_df = df.tail(min(num_candles, len(df))).copy()
        
        # Oblicz zakres cen (z marginesem 2%)
        min_price = float(recent_df['low'].min())
        max_price = float(recent_df['high'].max())
        price_margin = (max_price - min_price) * 0.02
        min_price -= price_margin
        max_price += price_margin
        price_range = max_price - min_price
        
        if price_range == 0:
            return "Brak zmienności cenowej"
        
        # Wysokość wykresu (liczba linii)
        chart_height = 15
        
        # Szerokość wykresu (liczba kolumn) - jedna kolumna na świecę
        chart_width = min(len(recent_df), 40)
        
        # Skaluj ceny do wysokości wykresu
        def price_to_y(price: float) -> int:
            if price_range == 0:
                return chart_height // 2
            normalized = (price - min_price) / price_range
            y = int(chart_height - 1 - (normalized * (chart_height - 1)))
            return max(0, min(chart_height - 1, y))
        
        # Utwórz siatkę wykresu
        chart = [[' ' for _ in range(chart_width)] for _ in range(chart_height)]
        
        # Rysuj świece jako linię (close prices)
        prices = recent_df['close'].values
        prev_y = None
        prev_x = None
        
        for i in range(len(prices)):
            x = i
            if x >= chart_width:
                break
            
            current_price = float(prices[i])
            y = price_to_y(current_price)
            
            # Rysuj punkt
            if i == len(prices) - 1:
                # Ostatnia świeca - zaznacz wyraźnie
                chart[y][x] = '●'
            else:
                chart[y][x] = '·'
            
            # Rysuj linię do poprzedniego punktu
            if prev_y is not None and prev_x is not None:
                # Rysuj linię między punktami (Bresenham-like)
                start_x, start_y = prev_x, prev_y
                end_x, end_y = x, y
                
                # Rysuj linię poziomą/pionową/ukośną
                if start_y == end_y:
                    # Pozioma
                    for line_x in range(start_x, end_x + 1):
                        if 0 <= line_x < chart_width:
                            chart[start_y][line_x] = '─'
                elif start_x == end_x:
                    # Pionowa
                    for line_y in range(min(start_y, end_y), max(start_y, end_y) + 1):
                        if 0 <= line_y < chart_height:
                            chart[line_y][start_x] = '│'
                else:
                    # Ukośna - użyj prostego algorytmu
                    dx = end_x - start_x
                    dy = end_y - start_y
                    steps = max(abs(dx), abs(dy))
                    
                    if steps > 0:
                        x_step = dx / steps
                        y_step = dy / steps
                        
                        for step in range(steps + 1):
                            line_x = int(start_x + x_step * step)
                            line_y = int(start_y + y_step * step)
                            
                            if 0 <= line_x < chart_width and 0 <= line_y < chart_height:
                                # Nie nadpisuj punktów
                                if chart[line_y][line_x] == ' ':
                                    if abs(dx) > abs(dy):
                                        chart[line_y][line_x] = '─'
                                    else:
                                        chart[line_y][line_x] = '│'
            
            prev_y = y
            prev_x = x
        
        # Dodaj etykiety osi Y (ceny)
        chart_lines = []
        chart_lines.append("")
        chart_lines.append(f"📈 WYKRES CENOWY - {symbol} (ostatnie {len(recent_df)} świec)")
        chart_lines.append("=" * (chart_width + 25))
        
        # Rysuj wykres z etykietami cen
        for y in range(chart_height):
            # Etykieta ceny (co 3-4 linie)
            if y % 4 == 0 or y == chart_height - 1:
                price_at_y = max_price - (y / (chart_height - 1)) * price_range
                price_label = f"${price_at_y:,.0f}"
            else:
                price_label = "   "
            
            # Linia wykresu
            chart_line = ''.join(chart[y])
            
            chart_lines.append(f"{price_label:>12} │{chart_line}")
        
        # Oś X (czas)
        chart_lines.append(" " * 13 + "└" + "─" * chart_width)
        
        # Etykiety czasu (pierwsza i ostatnia świeca)
        if len(recent_df) > 0:
            # Upewnij się, że index jest dostępny
            if hasattr(recent_df.index, '__getitem__'):
                first_time = recent_df.index[0]
                last_time = recent_df.index[-1]
            else:
                first_time = recent_df.iloc[0].get('timestamp', '')
                last_time = recent_df.iloc[-1].get('timestamp', '')
            
            if isinstance(first_time, pd.Timestamp):
                first_str = first_time.strftime('%H:%M')
                last_str = last_time.strftime('%H:%M')
            elif hasattr(first_time, 'strftime'):
                first_str = first_time.strftime('%H:%M')
                last_str = last_time.strftime('%H:%M')
            else:
                first_str = str(first_time)[:5] if len(str(first_time)) >= 5 else str(first_time)
                last_str = str(last_time)[:5] if len(str(last_time)) >= 5 else str(last_time)
            
            chart_lines.append(" " * 13 + f"{first_str:<{chart_width//2}}{last_str:>{chart_width//2}}")
        
        # Statystyki pod wykresem
        current_price = float(recent_df['close'].iloc[-1])
        first_price = float(recent_df['close'].iloc[0])
        change = ((current_price - first_price) / first_price) * 100 if first_price > 0 else 0
        
        chart_lines.append("")
        chart_lines.append(f"   📊 Statystyki:")
        chart_lines.append(f"      Cena początkowa: ${first_price:,.2f}")
        chart_lines.append(f"      Cena aktualna:   ${current_price:,.2f}")
        chart_lines.append(f"      Zmiana:          {change:+.2f}%")
        chart_lines.append(f"      Zakres:          ${min_price+price_margin:,.2f} - ${max_price-price_margin:,.2f}")
        chart_lines.append("")
        
        return "\n".join(chart_lines)
    
    # ========================================
    # DANE Z GIEŁDY
    # ========================================
    
    def _get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Pobiera dane rynkowe z dYdX.
        
        Returns:
            Dict z danymi: oracle_price, price_change_24h, volume_24h, trades_24h,
            open_interest, funding_rate, next_funding_time
        """
        try:
            ticker_data = self.dydx_collector.get_ticker(symbol)
            
            # Pobierz aktualny funding rate (ostatni)
            funding_rates = self.dydx_collector.get_funding_rates(symbol, limit=1)
            current_funding_rate = float(funding_rates['funding_rate'].iloc[-1]) if not funding_rates.empty else ticker_data.get('next_funding_rate', 0)
            
            # Oblicz czas do następnego funding (co 8 godzin: 00:00, 08:00, 16:00 UTC)
            from datetime import timezone
            now = datetime.now(timezone.utc)
            current_hour = now.hour
            
            # Znajdź następny funding (00:00, 08:00, 16:00)
            funding_hours = [0, 8, 16]
            next_funding_hour = None
            
            for hour in funding_hours:
                if hour > current_hour:
                    next_funding_hour = hour
                    break
            
            if next_funding_hour is None:
                # Następny funding jest jutro o 00:00
                next_funding_date = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                next_funding_date = now.replace(hour=next_funding_hour, minute=0, second=0, microsecond=0)
            
            time_to_funding = next_funding_date - now
            total_seconds = int(time_to_funding.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            next_funding_time_str = f"{hours:02d}:{minutes:02d}"
            
            # Pobierz maksymalną dźwignię (z konfiguracji lub domyślnie 20x dla dYdX)
            max_leverage = 20.0  # dYdX v4 standard
            
            return {
                'oracle_price': ticker_data.get('oracle_price', 0),
                'price_change_24h': ticker_data.get('price_change_24h', 0),
                'volume_24h': ticker_data.get('volume_24h', 0),
                'trades_24h': ticker_data.get('trades_24h', 0),
                'open_interest': ticker_data.get('open_interest', 0),
                'funding_rate_1h': current_funding_rate,
                'next_funding_time': next_funding_time_str,
                'max_leverage': max_leverage
            }
        except Exception as e:
            logger.warning(f"Błąd pobierania danych z dYdX: {e}")
            return {}
    
    def _display_market_data(self, symbol: str, current_price: float, market_data: Dict[str, Any]):
        """
        Wyświetla dane rynkowe z dYdX w logach.
        """
        if not market_data:
            return
        
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"📊 DANE RYNKOWE dYdX - {symbol}")
        logger.info("=" * 80)
        
        # Ceny
        oracle_price = market_data.get('oracle_price', 0)
        price_diff = current_price - oracle_price if oracle_price > 0 else 0
        price_diff_pct = (price_diff / oracle_price * 100) if oracle_price > 0 else 0
        
        logger.info(f"💰 Ceny:")
        logger.info(f"   Current Price:  ${current_price:,.2f}")
        logger.info(f"   Oracle Price:   ${oracle_price:,.2f} ({price_diff_pct:+.3f}%)")
        
        # 24h Change
        change_24h = market_data.get('price_change_24h', 0)
        change_24h_usd = (change_24h / 100) * oracle_price if oracle_price > 0 else 0
        change_emoji = "🟢" if change_24h > 0 else "🔴" if change_24h < 0 else "➖"
        logger.info(f"   {change_emoji} 24h Change:   ${change_24h_usd:+,.2f} ({change_24h:+.2f}%)")
        
        # Volume i Trades
        volume_24h = market_data.get('volume_24h', 0)
        trades_24h = market_data.get('trades_24h', 0)
        logger.info(f"")
        logger.info(f"📈 Aktywność:")
        logger.info(f"   24h Volume:     ${volume_24h:,.0f}")
        logger.info(f"   24h Trades:     {trades_24h:,}")
        
        # Open Interest
        open_interest = market_data.get('open_interest', 0)
        logger.info(f"")
        logger.info(f"💼 Pozycje:")
        logger.info(f"   Open Interest:  {open_interest:.2f} BTC")
        
        # Funding
        funding_rate = market_data.get('funding_rate_1h', 0)
        next_funding_time = market_data.get('next_funding_time', 'N/A')
        funding_emoji = "🔴" if funding_rate < 0 else "🟢" if funding_rate > 0 else "➖"
        logger.info(f"")
        logger.info(f"💸 Funding:")
        logger.info(f"   {funding_emoji} 1h Funding:    {funding_rate*100:.5f}%")
        logger.info(f"   ⏰ Next Funding:  {next_funding_time}")
        
        # Leverage
        max_leverage = market_data.get('max_leverage', 20.0)
        logger.info(f"")
        logger.info(f"⚡ Dźwignia:")
        logger.info(f"   Maximum Leverage: {max_leverage:.2f}×")
        
        logger.info("=" * 80)
        logger.info("")
    
    # ========================================
    # GŁÓWNA ANALIZA
    # ========================================
    
    def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD") -> Optional[TradingSignal]:
        """
        Analizuje dane i generuje sygnał używając LLM z Metodą Piotra Święsa.
        """
        if df is None or df.empty:
            logger.warning(f"Brak danych dla {symbol}")
            return None
        
        if len(df) < self.rsi_period + 5:
            logger.debug(f"Za mało danych ({len(df)} świec)")
            return None
        
        # Zapisz symbol
        self._current_symbol = symbol
        
        # Oblicz wskaźniki
        close = df['close']
        current_price = float(close.iloc[-1])
        
        # RSI
        rsi = self._calculate_rsi(close, self.rsi_period)
        rsi_data = self._detect_rsi_cross(rsi)
        
        # Gwałtowność ruchu
        sharp_move = self._detect_sharp_move(df)
        
        # Pobierz info o pozycji
        position_info = self._get_current_position(symbol)
        
        # Pobierz dane rynkowe z dYdX
        market_data = self._get_market_data(symbol)
        
        # Wyświetl wykres ASCII
        ascii_chart = self._generate_ascii_chart(df, symbol, num_candles=30)
        logger.info(ascii_chart)
        
        # Wyświetl dane rynkowe
        self._display_market_data(symbol, current_price, market_data)
        
        # Log stanu
        logger.debug(
            f"[{self.name}] {symbol}: RSI={rsi_data.get('current_rsi', 50):.1f}, "
            f"Sharp={sharp_move.get('is_sharp')} ({sharp_move.get('percent_change'):+.2f}%)"
        )
        
        # Wyświetl krótkie podsumowanie analizy
        logger.info(f"📊 [{self.name}] Analiza {symbol}:")
        logger.info(f"   RSI(14): {rsi_data.get('current_rsi', 50):.1f} | "
                   f"Przekupiony: {'TAK' if rsi_data.get('currently_above_70') else 'NIE'} | "
                   f"Wyprzedany: {'TAK' if rsi_data.get('currently_below_30') else 'NIE'}")
        logger.info(f"   Gwałtowny ruch: {'TAK' if sharp_move.get('is_sharp') else 'NIE'} | "
                   f"Zmiana: {sharp_move.get('percent_change'):+.2f}% ({sharp_move.get('direction')})")
        
        if position_info:
            logger.info(f"   📍 Pozycja: {position_info['side'].upper()} | "
                       f"PnL: ${position_info['pnl_usd']:+,.2f} ({position_info['pnl_percent']:+.2f}%)")
        
        # Zbuduj prompt
        prompt = self._build_prompt(
            symbol=symbol,
            current_price=current_price,
            rsi_data=rsi_data,
            sharp_move=sharp_move,
            position_info=position_info,
            market_data=market_data
        )
        
        # Wyślij do LLM
        try:
            from langchain.schema import HumanMessage, SystemMessage
            
            messages = [
                SystemMessage(content="Jesteś traderem używającym Metody Piotra Święsa. Analizujesz RSI i gwałtowne ruchy ceny, aby podejmować szybkie decyzje tradingowe."),
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
            
            # Wykonaj request
            start_time = time.time()
            response = self.llm_analyzer.llm.invoke(messages)
            response_time_ms = (time.time() - start_time) * 1000
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Pobierz usage
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
            
            # Parsuj odpowiedź
            signal = self._parse_llm_response(response_text, symbol, current_price, position_info)
            
            return signal
            
        except Exception as e:
            logger.error(f"Błąd komunikacji z LLM: {e}")
            return None
    
    def should_close_position(
        self,
        df: pd.DataFrame,
        entry_price: float,
        side: str,
        current_pnl_percent: float
    ) -> Optional[TradingSignal]:
        """
        Sprawdza czy pozycja powinna zostać zamknięta.
        Używa prostych reguł bez LLM dla szybkości.
        """
        if df is None or df.empty:
            return None
        
        symbol = getattr(self, '_current_symbol', 'BTC-USD')
        position_info = self._get_current_position(symbol)
        
        if not position_info:
            return None
        
        current_price = float(df['close'].iloc[-1])
        pnl_usd = position_info['pnl_usd']
        minutes_open = position_info['minutes_open']
        
        # Oblicz RSI
        rsi = self._calculate_rsi(df['close'], self.rsi_period)
        current_rsi = float(rsi.iloc[-1])
        
        # 1. Take Profit
        if pnl_usd >= self.target_profit_usd:
            self.last_close_time = datetime.now()
            logger.success(f"🎉 [{self.name}] TARGET PROFIT: +${pnl_usd:.2f}")
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=current_price,
                reason=f"Target profit: +${pnl_usd:.2f}",
                strategy=self.name
            )
        
        # 2. Stop Loss
        if pnl_usd <= -self.max_loss_usd:
            self.last_close_time = datetime.now()
            logger.warning(f"🛑 [{self.name}] STOP LOSS: ${pnl_usd:.2f}")
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=current_price,
                reason=f"Stop loss: ${pnl_usd:.2f}",
                strategy=self.name
            )
        
        # 3. Timeout
        if minutes_open >= self.max_hold_minutes and pnl_usd < self.target_profit_usd * 0.3:
            self.last_close_time = datetime.now()
            logger.info(f"⏰ [{self.name}] TIMEOUT: {minutes_open:.1f} min, PnL=${pnl_usd:.2f}")
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=8.0,
                price=current_price,
                reason=f"Timeout: {minutes_open:.0f}min, PnL=${pnl_usd:.2f}",
                strategy=self.name
            )
        
        # 4. RSI Reversal (z zyskiem)
        if side == 'long' and current_rsi > 60 and pnl_usd > 0:
            self.last_close_time = datetime.now()
            logger.info(f"📊 [{self.name}] RSI REVERSAL: LONG przy RSI={current_rsi:.1f}")
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=7.0,
                price=current_price,
                reason=f"RSI reversal: LONG przy RSI={current_rsi:.0f}, PnL=${pnl_usd:.2f}",
                strategy=self.name
            )
        
        if side == 'short' and current_rsi < 40 and pnl_usd > 0:
            self.last_close_time = datetime.now()
            logger.info(f"📊 [{self.name}] RSI REVERSAL: SHORT przy RSI={current_rsi:.1f}")
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=7.0,
                price=current_price,
                reason=f"RSI reversal: SHORT przy RSI={current_rsi:.0f}, PnL=${pnl_usd:.2f}",
                strategy=self.name
            )
        
        return None

