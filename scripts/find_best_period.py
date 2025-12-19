#!/usr/bin/env python3
"""
Find Best Trading Period
========================
Skrypt do znajdowania najbardziej korzystnego okresu historycznego dla testowania strategii.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

from loguru import logger
from src.collectors.exchange.dydx_collector import DydxCollector
import pandas as pd


def setup_logging():
    """Konfiguruje logowanie."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO",
        colorize=True
    )


def analyze_period(collector: DydxCollector, symbol: str, start_date: datetime, end_date: datetime, timeframe: str = "1h"):
    """Analizuje okres i zwraca statystyki."""
    logger.info(f"Analizuję okres: {start_date.date()} → {end_date.date()}")
    
    df = collector.fetch_historical_candles(
        ticker=symbol,
        resolution=timeframe,
        start_date=start_date,
        end_date=end_date
    )
    
    if df.empty or len(df) < 10:
        return None
    
    first_price = float(df.iloc[0]['close'])
    last_price = float(df.iloc[-1]['close'])
    change = ((last_price - first_price) / first_price) * 100
    
    # Oblicz volatility
    returns = df['close'].pct_change().dropna()
    volatility = returns.std() * 100
    
    # Oblicz max wzrost/spadek w okresie
    high = float(df['high'].max())
    low = float(df['low'].min())
    max_gain = ((high - first_price) / first_price) * 100
    max_drawdown = ((low - first_price) / first_price) * 100
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'days': (end_date - start_date).days,
        'first_price': first_price,
        'last_price': last_price,
        'change': change,
        'volatility': volatility,
        'max_gain': max_gain,
        'max_drawdown': max_drawdown,
        'candles': len(df),
        'df': df
    }


def find_best_periods(symbol: str = "BTC-USD", max_days_back: int = 180, timeframe: str = "1h"):
    """Znajduje najlepsze okresy historyczne."""
    logger.info(f"🔍 Szukam najlepszych okresów dla {symbol} (ostatnie {max_days_back} dni)")
    
    collector = DydxCollector(testnet=False)
    end_date = datetime.now()
    
    periods = []
    
    # Testuj różne okresy: 7, 14, 30, 60, 90, 120, 180 dni
    test_durations = [7, 14, 30, 60, 90, 120, 180]
    
    for days in test_durations:
        if days > max_days_back:
            continue
        
        start_date = end_date - timedelta(days=days)
        
        try:
            stats = analyze_period(collector, symbol, start_date, end_date, timeframe)
            if stats:
                periods.append(stats)
                logger.info(
                    f"  {days:3d} dni: {stats['change']:+.2f}% "
                    f"(vol: {stats['volatility']:.2f}%, "
                    f"max: {stats['max_gain']:+.2f}%, "
                    f"min: {stats['max_drawdown']:+.2f}%)"
                )
        except Exception as e:
            logger.warning(f"  Błąd dla {days} dni: {e}")
            continue
    
    if not periods:
        logger.error("Nie znaleziono żadnych okresów")
        return None, None
    
    # Sortuj po zmianie (malejąco)
    periods.sort(key=lambda x: x['change'], reverse=True)
    
    # Najlepszy okres
    best = periods[0]
    
    logger.info(f"\n🏆 NAJLEPSZY OKRES:")
    logger.info(f"   Okres: {best['start_date'].date()} → {best['end_date'].date()} ({best['days']} dni)")
    logger.info(f"   Zmiana: {best['change']:+.2f}%")
    logger.info(f"   Cena początkowa: ${best['first_price']:,.2f}")
    logger.info(f"   Cena końcowa: ${best['last_price']:,.2f}")
    logger.info(f"   Volatility: {best['volatility']:.2f}%")
    logger.info(f"   Max wzrost: {best['max_gain']:+.2f}%")
    logger.info(f"   Max spadek: {best['max_drawdown']:+.2f}%")
    logger.info(f"   Świec: {best['candles']}")
    
    return best, periods


def save_period_data(best_period: dict, symbol: str, output_dir: Path = None):
    """Zapisuje dane najlepszego okresu do pliku."""
    if output_dir is None:
        output_dir = Path("data/backtest_periods")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Nazwa pliku
    start_str = best_period['start_date'].strftime("%Y%m%d")
    end_str = best_period['end_date'].strftime("%Y%m%d")
    filename = f"{symbol.replace('-', '_')}_{start_str}_{end_str}.csv"
    filepath = output_dir / filename
    
    # Zapisz DataFrame (użyj CSV zamiast parquet)
    df = best_period['df']
    # Zmień rozszerzenie na .csv
    filepath = filepath.with_suffix('.csv')
    df.to_csv(filepath)
    
    logger.success(f"💾 Zapisano dane do: {filepath}")
    logger.info(f"   Rozmiar: {len(df)} świec")
    
    # Zapisz też metadane
    metadata_file = output_dir / f"{symbol.replace('-', '_')}_{start_str}_{end_str}_metadata.json"
    import json
    metadata = {
        'symbol': symbol,
        'start_date': best_period['start_date'].isoformat(),
        'end_date': best_period['end_date'].isoformat(),
        'days': best_period['days'],
        'first_price': best_period['first_price'],
        'last_price': best_period['last_price'],
        'change': best_period['change'],
        'volatility': best_period['volatility'],
        'max_gain': best_period['max_gain'],
        'max_drawdown': best_period['max_drawdown'],
        'candles': best_period['candles'],
        'data_file': filename
    }
    
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.success(f"💾 Zapisano metadane do: {metadata_file}")
    
    return filepath, metadata_file


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Znajdź najlepszy okres historyczny dla testowania strategii")
    parser.add_argument("--symbol", default="BTC-USD", help="Symbol pary")
    parser.add_argument("--max-days", type=int, default=180, help="Maksymalna liczba dni wstecz")
    parser.add_argument("--timeframe", default="1h", help="Timeframe (1h, 1d)")
    parser.add_argument("--save", action="store_true", help="Zapisz dane najlepszego okresu")
    
    args = parser.parse_args()
    
    setup_logging()
    
    best_period, all_periods = find_best_periods(
        symbol=args.symbol,
        max_days_back=args.max_days,
        timeframe=args.timeframe
    )
    
    if not best_period:
        logger.error("Nie znaleziono najlepszego okresu")
        return
    
    # Wyświetl top 5 okresów
    if all_periods:
        print("\n" + "=" * 80)
        print("📊 TOP 5 OKRESÓW:")
        print("=" * 80)
        for i, period in enumerate(all_periods[:5], 1):
            print(f"\n{i}. {period['days']} dni ({period['start_date'].date()} → {period['end_date'].date()}):")
            print(f"   Zmiana: {period['change']:+.2f}%")
            print(f"   Volatility: {period['volatility']:.2f}%")
            print(f"   Max wzrost: {period['max_gain']:+.2f}%")
            print(f"   Max spadek: {period['max_drawdown']:+.2f}%")
    
    # Zapisz jeśli wymagane
    if args.save:
        filepath, metadata_file = save_period_data(best_period, args.symbol)
        print(f"\n✅ Gotowe! Użyj tych danych do backtestingu:")
        print(f"   python scripts/backtest.py --strategy=piotrek_breakout_strategy --symbol={args.symbol} --start={best_period['start_date'].date()} --end={best_period['end_date'].date()}")


if __name__ == "__main__":
    main()

