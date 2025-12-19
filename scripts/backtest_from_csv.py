#!/usr/bin/env python3
"""
Backtesting Script from CSV
============================
Skrypt do testowania strategii na zapisanych danych CSV.
Używa danych z plików CSV zamiast pobierania z API.
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd

# Dodaj ścieżkę projektu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Załaduj .env jeśli istnieje
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

from loguru import logger
from src.trading.backtesting import BacktestEngine, BacktestResult
from src.trading.strategies.piotrek_strategy import PiotrekBreakoutStrategy
from src.trading.strategies.scalping_strategy import ScalpingStrategy
from src.trading.strategies.improved_breakout_strategy import ImprovedBreakoutStrategy
from src.trading.strategies.funding_rate_arbitrage_strategy import FundingRateArbitrageStrategy
from src.trading.strategies.piotr_swiec_strategy import PiotrSwiecStrategy
from src.trading.strategies.base_strategy import BaseStrategy


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


def load_csv_data(csv_file: Path = None) -> pd.DataFrame:
    """
    Wczytuje dane z bazy danych (BTC/USDC) lub z pliku CSV (fallback).
    
    Jeśli csv_file jest None, pobiera dane z bazy danych.
    Jeśli csv_file jest podany, używa go jako fallback.
    """
    # Próbuj najpierw z bazy danych
    if csv_file is None:
        try:
            from src.database.btcusdc_loader import load_btcusdc_from_db
            logger.info("📂 Wczytuję dane BTC/USDC z bazy danych...")
            df = load_btcusdc_from_db()
            
            if not df.empty:
                if 'timestamp' not in df.columns:
                    df['timestamp'] = df.index
                logger.success(f"✅ Wczytano {len(df)} świec z bazy danych")
                logger.info(f"   Okres: {df['timestamp'].min()} → {df['timestamp'].max()}")
                return df
        except Exception as e:
            logger.warning(f"Nie udało się wczytać z bazy danych: {e}, próbuję CSV...")
    
    # Fallback do CSV
    if csv_file is None:
        logger.error("❌ Brak pliku CSV i nie można wczytać z bazy danych")
        return pd.DataFrame()
    
    logger.info(f"📂 Wczytuję dane z: {csv_file}")
    
    if not csv_file.exists():
        logger.error(f"❌ Plik nie istnieje: {csv_file}")
        return pd.DataFrame()
    
    # Wczytaj CSV
    df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
    
    # Upewnij się, że mamy wszystkie potrzebne kolumny
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        logger.error(f"❌ Brakujące kolumny: {missing_cols}")
        return pd.DataFrame()
    
    # Jeśli index jest datetime, użyj go jako timestamp
    if df.index.dtype == 'datetime64[ns]':
        # Index jest już datetime, nie dodawaj kolumny timestamp
        df = df.sort_index()
    else:
        # Konwertuj index na datetime i użyj jako timestamp
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
    
    # Dodaj kolumnę timestamp dla kompatybilności z backtesting engine
    if 'timestamp' not in df.columns:
        df['timestamp'] = df.index
    
    logger.success(f"✅ Wczytano {len(df)} świec z CSV")
    logger.info(f"   Okres: {df['timestamp'].min()} → {df['timestamp'].max()}")
    
    return df


def main():
    parser = argparse.ArgumentParser(
        description="Backtesting strategii na danych z pliku CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  # Test na danych z bazy danych (BTC/USDC)
  python scripts/backtest_from_csv.py --strategy=piotrek_breakout_strategy

  # Test na danych z pliku CSV
  python scripts/backtest_from_csv.py --csv data/backtest_periods/binance/BTCUSDC_2022_1h.csv \\
    --strategy=piotrek_breakout_strategy

  # Test z najlepszymi parametrami
  python scripts/backtest_from_csv.py --strategy=scalping_strategy --param min_confidence=3.0 --param rsi_oversold=25
        """
    )
    
    # Plik CSV (opcjonalny, domyślnie używa bazy danych)
    parser.add_argument(
        "--csv",
        required=False,
        type=Path,
        help="Ścieżka do pliku CSV z danymi (opcjonalnie, domyślnie używa bazy danych)"
    )
    
    # Strategia
    parser.add_argument(
        "--strategy",
        default="piotrek_breakout_strategy",
        choices=["piotrek_breakout_strategy", "scalping_strategy", "improved_breakout_strategy", "funding_rate_arbitrage", "piotr_swiec_strategy"],
        help="Nazwa strategii do testowania"
    )
    
    # Symbol (dla wyświetlania)
    parser.add_argument(
        "--symbol",
        default="BTC/USDC",
        help="Symbol pary (tylko do wyświetlania)"
    )
    
    # Parametry strategii
    parser.add_argument(
        "--param",
        action="append",
        metavar="KEY=VALUE",
        help="Parametr strategii (można użyć wielokrotnie)"
    )
    
    # Parametry backtestingu
    parser.add_argument(
        "--balance",
        type=float,
        default=10000.0,
        help="Początkowy kapitał (domyślnie: 10000)"
    )
    
    parser.add_argument(
        "--slippage",
        type=float,
        default=0.1,
        help="Slippage w procentach (domyślnie: 0.1)"
    )
    
    parser.add_argument(
        "--leverage",
        type=float,
        default=1.0,
        help="Dźwignia (domyślnie: 1.0)"
    )
    
    parser.add_argument(
        "--position-size",
        type=float,
        default=10.0,
        help="Rozmiar pozycji w procentach (domyślnie: 10.0)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Szczegółowe logi"
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    # Wczytaj dane z CSV lub bazy danych
    df = load_csv_data(args.csv)
    
    if df.empty:
        logger.error("❌ Nie udało się wczytać danych")
        sys.exit(1)
    
    # Utwórz strategię
    strategy_config = {}
    
    # Parsuj parametry strategii
    if args.param:
        for param_str in args.param:
            if '=' not in param_str:
                logger.warning(f"Nieprawidłowy format parametru: {param_str}")
                continue
            
            key, value = param_str.split('=', 1)
            try:
                if '.' in value:
                    strategy_config[key] = float(value)
                else:
                    strategy_config[key] = int(value)
            except ValueError:
                strategy_config[key] = value
    
    # Określ timeframe na podstawie strategii
    if args.strategy == "scalping_strategy":
        strategy = ScalpingStrategy({
            'timeframe': '1min',
            **strategy_config
        })
    elif args.strategy == "improved_breakout_strategy":
        strategy = ImprovedBreakoutStrategy({
            'timeframe': '1h',
            **strategy_config
        })
    elif args.strategy == "funding_rate_arbitrage":
        strategy = FundingRateArbitrageStrategy({
            'timeframe': '1h',
            **strategy_config
        })
    elif args.strategy == "piotr_swiec_strategy":
        strategy = PiotrSwiecStrategy({
            'timeframe': '1h',  # Dane są 1h, ale strategia może działać na różnych timeframe'ach
            **strategy_config
        })
    else:
        strategy = PiotrekBreakoutStrategy({
            'timeframe': '1h',
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
    
    # Uruchom backtest
    logger.info("\n🚀 Uruchamiam backtest...")
    result = engine.run_backtest(
        strategy=strategy,
        symbol=args.symbol,
        df=df,
        position_size_percent=args.position_size,
        max_positions=1
    )
    
    # Ustaw nazwę strategii w wynikach
    result.strategy_name = strategy.name
    
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

