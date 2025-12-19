#!/usr/bin/env python3
"""
Test Backtestowy dla UnderhumanStrategyV2
========================================

To jest drop-in odpowiednik testu v1, ale importuje i uruchamia strategię UNDERHUMAN 2.0.
Zakłada ten sam BacktestEngine i ten sam format CSV (OHLCV 1h).

Użycie:
    python tests/integration/test_under_human_strategy_v2.py --csv data/backtest_periods/binance/BTCUSDT_2021_1h.csv
"""

import os
import sys
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict

from dotenv import load_dotenv
import pandas as pd
from loguru import logger

# Dodaj ścieżkę projektu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Załaduj .env jeśli istnieje
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

from src.trading.backtesting import BacktestEngine, BacktestResult

# Strategia V2 (plik: under_human_strategy_2.0.py → import przez __init__.py)
from src.trading.strategies import UnderhumanStrategyV2


def setup_logging(verbose: bool = False):
    """Konfiguruje logowanie - minimalne dla szybkości."""
    logger.remove()
    level = "WARNING" if not verbose else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level=level,
        colorize=True,
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
                df['year'] = df['timestamp'].dt.year
                logger.info(f"✅ Wczytano {len(df)} świec z bazy danych")
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

    df = pd.read_csv(csv_file, index_col=0, parse_dates=True)

    required_cols = ['open', 'high', 'low', 'close', 'volume']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        logger.error(f"❌ Brakujące kolumny: {missing_cols}")
        return pd.DataFrame()

    # index jako datetime
    if df.index.dtype != 'datetime64[ns]':
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    if 'timestamp' not in df.columns:
        df['timestamp'] = df.index
    df['year'] = df['timestamp'].dt.year

    logger.info(f"✅ Wczytano {len(df)} świec z CSV")
    logger.info(f"   Okres: {df['timestamp'].min()} → {df['timestamp'].max()}")
    return df


def load_multiple_csv_files(csv_files: List[Path]) -> Tuple[pd.DataFrame, Dict[int, Tuple[datetime, datetime]]]:
    """Łączy wiele plików CSV w jeden dataset."""
    all_dfs = []
    year_ranges: Dict[int, Tuple[datetime, datetime]] = {}

    for f in csv_files:
        df = load_csv_data(f)
        if df.empty:
            continue
        year = int(df['year'].iloc[0])
        year_ranges[year] = (df.index.min(), df.index.max())
        all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame(), {}

    merged = pd.concat(all_dfs).sort_index()
    merged = merged[~merged.index.duplicated(keep='first')]
    merged['timestamp'] = merged.index
    merged['year'] = merged['timestamp'].dt.year
    return merged, year_ranges


def print_per_year_summary(result: BacktestResult, year_ranges: Dict[int, Tuple[datetime, datetime]]):
    """Wyświetla podsumowanie wyników per rok z kolorami i emotkami."""
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    
    print(f"\n{CYAN}{'=' * 100}{RESET}")
    print(f"{BOLD}📅 PODSUMOWANIE PER ROK{RESET}")
    print(f"{CYAN}{'=' * 100}{RESET}")
    
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
    
    print(f"\n{BOLD}{'Rok':<6} {'Transakcje':<12} {'Zyskownych':<12} {'Stratnych':<12} {'PnL USD':<18} {'PnL %':<12}{RESET}")
    print(f"{CYAN}{'-' * 100}{RESET}")
    
    total_pnl_all_years = 0.0
    total_trades_all_years = 0
    total_winning = 0
    total_losing = 0
    
    for year in sorted(year_stats.keys()):
        stats = year_stats[year]
        num_trades = len(stats['trades'])
        total_trades_all_years += num_trades
        total_pnl_all_years += stats['total_pnl']
        total_winning += stats['winning']
        total_losing += stats['losing']
        
        initial_balance = result.initial_balance
        pnl_percent = (stats['total_pnl'] / initial_balance) * 100 if initial_balance > 0 else 0.0
        
        # Kolory i emotki
        if stats['total_pnl'] > 0:
            pnl_color = GREEN
            pnl_emoji = "📈"
        elif stats['total_pnl'] < 0:
            pnl_color = RED
            pnl_emoji = "📉"
        else:
            pnl_color = YELLOW
            pnl_emoji = "➖"
        
        pnl_str = f"{pnl_color}{pnl_emoji} ${stats['total_pnl']:+,.2f}{RESET}"
        pnl_pct_str = f"{pnl_color}{pnl_percent:+.2f}%{RESET}"
        
        winrate = (stats['winning'] / num_trades * 100) if num_trades > 0 else 0.0
        winrate_emoji = "✅" if winrate >= 50 else "❌"
        
        print(f"{BOLD}{year:<6}{RESET} {num_trades:<12} {GREEN}{stats['winning']:<12}{RESET} {RED}{stats['losing']:<12}{RESET} {pnl_str:<18} {pnl_pct_str:<12}")
    
    print(f"{CYAN}{'-' * 100}{RESET}")
    
    total_pnl_percent = (total_pnl_all_years / result.initial_balance) * 100 if result.initial_balance > 0 else 0.0
    total_winrate = (total_winning / total_trades_all_years * 100) if total_trades_all_years > 0 else 0.0
    
    if total_pnl_all_years > 0:
        total_pnl_color = GREEN
        total_emoji = "🎉"
    elif total_pnl_all_years < 0:
        total_pnl_color = RED
        total_emoji = "😞"
    else:
        total_pnl_color = YELLOW
        total_emoji = "➖"
    
    print(f"{BOLD}{'ŁĄCZNIE':<6}{RESET} {total_trades_all_years:<12} {GREEN}{total_winning:<12}{RESET} {RED}{total_losing:<12}{RESET} "
          f"{total_pnl_color}{total_emoji} ${total_pnl_all_years:+,.2f}{RESET:<18} "
          f"{total_pnl_color}{total_pnl_percent:+.2f}%{RESET:<12}")
    print(f"{CYAN}{'=' * 100}{RESET}")


def print_detailed_results(result: BacktestResult, year_ranges: Dict[int, Tuple[datetime, datetime]] = None):
    """Wypisuje wyniki z kolorami i emotkami."""
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    CYAN = '\033[0;36m'
    BLUE = '\033[0;34m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    
    # Podsumowanie per rok jeśli wiele lat
    if year_ranges and len(year_ranges) > 1:
        print_per_year_summary(result, year_ranges)
    
    print(f"\n{CYAN}{'=' * 100}{RESET}")
    print(f"{BOLD}📊 WYNIKI BACKTESTU - UNDERHUMAN 2.0{RESET}")
    print(f"{CYAN}{'=' * 100}{RESET}")

    # NAJPIERW TABELA TRANSAKCJI
    print("\n📋 WSZYSTKIE TRANSAKCJE:")
    print("-" * 100)
    header = f"{'#':<4} {'Data wejścia':<20} {'Data wyjścia':<20} {'Strona':<6} {'Cena wejścia':<14} {'Cena wyjścia':<14} {'PnL USD':<12} {'PnL %':<10} {'Powód':<18}"
    print(header)
    print("-" * 100)

    for idx, trade in enumerate(result.trades, start=1):
        entry_time = trade.get('entry_time')
        exit_time = trade.get('exit_time')
        side = trade.get('side', 'N/A').upper()
        entry_price = float(trade.get('entry_price', 0.0))
        exit_price = float(trade.get('exit_price', 0.0))
        pnl = float(trade.get('pnl', 0.0))
        pnl_percent = float(trade.get('pnl_percent', 0.0))
        reason = str(trade.get('exit_reason', 'N/A'))[:18]

        entry_str = entry_time.strftime('%Y-%m-%d %H:%M') if hasattr(entry_time, 'strftime') else str(entry_time)
        exit_str = exit_time.strftime('%Y-%m-%d %H:%M') if hasattr(exit_time, 'strftime') else str(exit_time)

        entry_price_str = f"${entry_price:,.2f}"
        exit_price_str = f"${exit_price:,.2f}"
        pnl_usd = f"${pnl:+,.2f}"
        pnl_pct = f"{pnl_percent:+.2f}%"

        pnl_color = GREEN if pnl > 0 else RED if pnl < 0 else YELLOW
        print(f"{idx:<4} {entry_str:<20} {exit_str:<20} {side:<6} {entry_price_str:<14} {exit_price_str:<14} {pnl_color}{pnl_usd:<12}{RESET} {pnl_color}{pnl_pct:<10}{RESET} {reason:<18}")
    
    print("-" * 100)
    
    # TERAZ PODSUMOWANIE FINANSOWE I STATYSTYKI
    # Emotki i kolory dla wyników
    pnl_emoji = "📈" if result.total_pnl > 0 else "📉" if result.total_pnl < 0 else "➖"
    pnl_color = GREEN if result.total_pnl > 0 else RED if result.total_pnl < 0 else YELLOW
    
    winrate_emoji = "✅" if result.win_rate >= 50 else "⚠️"
    winrate_color = GREEN if result.win_rate >= 50 else YELLOW
    
    dd_emoji = "⚠️" if result.max_drawdown > 20 else "✅"
    dd_color = RED if result.max_drawdown > 20 else YELLOW if result.max_drawdown > 10 else GREEN

    print(f"\n{BOLD}💰 PODSUMOWANIE FINANSOWE:{RESET}")
    print("-" * 100)
    print(f"   💵 Kapitał początkowy:  {BLUE}${result.initial_balance:,.2f}{RESET}")
    print(f"   💰 Kapitał końcowy:    {BLUE}${result.final_balance:,.2f}{RESET}")
    total_pnl = result.final_balance - result.initial_balance
    print(f"   {pnl_emoji} Zysk/Strata:        {pnl_color}${total_pnl:+,.2f} ({result.total_return:+.2f}%){RESET}")
    print(f"   💸 Opłaty łącznie:     {YELLOW}${result.total_fees:,.2f}{RESET}")
    print("-" * 100)
    
    # Lista zysków z podziałem na lata
    print_yearly_pnl_summary(result, GREEN, RED, RESET)
    
    print(f"\n{BOLD}📊 STATYSTYKI:{RESET}")
    print(f"   🎯 Liczba transakcji:  {CYAN}{len(result.trades)}{RESET}")
    print(f"   {winrate_emoji} Trafność (winrate): {winrate_color}{result.win_rate:.2f}%{RESET}")
    print(f"   ✅ Zyskownych:         {GREEN}{result.winning_trades}{RESET}")
    print(f"   ❌ Stratnych:          {RED}{result.losing_trades}{RESET}")
    print(f"   {dd_emoji} Max Drawdown:       {dd_color}{result.max_drawdown:.2f}%{RESET}")
    
    if result.total_trades > 0:
        avg_pnl = result.total_pnl / result.total_trades
        avg_emoji = "📈" if avg_pnl > 0 else "📉"
        avg_color = GREEN if avg_pnl > 0 else RED
        print(f"   {avg_emoji} Średni PnL:         {avg_color}${avg_pnl:+,.2f}{RESET}")
        print(f"   🏆 Najlepsza:         {GREEN}${result.largest_win:,.2f}{RESET}")
        print(f"   💥 Najgorsza:         {RED}${result.largest_loss:,.2f}{RESET}")

    if year_ranges:
        years = sorted(year_ranges.keys())
        start = min(year_ranges[y][0] for y in years)
        end = max(year_ranges[y][1] for y in years)
        print(f"\n{BOLD}🗓️  Okres:{RESET}             {start} → {end} ({', '.join(map(str, years))})")
    
    print(f"\n{CYAN}{'=' * 100}{RESET}")


def print_yearly_pnl_summary(result: BacktestResult, GREEN: str, RED: str, RESET: str):
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
    
    for year in sorted(year_stats.keys()):
        stats = year_stats[year]
        pnl = stats['total_pnl']
        pnl_color = GREEN if pnl > 0 else RED if pnl < 0 else ""
        pnl_percent = (pnl / result.initial_balance) * 100 if result.initial_balance > 0 else 0.0
        emoji = "📈" if pnl > 0 else "📉" if pnl < 0 else "➖"
        
        print(f"   {emoji} {year}: {pnl_color}${pnl:+,.2f}{RESET} ({pnl_color}{pnl_percent:+.2f}%{RESET}) - {stats['trades']} transakcji")
    
    print("-" * 100)


def parse_args():
    p = argparse.ArgumentParser(description="Backtest UnderhumanStrategyV2 na danych CSV")
    p.add_argument('--csv', nargs='+', required=False, help='Ścieżka(i) do pliku CSV (opcjonalnie, domyślnie używa bazy danych)')
    p.add_argument('--balance', type=float, default=10000.0, help='Kapitał początkowy')
    p.add_argument('--leverage', type=float, default=10.0, help='Dźwignia')
    p.add_argument('--position-size', type=float, default=15.0, help='Rozmiar pozycji w %')
    p.add_argument('--verbose', action='store_true', help='Więcej logów')
    return p.parse_args()


def main():
    args = parse_args()
    setup_logging(args.verbose)

    # Jeśli nie podano CSV, użyj bazy danych
    if args.csv is None:
        logger.info("📂 Używam danych z bazy danych (BTC/USDC)...")
        df = load_csv_data(None)
        year_ranges = {}
        if not df.empty:
            # Grupuj po latach
            for year in df['year'].unique():
                year_df = df[df['year'] == year]
                year_ranges[int(year)] = (year_df.index.min(), year_df.index.max())
    else:
    csv_paths = [Path(p) for p in args.csv]
    if len(csv_paths) > 1:
        logger.info(f"📂 Wczytuję {len(csv_paths)} plików CSV i łączę je...")
        df, year_ranges = load_multiple_csv_files(csv_paths)
    else:
        df = load_csv_data(csv_paths[0])
        year_ranges = {}
        if not df.empty:
            year_ranges[int(df['year'].iloc[0])] = (df.index.min(), df.index.max())

    if df.empty:
        logger.error("❌ Nie można wczytać danych")
        return 1

    logger.info("🤖 Inicjalizuję UnderhumanStrategyV2...")
    strategy = UnderhumanStrategyV2({
        '_backtest_mode': True,
        # V2 jest zaprojektowana pod 1h – parametry dostosowane do okna backtestu (100 świec)
        'timeframe': '1h',
        'ema_fast_period': 20,    # Zmniejszone z 50 (okno backtestu = 100)
        'ema_slow_period': 50,    # Zmniejszone z 200 (okno backtestu = 100)
        'atr_period': 14,
        'atr_long_period': 30,    # Zmniejszone z 50
        'rsi_period': 14,
        'vol_ma_period': 20,
        # progi
        'impulse_thr_atr_mult': 2.0,
        'vol_spike_mult': 2.0,
        'volatility_high_thr': 1.2,
        'volatility_low_thr': 0.8,
        # ryzyko
        'sl_trend_atr_mult': 1.0,
        'tp_trend_atr_mult': 2.0,
        'sl_range_atr_mult': 1.0,
        'tp_range_atr_mult': 1.0,
        # filtry (poluzowane dla lepszej aktywności)
        'counter_anomaly_threshold': 2,  # Łatwiejsze wejście counter-trend
        'pro_trend_min_anomaly': 0,      # Sam trend wystarczy dla pro-trend
        'range_min_anomaly': 1,          # Łatwiejsze wejście w range
        # anty-whipsaw
        'cooldown_bars': 3,
        'regime_lock_bars': 3,
        # egzekucja
        'slippage_percent': 0.1,
        'min_confidence_for_trade': 5.0,  # Obniżone dla lepszej aktywności
    })

    logger.info("⚙️  Inicjalizuję BacktestEngine...")
    engine = BacktestEngine(
        initial_balance=args.balance,
        taker_fee=0.0005,
        maker_fee=0.0,
        slippage_percent=0.1,
        leverage=args.leverage,
    )

    logger.info("🚀 Uruchamiam backtest (tryb ekspresowy)...")
    start_time = datetime.now()

    result = engine.run_backtest(
        strategy=strategy,
        symbol="BTC/USDC",  # Zmieniono z BTC-USD na BTC/USDC
        df=df,
        position_size_percent=args.position_size,
        max_positions=1,
    )

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() or 1e-9

    print_detailed_results(result, year_ranges if len(year_ranges) > 1 else None)

    print(f"\n⏱️  Czas wykonania: {duration:.2f} sekund")
    print(f"📊 Przetworzono {len(df)} świec")
    print(f"⚡ Prędkość: {len(df)/duration:.0f} świec/sekundę")
    
    # Wyświetl wyniki w formacie JSON dla skryptu bash (na stderr żeby nie mieszać z normalnym outputem)
    summary = {
        'initial_balance': result.initial_balance,
        'final_balance': result.final_balance,
        'total_pnl': result.total_pnl,
        'total_return': result.total_return,
        'total_trades': len(result.trades),
        'winning_trades': result.winning_trades,
        'losing_trades': result.losing_trades,
        'win_rate': result.win_rate,
        'max_drawdown': result.max_drawdown,
        'largest_win': result.largest_win,
        'largest_loss': result.largest_loss,
        'year': int(df['year'].iloc[-1]) if not df.empty and 'year' in df.columns else None
    }
    print(f"\n<!--JSON_RESULT_START-->{json.dumps(summary)}<!--JSON_RESULT_END-->", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
