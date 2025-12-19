"""
Test Prompt Strategy
===================
Testowa strategia do weryfikacji działania systemu tradingowego.

Logika:
- Iteracja 0: LONG (~100 USD)
- Iteracje 1-10: WAIT
- Iteracja 11: CLOSE (jeśli pozycja otwarta) lub SHORT (jeśli brak pozycji)

Autor: AI Assistant
Data: 2025-12-17
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import pandas as pd
import json
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType
from src.analysis.llm.market_analyzer import MarketAnalyzerLLM
from src.utils.api_logger import get_api_logger


class TestPromptStrategy(BaseStrategy):
    """
    Testowa strategia prompt-based do weryfikacji systemu.
    
    Wykonuje:
    - Iteracja 0: LONG (~100 USD)
    - Iteracje 1-10: WAIT
    - Iteracja 11: CLOSE/SHORT
    """
    
    name = "TestPromptStrategy"
    description = "Testowa strategia - weryfikacja działania systemu"
    timeframe = "1min"
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        
        # Ścieżka do promptu
        self.prompt_file = self.config.get('prompt_file', 'prompts/trading/test_prompt_strategy.txt')
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
        
        # Licznik iteracji
        self.iteration_count = 0
        
        # Parametry pozycji
        self.test_position_size_usd = self.config.get('test_position_size_usd', 100.0)
        self.stop_loss_usd = self.config.get('stop_loss_usd', 500.0)
        self.take_profit_usd = self.config.get('take_profit_usd', 1000.0)
        
        # Kontekst sesji
        self.session_context: Dict[str, Any] = {}
        self.paper_trading_engine = None
        
        logger.info(f"TestPromptStrategy zainicjalizowana")
        logger.info(f"  Prompt: {self.prompt_file}")
        logger.info(f"  LLM: {self.provider}/{self.model}")
        logger.info(f"  Rozmiar pozycji testowej: ${self.test_position_size_usd}")
    
    def set_session_context(self, context: Dict[str, Any]):
        """Ustawia kontekst sesji."""
        self.session_context = context
        logger.debug(f"Kontekst sesji ustawiony: {context}")
    
    def set_paper_trading_engine(self, engine):
        """Ustawia referencję do paper trading engine."""
        self.paper_trading_engine = engine
        logger.debug("Paper trading engine ustawiony")
    
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
    
    def _build_prompt(
        self,
        symbol: str,
        current_price: float,
        iteration: int,
        position_info: Optional[Dict[str, Any]]
    ) -> str:
        """
        Buduje prompt dla LLM z informacją o iteracji.
        """
        context_text = f"""
=== KONTEKST TESTU ===
Iteracja: {iteration}
Kapitał początkowy: ${self.session_context.get('balance', 10000):,.2f}
Rozmiar pozycji testowej: ${self.test_position_size_usd}
"""
        
        if position_info:
            position_text = f"""
=== OTWARTA POZYCJA ===
Typ: {position_info['side'].upper()}
Cena wejścia: ${position_info['entry_price']:,.2f}
Aktualna cena: ${position_info['current_price']:,.2f}
Rozmiar: {position_info['size']:.6f} BTC
PnL: ${position_info['pnl_usd']:+,.2f} ({position_info['pnl_percent']:+.2f}%)
Otwarta od: {position_info['minutes_open']:.1f} minut
"""
        else:
            position_text = """
=== BRAK OTWARTEJ POZYCJI ===
"""
        
        full_prompt = f"""
{self.prompt_template}

{context_text}

{position_text}

=== INFORMACJE O ITERACJI ===
Aktualna iteracja: {iteration}
Aktualna cena: ${current_price:,.2f}
Symbol: {symbol}

=== ZADANIE ===
Zgodnie z zasadami Test Prompt Strategy:
- Iteracja 0: LONG (~100 USD)
- Iteracje 1-10: WAIT
- Iteracja 11: CLOSE (jeśli pozycja otwarta) lub SHORT (jeśli brak pozycji)

Odpowiedz TYLKO w formacie JSON zgodnie z FORMAT ODPOWIEDZI.
"""
        
        return full_prompt
    
    def analyze(
        self,
        df: pd.DataFrame,
        symbol: str = "BTC-USD",
        paper_trading_engine=None
    ) -> Optional[TradingSignal]:
        """
        Analizuje rynek i zwraca sygnał testowy.
        """
        if paper_trading_engine:
            self.paper_trading_engine = paper_trading_engine
        
        if df is None or df.empty:
            logger.warning(f"Brak danych dla {symbol}")
            return None
        
        # Oblicz aktualną cenę
        current_price = float(df['close'].iloc[-1])
        
        # Pobierz informacje o pozycji
        position_info = self._get_current_position(symbol)
        
        # Zbuduj prompt
        prompt = self._build_prompt(
            symbol=symbol,
            current_price=current_price,
            iteration=self.iteration_count,
            position_info=position_info
        )
        
        # Wyślij do LLM
        logger.info("")
        logger.info(f"🤖 Iteracja {self.iteration_count} - Wysyłam zapytanie do LLM...")
        
        try:
            from langchain.schema import HumanMessage, SystemMessage
            import time
            
            messages = [
                SystemMessage(content="Jesteś testowym traderem. Wykonujesz dokładnie instrukcje z promptu testowego."),
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
                metadata={"method": "analyze", "strategy": self.name, "symbol": symbol, "iteration": self.iteration_count}
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
                metadata={"method": "analyze", "strategy": self.name, "symbol": symbol, "iteration": self.iteration_count}
            )
            
            # Parsuj odpowiedź
            signal = self._parse_llm_response(response_text, symbol, current_price, position_info)
            
            # Zwiększ licznik iteracji
            self.iteration_count += 1
            
            if signal:
                logger.info(f"✅ Sygnał: {signal.signal_type.value} (confidence: {signal.confidence})")
                logger.info(f"   Powód: {signal.reason}")
            else:
                logger.info("⏸️  Brak sygnału (WAIT lub błąd parsowania)")
            
            return signal
            
        except Exception as e:
            logger.error(f"Błąd podczas analizy LLM: {e}")
            # Zwiększ licznik nawet przy błędzie
            self.iteration_count += 1
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
            
            # Rozmiar pozycji w USD
            size_usd_raw = position_params.get('size_usd', self.test_position_size_usd)
            size_usd = float(size_usd_raw) if size_usd_raw is not None else self.test_position_size_usd
            
            # Stop loss i take profit
            stop_loss_usd_raw = position_params.get('stop_loss_usd')
            stop_loss_usd = float(stop_loss_usd_raw) if stop_loss_usd_raw is not None else self.stop_loss_usd
            
            take_profit_usd_raw = position_params.get('take_profit_usd')
            take_profit_usd = float(take_profit_usd_raw) if take_profit_usd_raw is not None else self.take_profit_usd
            
            # Powód
            reason = data.get('reason', f'{action} signal from test strategy (iteracja {self.iteration_count})')
            
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
            
            # Oblicz size_percent na podstawie size_usd
            balance = self.session_context.get('balance', 10000)
            if balance > 0:
                # size_usd / balance * 100 = size_percent
                size_percent = (size_usd / balance) * 100
            else:
                size_percent = 1.0  # 1% domyślnie
            
            # Oblicz rozmiar pozycji w BTC (potrzebny do obliczenia stop_loss/take_profit)
            position_size_btc = size_usd / entry_price if entry_price > 0 else 0
            
            # Oblicz stop_loss i take_profit jako ceny (na podstawie USD)
            stop_loss_price = None
            take_profit_price = None
            
            if entry_price > 0 and position_size_btc > 0:
                if signal_type == SignalType.BUY:  # LONG
                    stop_loss_price = entry_price - (stop_loss_usd / position_size_btc)
                    take_profit_price = entry_price + (take_profit_usd / position_size_btc)
                elif signal_type == SignalType.SELL:  # SHORT
                    stop_loss_price = entry_price + (stop_loss_usd / position_size_btc)
                    take_profit_price = entry_price - (take_profit_usd / position_size_btc)
            
            signal = TradingSignal(
                symbol=symbol,
                signal_type=signal_type,
                price=entry_price,
                confidence=confidence,
                reason=reason,
                strategy=self.name,
                stop_loss=stop_loss_price,
                take_profit=take_profit_price,
                size_percent=size_percent
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
        logger.info(f"Pozycja zamknięta: PnL=${pnl:+,.2f}, powód: {reason}")

