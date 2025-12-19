"""
Prompt Strategy
===============
Strategia tradingowa oparta na analizie LLM (Large Language Model).

Strategia wysyła do AI wszystkie dane kursu od początku sesji wraz z promptem
z pliku i otrzymuje decyzję tradingową wraz z obserwacjami.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import pandas as pd
import json
import os
import time
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType
from src.analysis.llm.market_analyzer import MarketAnalyzerLLM
from src.utils.api_logger import get_api_logger
from src.analysis.market_news_analyzer import MarketNewsAnalyzer
from src.utils.web_search import get_web_search_engine


class PromptStrategy(BaseStrategy):
    """
    Strategia tradingowa oparta na analizie LLM.
    
    Konfiguracja:
    - prompt_file: Ścieżka do pliku z promptem
    - provider: "anthropic" lub "openai" (default: "anthropic")
    - model: Nazwa modelu (default: "claude-3-5-haiku-20241022")
    - api_key: Klucz API (opcjonalnie, z .env)
    - max_history_candles: Maksymalna liczba świec w historii (default: 100)
    """
    
    name = "PromptStrategy"
    description = "Strategia tradingowa oparta na analizie LLM z promptem z pliku"
    timeframe = "1h"
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        
        # Domyślna konfiguracja
        self.prompt_file = self.config.get('prompt_file')
        if not self.prompt_file:
            raise ValueError("prompt_file jest wymagany w konfiguracji")
        
        # Sprawdź czy plik istnieje
        prompt_path = Path(self.prompt_file)
        if not prompt_path.exists():
            raise FileNotFoundError(f"Plik promptu nie istnieje: {self.prompt_file}")
        
        # Wczytaj prompt
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.prompt_template = f.read()
        
        # Konfiguracja LLM
        self.provider = self.config.get('provider', 'anthropic')
        self.model = self.config.get('model', 'claude-3-5-haiku-20241022')
        self.api_key = self.config.get('api_key')
        self.max_history_candles = self.config.get('max_history_candles', 100)
        
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
        
        # Inicjalizuj analizator wiadomości i sentymentu
        self.news_analyzer = MarketNewsAnalyzer()
        
        # Inicjalizuj silnik wyszukiwania w internecie
        self.web_search = get_web_search_engine()
        
        # Cache dla danych sentymentu (aktualizowane co interwał)
        self.sentiment_cache: Dict[str, Dict[str, Any]] = {}
        self.sentiment_cache_time: Dict[str, datetime] = {}
        self.sentiment_cache_interval = 300  # 5 minut
        
        # Historia cen od początku sesji (będzie aktualizowana przez bota)
        self.price_history: Dict[str, List[pd.DataFrame]] = {}
        
        # Kontekst sesji (balance, time_limit, max_loss, mode)
        self.session_context: Dict[str, Any] = {}
        
        # Historia decyzji LLM (z parametrami)
        self.decision_history: List[Dict[str, Any]] = []
        
        # Referencja do paper trading engine (do pobierania wyników transakcji)
        self.paper_trading_engine = None
        
        logger.info(f"Strategia {self.name} zainicjalizowana z promptem: {self.prompt_file}")
    
    def set_session_context(self, context: Dict[str, Any]):
        """
        Ustawia kontekst sesji (balance, time_limit, max_loss, mode).
        
        Args:
            context: Słownik z kontekstem sesji
        """
        self.session_context = context
        logger.debug(f"Kontekst sesji ustawiony: {context}")
    
    def set_paper_trading_engine(self, engine):
        """
        Ustawia referencję do paper trading engine (do pobierania wyników transakcji).
        
        Args:
            engine: Instancja PaperTradingEngine
        """
        self.paper_trading_engine = engine
        logger.debug("Paper trading engine ustawiony")
    
    def update_price_history(self, symbol: str, df: pd.DataFrame):
        """
        Aktualizuje historię cen dla symbolu.
        
        Args:
            symbol: Symbol rynku
            df: DataFrame z danymi OHLCV
        """
        if df is None or df.empty:
            return
        
        # Upewnij się, że timestamp jest kolumną (nie indeksem)
        if df.index.name == 'timestamp' or isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
        
        # Upewnij się, że mamy kolumnę timestamp
        if 'timestamp' not in df.columns:
            logger.warning(f"Brak kolumny 'timestamp' w DataFrame dla {symbol}")
            return
        
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        # Dodaj nowe dane (unikalne po timestamp)
        if not self.price_history[symbol]:
            self.price_history[symbol].append(df)
        else:
            # Połącz z istniejącą historią, unikając duplikatów
            existing_df = pd.concat(self.price_history[symbol], ignore_index=True)
            
            # Upewnij się, że timestamp jest kolumną
            if existing_df.index.name == 'timestamp' or isinstance(existing_df.index, pd.DatetimeIndex):
                existing_df = existing_df.reset_index()
            
            existing_df = existing_df.drop_duplicates(subset=['timestamp'], keep='last')
            
            # Dodaj nowe dane
            combined = pd.concat([existing_df, df], ignore_index=True)
            combined = combined.drop_duplicates(subset=['timestamp'], keep='last')
            combined = combined.sort_values('timestamp')
            
            # Ogranicz do max_history_candles
            if len(combined) > self.max_history_candles:
                combined = combined.tail(self.max_history_candles)
            
            self.price_history[symbol] = [combined]
    
    def _format_price_history(self, symbol: str) -> str:
        """
        Formatuje historię cen do tekstu dla LLM.
        
        Args:
            symbol: Symbol rynku
            
        Returns:
            Sformatowana historia cen jako tekst
        """
        if symbol not in self.price_history or not self.price_history[symbol]:
            return "Brak danych historycznych"
        
        df = self.price_history[symbol][0]
        
        # Upewnij się, że timestamp jest kolumną (nie indeksem)
        if df.index.name == 'timestamp' or isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
        
        # Formatuj jako tabela
        lines = [f"\nHistoria cen dla {symbol}:"]
        lines.append(f"{'Timestamp':<20} {'Open':<12} {'High':<12} {'Low':<12} {'Close':<12} {'Volume':<15}")
        lines.append("-" * 90)
        
        # Pokaż ostatnie 20 świec (lub wszystkie jeśli mniej)
        display_df = df.tail(20)
        
        for _, row in display_df.iterrows():
            timestamp = str(row.get('timestamp', ''))[:19]  # YYYY-MM-DD HH:MM:SS
            open_price = f"{row.get('open', 0):.2f}"
            high_price = f"{row.get('high', 0):.2f}"
            low_price = f"{row.get('low', 0):.2f}"
            close_price = f"{row.get('close', 0):.2f}"
            volume = f"{row.get('volume', 0):.0f}"
            
            lines.append(f"{timestamp:<20} {open_price:<12} {high_price:<12} {low_price:<12} {close_price:<12} {volume:<15}")
        
        # Dodaj statystyki
        if len(df) > 0:
            current_price = float(df['close'].iloc[-1])
            price_24h_ago = float(df['close'].iloc[0]) if len(df) > 0 else current_price
            change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100
            
            lines.append("\nStatystyki:")
            lines.append(f"  Cena aktualna: ${current_price:.2f}")
            lines.append(f"  Zmiana (od początku historii): {change_24h:+.2f}%")
            lines.append(f"  Min: ${float(df['low'].min()):.2f}")
            lines.append(f"  Max: ${float(df['high'].max()):.2f}")
            lines.append(f"  Średni wolumen: {df['volume'].mean():.0f}")
        
        return "\n".join(lines)
    
    def _format_decision_history(self) -> str:
        """
        Formatuje historię decyzji LLM do tekstu.
        
        Returns:
            Sformatowana historia decyzji jako tekst
        """
        if not self.decision_history:
            return "\nHistoria decyzji: Brak poprzednich decyzji"
        
        lines = ["\nHistoria poprzednich decyzji LLM:"]
        lines.append(f"{'Timestamp':<20} {'Akcja':<8} {'Cena':<12} {'Confidence':<12} {'Stop Loss':<12} {'Take Profit':<12} {'Size %':<8} {'Wynik':<15}")
        lines.append("-" * 120)
        
        # Pokaż ostatnie 20 decyzji (lub wszystkie jeśli mniej)
        display_decisions = self.decision_history[-20:]
        
        for decision in display_decisions:
            timestamp = decision.get('timestamp', '')[:19] if isinstance(decision.get('timestamp'), str) else str(decision.get('timestamp', ''))[:19]
            action = decision.get('action', 'N/A')
            price = f"${decision.get('price', 0):.2f}"
            confidence = f"{decision.get('confidence', 0):.1f}"
            stop_loss = f"${decision.get('stop_loss', 0):.2f}" if decision.get('stop_loss') else "N/A"
            take_profit = f"${decision.get('take_profit', 0):.2f}" if decision.get('take_profit') else "N/A"
            size_percent = f"{decision.get('size_percent', 0):.1f}%"
            
            # Wynik transakcji (jeśli dostępny)
            result = decision.get('result', 'N/A')
            if result != 'N/A' and isinstance(result, dict):
                pnl = result.get('pnl', 0)
                pnl_percent = result.get('pnl_percent', 0)
                exit_reason = result.get('exit_reason', 'N/A')
                if pnl > 0:
                    result = f"✅ +${pnl:.2f} (+{pnl_percent:.2f}%)"
                elif pnl < 0:
                    result = f"❌ ${pnl:.2f} ({pnl_percent:.2f}%)"
                else:
                    result = f"➖ ${pnl:.2f}"
                result += f" | {exit_reason}"
            
            lines.append(f"{timestamp:<20} {action:<8} {price:<12} {confidence:<12} {stop_loss:<12} {take_profit:<12} {size_percent:<8} {result:<15}")
            
            # Dodaj obserwacje LLM jeśli dostępne
            observations = decision.get('observations', '')
            reason = decision.get('reason', '')
            if observations or reason:
                lines.append(f"  Obserwacje: {observations[:100]}..." if len(observations) > 100 else f"  Obserwacje: {observations}")
                if reason:
                    lines.append(f"  Powód: {reason}")
        
        # Dodaj statystyki
        if len(self.decision_history) > 0:
            total_decisions = len(self.decision_history)
            buy_decisions = sum(1 for d in self.decision_history if d.get('action') == 'BUY')
            sell_decisions = sum(1 for d in self.decision_history if d.get('action') == 'SELL')
            hold_decisions = sum(1 for d in self.decision_history if d.get('action') == 'HOLD')
            close_decisions = sum(1 for d in self.decision_history if d.get('action') == 'CLOSE')
            
            # Oblicz statystyki wyników
            completed_trades = [d for d in self.decision_history if d.get('result') != 'N/A' and isinstance(d.get('result'), dict)]
            if completed_trades:
                wins = sum(1 for d in completed_trades if d.get('result', {}).get('pnl', 0) > 0)
                losses = sum(1 for d in completed_trades if d.get('result', {}).get('pnl', 0) <= 0)
                total_pnl = sum(d.get('result', {}).get('pnl', 0) for d in completed_trades)
                win_rate = (wins / len(completed_trades)) * 100 if completed_trades else 0
                
                lines.append("\nStatystyki decyzji:")
                lines.append(f"  Łącznie decyzji: {total_decisions}")
                lines.append(f"  BUY: {buy_decisions}, SELL: {sell_decisions}, HOLD: {hold_decisions}, CLOSE: {close_decisions}")
                lines.append(f"  Zakończone transakcje: {len(completed_trades)}")
                lines.append(f"  Win Rate: {win_rate:.1f}% ({wins}W/{losses}L)")
                lines.append(f"  Łączny PnL: ${total_pnl:.2f}")
        
        return "\n".join(lines)
    
    def _update_decision_history_with_results(self):
        """
        Aktualizuje historię decyzji o wyniki transakcji z paper trading engine.
        """
        if not self.paper_trading_engine:
            return
        
        try:
            # Pobierz ostatnie transakcje (ostatnie 50)
            trades = self.paper_trading_engine.get_trade_history(limit=50)
            
            # Dla każdej decyzji w historii, sprawdź czy ma odpowiadającą transakcję
            for decision in self.decision_history:
                # Jeśli decyzja już ma wynik, pomiń
                if decision.get('result') != 'N/A':
                    continue
                
                # Znajdź transakcję odpowiadającą tej decyzji
                # Dopasuj po symbolu, czasie (w przybliżeniu) i akcji
                decision_timestamp = decision.get('timestamp')
                decision_action = decision.get('action')
                decision_symbol = decision.get('symbol', 'BTC-USD')
                
                if not decision_timestamp:
                    continue
                
                # Konwertuj timestamp na datetime jeśli to string
                if isinstance(decision_timestamp, str):
                    try:
                        decision_timestamp = datetime.fromisoformat(decision_timestamp.replace('Z', '+00:00'))
                    except:
                        continue
                
                # Szukaj transakcji w oknie 5 minut od decyzji
                for trade in trades:
                    # Sprawdź czy symbol się zgadza
                    if trade.symbol != decision_symbol:
                        continue
                    
                    # Sprawdź czy czas wejścia jest blisko czasu decyzji
                    entry_time = trade.entry_time
                    if isinstance(entry_time, str):
                        try:
                            entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                        except:
                            continue
                    
                    # Sprawdź różnicę czasu (maksymalnie 5 minut)
                    time_diff = abs((entry_time - decision_timestamp).total_seconds())
                    if time_diff > 300:  # 5 minut
                        continue
                    
                    # Sprawdź czy akcja się zgadza (BUY -> LONG, SELL -> SHORT)
                    action_match = False
                    if decision_action == 'BUY' and trade.side.value == 'LONG':
                        action_match = True
                    elif decision_action == 'SELL' and trade.side.value == 'SHORT':
                        action_match = True
                    
                    if action_match:
                        # Znajdź wynik transakcji
                        decision['result'] = {
                            'pnl': float(trade.net_pnl),
                            'pnl_percent': float(trade.pnl_percent),
                            'exit_reason': trade.exit_reason or 'manual',
                            'entry_price': float(trade.entry_price),
                            'exit_price': float(trade.exit_price),
                            'duration_minutes': float(trade.duration_minutes) if hasattr(trade, 'duration_minutes') else 0
                        }
                        break
        except Exception as e:
            logger.warning(f"Błąd aktualizacji historii decyzji o wyniki: {e}")
    
    def _get_sentiment_analysis(self, symbol: str) -> str:
        """
        Pobiera i formatuje analizę sentymentu i wiadomości dla symbolu.
        
        Args:
            symbol: Symbol rynku
            
        Returns:
            Sformatowany tekst z analizą sentymentu
        """
        # Sprawdź cache (aktualizuj co 5 minut)
        now = datetime.now()
        cache_key = symbol
        
        if cache_key in self.sentiment_cache_time:
            cache_age = (now - self.sentiment_cache_time[cache_key]).total_seconds()
            if cache_age < self.sentiment_cache_interval and cache_key in self.sentiment_cache:
                # Użyj cache
                sentiment_data = self.sentiment_cache[cache_key]
            else:
                # Pobierz nowe dane
                sentiment_data = self.news_analyzer.collect_market_sentiment(symbol)
                self.sentiment_cache[cache_key] = sentiment_data
                self.sentiment_cache_time[cache_key] = now
        else:
            # Pierwsze pobranie
            sentiment_data = self.news_analyzer.collect_market_sentiment(symbol)
            self.sentiment_cache[cache_key] = sentiment_data
            self.sentiment_cache_time[cache_key] = now
        
        # Formatuj dla prompta
        return self.news_analyzer.format_market_analysis_for_prompt(sentiment_data)
    
    def _build_prompt(self, symbol: str, current_price: float) -> str:
        """
        Buduje pełny prompt dla LLM.
        
        Args:
            symbol: Symbol rynku
            current_price: Aktualna cena
            
        Returns:
            Pełny prompt jako tekst
        """
        # Aktualizuj historię decyzji o wyniki transakcji
        self._update_decision_history_with_results()
        
        # Historia cen
        price_history_text = self._format_price_history(symbol)
        
        # Historia decyzji LLM
        decision_history_text = self._format_decision_history()
        
        # Kontekst sesji
        context_text = "\nKontekst sesji tradingowej:"
        context_text += f"\n  Kapitał początkowy: ${self.session_context.get('balance', 0):,.2f}"
        context_text += f"\n  Limit czasu: {self.session_context.get('time_limit', 'N/A')}"
        context_text += f"\n  Maksymalna strata: ${self.session_context.get('max_loss', 0):,.2f}"
        context_text += f"\n  Tryb: {self.session_context.get('mode', 'paper')}"
        
        # Aktualna sytuacja
        current_situation = f"\nAktualna sytuacja:\n  Symbol: {symbol}\n  Aktualna cena: ${current_price:.2f}"
        
        # Analiza sentymentu i wiadomości
        sentiment_analysis_text = self._get_sentiment_analysis(symbol)
        
        # Wyniki wyszukiwania (jeśli były wcześniej wykonane - tylko jeśli LLM o to poprosił)
        web_search_results_text = getattr(self, '_last_web_search_results', '')
        
        # Wyświetl wyniki wyszukiwania w konsoli tylko jeśli LLM o to poprosił
        if web_search_results_text:
            logger.info("")
            logger.info("=" * 80)
            logger.info("🔍 WYNIKI WYSZUKIWANIA W INTERNECIE (na żądanie LLM)")
            logger.info("=" * 80)
            # Formatuj wyniki wyszukiwania dla wyświetlenia (usuń markdown z prompta)
            search_lines = web_search_results_text.split('\n')
            for line in search_lines:
                if line.strip() and not line.strip().startswith('==='):
                    logger.info(f"   {line.strip()}")
            logger.info("=" * 80)
            logger.info("")
        
        # Połącz wszystko
        full_prompt = f"""{self.prompt_template}

{context_text}

{price_history_text}

{decision_history_text}

{sentiment_analysis_text}

{web_search_results_text}

{current_situation}

WAŻNE: Odpowiedz w formacie JSON:
{{
    "action": "BUY" | "SELL" | "HOLD" | "CLOSE" | "SEARCH",
    "confidence": 0.0-10.0,
    "price": {current_price},
    "stop_loss": <cena stop loss lub null>,
    "take_profit": <cena take profit lub null>,
    "size_percent": <procent kapitału do użycia (0-100)>,
    "observations": "<szczegółowe obserwacje i uzasadnienie decyzji>",
    "reason": "<krótkie uzasadnienie decyzji>",
    "search_queries": <opcjonalnie: lista zapytań do wyszukania w internecie - użyj jeśli potrzebujesz aktualnych informacji>
}}

UWAGA: Jeśli potrzebujesz wyszukać informacje w internecie przed podjęciem decyzji, ustaw "action": "SEARCH" i podaj listę zapytań w "search_queries".
Po otrzymaniu wyników wyszukiwania, podejmiesz decyzję tradingową w kolejnej odpowiedzi.
"""
        
        return full_prompt
    
    def _parse_llm_response(self, response: str, symbol: str, current_price: float) -> Optional[TradingSignal]:
        """
        Parsuje odpowiedź LLM i tworzy sygnał tradingowy.
        
        Args:
            response: Odpowiedź z LLM
            symbol: Symbol rynku
            current_price: Aktualna cena
            
        Returns:
            TradingSignal lub None jeśli błąd
        """
        try:
            # Spróbuj wyciągnąć JSON z odpowiedzi
            # LLM może zwrócić tekst z JSON w środku
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.error(f"Nie znaleziono JSON w odpowiedzi LLM: {response[:200]}")
                return None
            
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            # Sprawdź czy LLM prosi o wyszukanie informacji
            if data.get('action') == 'SEARCH' and data.get('search_queries'):
                # Wykonaj wyszukiwanie (bez logowania w konsoli - szczegóły tylko w pliku)
                search_queries = data.get('search_queries', [])
                
                # Wykonaj wszystkie wyszukiwania
                all_search_results = []
                for query in search_queries:
                    try:
                        search_result = self.web_search.search(query, max_results=3)
                        if search_result.get("success"):
                            all_search_results.append(search_result)
                    except Exception as e:
                        logger.debug(f"Błąd wyszukiwania '{query}': {e}")
                
                # Formatuj wyniki dla prompta
                if all_search_results:
                    search_text_parts = []
                    for i, search_result in enumerate(all_search_results, 1):
                        formatted = self.web_search.format_search_results_for_prompt(search_result)
                        search_text_parts.append(formatted)
                    
                    # Zapisz wyniki do użycia w następnym promptcie
                    self._last_web_search_results = "\n".join(search_text_parts)
                    
                    # Zwróć None - sygnał, że trzeba ponownie wysłać prompt z wynikami wyszukiwania
                    return None  # Zwróć None, aby system ponownie wywołał analyze z wynikami wyszukiwania
                else:
                    # Kontynuuj normalnie bez wyników wyszukiwania
                    pass
            
            # Mapuj action na SignalType
            action_map = {
                'BUY': SignalType.BUY,
                'SELL': SignalType.SELL,
                'HOLD': SignalType.HOLD,
                'CLOSE': SignalType.CLOSE
            }
            
            action_str = data.get('action', 'HOLD').upper()
            if action_str not in action_map:
                logger.warning(f"Nieznana akcja: {action_str}, używam HOLD")
                action_str = 'HOLD'
            
            signal_type = action_map[action_str]
            
            # Jeśli HOLD, nie generuj sygnału, ale wyświetl informację
            if signal_type == SignalType.HOLD:
                # Wyświetl informację o decyzji HOLD
                logger.info("")
                logger.info("=" * 80)
                logger.info(f"🤖 DECYZJA LLM dla {symbol}: ⏸️  CZEKANIE (HOLD)")
                logger.info("=" * 80)
                
                # Wyświetl uzasadnienie jeśli dostępne
                reason = data.get('reason', '')
                observations = data.get('observations', '')
                confidence = data.get('confidence', 0.0)
                
                if confidence:
                    logger.info(f"Pewność: {float(confidence):.1f}/10.0")
                
                if reason:
                    logger.info("")
                    logger.info("📋 Uzasadnienie:")
                    reason_lines = reason.split('\n')
                    for line in reason_lines:
                        if line.strip():
                            logger.info(f"   {line.strip()}")
                
                if observations:
                    logger.info("")
                    logger.info("🔍 Obserwacje:")
                    observations_lines = observations.split('\n')
                    for line in observations_lines:
                        if line.strip():
                            logger.info(f"   {line.strip()}")
                
                logger.info("=" * 80)
                logger.info("")
                
                return None
            
            # Utwórz sygnał
            signal = TradingSignal(
                signal_type=signal_type,
                symbol=symbol,
                confidence=float(data.get('confidence', 5.0)),
                price=float(data.get('price', current_price)),
                stop_loss=float(data.get('stop_loss')) if data.get('stop_loss') else None,
                take_profit=float(data.get('take_profit')) if data.get('take_profit') else None,
                size_percent=float(data.get('size_percent', 10.0)),
                reason=data.get('reason', 'Decyzja LLM'),
                strategy=self.name,
                observations=data.get('observations', '')
            )
            
            # Wyświetl decyzję LLM w czytelnej formie (bez szczegółów requestów/odpowiedzi)
            self._display_llm_decision(signal, symbol, current_price)
            
            return signal
            
        except json.JSONDecodeError as e:
            logger.error(f"Błąd parsowania JSON z LLM: {e}")
            logger.debug(f"Odpowiedź LLM: {response[:500]}")
            return None
        except Exception as e:
            logger.error(f"Błąd parsowania odpowiedzi LLM: {e}")
            return None
    
    def _display_llm_decision(self, signal: TradingSignal, symbol: str, current_price: float):
        """
        Wyświetla decyzję LLM w czytelnej formie dla człowieka.
        
        Args:
            signal: Sygnał tradingowy z decyzją LLM
            symbol: Symbol rynku
            current_price: Aktualna cena
        """
        # Mapuj typ sygnału na czytelną nazwę
        action_map = {
            SignalType.BUY: "🟢 KUPNO (LONG)",
            SignalType.SELL: "🔴 SPRZEDAŻ (SHORT)",
            SignalType.HOLD: "⏸️  CZEKANIE",
            SignalType.CLOSE: "🔚 ZAMKNIĘCIE POZYCJI"
        }
        
        action_name = action_map.get(signal.signal_type, str(signal.signal_type))
        
        # Wyświetl nagłówek decyzji
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"🤖 DECYZJA LLM dla {symbol}")
        logger.info("=" * 80)
        logger.info(f"Akcja: {action_name}")
        logger.info(f"Pewność: {signal.confidence:.1f}/10.0")
        logger.info(f"Cena: ${signal.price:.2f} (aktualna: ${current_price:.2f})")
        
        # Parametry pozycji
        if signal.stop_loss:
            logger.info(f"Stop Loss: ${signal.stop_loss:.2f}")
        if signal.take_profit:
            logger.info(f"Take Profit: ${signal.take_profit:.2f}")
        logger.info(f"Rozmiar pozycji: {signal.size_percent:.1f}% kapitału")
        
        # Uzasadnienie
        if signal.reason:
            logger.info("")
            logger.info("📋 Uzasadnienie:")
            # Formatuj uzasadnienie (podziel na linie jeśli długie)
            reason_lines = signal.reason.split('\n')
            for line in reason_lines:
                if line.strip():
                    logger.info(f"   {line.strip()}")
        
        # Obserwacje
        if signal.observations:
            logger.info("")
            logger.info("🔍 Obserwacje i analiza:")
            # Formatuj obserwacje (podziel na linie jeśli długie)
            observations_lines = signal.observations.split('\n')
            for line in observations_lines:
                if line.strip():
                    logger.info(f"   {line.strip()}")
        
        logger.info("=" * 80)
        logger.info("")
    
    def _display_current_price_analysis(self, df: pd.DataFrame, symbol: str, current_price: float):
        """
        Wyświetla analizę aktualnego kursu w czytelnej formie.
        
        Args:
            df: DataFrame z danymi OHLCV
            symbol: Symbol rynku
            current_price: Aktualna cena
        """
        if df is None or df.empty:
            logger.warning(f"Brak danych do analizy dla {symbol}")
            return
        
        # Oblicz statystyki
        price_24h_ago = float(df['close'].iloc[0]) if len(df) > 0 else current_price
        change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100 if price_24h_ago > 0 else 0.0
        
        min_price = float(df['low'].min())
        max_price = float(df['high'].max())
        avg_volume = float(df['volume'].mean())
        current_volume = float(df['volume'].iloc[-1]) if len(df) > 0 else 0.0
        
        # Oblicz zmiany w różnych okresach
        if len(df) >= 10:
            price_10_candles_ago = float(df['close'].iloc[-10])
            change_10 = ((current_price - price_10_candles_ago) / price_10_candles_ago) * 100 if price_10_candles_ago > 0 else 0.0
        else:
            change_10 = change_24h
        
        # Określ trend
        if len(df) >= 2:
            prev_price = float(df['close'].iloc[-2])
            trend_short = "🟢 Wzrostowy" if current_price > prev_price else "🔴 Spadkowy" if current_price < prev_price else "➖ Neutralny"
        else:
            trend_short = "➖ Neutralny"
        
        # Wyświetl analizę
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"📊 ANALIZA AKTUALNEGO KURSU - {symbol}")
        logger.info("=" * 80)
        logger.info(f"Aktualna cena: ${current_price:,.2f}")
        
        # Zmiany cenowe
        change_emoji = "🟢" if change_24h > 0 else "🔴" if change_24h < 0 else "➖"
        logger.info(f"Zmiana (od początku historii): {change_emoji} {change_24h:+.2f}%")
        
        if len(df) >= 10:
            change_10_emoji = "🟢" if change_10 > 0 else "🔴" if change_10 < 0 else "➖"
            logger.info(f"Zmiana (ostatnie 10 świec): {change_10_emoji} {change_10:+.2f}%")
        
        logger.info(f"Trend krótkoterminowy: {trend_short}")
        
        # Statystyki cenowe
        logger.info("")
        logger.info("Statystyki cenowe:")
        logger.info(f"  Min (w historii): ${min_price:,.2f}")
        logger.info(f"  Max (w historii): ${max_price:,.2f}")
        logger.info(f"  Zakres: ${max_price - min_price:,.2f} ({(max_price - min_price) / current_price * 100:.2f}%)")
        
        # Wolumen
        logger.info("")
        logger.info("Wolumen:")
        logger.info(f"  Aktualny: {current_volume:,.0f}")
        logger.info(f"  Średni: {avg_volume:,.0f}")
        if avg_volume > 0:
            volume_ratio = current_volume / avg_volume
            volume_indicator = "📈 Wysoki" if volume_ratio > 1.5 else "📉 Niski" if volume_ratio < 0.5 else "➖ Normalny"
            logger.info(f"  Stosunek do średniej: {volume_ratio:.2f}x ({volume_indicator})")
        
        # Ostatnie 5 świec (krótki podgląd)
        if len(df) >= 5:
            logger.info("")
            logger.info("Ostatnie 5 świec:")
            recent_df = df.tail(5)
            for idx, row in recent_df.iterrows():
                timestamp = str(row.get('timestamp', ''))[:19] if 'timestamp' in row else str(idx)[:19]
                open_p = float(row.get('open', 0))
                high_p = float(row.get('high', 0))
                low_p = float(row.get('low', 0))
                close_p = float(row.get('close', 0))
                vol = float(row.get('volume', 0))
                candle_change = ((close_p - open_p) / open_p) * 100 if open_p > 0 else 0.0
                candle_emoji = "🟢" if candle_change > 0 else "🔴" if candle_change < 0 else "➖"
                logger.info(f"  {timestamp} | O: ${open_p:,.2f} H: ${high_p:,.2f} L: ${low_p:,.2f} C: ${close_p:,.2f} {candle_emoji} {candle_change:+.2f}% | V: {vol:,.0f}")
        
        logger.info("=" * 80)
        logger.info("")
    
    def analyze(
        self,
        df: pd.DataFrame,
        symbol: str = "BTC-USD"
    ) -> Optional[TradingSignal]:
        """
        Analizuje dane rynkowe używając LLM.
        
        Args:
            df: DataFrame z danymi OHLCV
            symbol: Symbol rynku
            
        Returns:
            TradingSignal lub None
        """
        if df is None or df.empty:
            logger.warning(f"Brak danych dla {symbol}")
            return None
        
        # Zapisz symbol dla should_close_position
        self._current_symbol = symbol
        
        # Aktualizuj historię
        self.update_price_history(symbol, df)
        
        # Pobierz aktualną cenę
        current_price = float(df['close'].iloc[-1])
        
        # Wyświetl analizę aktualnego kursu (zawsze, przed decyzją LLM)
        self._display_current_price_analysis(df, symbol, current_price)
        
        # Zbuduj prompt (z wynikami wyszukiwania jeśli były)
        prompt = self._build_prompt(symbol, current_price)
        
        # Wyślij do LLM
        try:
            # Użyj bezpośrednio LLM (nie przez MarketAnalyzerLLM.generate_market_report)
            # Wszystkie szczegóły requestów/odpowiedzi są logowane tylko do pliku przez API logger
            from langchain.schema import HumanMessage, SystemMessage
            
            messages = [
                SystemMessage(content="Jesteś ekspertem od tradingu kryptowalut. Analizujesz dane rynkowe i podejmujesz decyzje tradingowe. Możesz prosić o wyszukanie informacji w internecie jeśli potrzebujesz aktualnych danych."),
                HumanMessage(content=prompt)
            ]
            
            # Przygotuj messages do logowania
            messages_for_log = [
                {"role": msg.type if hasattr(msg, 'type') else str(type(msg).__name__), "content": msg.content}
                for msg in messages
            ]
            
            # Loguj request
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
            try:
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
                
                # Parsuj odpowiedź (szczegóły są logowane tylko do pliku przez API logger)
                signal = self._parse_llm_response(response_text, symbol, current_price)
                
                # Jeśli signal jest None (LLM poprosił o wyszukanie), wykonaj ponownie analyze
                if signal is None and hasattr(self, '_last_web_search_results') and self._last_web_search_results:
                    logger.info("🔄 Ponowne wywołanie analyze z wynikami wyszukiwania...")
                    # Wyczyść cache wyszukiwania (już dodane do prompta)
                    # Wywołaj ponownie analyze (z wynikami wyszukiwania w promptcie)
                    return self.analyze(df, symbol)  # Rekurencyjne wywołanie z wynikami wyszukiwania
                
                # Zapisz decyzję w historii (przed zwróceniem sygnału)
                if signal:
                    decision = {
                        'timestamp': datetime.now().isoformat(),
                        'symbol': symbol,
                        'action': signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type),
                        'price': float(signal.price) if signal.price else current_price,
                        'confidence': float(signal.confidence) if signal.confidence else 0.0,
                        'stop_loss': float(signal.stop_loss) if signal.stop_loss else None,
                        'take_profit': float(signal.take_profit) if signal.take_profit else None,
                        'size_percent': getattr(signal, 'size_percent', None),
                        'observations': getattr(signal, 'observations', ''),
                        'reason': signal.reason or '',
                        'result': 'N/A'  # Zostanie zaktualizowane po zamknięciu pozycji
                    }
                    self.decision_history.append(decision)
                    logger.debug(f"Zapisano decyzję w historii: {decision['action']} @ {decision['price']}")
                    
                    # Wyczyść wyniki wyszukiwania po użyciu
                    if hasattr(self, '_last_web_search_results'):
                        delattr(self, '_last_web_search_results')
                
                return signal
            except Exception as e:
                response_time_ms = (time.time() - start_time) * 1000
                error_msg = str(e)
                
                # Loguj błąd
                self.api_logger.log_response(
                    provider=self.provider,
                    model=self.model,
                    response_text="",
                    response_time_ms=response_time_ms,
                    metadata={"method": "analyze", "strategy": self.name, "symbol": symbol},
                    error=error_msg
                )
                
                logger.error(f"Błąd komunikacji z LLM: {e}")
                return None
        except Exception as e:
            logger.error(f"Błąd w metodzie analyze: {e}")
            return None
    
    def should_close_position(
        self,
        df: pd.DataFrame,
        entry_price: float,
        side: str,
        current_pnl_percent: float
    ) -> Optional[TradingSignal]:
        """
        Sprawdza czy pozycja powinna zostać zamknięta używając LLM.
        
        Args:
            df: DataFrame z danymi OHLCV
            entry_price: Cena wejścia
            side: "long" lub "short"
            current_pnl_percent: Aktualny PnL w %
            
        Returns:
            TradingSignal.CLOSE lub None
        """
        # Dla uproszczenia, użyj standardowej logiki
        # (można rozszerzyć o analizę LLM)
        if df is None or df.empty:
            return None
        
        # Pobierz symbol z kontekstu (jeśli dostępny) lub użyj domyślnego
        symbol = getattr(self, '_current_symbol', 'BTC-USD')
        current_price = float(df['close'].iloc[-1])
        
        if current_pnl_percent <= -10.0:  # Stop loss
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=current_price,
                reason="Stop loss (-10%)",
                strategy=self.name
            )
        
        if current_pnl_percent >= 20.0:  # Take profit
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=current_price,
                reason="Take profit (+20%)",
                strategy=self.name
            )
        
        return None

