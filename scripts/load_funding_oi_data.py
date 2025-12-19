#!/usr/bin/env python3
"""
Load Funding Rates and Open Interest Data
=========================================
Pobiera dane funding rates i open interest z Binance Futures
i zapisuje je do bazy danych PostgreSQL.

Użycie:
    python scripts/load_funding_oi_data.py
    python scripts/load_funding_oi_data.py --days=30
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
import argparse
from loguru import logger

# Dodaj ścieżkę projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.collectors.exchange.binance_collector import BinanceCollector
from src.database.manager import DatabaseManager


def load_funding_rates_and_oi(
    symbol: str = "BTC/USDT:USDT",
    days: int = 365,
    exchange_name: str = "binance"
):
    """
    Pobiera i zapisuje funding rates i open interest do bazy danych.
    
    Args:
        symbol: Symbol perpetual futures (np. "BTC/USDT:USDT")
        days: Liczba dni wstecz do pobrania
        exchange_name: Nazwa giełdy w bazie danych
    """
    # Załaduj .env
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    database_url = os.getenv('DATABASE_URL')
    use_timescale = os.getenv('USE_TIMESCALE', 'false').lower() == 'true'
    
    # Inicjalizuj kolektor i bazę
    collector = BinanceCollector(sandbox=False)
    db = DatabaseManager(database_url=database_url, use_timescale=use_timescale)
    
    # Utwórz tabele jeśli nie istnieją
    db.create_tables()
    
    # Oblicz zakres dat
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    logger.info(f"Pobieram funding rates i open interest dla {symbol}")
    logger.info(f"Okres: {start_date.date()} → {end_date.date()} ({days} dni)")
    
    # Pobierz funding rates
    logger.info("📊 Pobieram funding rates...")
    funding_df = collector.get_funding_rates(
        symbol=symbol,
        since=start_date,
        limit=10000
    )
    
    if not funding_df.empty:
        logger.info(f"Pobrano {len(funding_df)} funding rates")
        # Tickers używają symbolu spot, więc konwertuj symbol perpetual na spot
        ticker_symbol = "BTC/USDC" if "BTC" in symbol else symbol.replace(":USDT", "").replace("/USDT", "/USDC")
        saved = db.save_funding_rates(
            df=funding_df,
            exchange=exchange_name,
            symbol=ticker_symbol  # Używamy symbolu spot dla tickers
        )
        logger.success(f"✅ Zapisano {saved} funding rates do tickers")
    else:
        logger.warning("Brak funding rates do zapisania")
    
    # Pobierz open interest
    logger.info("📊 Pobieram open interest...")
    oi_df = collector.get_open_interest(
        symbol=symbol,
        since=start_date,
        limit=10000
    )
    
    if not oi_df.empty:
        logger.info(f"Pobrano {len(oi_df)} rekordów open interest")
        # Dodaj cenę z OHLCV dla lepszego dopasowania
        ohlcv_df = db.get_ohlcv(
            exchange=exchange_name,
            symbol="BTC/USDC",  # Używamy spot dla ceny
            timeframe="1m",
            start_date=start_date,
            end_date=end_date
        )
        
        if not ohlcv_df.empty:
            # Merge open interest z ceną
            oi_df = oi_df.join(ohlcv_df[['close']], how='left')
            oi_df.rename(columns={'close': 'price'}, inplace=True)
        
        saved = db.save_open_interest(
            df=oi_df,
            exchange=exchange_name,
            symbol=symbol
        )
        logger.success(f"✅ Zapisano {saved} rekordów open interest do bazy")
    else:
        logger.warning("Brak open interest do zapisania")
    
    # Podsumowanie
    logger.info("\n📈 Podsumowanie:")
    # Sprawdź funding rates w tickers (używamy symbolu spot dla tickers)
    ticker_symbol = "BTC/USDC"  # Tickers używają symbolu spot
    funding_count = db.get_funding_rates(exchange_name, ticker_symbol).shape[0]
    oi_count = db.get_open_interest(exchange_name, symbol).shape[0]
    logger.info(f"   Funding rates w tickers: {funding_count}")
    logger.info(f"   Open interest w bazie: {oi_count}")


def main():
    parser = argparse.ArgumentParser(
        description="Pobiera i zapisuje funding rates i open interest do bazy danych"
    )
    parser.add_argument(
        '--days',
        type=int,
        default=365,
        help='Liczba dni wstecz do pobrania (domyślnie: 365)'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default="BTC/USDT:USDT",
        help='Symbol perpetual futures (domyślnie: BTC/USDT:USDT)'
    )
    
    args = parser.parse_args()
    
    # Konfiguruj logger
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO",
        colorize=True
    )
    
    try:
        load_funding_rates_and_oi(
            symbol=args.symbol,
            days=args.days
        )
        logger.success("✅ Zakończono pomyślnie")
        return 0
    except Exception as e:
        logger.error(f"❌ Błąd: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

