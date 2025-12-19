#!/usr/bin/env python3
"""
Test Backtestowy dla UnderhumanStrategy v1.1
=============================================
Testuje strategię UnderhumanStrategyV11 na danych historycznych z bazy danych PostgreSQL.
Działa w trybie ekspresowym - najszybciej jak się da.

Użycie:
    python tests/integration/test_under_human_strategy_1.1.py
    python tests/integration/test_under_human_strategy_1.1.py --limit-days=30
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict
from dotenv import load_dotenv
import pandas as pd

# Dodaj ścieżkę projektu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Załaduj .env jeśli istnieje
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

from loguru import logger
from src.trading.backtesting import BacktestEngine, BacktestResult
# Import strategii - użyj z __init__.py
from src.trading.strategies import UnderhumanStrategyV11


def setup_logging(verbose: bool = False):
    """Konfiguruje logowanie - minimalne dla szybkości."""
    logger.remove()
    level = "WARNING" if not verbose else "INFO"  # WARNING dla szybkości
    
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level=level,
        colorize=True
    )


def get_year_ranges(df: pd.DataFrame) -> Dict[int, Tuple[datetime, datetime]]:
    """Wyciąga zakresy dat per rok z DataFrame."""
    year_ranges = {}
    
    if df.empty or 'year' not in df.columns:
        return year_ranges
    
    for year in df['year'].unique():
        year_df = df[df['year'] == year]
        if not year_df.empty:
            start_date = year_df['timestamp'].min()
            end_date = year_df['timestamp'].max()
            year_ranges[int(year)] = (start_date, end_date)
            logger.info(f"   Rok {year}: {start_date.date()} → {end_date.date()}")
    
    return year_ranges


def print_detailed_results(result: BacktestResult, year_ranges: Dict[int, Tuple[datetime, datetime]] = None):
    """Wyświetla szczegółowe wyniki backtestu z listą wszystkich transakcji."""
    # Jeśli mamy wiele lat, pokaż podsumowanie per rok NAJPIERW
    if year_ranges and len(year_ranges) > 1:
        print_per_year_summary(result, year_ranges)
    
    print("\n" + "=" * 100)
    print("📊 SZCZEGÓŁOWE WYNIKI BACKTESTU - UNDERHUMAN STRATEGY v1.1")
    print("=" * 100)
    
    # NAJPIERW TABELA TRANSAKCJI
    print(f"\n📋 WSZYSTKIE TRANSAKCJE:")
    print("-" * 100)
    
    if result.trades:
        # Nagłówki
        print(f"{'#':<4} {'Data wejścia':<20} {'Data wyjścia':<20} {'Strona':<6} {'Cena wejścia':<14} "
              f"{'Cena wyjścia':<14} {'PnL USD':<12} {'PnL %':<10} {'Powód':<20}")
        print("-" * 100)
        
        # Transakcje
        for i, trade in enumerate(result.trades, 1):
            # Transakcje są słownikami
            entry_time = trade.get('entry_time')
            exit_time = trade.get('exit_time')
            
            # Konwertuj na datetime jeśli potrzeba
            if isinstance(entry_time, pd.Timestamp):
                entry_time = entry_time.to_pydatetime()
            if isinstance(exit_time, pd.Timestamp):
                exit_time = exit_time.to_pydatetime()
            
            # Formatuj datę
            entry_str = entry_time.strftime('%Y-%m-%d %H:%M') if entry_time else 'N/A'
            exit_str = exit_time.strftime('%Y-%m-%d %H:%M') if exit_time else 'N/A'
            
            side = trade.get('side', 'N/A')
            entry_price = trade.get('entry_price', 0.0)
            exit_price = trade.get('exit_price', 0.0)
            pnl = trade.get('pnl', 0.0)
            pnl_percent = trade.get('pnl_percent', 0.0)
            exit_reason = trade.get('exit_reason', 'N/A')
            
            # Kolor dla PnL
            pnl_color = "\033[32m" if pnl > 0 else "\033[31m" if pnl < 0 else ""
            reset_color = "\033[0m"
            pnl_str = f"{pnl_color}${pnl:+,.2f}{reset_color}"
            pnl_pct_str = f"{pnl_color}{pnl_percent:+.2f}%{reset_color}"
            
            print(f"{i:<4} {entry_str:<20} {exit_str:<20} {side:<6} ${entry_price:<13,.2f} "
                  f"${exit_price:<13,.2f} {pnl_str:<20} {pnl_pct_str:<18} {exit_reason:<20}")
    else:
        print("   Brak transakcji")
    
    print("-" * 100)
    
    # WYNIKI FINANSOWE
    print(f"\n💰 WYNIKI FINANSOWE:")
    print("-" * 100)
    
    roi = result.roi
    roi_color = "\033[32m" if roi > 0 else "\033[31m" if roi < 0 else ""
    reset_color = "\033[0m"
    
    print(f"   Początkowy kapitał:  ${result.initial_balance:,.2f}")
    print(f"   Końcowy kapitał:     ${result.final_balance:,.2f}")
    print(f"   Zysk/Strata:         {roi_color}${result.total_pnl:+,.2f}{reset_color}")
    print(f"   ROI:                 {roi_color}{roi:+.2f}%{reset_color}")
    
    print(f"\n📈 STATYSTYKI:")
    print(f"   Liczba transakcji: {result.total_trades}")
    win_color = "\033[32m" if result.winning_trades > result.losing_trades else "\033[31m"
    print(f"   Zyskownych:        {win_color}{result.winning_trades}{reset_color} ({result.win_rate:.1f}%)")
    print(f"   Stratnych:         {result.losing_trades} ({100-result.win_rate:.1f}%)")
    print(f"   Najlepsza:         \033[32m${result.largest_win:,.2f}\033[0m")
    loss_color = "\033[31m"
    print(f"   Najgorsza:         {loss_color}${result.largest_loss:,.2f}\033[0m")
    avg_pnl = result.total_pnl / result.total_trades if result.total_trades > 0 else 0.0
    avg_color = "\033[32m" if avg_pnl > 0 else "\033[31m" if avg_pnl < 0 else ""
    print(f"   Średni PnL:        {avg_color}${avg_pnl:+,.2f}\033[0m")
    print(f"   Max drawdown:      {result.max_drawdown:.2f}%")
    
    print("=" * 100)


def print_yearly_pnl_summary(result: BacktestResult):
    """Wyświetla listę zysków/strat z podziałem na lata."""
    year_stats = {}
    
    for trade in result.trades:
        entry_time = trade.get('entry_time')
        if isinstance(entry_time, pd.Timestamp):
            entry_time = entry_time.to_pydatetime()
        
        trade_year = None
        if hasattr(entry_time, 'year'):
            trade_year = entry_time.year
        else:
            try:
                trade_year = pd.to_datetime(entry_time).year
            except:
                continue
        
        if trade_year not in year_stats:
            year_stats[trade_year] = {
                'total_pnl': 0.0,
                'trades': 0
            }
        
        pnl = trade.get('pnl', 0.0)
        year_stats[trade_year]['total_pnl'] += pnl
        year_stats[trade_year]['trades'] += 1
    
    if not year_stats:
        return
    
    print(f"\n📊 ZYSKI/STRATY PER ROK:")
    print("-" * 100)
    
    reset_color = "\033[0m"
    
    for year in sorted(year_stats.keys()):
        stats = year_stats[year]
        pnl = stats['total_pnl']
        pnl_color = "\033[32m" if pnl > 0 else "\033[31m" if pnl < 0 else ""
        pnl_percent = (pnl / result.initial_balance) * 100 if result.initial_balance > 0 else 0.0
        
        print(f"   {year}: {pnl_color}${pnl:+,.2f}{reset_color} ({pnl_color}{pnl_percent:+.2f}%{reset_color}) - {stats['trades']} transakcji")
    
    print("-" * 100)


def print_per_year_summary(result: BacktestResult, year_ranges: Dict[int, Tuple[datetime, datetime]]):
    """Wyświetla podsumowanie wyników per rok."""
    print("\n" + "=" * 100)
    print("📅 PODSUMOWANIE PER ROK")
    print("=" * 100)
    
    # Grupuj transakcje według roku
    year_stats = {}
    
    for trade in result.trades:
        entry_time = trade.get('entry_time')
        if isinstance(entry_time, pd.Timestamp):
            entry_time = entry_time.to_pydatetime()
        
        # Określ rok transakcji
        trade_year = None
        if hasattr(entry_time, 'year'):
            trade_year = entry_time.year
        else:
            # Spróbuj wyciągnąć z daty
            try:
                trade_year = pd.to_datetime(entry_time).year
            except:
                continue
        
        if trade_year not in year_stats:
            year_stats[trade_year] = {
                'trades': [],
                'total_pnl': 0.0,
                'winning': 0,
                'losing': 0
            }
        
        pnl = trade.get('pnl', 0.0)
        year_stats[trade_year]['trades'].append(trade)
        year_stats[trade_year]['total_pnl'] += pnl
        if pnl > 0:
            year_stats[trade_year]['winning'] += 1
        elif pnl < 0:
            year_stats[trade_year]['losing'] += 1
    
    # Wyświetl wyniki dla każdego roku
    print(f"\n{'Rok':<6} {'Transakcje':<12} {'Zyskownych':<12} {'Stratnych':<12} {'PnL USD':<15} {'PnL %':<12}")
    print("-" * 100)
    
    total_pnl_all_years = 0.0
    total_trades_all_years = 0
    
    for year in sorted(year_stats.keys()):
        stats = year_stats[year]
        num_trades = len(stats['trades'])
        total_trades_all_years += num_trades
        total_pnl_all_years += stats['total_pnl']
        
        # Oblicz PnL % (zakładając początkowy kapitał 10000)
        initial_balance = 10000.0
        pnl_percent = (stats['total_pnl'] / initial_balance) * 100
        
        # Kolor dla PnL
        pnl_color = "\033[32m" if stats['total_pnl'] > 0 else "\033[31m" if stats['total_pnl'] < 0 else ""
        reset_color = "\033[0m"
        win_color = "\033[32m" if stats['winning'] > stats['losing'] else ""
        loss_color = "\033[31m" if stats['losing'] > stats['winning'] else ""
        
        pnl_str = f"{pnl_color}${stats['total_pnl']:+,.2f}{reset_color}"
        pnl_pct_str = f"{pnl_color}{pnl_percent:+.2f}%{reset_color}"
        winning_str = f"{win_color}{stats['winning']}{reset_color}"
        losing_str = f"{loss_color}{stats['losing']}{reset_color}"
        
        print(f"{year:<6} {num_trades:<12} {winning_str:<20} {losing_str:<20} {pnl_str:<15} {pnl_pct_str:<12}")
    
    print("-" * 100)
    
    # Podsumowanie łączne
    total_pnl_percent = (total_pnl_all_years / 10000.0) * 100
    total_pnl_color = "\033[32m" if total_pnl_all_years > 0 else "\033[31m" if total_pnl_all_years < 0 else ""
    reset_color = "\033[0m"
    
    total_pnl_str = f"{total_pnl_color}${total_pnl_all_years:+,.2f}{reset_color}"
    total_pnl_pct_str = f"{total_pnl_color}{total_pnl_percent:+.2f}%{reset_color}"
    
    print(f"{'ŁĄCZNIE':<6} {total_trades_all_years:<12} {'-':<12} {'-':<12} "
          f"{total_pnl_str:<15} {total_pnl_pct_str:<12}")
    print("=" * 100)


def main():
    parser = argparse.ArgumentParser(
        description="Backtesting UnderhumanStrategyV11 na danych z bazy danych PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  # Test na wszystkich danych z bazy
    python tests/integration/test_under_human_strategy_1.1.py

  # Test z limitem dni (szybszy)
    python tests/integration/test_under_human_strategy_1.1.py --limit-days=30

  # Test z parametrami
    python tests/integration/test_under_human_strategy_1.1.py --limit-days=365 \\
    --balance=50000 --leverage=5.0
        """
    )
    
    parser.add_argument(
        '--limit-days',
        type=int,
        default=None,
        help='Limit danych do ostatnich N dni (domyślnie: wszystkie dane)'
    )
    
    parser.add_argument(
        '--balance',
        type=float,
        default=10000.0,
        help='Początkowy kapitał (domyślnie: 10000)'
    )
    
    parser.add_argument(
        '--leverage',
        type=float,
        default=10.0,
        help='Dźwignia (domyślnie: 10.0)'
    )
    
    parser.add_argument(
        '--position-size',
        type=float,
        default=15.0,
        help='Rozmiar pozycji w %% kapitału (domyślnie: 15.0)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Szczegółowe logowanie'
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    # Pobierz dane z bazy danych
    try:
        from src.database.btcusdc_loader import load_btcusdc_from_db
        
        logger.info("📂 Wczytuję dane BTC/USDC z bazy danych...")
        df = load_btcusdc_from_db(limit_days=args.limit_days)
        
        if df.empty:
            logger.error("❌ Baza danych zwróciła pusty DataFrame")
            print("❌ Baza danych zwróciła pusty DataFrame")
            print("   Upewnij się, że:")
            print("   1. PostgreSQL jest uruchomiony")
            print("   2. DATABASE_URL jest ustawiony w .env")
            print("   3. Dane OHLCV są załadowane do bazy")
            return 1
        
        if 'timestamp' not in df.columns:
            df['timestamp'] = df.index
        df['year'] = df['timestamp'].dt.year
        
        logger.info(f"✅ Wczytano {len(df)} świec z bazy danych")
        logger.info(f"   Okres: {df['timestamp'].min()} → {df['timestamp'].max()}")
        
        if args.limit_days:
            logger.info(f"   Ograniczono do ostatnich {args.limit_days} dni")
        
    except Exception as e:
        logger.error(f"❌ Błąd podczas wczytywania danych z bazy: {e}")
        print(f"❌ Błąd podczas wczytywania danych z bazy: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Wyciągnij zakresy dat per rok
    year_ranges = get_year_ranges(df)
    
    # Konfiguracja strategii
    strategy_config = {
        '_backtest_mode': True,  # Tryb backtestingu - nie pobieraj z API
        'initial_balance': args.balance,
        'leverage': args.leverage,
        'position_size_percent': args.position_size,
    }
    
    # Utwórz strategię
    strategy = UnderhumanStrategyV11(strategy_config)
    
    # Ustaw timeframe na 1m (zgodnie z danymi)
    strategy.timeframe = "1m"
    
    # Inicjalizuj silnik backtestingu
    logger.info("⚙️  Inicjalizuję BacktestEngine...")
    engine = BacktestEngine(
        initial_balance=args.balance,
        taker_fee=0.0005,  # 0.05% dYdX
        maker_fee=0.0,
        slippage_percent=0.1,
        leverage=args.leverage
    )
    
    # Uruchom backtest
    logger.info("🚀 Uruchamiam backtest...")
    print("\n" + "=" * 100)
    print("🧪 BACKTEST - UNDERHUMAN STRATEGY v1.1")
    print("=" * 100)
    print(f"   Kapitał:         ${args.balance:,.2f}")
    print(f"   Dźwignia:        {args.leverage}x")
    print(f"   Rozmiar pozycji: {args.position_size}%")
    print(f"   Timeframe:       1m")
    print(f"   Liczba świec:    {len(df):,}")
    if args.limit_days:
        print(f"   Ograniczenie:     Ostatnie {args.limit_days} dni")
    print("=" * 100)
    print()
    
    result = engine.run_backtest(
        strategy=strategy,
        symbol="BTC/USDC",
        df=df,
        position_size_percent=args.position_size,
        max_positions=1
    )
    
    # Wyświetl wyniki
    print_detailed_results(result, year_ranges)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
