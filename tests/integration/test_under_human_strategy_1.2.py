import os
import sys
import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict
from dotenv import load_dotenv
import pandas as pd

# Dodaj ścieżkę do projektu
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.trading.backtesting import BacktestEngine, BacktestResult
# Import: plik under_human_strategy_1.2.py → import przez __init__.py
from src.trading.strategies import UnderhumanStrategyV12
from loguru import logger

# Załaduj zmienne środowiskowe
load_dotenv()

# Konfiguracja logowania do pliku
LOG_DIR = project_root / ".dev" / "logs" / "strategies"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "under_human_strategy_1.2.log"


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
    if year_ranges and len(year_ranges) > 1:
        print_per_year_summary(result, year_ranges)
    
    print("\n" + "=" * 100)
    print("📊 SZCZEGÓŁOWE WYNIKI BACKTESTU - UNDERHUMAN STRATEGY v1.2")
    print("=" * 100)
    
    # ZAPISZ DO LOGU (nagłówek)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write("\n" + "=" * 100 + "\n")
        f.write(f"WYNIKI BACKTESTU - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 100 + "\n")
    
    # NAJPIERW TABELA TRANSAKCJI
    print(f"\n📋 WSZYSTKIE TRANSAKCJE:")
    print("-" * 100)
    
    if result.trades:
        print(f"{'#':<4} {'Data wejścia':<20} {'Data wyjścia':<20} {'Strona':<6} {'Cena wejścia':<14} "
              f"{'Cena wyjścia':<14} {'PnL USD':<12} {'PnL %':<10} {'Powód':<20}")
        print("-" * 100)
        
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write("TRANSAKCJE:\n")
            f.write("-" * 100 + "\n")
        
        for i, trade in enumerate(result.trades, 1):
            entry_time = trade.get('entry_time')
            exit_time = trade.get('exit_time')
            
            if isinstance(entry_time, pd.Timestamp):
                entry_time = entry_time.to_pydatetime()
            if isinstance(exit_time, pd.Timestamp):
                exit_time = exit_time.to_pydatetime()
            
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
            
            pnl_color = "\033[32m" if pnl > 0 else "\033[31m" if pnl < 0 else ""
            reset_color = "\033[0m"
            
            print(f"{i:<4} {entry_str:<20} {exit_str:<20} {side:<6} {entry_price_str:<14} "
                  f"{exit_price_str:<14} {pnl_color}{pnl_usd:<12}{reset_color} {pnl_color}{pnl_pct:<10}{reset_color} {reason:<20}")
            
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{i} | {entry_str} | {exit_str} | {side} | ${entry_price:,.2f} | "
                       f"${exit_price:,.2f} | ${pnl:+,.2f} | {pnl_percent:+.2f}% | {reason}\n")
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
    
    # ZAPISZ DO LOGU
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"Saldo początkowe: ${result.initial_balance:,.2f}\n")
        f.write(f"Saldo końcowe: ${result.final_balance:,.2f}\n")
        f.write(f"Całkowity PnL: ${result.total_pnl:,.2f}\n")
        f.write(f"ROI: {result.total_return:+.2f}%\n")
        f.write(f"Liczba transakcji: {result.total_trades}\n")
        f.write(f"Zyskownych: {result.winning_trades} ({result.win_rate:.1f}%)\n")
        f.write(f"Stratnych: {result.losing_trades} ({100-result.win_rate:.1f}%)\n")
        f.write(f"Max drawdown: {result.max_drawdown:.2f}%\n")
        f.write("\n" + "-" * 100 + "\n")
        f.write("PODSUMOWANIE FINANSOWE:\n")
        f.write("-" * 100 + "\n")
        f.write(f"Kapitał początkowy: ${result.initial_balance:,.2f}\n")
        f.write(f"Kapitał końcowy: ${result.final_balance:,.2f}\n")
        f.write(f"Całkowity zysk/strata: ${total_pnl:+,.2f}\n")
        f.write(f"Zwrot (ROI): {result.total_return:+.2f}%\n")
        f.write(f"Opłaty łącznie: ${result.total_fees:,.2f}\n")
        f.write("-" * 100 + "\n")
    
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
    
    # Zapisz do logu
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write("\nZYSKI/STRATY PER ROK:\n")
        f.write("-" * 100 + "\n")
        for year in sorted(year_stats.keys()):
            stats = year_stats[year]
            pnl = stats['total_pnl']
            pnl_percent = (pnl / result.initial_balance) * 100 if result.initial_balance > 0 else 0.0
            f.write(f"{year}: ${pnl:+,.2f} ({pnl_percent:+.2f}%) - {stats['trades']} transakcji\n")
        f.write("-" * 100 + "\n")


def print_per_year_summary(result: BacktestResult, year_ranges: Dict[int, Tuple[datetime, datetime]]):
    """Wyświetla podsumowanie wyników per rok."""
    print("\n" + "=" * 100)
    print("📅 PODSUMOWANIE PER ROK")
    print("=" * 100)
    
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
    
    print(f"\n{'Rok':<6} {'Transakcje':<12} {'Zyskownych':<12} {'Stratnych':<12} {'PnL USD':<15} {'PnL %':<12}")
    print("-" * 100)
    
    total_pnl_all_years = 0.0
    total_trades_all_years = 0
    
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write("\nPODSUMOWANIE PER ROK:\n")
        f.write("-" * 100 + "\n")
    
    for year in sorted(year_stats.keys()):
        stats = year_stats[year]
        num_trades = len(stats['trades'])
        total_trades_all_years += num_trades
        total_pnl_all_years += stats['total_pnl']
        
        initial_balance = 10000.0
        pnl_percent = (stats['total_pnl'] / initial_balance) * 100
        
        pnl_color = "\033[32m" if stats['total_pnl'] > 0 else "\033[31m" if stats['total_pnl'] < 0 else ""
        reset_color = "\033[0m"
        win_color = "\033[32m" if stats['winning'] > stats['losing'] else ""
        loss_color = "\033[31m" if stats['losing'] > stats['winning'] else ""
        
        pnl_str = f"{pnl_color}${stats['total_pnl']:+,.2f}{reset_color}"
        pnl_pct_str = f"{pnl_color}{pnl_percent:+.2f}%{reset_color}"
        winning_str = f"{win_color}{stats['winning']}{reset_color}"
        losing_str = f"{loss_color}{stats['losing']}{reset_color}"
        
        print(f"{year:<6} {num_trades:<12} {winning_str:<20} {losing_str:<20} {pnl_str:<15} {pnl_pct_str:<12}")
        
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{year} | {num_trades} | {stats['winning']} | {stats['losing']} | "
                   f"${stats['total_pnl']:+,.2f} | {pnl_percent:+.2f}%\n")
    
    print("-" * 100)
    
    total_pnl_percent = (total_pnl_all_years / 10000.0) * 100
    total_pnl_color = "\033[32m" if total_pnl_all_years > 0 else "\033[31m" if total_pnl_all_years < 0 else ""
    reset_color = "\033[0m"
    
    print(f"{'ŁĄCZNIE':<6} {total_trades_all_years:<12} {'-':<12} {'-':<12} "
          f"{total_pnl_color}${total_pnl_all_years:+,.2f}{reset_color:<15} "
          f"{total_pnl_color}{total_pnl_percent:+.2f}%{reset_color:<12}")
    print("=" * 100)
    
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"ŁĄCZNIE | {total_trades_all_years} | - | - | ${total_pnl_all_years:+,.2f} | {total_pnl_percent:+.2f}%\n")


def main():
    parser = argparse.ArgumentParser(
        description="Backtesting UnderhumanStrategyV12 na danych z bazy danych PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  # Test na wszystkich danych z bazy
    python tests/integration/test_under_human_strategy_1.2.py

  # Test z limitem dni (szybszy)
    python tests/integration/test_under_human_strategy_1.2.py --limit-days=30

  # Test z parametrami
    python tests/integration/test_under_human_strategy_1.2.py --limit-days=365 \\
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
        help='Rozmiar pozycji w %% kapitału (domyślnie: 15.0) - bazowy, będzie skalowany dynamicznie'
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
    
    strategy_config = {
        "_backtest_mode": True,
        "min_confidence_for_trade": 8.0,
        "atr_period": 14,
        "atr_sl_multiplier": 2.0,
        "atr_tp_multiplier": 3.0,
        "trend_ema_fast": 20,
        "trend_ema_slow": 50,
        "trend_strength_threshold": 0.5,
        "trailing_stop_activation_pnl": 200.0,
        "trailing_stop_atr_multiplier": 1.5,
        "max_drawdown_percent": 20.0,
        # NOWE parametry v1.2
        "base_position_size": 15.0,
        "max_position_size": 20.0,
        "min_position_size": 10.0,
        "max_volatility_percent": 5.0,
        "min_volatility_percent": 0.3,
        "volatility_period": 24,
        "max_consecutive_losses": 3,
        "loss_cooldown_seconds": 600,
        "trend_reversal_threshold": 0.3
    }
    
    strategy = UnderhumanStrategyV12(config=strategy_config)
    
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
    print("🧪 BACKTEST - UNDERHUMAN STRATEGY v1.2")
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
    
    start_time = datetime.now()
    
    result = engine.run_backtest(
        strategy=strategy,
        symbol="BTC/USDC",
        df=df,
        position_size_percent=args.position_size,
        max_positions=1
    )
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print_detailed_results(result, year_ranges if len(year_ranges) > 1 else None)
    
    print(f"\n⏱️  Czas wykonania: {duration:.2f} sekund")
    print(f"📊 Przetworzono {len(df)} świec")
    print(f"⚡ Prędkość: {len(df)/duration:.0f} świec/sekundę")
    print(f"📝 Pełne logi zapisane do: {LOG_FILE}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

