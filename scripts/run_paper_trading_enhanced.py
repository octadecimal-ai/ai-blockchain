#!/usr/bin/env python3
"""
Enhanced Paper Trading Runner
==============================
Ulepszona wersja z real-time logowaniem i podsumowaniami.
"""

import os
import sys
import argparse
import signal
import time
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Dodaj ścieżkę projektu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Załaduj .env jeśli istnieje
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.trading.paper_trading import PaperTradingEngine
from src.trading.trading_bot import TradingBot
from src.trading.strategies.piotrek_strategy import PiotrekBreakoutStrategy
from src.trading.strategies.scalping_strategy import ScalpingStrategy
from src.trading.strategies.funding_rate_arbitrage_strategy import FundingRateArbitrageStrategy
from src.trading.strategies.improved_breakout_strategy import ImprovedBreakoutStrategy
from src.trading.strategies.prompt_strategy import PromptStrategy
from src.trading.strategies.prompt_strategy_v11 import PromptStrategyV11
from src.trading.strategies.prompt_strategy_v12 import PromptStrategyV12
from src.trading.strategies.piotr_swiec_strategy import PiotrSwiecStrategy
from src.trading.strategies.piotr_swiec_prompt_strategy import PiotrSwiecPromptStrategy
from src.trading.strategies.ultra_short_prompt_strategy import UltraShortPromptStrategy
from src.trading.strategies.test_prompt_strategy import TestPromptStrategy
from src.trading.strategies.sentiment_propagation_strategy import SentimentPropagationStrategy
# Import: plik under_human_strategy_1.0.py → import przez __init__.py
from src.trading.strategies import UnderhumanStrategyV10
from src.trading.models import Base as TradingBase
from src.trading.models_extended import Strategy, TradeRegister, TradingSession
from src.database.models import Base as DatabaseBase, create_timescale_hypertables
from src.utils.time_parser import parse_time_duration, format_duration, TimeParseError

# Import wszystkich modeli aby były zarejestrowane w metadata
from src.trading import (
    PaperAccount, PaperPosition, PaperOrder, PaperTrade,
    Strategy, TradeRegister, TradingSession
)


class EnhancedTradingBot(TradingBot):
    """
    Ulepszona wersja bota z logowaniem w czasie rzeczywistym.
    """
    
    def __init__(self, *args, **kwargs):
        # Dodatkowe parametry
        self.time_limit_seconds = kwargs.pop('time_limit_seconds', None)
        self.max_loss_limit = kwargs.pop('max_loss_limit', None)
        self.position_size_config = kwargs.pop('position_size_config', None)
        self.session_start = datetime.now()
        self.last_summary_time = datetime.now()
        self.summary_interval = 60  # Co 60 sekund pokaż podsumowanie
        
        super().__init__(*args, **kwargs)
        
        # Ustaw position_size_config w rodzicu jeśli został przekazany
        if self.position_size_config:
            self.position_size_config = self.position_size_config
        
        # Statystyki sesji
        self.session_stats = {
            'trades_opened': 0,
            'trades_closed': 0,
            'total_profit': 0.0,
            'total_loss': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0
        }
    
    def should_stop_session(self) -> tuple:
        """
        Sprawdza czy sesja powinna zostać zatrzymana.
        
        Returns:
            (should_stop, reason)
        """
        # Sprawdź limit czasu
        if self.time_limit_seconds:
            elapsed = (datetime.now() - self.session_start).total_seconds()
            if elapsed >= self.time_limit_seconds:
                return True, f"time_limit (osiągnięto {format_duration(int(elapsed))})"
        
        # Sprawdź limit straty
        if self.max_loss_limit:
            account_summary = self.engine_pt.get_account_summary()
            total_pnl = account_summary['total_pnl']
            
            if total_pnl <= -abs(self.max_loss_limit):
                return True, f"max_loss (strata: ${abs(total_pnl):.2f})"
        
        return False, None
    
    def log_trade_opened(self, position):
        """Loguje otwarcie transakcji."""
        emoji = "🟢" if position.side.value == "long" else "🔴"
        
        logger.success(
            f"\n{'='*70}\n"
            f"{emoji} NOWA POZYCJA OTWARTA\n"
            f"{'='*70}\n"
            f"Symbol:     {position.symbol}\n"
            f"Strona:     {position.side.value.upper()}\n"
            f"Rozmiar:    {position.size:.6f}\n"
            f"Cena:       ${position.entry_price:,.2f}\n"
            f"Wartość:    ${position.size * position.entry_price:,.2f}\n"
            f"Dźwignia:   {position.leverage}x\n"
            f"Margin:     ${position.margin_used:,.2f}\n"
            f"Stop Loss:  ${position.stop_loss:,.2f}" if position.stop_loss else "Stop Loss:  Brak\n"
            f"Take Profit: ${position.take_profit:,.2f}" if position.take_profit else "Take Profit: Brak\n"
            f"Strategia:  {position.strategy or 'N/A'}\n"
            f"{'='*70}"
        )
        
        self.session_stats['trades_opened'] += 1
    
    def log_trade_closed(self, trade):
        """Loguje zamknięcie transakcji."""
        is_profit = trade.net_pnl > 0
        emoji = "🎉" if is_profit else "😞"
        color = "green" if is_profit else "red"
        
        # Aktualizuj statystyki
        self.session_stats['trades_closed'] += 1
        if is_profit:
            self.session_stats['total_profit'] += trade.net_pnl
        else:
            self.session_stats['total_loss'] += abs(trade.net_pnl)
        
        if trade.net_pnl > self.session_stats['best_trade']:
            self.session_stats['best_trade'] = trade.net_pnl
        if trade.net_pnl < self.session_stats['worst_trade']:
            self.session_stats['worst_trade'] = trade.net_pnl
        
        duration = int((trade.exit_time - trade.entry_time).total_seconds())
        
        logger.opt(colors=True).info(
            f"\n{'='*70}\n"
            f"{emoji} POZYCJA ZAMKNIĘTA\n"
            f"{'='*70}\n"
            f"Symbol:         {trade.symbol}\n"
            f"Strona:         {trade.side.value.upper()}\n"
            f"Rozmiar:        {trade.size:.6f}\n"
            f"Wejście:        ${trade.entry_price:,.2f}\n"
            f"Wyjście:        ${trade.exit_price:,.2f}\n"
            f"Zmiana:         {((trade.exit_price - trade.entry_price) / trade.entry_price * 100):+.2f}%\n"
            f"<{color}>PnL (brutto):   ${trade.pnl:+,.2f}</{color}>\n"
            f"Opłaty:         ${trade.total_fees:,.2f}\n"
            f"<{color}>PnL (netto):    ${trade.net_pnl:+,.2f} ({trade.pnl_percent:+.2f}%)</{color}>\n"
            f"Czas trwania:   {format_duration(duration)}\n"
            f"Powód wyjścia:  {trade.exit_reason}\n"
            f"{'='*70}"
        )
    
    def show_live_summary(self, force: bool = False):
        """Pokazuje podsumowanie na żywo."""
        now = datetime.now()
        if not force and (now - self.last_summary_time).total_seconds() < self.summary_interval:
            return
        
        self.last_summary_time = now
        
        account_summary = self.engine_pt.get_account_summary()
        elapsed = int((now - self.session_start).total_seconds())
        
        # Oblicz saldo z unrealized PnL
        equity = account_summary['equity']
        unrealized_pnl = account_summary['unrealized_pnl']
        
        # Kolory dla PnL
        total_pnl = account_summary['total_pnl']
        pnl_color = "green" if total_pnl >= 0 else "red"
        unrealized_color = "green" if unrealized_pnl >= 0 else "red"
        
        logger.opt(colors=True).info(
            f"\n{'─'*70}\n"
            f"📊 <cyan><b>PODSUMOWANIE NA ŻYWO</b></cyan> (czas: {format_duration(elapsed)})\n"
            f"{'─'*70}\n"
            f"<white>Konto:           {account_summary['account_name']}</white>\n"
            f"<white>Saldo:           ${account_summary['current_balance']:,.2f}</white>\n"
            f"<{unrealized_color}>Unrealized PnL:  ${unrealized_pnl:+,.2f}</{unrealized_color}>\n"
            f"<white><b>Equity:          ${equity:,.2f}</b></white>\n"
            f"{'─'*70}\n"
            f"<{pnl_color}><b>Całkowity PnL:   ${total_pnl:+,.2f}</b></{pnl_color}>\n"
            f"<white>Zarobiono:       ${self.session_stats['total_profit']:,.2f}</white>\n"
            f"<white>Stracono:        ${self.session_stats['total_loss']:,.2f}</white>\n"
            f"<white>ROI:             {account_summary['roi']:+.2f}%</white>\n"
            f"{'─'*70}\n"
            f"<white>Transakcje:      {self.session_stats['trades_closed']} zamknięte, "
            f"{account_summary['open_positions']} otwarte</white>\n"
            f"<white>Win Rate:        {account_summary['win_rate']:.1f}%</white>\n"
            f"<green>Najlepsza:       ${self.session_stats['best_trade']:+,.2f}</green>\n"
            f"<red>Najgorsza:       ${self.session_stats['worst_trade']:+,.2f}</red>\n"
            f"{'─'*70}\n"
        )
        
        # Wyświetl statystyki API LLM (jeśli używane)
        try:
            from src.utils.api_logger import get_api_logger
            api_logger = get_api_logger()
            api_logger.print_session_stats()
        except Exception:
            pass  # Ignoruj błędy jeśli API logger nie jest dostępny
        
        # Pokaż otwarte pozycje
        open_positions = self.engine_pt.get_open_positions()
        if open_positions:
            logger.info("📈 Otwarte pozycje:")
            for pos in open_positions:
                current_price = self.engine_pt.get_current_price(pos.symbol)
                pnl, pnl_pct = pos.calculate_pnl(current_price)
                pnl_emoji = "🟢" if pnl > 0 else "🔴"
                logger.opt(colors=True).info(
                    f"  {pnl_emoji} <white>{pos.symbol}</white> <cyan>{pos.side.value.upper()}</cyan>: "
                    f"{pos.size:.6f} @ ${pos.entry_price:,.2f} → ${current_price:,.2f} | "
                    f"PnL: <{'green' if pnl > 0 else 'red'}>${pnl:+,.2f} ({pnl_pct:+.2f}%)</{'green' if pnl > 0 else 'red'}>"
                )
    
    def _handle_buy_signal(self, signal):
        """Override z logowaniem - zwraca bool jak klasa bazowa."""
        # Sprawdź czy nie mamy za dużo pozycji
        open_positions = self.engine_pt.get_open_positions()
        if len(open_positions) >= self.max_positions:
            logger.warning(f"Maksymalna liczba pozycji ({self.max_positions}) - ignoruję sygnał BUY")
            return False
        
        # Sprawdź czy nie mamy już pozycji na tym symbolu
        symbol_positions = [p for p in open_positions if p.symbol == signal.symbol]
        if symbol_positions:
            logger.warning(f"Już mamy otwartą pozycję na {signal.symbol} - ignoruję")
            return False
        
        # Oblicz rozmiar pozycji
        if self.position_size_config:
            # Stały rozmiar pozycji (np. 1 BTC)
            symbol_base = signal.symbol.split("-")[0]  # BTC z BTC-USD
            if symbol_base == self.position_size_config['symbol']:
                size = self.position_size_config['size']
                logger.info(f"Używam stałego rozmiaru pozycji: {size} {symbol_base}")
            else:
                # Dla innych symboli użyj procentu
                account = self.engine_pt.get_account_summary()
                capital_to_use = account['current_balance'] * (self.position_size_percent / 100)
                size = capital_to_use / signal.price
        else:
            # Procent kapitału
            account = self.engine_pt.get_account_summary()
            capital_to_use = account['current_balance'] * (self.position_size_percent / 100)
            size = capital_to_use / signal.price
        
        # Otwórz pozycję
        position = self.engine_pt.open_position(
            symbol=signal.symbol,
            side="long",
            size=size,
            leverage=self.default_leverage,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            strategy=signal.strategy,
            notes=signal.reason
        )
        
        if position:
            logger.success(f"✅ Otwarto pozycję na sygnał: {signal}")
            self.log_trade_opened(position)
            return True
        
        return False
    
    def run_cycle(self):
        """Override z sprawdzaniem limitów."""
        # Sprawdź czy nie przekroczono limitów
        should_stop, reason = self.should_stop_session()
        if should_stop:
            logger.warning(f"⏹️  Zatrzymanie sesji: {reason}")
            self.stop()
            return
        
        # Standardowy cykl
        super().run_cycle()
        
        # Pokaż podsumowanie
        self.show_live_summary()
    
    def check_positions_for_exit(self):
        """Override z logowaniem."""
        positions_before = len(self.engine_pt.get_open_positions())
        super().check_positions_for_exit()
        positions_after = len(self.engine_pt.get_open_positions())
        
        # Jeśli zamknięto pozycje, zaloguj
        if positions_before > positions_after:
            closed_count = positions_before - positions_after
            logger.info(f"📊 Zamknięto {closed_count} pozycji przez strategię")


def setup_logging(verbose: bool = False):
    """Konfiguruje kolorowe logowanie."""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=level,
        colorize=True
    )
    
    # Log do pliku
    os.makedirs("logs", exist_ok=True)
    logger.add(
        "logs/trading_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Enhanced Paper Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Parametry podstawowe
    parser.add_argument("--account", default="piotrek_bot", help="Nazwa konta")
    parser.add_argument("--balance", type=float, default=10000.0, help="Początkowy kapitał")
    parser.add_argument("--symbols", default="BTC-USD,ETH-USD", help="Symbole (oddzielone przecinkami)")
    parser.add_argument("--leverage", type=float, default=2.0, help="Dźwignia")
    parser.add_argument("--strategy", default="piotrek_breakout_strategy", help="Nazwa strategii (piotrek_breakout_strategy, scalping_strategy, funding_rate_arbitrage, improved_breakout_strategy, prompt_strategy, prompt_strategy_v11, prompt_strategy_v12, piotr_swiec_strategy, piotr_swiec_prompt_strategy, ultra_short_prompt_strategy, test_prompt_strategy, under_human_strategy_1.0, sentiment_propagation_strategy)")
    
    # Prompt strategy
    parser.add_argument("--prompt-file", help="Ścieżka do pliku z promptem (wymagane dla prompt_strategy)")
    
    # Timing
    parser.add_argument("--time-limit", help="Limit czasu (np. 10h, 30min)")
    parser.add_argument("--interval", default="5min", help="Interwał sprawdzania")
    
    # Limity
    parser.add_argument("--max-loss", type=float, help="Maksymalna strata w USD")
    
    # Pozycja
    parser.add_argument(
        "--position-size",
        help="Stały rozmiar pozycji (np. BTC:1, ETH:10). Format: SYMBOL:ILOŚĆ"
    )
    
    # Dźwięki
    parser.add_argument(
        "--no-sounds",
        action="store_true",
        help="Wyłącz dźwięki powiadomień"
    )
    parser.add_argument(
        "--sounds-tts",
        action="store_true",
        help="Użyj text-to-speech zamiast dźwięków systemowych"
    )
    
    # Inne
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument(
        "--db",
        default=None,
        help="Database URL (domyślnie: DATABASE_URL z .env lub SQLite)"
    )
    
    # Sentiment Propagation Strategy
    parser.add_argument(
        "--sentiment-source",
        default="llm",
        choices=["llm", "gdelt"],
        help="Źródło danych sentymentu dla SentimentPropagationStrategy: llm (llm_sentiment_analysis) lub gdelt (GDELT API). Domyślnie: llm"
    )
    
    args = parser.parse_args()
    
    # Pobierz URL bazy danych (TYLKO PostgreSQL)
    if args.db:
        database_url = args.db
    else:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL nie jest ustawiony! Ustaw zmienną środowiskową DATABASE_URL (PostgreSQL)")
            logger.error("Przykład: export DATABASE_URL='postgresql://user:pass@localhost:5432/dbname'")
            sys.exit(1)
        else:
            logger.info(f"Używam PostgreSQL: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    
    # Setup
    setup_logging(args.verbose)
    os.makedirs("data", exist_ok=True)
    
    # Konfiguruj dźwięki
    if args.no_sounds:
        os.environ['TRADING_SOUNDS_ENABLED'] = 'false'
    if args.sounds_tts:
        os.environ['TRADING_SOUNDS_TTS'] = 'true'
    
    # Parsuj czasy
    try:
        time_limit_seconds = parse_time_duration(args.time_limit) if args.time_limit else None
        interval_seconds = parse_time_duration(args.interval)
    except TimeParseError as e:
        logger.error(f"Błąd parsowania czasu: {e}")
        sys.exit(1)
    
    # Baza danych
    is_postgresql = 'postgresql' in database_url.lower()
    engine = create_engine(database_url, echo=False)
    
    # Utwórz wszystkie tabele (trading + database)
    # Import wszystkich modeli aby były zarejestrowane
    from src.database.models import (
        OHLCV, Ticker, Trade, TechnicalIndicator,
        SentimentScore, Signal, Portfolio, Position
    )
    
    DatabaseBase.metadata.create_all(engine)
    TradingBase.metadata.create_all(engine)
    
    # TimescaleDB hypertables (tylko dla PostgreSQL)
    if is_postgresql and os.getenv('USE_TIMESCALE', 'false').lower() == 'true':
        try:
            create_timescale_hypertables(engine)
            logger.debug("Hypertables TimescaleDB utworzone")
        except Exception as e:
            logger.warning(f"Nie udało się utworzyć hypertables: {e}")
    
    logger.debug("Tabele w bazie danych utworzone")
    
    # Symbole
    symbols = [s.strip() for s in args.symbols.split(",")]
    
    # Parsuj position-size (format: BTC:1, ETH:10)
    position_size_config = None
    if args.position_size:
        try:
            parts = args.position_size.split(":")
            if len(parts) == 2:
                position_size_config = {
                    'symbol': parts[0].upper(),  # BTC, ETH, etc.
                    'size': float(parts[1])  # 1, 10, etc.
                }
                logger.info(f"Stały rozmiar pozycji: {position_size_config['size']} {position_size_config['symbol']}")
            else:
                logger.warning(f"Nieprawidłowy format --position-size: {args.position_size} (oczekiwano: SYMBOL:ILOŚĆ)")
        except Exception as e:
            logger.warning(f"Błąd parsowania --position-size: {e}")
    
    # Wybierz strategię
    strategy_name = args.strategy.lower() if hasattr(args, 'strategy') else 'piotrek_breakout_strategy'
    
    # Utwórz DydxCollector (potrzebny dla Funding Rate Arbitrage)
    from src.collectors.exchange.dydx_collector import DydxCollector
    dydx_collector = DydxCollector(testnet=False)
    
    if strategy_name == 'funding_rate_arbitrage':
        # Strategia Funding Rate Arbitrage - konserwatywne parametry dla pierwszego testu
        # UWAGA: Aktualny funding rate dla BTC-USD to ~0.0010% (0.01%)
        # Dla pierwszego testu ustawiamy niższy próg (0.005%) aby strategia mogła działać
        # W produkcji zwiększ do 0.02-0.03% dla bezpieczeństwa
        strategy_config = {
            'timeframe': '1h',  # Sprawdzanie co godzinę
            'min_funding_rate': 0.005,  # 0.005% na 8h (niższy próg dla pierwszego testu)
            'target_funding_rate': 0.06,  # 0.06% na 8h
            'max_position_size': 30.0,  # 30% kapitału (konserwatywne)
            'funding_interval_hours': 8,
            'min_holding_hours': 48,  # Trzymaj minimum 48h (2-3 płatności funding)
            'use_spot_hedge': True,
            'max_leverage': 2.0,
            'dydx_collector': dydx_collector,  # Przekaż collector dla rzeczywistych funding rates
            'use_real_funding_rate': True  # Użyj rzeczywistych funding rates z dYdX
        }
        strategy = FundingRateArbitrageStrategy(strategy_config)
    elif strategy_name == 'prompt_strategy':
        # Strategia Prompt Strategy - używa LLM do podejmowania decyzji
        if not args.prompt_file:
            logger.error("--prompt-file jest wymagane dla prompt_strategy!")
            sys.exit(1)
        
        strategy = PromptStrategy({
            'prompt_file': args.prompt_file,
            'provider': os.getenv('LLM_PROVIDER', 'anthropic'),
            'model': os.getenv('LLM_MODEL', 'claude-3-5-haiku-20241022'),
            'api_key': os.getenv('ANTHROPIC_API_KEY') or os.getenv('OPENAI_API_KEY'),
            'max_history_candles': 100
        })
        
        # Ustaw kontekst sesji dla strategii
        session_context = {
            'balance': args.balance,
            'time_limit': args.time_limit,
            'max_loss': args.max_loss,
            'mode': 'paper'  # Zawsze paper dla tego skryptu
        }
        strategy.set_session_context(session_context)
    elif strategy_name == 'prompt_strategy_v11':
        # Strategia Prompt Strategy v1.1 - ulepszona wersja z wskaźnikami technicznymi
        if not args.prompt_file:
            logger.error("--prompt-file jest wymagane dla prompt_strategy_v11!")
            sys.exit(1)
        
        strategy = PromptStrategyV11({
            'prompt_file': args.prompt_file,
            'provider': os.getenv('LLM_PROVIDER', 'anthropic'),
            'model': os.getenv('LLM_MODEL', 'claude-3-5-haiku-20241022'),
            'api_key': os.getenv('ANTHROPIC_API_KEY') or os.getenv('OPENAI_API_KEY'),
            'max_history_candles': 50,
            # Wskaźniki techniczne
            'rsi_period': 14,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'bb_period': 20,
            'bb_std': 2.0,
            'atr_period': 14,
            # Trailing stop
            'trailing_stop_enabled': True,
            'trailing_stop_atr_multiplier': 2.0,
            'trailing_stop_percent': 3.0,
            # Dynamiczny trading
            'min_confidence_for_trade': 5.0,
            'force_close_on_reversal': True,
            'max_hold_candles': 48
        })
        
        # Ustaw kontekst sesji dla strategii
        session_context = {
            'balance': args.balance,
            'time_limit': args.time_limit,
            'max_loss': args.max_loss,
            'mode': 'paper'
        }
        strategy.set_session_context(session_context)
    elif strategy_name == 'prompt_strategy_v12':
        # Strategia Prompt Strategy v1.2 - ulepszona wersja z agresywnym zarządzaniem pozycjami
        if not args.prompt_file:
            logger.error("--prompt-file jest wymagane dla prompt_strategy_v12!")
            sys.exit(1)
        
        strategy = PromptStrategyV12({
            'prompt_file': args.prompt_file,
            'provider': os.getenv('LLM_PROVIDER', 'anthropic'),
            'model': os.getenv('LLM_MODEL', 'claude-3-5-haiku-20241022'),
            'api_key': os.getenv('ANTHROPIC_API_KEY') or os.getenv('OPENAI_API_KEY'),
            'max_history_candles': 50,
            # Wskaźniki techniczne
            'rsi_period': 14,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'bb_period': 20,
            'bb_std': 2.0,
            'atr_period': 14,
            # Automatyczne zamykanie pozycji (NOWE!)
            'auto_take_profit_percent': 2.0,  # +2% take profit
            'auto_stop_loss_percent': -1.5,   # -1.5% stop loss
            'max_hold_hours': 4.0,            # Max 4h trzymania
            # Trailing stop
            'trailing_stop_enabled': True,
            'trailing_stop_atr_multiplier': 2.0,
            'trailing_stop_percent': 2.0,
            # Dynamiczny trading
            'min_confidence_for_trade': 6.0,
            'force_close_on_reversal': True,
            'max_hold_candles': 24,
            # Whale tracking
            'whale_tracking_enabled': True,
            'whale_trade_threshold': 10.0
        })
        
        # Ustaw kontekst sesji dla strategii
        session_context = {
            'balance': args.balance,
            'time_limit': args.time_limit,
            'max_loss': args.max_loss,
            'mode': 'paper'
        }
        strategy.set_session_context(session_context)
    elif strategy_name == 'improved_breakout_strategy':
        # Strategia Improved Breakout - AGRESYWNE parametry dla szybkiego generowania transakcji
        # Parametry ustawione tak, aby strategia mogła wygenerować transakcje w ciągu 12h
        strategy = ImprovedBreakoutStrategy({
            'timeframe': '1h',  # 1h timeframe
            'breakout_threshold': 0.2,  # Bardzo niski próg (0.2% zamiast 0.5%) - łatwiej wykryje breakout
            'min_confidence': 2.5,  # Niska pewność (2.5 zamiast 4.0) - łatwiej wygeneruje sygnał
            'risk_reward_ratio': 1.5,  # Niższy risk/reward dla szybszych transakcji
            'atr_multiplier': 1.5,  # Mniejszy stop loss (1.5 zamiast 2.0)
            'min_volume_ratio': 1.2,  # Niższy próg wolumenu (1.2 zamiast 1.5) - łatwiej przejdzie filtr
            'use_trend_filter': False,  # Wyłącz filtr trendu - więcej sygnałów
            'use_volume_filter': False,  # Wyłącz filtr wolumenu - więcej sygnałów
            'trailing_stop_enabled': True,
            'trailing_stop_atr_multiplier': 1.2,
            'use_rsi': True,
            'rsi_period': 14,
            'rsi_oversold': 40,  # Szerszy zakres (40 zamiast 35) - łatwiej wykryje
            'rsi_overbought': 60,  # Szerszy zakres (60 zamiast 65) - łatwiej wykryje
            'trend_sma_period': 30,  # Krótszy okres (30 zamiast 50) - szybsze wykrycie trendu
            'trend_ema_period': 15  # Krótszy okres (15 zamiast 20) - szybsze wykrycie trendu
        })
    elif strategy_name == 'scalping_strategy':
        # Strategia Scalping - szybkie transakcje
        # Użyj krótkiego timeframe (1min lub 5min) dla scalping
        strategy = ScalpingStrategy({
            'timeframe': '1min',  # Krótki timeframe dla scalping
            'min_price_change': 0.1,
            'max_price_change': 0.5,
            'min_confidence': 4.0,
            'rsi_period': 7,
            'rsi_oversold': 25,
            'rsi_overbought': 75,
            'macd_fast': 8,
            'macd_slow': 21,
            'macd_signal': 5,
            'atr_period': 7,
            'atr_multiplier': 1.5,
            'atr_take_profit': 2.0,
            'min_volume_ratio': 1.2,
            'risk_reward_ratio': 1.5,
            'slippage_percent': 0.1
        })
    elif strategy_name == 'piotr_swiec_strategy':
        # Strategia Piotra Święsa - impulsowa z RSI
        strategy = PiotrSwiecStrategy({
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'atr_period': 14,
            # Parametry impulsu
            'impulse_lookback': 4,
            'impulse_threshold_pct': 0.8,
            'impulse_atr_mult': 2.0,
            'use_atr_for_impulse': False,
            # Target/Loss w USD
            'target_profit_usd': 500.0,
            'max_loss_usd': 500.0,
            # Timing
            'max_hold_seconds': 900,  # 15 min
            'cooldown_seconds': 120,   # 2 min
            # Slippage
            'slippage_percent': 0.1,
            # Position sizing
            'position_size_btc': 0.1,
            'use_fixed_size': True,
            # Confidence
            'min_confidence_for_trade': 8.0
        })
    elif strategy_name == 'piotr_swiec_prompt_strategy':
        # Strategia Piotra Święsa z LLM
        prompt_file = args.prompt_file or 'prompts/trading/piotr_swiec_method.txt'
        strategy = PiotrSwiecPromptStrategy({
            'prompt_file': prompt_file,
            # RSI
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            # Sharp move
            'sharp_move_lookback': 5,
            'sharp_move_threshold': 0.8,
            # Target/Loss
            'target_profit_usd': 800.0,
            'max_loss_usd': 500.0,
            'position_size_percent': 15.0,
            # Timing
            'max_hold_minutes': 15,
            'cooldown_minutes': 2
        })
    elif strategy_name == 'ultra_short_prompt_strategy':
        # Strategia Ultra Short - VWAP Fakeout z LLM
        prompt_file = args.prompt_file or 'prompts/trading/ultra_short_strategy_prompt.txt'
        strategy = UltraShortPromptStrategy({
            'prompt_file': prompt_file,
            'provider': os.getenv('LLM_PROVIDER', 'anthropic'),
            'model': os.getenv('LLM_MODEL', 'claude-3-5-haiku-20241022'),
            'api_key': os.getenv('ANTHROPIC_API_KEY') or os.getenv('OPENAI_API_KEY'),
            # RSI
            'rsi_period': 14,
            'rsi_short_threshold': 65,  # Filtr dla SHORT
            'rsi_long_threshold': 35,  # Filtr dla LONG
            # VWAP fakeout
            'vwap_fakeout_min_percent': 0.5,  # Min wybicie w %
            'vwap_fakeout_max_percent': 1.0,  # Max wybicie w %
            # Target/Loss w USD
            'target_profit_usd_min': 300.0,
            'target_profit_usd_max': 800.0,
            'max_loss_usd_min': 300.0,
            'max_loss_usd_max': 500.0,
            # Position sizing
            'position_size_percent_min': 10.0,
            'position_size_percent_max': 20.0,
            # Timing
            'max_hold_minutes': 15,
            'min_hold_minutes': 10,
            'cooldown_minutes': 2
        })
        
        # Ustaw kontekst sesji dla strategii
        session_context = {
            'balance': args.balance,
            'time_limit': args.time_limit,
            'max_loss': args.max_loss,
            'mode': 'paper'
        }
        strategy.set_session_context(session_context)
    elif strategy_name == 'test_prompt_strategy':
        # Testowa strategia prompt-based
        prompt_file = args.prompt_file or 'prompts/trading/test_prompt_strategy.txt'
        strategy = TestPromptStrategy({
            'prompt_file': prompt_file,
            'provider': os.getenv('LLM_PROVIDER', 'anthropic'),
            'model': os.getenv('LLM_MODEL', 'claude-3-5-haiku-20241022'),
            'api_key': os.getenv('ANTHROPIC_API_KEY') or os.getenv('OPENAI_API_KEY'),
            # Parametry testowe
            'test_position_size_usd': 100.0,
            'stop_loss_usd': 500.0,
            'take_profit_usd': 1000.0
        })
        
        # Ustaw kontekst sesji dla strategii
        session_context = {
            'balance': args.balance,
            'time_limit': args.time_limit,
            'max_loss': args.max_loss,
            'mode': 'paper'
        }
        strategy.set_session_context(session_context)
    elif strategy_name == 'under_human_strategy_1.0':
        # Strategia UNDERHUMAN v1.0 - handluje zmianę stanu rynku
        strategy = UnderhumanStrategyV10({
            # RSI
            'rsi_period': 14,
            # Okna analizy
            'lookback_state': 36,      # 3h na 5min
            'lookback_short': 6,       # 30min
            'lookback_impulse': 4,     # 20min
            # Anomalie
            'impulse_threshold_pct': 0.8,
            'min_anomalies_to_trade': 2,
            # Orderbook
            'orderbook_levels': 10,
            'imbalance_threshold': 0.18,
            # Funding/OI
            'funding_divergence_z': 1.2,
            'oi_divergence_z': 1.2,
            # Reaction delay
            'delay_threshold': 1.35,
            # Money/risk
            'target_profit_usd_min': 400.0,
            'target_profit_usd_max': 1000.0,
            'max_loss_usd': 500.0,
            # Timing
            'max_hold_seconds': 900,  # 15 min
            'cooldown_seconds': 120,   # 2 min
            # Slippage
            'slippage_percent': 0.1,
            # Confidence
            'min_confidence_for_trade': 7.0,
            # Position size
            'position_size_btc': 0.1
        })
    elif strategy_name == 'sentiment_propagation_strategy':
        # Strategia Propagacji Sentymentu - oparta na propagacji sentymentu między regionami
        symbol = args.symbols[0] if args.symbols else "BTC/USDC"
        sentiment_source = getattr(args, 'sentiment_source', 'llm')  # llm lub gdelt
        
        # Konfiguracja w zależności od źródła danych
        if sentiment_source == 'llm':
            # Użyj danych z llm_sentiment_analysis
            use_llm_data = True
            logger.info("Używam danych z llm_sentiment_analysis jako źródła sentymentu")
        else:  # gdelt
            # Użyj danych z GDELT API
            use_llm_data = False
            logger.info("Używam danych z GDELT API jako źródła sentymentu")
        
        strategy = SentimentPropagationStrategy({
            'symbol': symbol,  # Symbol dla danych LLM z bazy
            'query': 'bitcoin OR cryptocurrency',  # Używane dla GDELT lub jako fallback
            'countries': ['US', 'CN', 'JP', 'KR', 'DE', 'GB'],
            'days_back': 7,
            'min_wave_strength': 0.5,
            'min_confidence': 6.0,
            'recent_wave_hours': 24,
            'target_profit_percent': 2.0,
            'stop_loss_percent': 1.5,
            'max_hold_hours': 48,
            'use_llm_data': use_llm_data,  # Przekaż wybór źródła danych
            '_backtest_mode': False  # Używamy rzeczywistego API
        })
    else:
        # Strategia Breakout (domyślna) - AGRESYWNE parametry dla szybkiego testowania
        # Dla normalnego użycia zwiększ min_confidence do 5-6 i breakout_threshold do 0.8-1.0
        strategy = PiotrekBreakoutStrategy({
            'breakout_threshold': 0.3,  # Bardzo niski próg - łatwiej wykryje breakout
            'consolidation_threshold': 0.3,  # Niższy próg konsolidacji
            'min_confidence': 3,  # Bardzo niska pewność - łatwiej wygeneruje sygnał
            'risk_reward_ratio': 1.5,  # Niższy risk/reward dla szybszych transakcji
            'lookback_period': 15,  # Krótszy okres analizy
            'consolidation_candles': 2,  # Szybsze wykrycie konsolidacji
            'use_rsi': True,
            'rsi_period': 14,
            'rsi_oversold': 35,  # Szerszy zakres dla RSI (łatwiej wykryje)
            'rsi_overbought': 65
        })
    
    # Bot
    bot = EnhancedTradingBot(
        database_url=database_url,
        account_name=args.account,
        initial_balance=args.balance,
        symbols=symbols,
        strategy=strategy,
        check_interval=interval_seconds,
        time_limit_seconds=time_limit_seconds,
        max_loss_limit=args.max_loss,
        position_size_config=position_size_config
    )
    
    # Pokaż konfigurację
    logger.info(f"🚀 Uruchamiam Enhanced Trading Bot")
    logger.info(f"   Strategia: {strategy.name}")
    logger.info(f"   Symbole: {', '.join(symbols)}")
    logger.info(f"   Interwał: {format_duration(interval_seconds)}")
    if time_limit_seconds:
        logger.info(f"   Limit czasu: {format_duration(time_limit_seconds)}")
    if args.max_loss:
        logger.info(f"   Maksymalna strata: ${args.max_loss:.2f}")
    logger.info("")
    
    # Pokaż początkowy stan
    bot.show_live_summary(force=True)
    
    logger.info("\n🎯 Bot uruchomiony! Naciśnij Ctrl+C aby zatrzymać\n")
    
    # Obsługa SIGINT
    def signal_handler(sig, frame):
        logger.info("\n\n⏹️  Otrzymano sygnał zatrzymania...")
        bot.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Uruchom
    try:
        bot.start()
    except KeyboardInterrupt:
        pass
    finally:
        # Końcowe podsumowanie
        bot.show_live_summary(force=True)


if __name__ == "__main__":
    main()

