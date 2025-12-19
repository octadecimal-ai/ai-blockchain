#!/usr/bin/env python3
"""
Skrypt do czyszczenia danych BTC/USDC z bazy danych.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Dodaj ścieżkę projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text

# Załaduj .env
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)

def clear_btcusdc_data(database_url: str = None, timeframe: str = None):
    """
    Czyści dane BTC/USDC z bazy danych.
    
    Args:
        database_url: URL bazy danych (domyślnie z .env)
        timeframe: Opcjonalnie, usuń tylko dane dla konkretnego timeframe (np. '1h', '1m')
    """
    if database_url is None:
        database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        logger.error("❌ Brak DATABASE_URL w .env")
        return False
    
    logger.info(f"🔗 Łączę z bazą danych...")
    engine = create_engine(database_url)
    
    try:
        with engine.begin() as conn:
            if timeframe:
                # Usuń tylko dane dla konkretnego timeframe
                result = conn.execute(text(
                    "DELETE FROM ohlcv WHERE exchange = 'binance' AND symbol = 'BTC/USDC' AND timeframe = :timeframe"
                ), {"timeframe": timeframe})
                logger.info(f"🗑️  Usuwam dane BTC/USDC dla timeframe: {timeframe}")
            else:
                # Usuń wszystkie dane BTC/USDC
                result = conn.execute(text(
                    "DELETE FROM ohlcv WHERE exchange = 'binance' AND symbol = 'BTC/USDC'"
                ))
                logger.info("🗑️  Usuwam wszystkie dane BTC/USDC")
            
            deleted_count = result.rowcount
            logger.success(f"✅ Usunięto {deleted_count} rekordów")
            return True
            
    except Exception as e:
        logger.error(f"❌ Błąd podczas czyszczenia: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Czyści dane BTC/USDC z bazy danych")
    parser.add_argument(
        '--timeframe',
        type=str,
        help='Usuń tylko dane dla konkretnego timeframe (np. 1h, 1m). Jeśli nie podano, usuwa wszystkie.'
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Potwierdź usunięcie danych (wymagane)'
    )
    
    args = parser.parse_args()
    
    if not args.confirm:
        logger.warning("⚠️  Użyj --confirm aby potwierdzić usunięcie danych")
        sys.exit(1)
    
    if args.timeframe:
        logger.info(f"Usuwam dane BTC/USDC dla timeframe: {args.timeframe}")
    else:
        logger.warning("⚠️  Usuwam WSZYSTKIE dane BTC/USDC z bazy!")
    
    success = clear_btcusdc_data(timeframe=args.timeframe)
    sys.exit(0 if success else 1)

