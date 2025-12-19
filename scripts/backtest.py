#!/usr/bin/env python3
"""
Backtesting Script
==================
Skrypt do testowania strategii na danych historycznych.
Pozwala szybko przetestować różne parametry bez ryzyka.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Dodaj ścieżkę projektu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Załaduj .env jeśli istnieje
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

from loguru import logger
from src.trading.backtesting import BacktestEngine
from src.trading.strategies.piotrek_strategy import PiotrekBreakoutStrategy
from src.trading.strategies.scalping_strategy import ScalpingStrategy
from src.trading.strategies.improved_breakout_strategy import ImprovedBreakoutStrategy


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


def parse_date(date_str: str) -> datetime:
    """Parsuje datę z różnych formatów."""
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d",
        "%d.%m.%Y"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # Spróbuj jako "N dni temu"
    if date_str.endswith('d') or date_str.endswith('days'):
        days = int(date_str.rstrip('days').rstrip('d').strip())
        return datetime.now() - timedelta(days=days)
    
    raise ValueError(f"Nie można sparsować daty: {date_str}")


def main():
    parser = argparse.ArgumentParser(
        description="Backtesting strategii tradingowych na danych historycznych",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  # Test scalping na ostatnich 30 dniach
  python scripts/backtest.py --strategy=scalping_strategy --symbol=BTC-USD --days=30

  # Test breakout na konkretnym okresie
  python scripts/backtest.py --strategy=piotrek_breakout_strategy --symbol=BTC-USD \\
    --start=2024-01-01 --end=2024-12-01

  # Test z własnymi parametrami
  python scripts/backtest.py --strategy=scalping_strategy --symbol=BTC-USD --days=90 \\
    --param min_confidence=3.0 --param rsi_oversold=30
        """
    )
    
    # Strategia
    parser.add_argument(
        "--strategy",
        default="piotrek_breakout_strategy",
        choices=["piotrek_breakout_strategy", "scalping_strategy", "improved_breakout_strategy"],
        help="Nazwa strategii do testowania"
    )
    
    # Symbol i okres
    parser.add_argument(
        "--symbol",
        default="BTC-USD",
        help="Symbol pary (np. BTC-USD, ETH-USD)"
    )
    
    parser.add_argument(
        "--timeframe",
        default=None,
        help="Timeframe (1m, 5m, 1h, 1d). Domyślnie z strategii"
    )
    
    parser.add_argument(
        "--days",
        type=int,
        help="Liczba dni wstecz (np. 30 dla ostatniego miesiąca)"
    )
    
    parser.add_argument(
        "--start",
        help="Data początkowa (YYYY-MM-DD lub '30d' dla 30 dni temu)"
    )
    
    parser.add_argument(
        "--end",
        help="Data końcowa (YYYY-MM-DD, domyślnie: teraz)"
    )
    
    # Parametry backtestingu
    parser.add_argument(
        "--balance",
        type=float,
        default=10000.0,
        help="Początkowy kapitał (domyślnie: 10000)"
    )
    
    parser.add_argument(
        "--position-size",
        type=float,
        default=10.0,
        help="% kapitału na pozycję (domyślnie: 10%)"
    )
    
    parser.add_argument(
        "--slippage",
        type=float,
        default=0.1,
        help="Slippage w % (domyślnie: 0.1%)"
    )
    
    parser.add_argument(
        "--leverage",
        type=float,
        default=1.0,
        help="Dźwignia (domyślnie: 1.0 = brak)"
    )
    
    # Parametry strategii
    parser.add_argument(
        "--param",
        action="append",
        metavar="KEY=VALUE",
        help="Parametr strategii (można użyć wielokrotnie, np. --param min_confidence=5.0)"
    )
    
    # Inne
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Szczegółowe logi"
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    # Określ okres testowania
    if args.days:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
    elif args.start:
        start_date = parse_date(args.start)
        end_date = parse_date(args.end) if args.end else datetime.now()
    else:
        # Domyślnie: ostatnie 30 dni
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
    
    logger.info(f"📅 Okres testowania: {start_date.date()} → {end_date.date()}")
    logger.info(f"   ({end_date - start_date} = {(end_date - start_date).days} dni)")
    
    # Utwórz strategię
    strategy_config = {}
    
    # Parsuj parametry strategii
    if args.param:
        for param_str in args.param:
            if '=' not in param_str:
                logger.warning(f"Nieprawidłowy format parametru: {param_str} (oczekiwano KEY=VALUE)")
                continue
            
            key, value = param_str.split('=', 1)
            # Spróbuj przekonwertować na odpowiedni typ
            try:
                if '.' in value:
                    strategy_config[key] = float(value)
                else:
                    strategy_config[key] = int(value)
            except ValueError:
                strategy_config[key] = value
    
    if args.strategy == "scalping_strategy":
        strategy = ScalpingStrategy({
            'timeframe': args.timeframe or '1min',
            **strategy_config
        })
    elif args.strategy == "improved_breakout_strategy":
        strategy = ImprovedBreakoutStrategy({
            'timeframe': args.timeframe or '1h',
            **strategy_config
        })
    else:
        strategy = PiotrekBreakoutStrategy({
            'timeframe': args.timeframe or '1h',
            **strategy_config
        })
    
    logger.info(f"📊 Strategia: {strategy.name}")
    if strategy_config:
        logger.info(f"   Parametry: {strategy_config}")
    
    # Utwórz silnik backtestingu
    engine = BacktestEngine(
        initial_balance=args.balance,
        slippage_percent=args.slippage,
        leverage=args.leverage
    )
    
    # Pobierz dane historyczne
    timeframe = args.timeframe or strategy.timeframe
    logger.info(f"📥 Pobieram dane historyczne dla {args.symbol} ({timeframe})...")
    
    df = engine.fetch_historical_data(
        symbol=args.symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date
    )
    
    if df.empty:
        logger.error("❌ Nie udało się pobrać danych historycznych")
        sys.exit(1)
    
    logger.info(f"✅ Pobrano {len(df)} świec")
    logger.info(f"   Pierwsza świeca: {df.iloc[0].get('timestamp', df.index[0])}")
    logger.info(f"   Ostatnia świeca: {df.iloc[-1].get('timestamp', df.index[-1])}")
    
    # Uruchom backtest
    logger.info("\n🚀 Uruchamiam backtest...")
    result = engine.run_backtest(
        strategy=strategy,
        symbol=args.symbol,
        df=df,
        position_size_percent=args.position_size,
        max_positions=1
    )
    
    # Wyświetl wyniki
    engine.print_results(result)
    
    # Podsumowanie
    print("\n" + "=" * 70)
    if result.total_return > 0:
        print(f"✅ Strategia zyskowna: +{result.total_return:.2f}%")
    else:
        print(f"❌ Strategia stratna: {result.total_return:.2f}%")
    print("=" * 70)


if __name__ == "__main__":
    main()

