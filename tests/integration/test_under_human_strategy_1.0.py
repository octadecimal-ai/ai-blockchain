#!/usr/bin/env python3
"""
Test Backtestowy dla UnderhumanStrategy
========================================
Testuje strategię UnderhumanStrategyV10 na danych historycznych z bazy danych PostgreSQL.
Działa w trybie ekspresowym - najszybciej jak się da.

Użycie:
    python tests/integration/test_under_human_strategy_1.0.py
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
from src.trading.strategies import UnderhumanStrategyV10


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
    print("📊 SZCZEGÓŁOWE WYNIKI BACKTESTU - UNDERHUMAN STRATEGY v1.0")
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
            if hasattr(entry_time, 'strftime'):
                entry_str = entry_time.strftime("%Y-%m-%d %H:%M")
            else:
                entry_str = str(entry_time)[:16] if entry_time else "N/A"
            
            if hasattr(exit_time, 'strftime'):
                exit_str = exit_time.strftime("%Y-%m-%d %H:%M")
            else:
                exit_str = str(exit_time)[:16] if exit_time else "N/A"
            
            side = trade.get('side', 'N/A').upper()
            entry_price = trade.get('entry_price', 0.0)
            exit_price = trade.get('exit_price', 0.0)
            pnl = trade.get('pnl', 0.0)
            pnl_percent = trade.get('pnl_percent', 0.0)
            reason = trade.get('exit_reason', 'N/A')[:18]
            
            entry_price_str = f"${entry_price:,.2f}"
            exit_price_str = f"${exit_price:,.2f}"
            pnl_usd = f"${pnl:+,.2f}"
            pnl_pct = f"{pnl_percent:+.2f}%"
            
            # Kolor dla PnL
            pnl_color = "\033[32m" if pnl > 0 else "\033[31m" if pnl < 0 else ""
            reset_color = "\033[0m"
            
            print(f"{i:<4} {entry_str:<20} {exit_str:<20} {side:<6} {entry_price_str:<14} "
                  f"{exit_price_str:<14} {pnl_color}{pnl_usd:<12}{reset_color} {pnl_color}{pnl_pct:<10}{reset_color} {reason:<20}")
    else:
        print("   Brak transakcji")
    
    print("-" * 100)
    
    # TERAZ PODSUMOWANIE FINANSOWE I STATYSTYKI
    print(f"\n💰 PODSUMOWANIE FINANSOWE:")
    print("-" * 100)
    print(f"   Kapitał początkowy:  ${result.initial_balance:,.2f}")
    print(f"   Kapitał końcowy:      ${result.final_balance:,.2f}")
    total_pnl = result.final_balance - result.initial_balance
    total_pnl_color = "\033[32m" if total_pnl > 0 else "\033[31m" if total_pnl < 0 else ""
    reset_color = "\033[0m"
    print(f"   Całkowity zysk/strata: {total_pnl_color}${total_pnl:+,.2f}{reset_color}")
    print(f"   Zwrot (ROI):          {total_pnl_color}{result.total_return:+.2f}%{reset_color}")
    print(f"   Opłaty łącznie:       ${result.total_fees:,.2f}")
    print("-" * 100)
    
    # Lista zysków z podziałem na lata
    print_yearly_pnl_summary(result)
    
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
        description="Backtesting UnderhumanStrategyV10 na danych z bazy danych PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  # Test z domyślnymi parametrami
    python tests/integration/test_under_human_strategy_1.0.py

  # Test z parametrami
    python tests/integration/test_under_human_strategy_1.0.py --balance=50000 --leverage=5.0
        """
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
    
    parser.add_argument(
        '--limit-days',
        type=int,
        default=None,
        help='Ograniczenie do ostatnich N dni (dla szybszych testów, domyślnie: wszystkie dane)'
    )
    
    args = parser.parse_args()
    
    # Konfiguruj logowanie
    setup_logging(args.verbose)
    
    # Wczytaj dane z bazy danych
    try:
        from src.database.btcusdc_loader import load_btcusdc_from_db
        
        logger.info("📂 Wczytuję dane BTC/USDC z bazy danych PostgreSQL...")
        if args.limit_days:
            logger.info(f"   Ograniczenie do ostatnich {args.limit_days} dni")
        
        df = load_btcusdc_from_db(limit_days=args.limit_days)
        
        if df.empty:
            logger.error("❌ Baza danych zwróciła pusty DataFrame")
            print("❌ Nie można wczytać danych - baza zwróciła pusty DataFrame")
            return 1
        
        if 'timestamp' not in df.columns:
            df['timestamp'] = df.index
        df['year'] = df['timestamp'].dt.year
        logger.info(f"✅ Wczytano {len(df)} świec z bazy danych")
        logger.info(f"   Okres: {df['timestamp'].min()} → {df['timestamp'].max()}")
        
        year_ranges = get_year_ranges(df)
    except Exception as e:
        logger.error(f"❌ Błąd podczas wczytywania danych: {e}")
        print(f"❌ Nie można wczytać danych z bazy danych: {e}")
        print("   Sprawdź połączenie z PostgreSQL i czy dane są dostępne")
        return 1
    
    if df.empty:
        logger.error("❌ Nie można wczytać danych - baza zwróciła pusty DataFrame")
        print("❌ Nie można wczytać danych - baza zwróciła pusty DataFrame")
        return 1
    
    # Inicjalizuj strategię
    logger.info("🤖 Inicjalizuję UnderhumanStrategyV10...")
    strategy = UnderhumanStrategyV10({
        '_backtest_mode': True,  # Tryb backtestingu - nie pobieraj z API
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
        'position_size_btc': 0.1
    })
    
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
    logger.info("🚀 Uruchamiam backtest (tryb ekspresowy)...")
    if len(year_ranges) > 1:
        logger.info(f"   Test ciągły dla lat: {sorted(year_ranges.keys())}")
    start_time = datetime.now()
    
    result = engine.run_backtest(
        strategy=strategy,
        symbol="BTC/USDC",  # Zmieniono z BTC-USD na BTC/USDC
        df=df,
        position_size_percent=args.position_size,
        max_positions=1
    )
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Wyświetl wyniki
    print_detailed_results(result, year_ranges if len(year_ranges) > 1 else None)
    
    print(f"\n⏱️  Czas wykonania: {duration:.2f} sekund")
    print(f"📊 Przetworzono {len(df)} świec")
    print(f"⚡ Prędkość: {len(df)/duration:.0f} świec/sekundę")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

