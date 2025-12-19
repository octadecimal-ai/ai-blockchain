#!/usr/bin/env python3
"""
Skrypt do uruchamiania UnderhumanStrategy w trybie live trading.

Użycie:
    python scripts/run_underhuman_strategy.py --v=1.0
    python scripts/run_underhuman_strategy.py --v=1.4 --balance=50000 --interval=60

Przykłady:
    # Uruchom v1.0 z domyślnymi ustawieniami
    python scripts/run_underhuman_strategy.py --v=1.0

    # Uruchom v1.4 z własną konfiguracją
    python scripts/run_underhuman_strategy.py --v=1.4 --balance=50000 --interval=60

    # Tylko sprawdź status konta
    python scripts/run_underhuman_strategy.py --v=1.0 --status

    # Resetuj konto
    python scripts/run_underhuman_strategy.py --v=1.0 --reset
"""

import os
import sys
import argparse
from pathlib import Path

# Dodaj ścieżkę projektu do PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.trading.paper_trading import PaperTradingEngine
from src.trading.trading_bot import TradingBot
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
    log_dir = project_root / "logs" / "underhuman_strategy"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_dir / "underhuman_{time:YYYY-MM-DD}.log"),
        rotation="1 day",
        retention="30 days",
        level="DEBUG"
    )


def get_strategy(version: str, config: dict = None):
    """
    Zwraca strategię UnderhumanStrategy dla danej wersji.
    
    Args:
        version: Wersja strategii (1.0, 1.1, 1.2, 1.3, 1.4)
        config: Opcjonalna konfiguracja strategii
        
    Returns:
        Instancja strategii
    """
    from src.trading.strategies import (
        UnderhumanStrategyV10,
        UnderhumanStrategyV11,
        UnderhumanStrategyV12,
        UnderhumanStrategyV13,
        UnderhumanStrategyV14
    )
    
    strategy_map = {
        "1.0": UnderhumanStrategyV10,
        "1.1": UnderhumanStrategyV11,
        "1.2": UnderhumanStrategyV12,
        "1.3": UnderhumanStrategyV13,
        "1.4": UnderhumanStrategyV14,
    }
    
    if version not in strategy_map:
        raise ValueError(f"Nieznana wersja strategii: {version}. Dostępne: {', '.join(strategy_map.keys())}")
    
    strategy_class = strategy_map[version]
    
    # Konfiguracja domyślna dla live trading
    default_config = {
        '_backtest_mode': False,  # Tryb live - pobieraj dane z API
        'rsi_period': 14,
        'lookback_state': 36,
        'lookback_short': 6,
        'lookback_impulse': 4,
        'impulse_threshold_pct': 0.8,
        'min_anomalies_to_trade': 2,
        'orderbook_levels': 10,
        'imbalance_threshold': 0.18,
        'funding_divergence_z': 1.2,
        'oi_divergence_z': 1.2,
        'delay_threshold': 1.35,
        'target_profit_usd_min': 400.0,
        'target_profit_usd_max': 1000.0,
        'max_loss_usd': 500.0,
        'max_hold_seconds': 900,
        'cooldown_seconds': 120,
        'slippage_percent': 0.1,
        'min_confidence_for_trade': 7.0,
        'position_size_btc': 0.1,
    }
    
    # Połącz z konfiguracją użytkownika
    if config:
        default_config.update(config)
    
    return strategy_class(default_config)


def show_status(engine: PaperTradingEngine, version: str):
    """Pokazuje status konta."""
    summary = engine.get_account_summary()
    stats = engine.get_performance_stats()
    
    print("\n" + "=" * 70)
    print(f"📊 UNDERHUMAN STRATEGY v{version} - STATUS KONTA")
    print("=" * 70)
    print(f"Konto: {summary['account_name']}")
    print(f"Saldo początkowe: ${summary['initial_balance']:,.2f}")
    print(f"Saldo aktualne: ${summary['current_balance']:,.2f}")
    print(f"Unrealized PnL: ${summary['unrealized_pnl']:,.2f}")
    print(f"Equity: ${summary['equity']:,.2f}")
    print("-" * 70)
    print(f"Całkowity PnL: ${summary['total_pnl']:,.2f}")
    print(f"ROI: {summary['roi']:.2f}%")
    print(f"Max Drawdown: {summary['max_drawdown']:.2f}%")
    print("-" * 70)
    print(f"Liczba transakcji: {stats['total_trades']}")
    print(f"Win Rate: {stats['win_rate']:.1f}%")
    print(f"Profit Factor: {stats['profit_factor']:.2f}")
    print(f"Średni zysk: ${stats['avg_win']:.2f}")
    print(f"Średnia strata: ${stats['avg_loss']:.2f}")
    print("-" * 70)
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
    
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Uruchom UnderhumanStrategy w trybie live trading na dYdX",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  %(prog)s --v=1.0                        Uruchom v1.0 z domyślnymi ustawieniami
  %(prog)s --v=1.4 --balance=50000        Uruchom v1.4 z kapitałem $50,000
  %(prog)s --v=1.0 --status               Pokaż status konta
  %(prog)s --v=1.0 --reset                Zresetuj konto
  %(prog)s --v=1.4 --interval=60          Sprawdzaj co 60 sekund
        """
    )
    
    parser.add_argument(
        "--v", "--version",
        type=str,
        default="1.0",
        help="Wersja strategii (1.0, 1.1, 1.2, 1.3, 1.4) - domyślnie: 1.0"
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
        default="underhuman_bot",
        help="Nazwa konta paper trading (domyślnie: underhuman_bot)"
    )
    
    parser.add_argument(
        "--balance", "-b",
        type=float,
        default=10000.0,
        help="Początkowy kapitał w USD (domyślnie: 10000)"
    )
    
    parser.add_argument(
        "--symbols",
        default="BTC-USD",
        help="Lista symboli do monitorowania (oddzielone przecinkami, domyślnie: BTC-USD)"
    )
    
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=60,
        help="Interwał sprawdzania w sekundach (domyślnie: 60 = 1 min)"
    )
    
    parser.add_argument(
        "--leverage", "-l",
        type=float,
        default=10.0,
        help="Domyślna dźwignia (domyślnie: 10.0)"
    )
    
    parser.add_argument(
        "--position-size",
        type=float,
        default=15.0,
        help="Rozmiar pozycji w %% kapitału (domyślnie: 15.0)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Pokaż szczegółowe logi"
    )
    
    parser.add_argument(
        "--db",
        default="sqlite:///data/underhuman_trading.db",
        help="URL bazy danych (domyślnie: sqlite:///data/underhuman_trading.db)"
    )
    
    args = parser.parse_args()
    
    # Normalizuj wersję (usuń "v" jeśli jest)
    version = args.v.replace("v", "").replace("V", "")
    
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
        show_status(pt_engine, version)
        session.close()
        return 0
    
    # Reset konta
    if args.reset:
        confirm = input(f"Czy na pewno chcesz zresetować konto '{args.account}'? (y/N): ")
        if confirm.lower() == 'y':
            pt_engine.reset_account(args.balance)
            logger.success(f"Konto zresetowane do ${args.balance}")
        else:
            logger.info("Anulowano")
        session.close()
        return 0
    
    # Utwórz strategię
    try:
        strategy = get_strategy(version)
        logger.info(f"✅ Załadowano strategię: {strategy.name}")
    except Exception as e:
        logger.error(f"❌ Błąd podczas ładowania strategii: {e}")
        session.close()
        return 1
    
    # Uruchom bota
    symbols = [s.strip() for s in args.symbols.split(",")]
    
    bot = TradingBot(
        database_url=args.db,
        account_name=args.account,
        initial_balance=args.balance,
        symbols=symbols,
        strategy=strategy,
        check_interval=args.interval
    )
    
    # Ustaw dźwignię i rozmiar pozycji
    bot.default_leverage = args.leverage
    bot.position_size_percent = args.position_size
    
    # Pokaż status przed uruchomieniem
    show_status(pt_engine, version)
    
    print(f"\n🚀 Uruchamiam UnderhumanStrategy v{version}...")
    print(f"   Strategia: {strategy.name}")
    print(f"   Symbole: {symbols}")
    print(f"   Interwał: {args.interval}s")
    print(f"   Kapitał: ${args.balance:,.2f}")
    print(f"   Dźwignia: {args.leverage}x")
    print(f"   Rozmiar pozycji: {args.position_size}%")
    print(f"   Timeframe: {strategy.timeframe}")
    print(f"\n   Naciśnij Ctrl+C aby zatrzymać\n")
    
    try:
        bot.start()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Zatrzymywanie bota...")
    finally:
        session.close()
        logger.info("✅ Bot zatrzymany")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

