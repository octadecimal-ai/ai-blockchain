#!/usr/bin/env python3
"""
Skrypt do uruchamiania Paper Trading na dYdX.

Użycie:
    python scripts/run_paper_trading.py [opcje]

Przykłady:
    # Uruchom z domyślnymi ustawieniami
    python scripts/run_paper_trading.py

    # Uruchom z własną konfiguracją
    python scripts/run_paper_trading.py --balance 50000 --symbols BTC-USD,ETH-USD,SOL-USD

    # Tylko sprawdź stan konta
    python scripts/run_paper_trading.py --status

    # Resetuj konto
    python scripts/run_paper_trading.py --reset
"""

import os
import sys
import argparse

# Dodaj ścieżkę projektu do PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.trading.paper_trading import PaperTradingEngine
from src.trading.trading_bot import TradingBot
from src.trading.strategies.piotrek_strategy import PiotrekBreakoutStrategy
from src.trading.models import Base


def setup_logging(verbose: bool = False):
    """Konfiguruje logowanie."""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level=level,
        colorize=True
    )
    
    # Log do pliku
    os.makedirs("logs", exist_ok=True)
    logger.add(
        "logs/paper_trading_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level="DEBUG"
    )


def show_status(engine: PaperTradingEngine):
    """Pokazuje status konta."""
    summary = engine.get_account_summary()
    stats = engine.get_performance_stats()
    
    print("\n" + "=" * 60)
    print("📊 PAPER TRADING - STATUS KONTA")
    print("=" * 60)
    print(f"Konto: {summary['account_name']}")
    print(f"Saldo początkowe: ${summary['initial_balance']:,.2f}")
    print(f"Saldo aktualne: ${summary['current_balance']:,.2f}")
    print(f"Unrealized PnL: ${summary['unrealized_pnl']:,.2f}")
    print(f"Equity: ${summary['equity']:,.2f}")
    print("-" * 60)
    print(f"Całkowity PnL: ${summary['total_pnl']:,.2f}")
    print(f"ROI: {summary['roi']:.2f}%")
    print(f"Max Drawdown: {summary['max_drawdown']:.2f}%")
    print("-" * 60)
    print(f"Liczba transakcji: {stats['total_trades']}")
    print(f"Win Rate: {stats['win_rate']:.1f}%")
    print(f"Profit Factor: {stats['profit_factor']:.2f}")
    print(f"Średni zysk: ${stats['avg_win']:.2f}")
    print(f"Średnia strata: ${stats['avg_loss']:.2f}")
    print("-" * 60)
    print(f"Otwarte pozycje: {summary['open_positions']}")
    
    # Pokaż otwarte pozycje
    positions = engine.get_open_positions()
    if positions:
        print("\n📈 OTWARTE POZYCJE:")
        for pos in positions:
            current_price = engine.get_current_price(pos.symbol)
            pnl, pnl_pct = pos.calculate_pnl(current_price)
            emoji = "🟢" if pnl > 0 else "🔴"
            print(f"  {emoji} {pos.symbol} {pos.side.value.upper()}: "
                  f"{pos.size:.4f} @ ${pos.entry_price:,.2f} → ${current_price:,.2f} "
                  f"| PnL: ${pnl:,.2f} ({pnl_pct:+.2f}%)")
    
    # Ostatnie transakcje
    trades = engine.get_trade_history(limit=5)
    if trades:
        print("\n📋 OSTATNIE TRANSAKCJE:")
        for trade in trades:
            emoji = "🟢" if trade.net_pnl > 0 else "🔴"
            print(f"  {emoji} {trade.symbol} {trade.side.value.upper()}: "
                  f"${trade.entry_price:,.2f} → ${trade.exit_price:,.2f} | "
                  f"PnL: ${trade.net_pnl:,.2f} ({trade.exit_reason})")
    
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Paper Trading na dYdX z wykorzystaniem strategii Piotrka",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  %(prog)s                        Uruchom bota z domyślnymi ustawieniami
  %(prog)s --status               Pokaż status konta
  %(prog)s --reset                Zresetuj konto do stanu początkowego
  %(prog)s --balance 50000        Ustaw początkowy kapitał na $50,000
  %(prog)s --symbols BTC-USD,ETH-USD  Monitoruj tylko BTC i ETH
  %(prog)s --interval 60          Sprawdzaj co 60 sekund
        """
    )
    
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Pokaż status konta i wyjdź"
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Zresetuj konto do stanu początkowego"
    )
    
    parser.add_argument(
        "--account", "-a",
        default="piotrek_bot",
        help="Nazwa konta paper trading (domyślnie: piotrek_bot)"
    )
    
    parser.add_argument(
        "--balance", "-b",
        type=float,
        default=10000.0,
        help="Początkowy kapitał w USD (domyślnie: 10000)"
    )
    
    parser.add_argument(
        "--symbols",
        default="BTC-USD,ETH-USD",
        help="Lista symboli do monitorowania (oddzielone przecinkami)"
    )
    
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=300,
        help="Interwał sprawdzania w sekundach (domyślnie: 300 = 5 min)"
    )
    
    parser.add_argument(
        "--leverage", "-l",
        type=float,
        default=2.0,
        help="Domyślna dźwignia (domyślnie: 2.0)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Pokaż szczegółowe logi"
    )
    
    parser.add_argument(
        "--db",
        default="sqlite:///data/paper_trading.db",
        help="URL bazy danych"
    )
    
    args = parser.parse_args()
    
    # Setup
    setup_logging(args.verbose)
    os.makedirs("data", exist_ok=True)
    
    # Baza danych
    engine = create_engine(args.db, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Paper Trading Engine
    pt_engine = PaperTradingEngine(
        session=session,
        account_name=args.account
    )
    
    # Tylko status
    if args.status:
        show_status(pt_engine)
        return
    
    # Reset konta
    if args.reset:
        confirm = input(f"Czy na pewno chcesz zresetować konto '{args.account}'? (y/N): ")
        if confirm.lower() == 'y':
            pt_engine.reset_account(args.balance)
            logger.success(f"Konto zresetowane do ${args.balance}")
        else:
            logger.info("Anulowano")
        return
    
    # Uruchom bota
    symbols = [s.strip() for s in args.symbols.split(",")]
    
    strategy = PiotrekBreakoutStrategy({
        'breakout_threshold': 0.8,
        'consolidation_threshold': 0.4,
        'min_confidence': 5,
        'risk_reward_ratio': 2.0
    })
    
    bot = TradingBot(
        database_url=args.db,
        account_name=args.account,
        initial_balance=args.balance,
        symbols=symbols,
        strategy=strategy,
        check_interval=args.interval
    )
    
    # Pokaż status przed uruchomieniem
    show_status(pt_engine)
    
    print(f"\n🚀 Uruchamiam bota...")
    print(f"   Symbole: {symbols}")
    print(f"   Interwał: {args.interval}s")
    print(f"   Strategia: {strategy.name}")
    print(f"\n   Naciśnij Ctrl+C aby zatrzymać\n")
    
    try:
        bot.start()
    except KeyboardInterrupt:
        pass
    finally:
        session.close()


if __name__ == "__main__":
    main()

