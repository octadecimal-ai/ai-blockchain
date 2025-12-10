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
        self.session_start = datetime.now()
        self.last_summary_time = datetime.now()
        self.summary_interval = 60  # Co 60 sekund pokaż podsumowanie
        
        super().__init__(*args, **kwargs)
        
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
        """Override z logowaniem."""
        position = super()._handle_buy_signal(signal)
        if position:
            self.log_trade_opened(position)
        return position
    
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
    
    # Timing
    parser.add_argument("--time-limit", help="Limit czasu (np. 10h, 30min)")
    parser.add_argument("--interval", default="5min", help="Interwał sprawdzania")
    
    # Limity
    parser.add_argument("--max-loss", type=float, help="Maksymalna strata w USD")
    
    # Inne
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument(
        "--db",
        default=None,
        help="Database URL (domyślnie: DATABASE_URL z .env lub SQLite)"
    )
    
    args = parser.parse_args()
    
    # Pobierz URL bazy danych
    if args.db:
        database_url = args.db
    else:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            database_url = "sqlite:///data/paper_trading.db"
            logger.info(f"Brak DATABASE_URL w .env - używam SQLite: {database_url}")
        else:
            logger.info(f"Używam DATABASE_URL z .env: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    
    # Setup
    setup_logging(args.verbose)
    os.makedirs("data", exist_ok=True)
    
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
        OHLCV, Ticker, FundingRate, Trade, TechnicalIndicator,
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
    
    # Strategia
    strategy = PiotrekBreakoutStrategy({
        'breakout_threshold': 0.8,
        'consolidation_threshold': 0.4,
        'min_confidence': 5,
        'risk_reward_ratio': 2.0
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
        max_loss_limit=args.max_loss
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

