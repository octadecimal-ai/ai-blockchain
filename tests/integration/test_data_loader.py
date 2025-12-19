"""
Wspólna funkcja do wczytywania danych dla testów.
Używa bazy danych (BTC/USDC) z fallback do CSV.
"""

from pathlib import Path
from typing import Optional
import pandas as pd
from loguru import logger


def load_csv_data(csv_file: Optional[Path] = None) -> pd.DataFrame:
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
        df = df.sort_index()
    else:
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
    
    # Dodaj kolumnę timestamp dla kompatybilności
    if 'timestamp' not in df.columns:
        df['timestamp'] = df.index
    
    # Dodaj kolumnę z rokiem dla późniejszej analizy
    df['year'] = df['timestamp'].dt.year
    
    logger.info(f"✅ Wczytano {len(df)} świec z CSV")
    logger.info(f"   Okres: {df['timestamp'].min()} → {df['timestamp'].max()}")
    
    return df

