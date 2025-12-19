#!/usr/bin/env python3
"""
Update 2025 Data
================
Skrypt do uzupełnienia danych BTC/USDC z 2025 roku do aktualnej daty.
Pobiera brakujące dane z Binance i aktualizuje plik CSV.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import json
from dotenv import load_dotenv

# Dodaj ścieżkę projektu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Załaduj .env jeśli istnieje
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

from loguru import logger
from src.collectors.exchange.binance_collector import BinanceCollector

# Konfiguracja logowania
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="INFO",
    colorize=True
)


def load_existing_data(csv_file: Path = None) -> pd.DataFrame:
    """
    Wczytuje istniejące dane z bazy danych (BTC/USDC) lub z CSV (fallback).
    
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
                df = df.sort_index()
                logger.success(f"✅ Wczytano {len(df)} świec z bazy danych")
                logger.info(f"   Okres: {df.index[0]} → {df.index[-1]}")
                return df
        except Exception as e:
            logger.warning(f"Nie udało się wczytać z bazy danych: {e}, próbuję CSV...")
    
    # Fallback do CSV
    if csv_file is None:
        logger.error("❌ Brak pliku CSV i nie można wczytać z bazy danych")
        return pd.DataFrame()
    
    if not csv_file.exists():
        logger.error(f"Plik nie istnieje: {csv_file}")
        return pd.DataFrame()
    
    logger.info(f"📂 Wczytuję istniejące dane z CSV: {csv_file}")
    df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
    df = df.sort_index()
    
    logger.success(f"✅ Wczytano {len(df)} świec z CSV")
    logger.info(f"   Okres: {df.index[0]} → {df.index[-1]}")
    
    return df


def fetch_missing_data(
    collector: BinanceCollector,
    start_date: datetime,
    end_date: datetime,
    symbol: str = "BTC/USDC",
    timeframe: str = "1h"
) -> pd.DataFrame:
    """Pobiera brakujące dane z Binance."""
    logger.info(f"📥 Pobieram brakujące dane: {start_date} → {end_date}")
    
    df = collector.fetch_historical(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date
    )
    
    if df.empty:
        logger.warning("⚠️  Nie pobrano żadnych danych")
        return pd.DataFrame()
    
    logger.success(f"✅ Pobrano {len(df)} nowych świec")
    return df


def merge_data(existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """Łączy istniejące i nowe dane, usuwa duplikaty."""
    if existing_df.empty:
        return new_df
    
    if new_df.empty:
        return existing_df
    
    # Połącz dane
    combined = pd.concat([existing_df, new_df])
    
    # Usuń duplikaty (zachowaj pierwszy)
    combined = combined[~combined.index.duplicated(keep='first')]
    
    # Sortuj po dacie
    combined = combined.sort_index()
    
    logger.info(f"📊 Połączono dane: {len(existing_df)} + {len(new_df)} = {len(combined)} (po usunięciu duplikatów)")
    
    return combined


def save_data(df: pd.DataFrame, csv_file: Path, metadata_file: Path, year: str = "2025"):
    """Zapisuje dane do CSV i aktualizuje metadata."""
    # Zapisuj CSV
    logger.info(f"💾 Zapisuję dane do: {csv_file}")
    df.to_csv(csv_file)
    logger.success(f"✅ Zapisano {len(df)} świec do CSV")
    
    # Aktualizuj metadata
    first_price = float(df['close'].iloc[0])
    last_price = float(df['close'].iloc[-1])
    high_price = float(df['high'].max())
    low_price = float(df['low'].min())
    change_percent = ((last_price - first_price) / first_price) * 100
    
    # Oblicz volatility (odchylenie standardowe zmian cen)
    price_changes = df['close'].pct_change() * 100
    volatility_percent = float(price_changes.std())
    
    metadata = {
        "year": year,
        "symbol": "BTC/USDC",
        "timeframe": "1h",
        "start_date": df.index[0].strftime('%Y-%m-%dT%H:%M:%S'),
        "end_date": df.index[-1].strftime('%Y-%m-%dT%H:%M:%S'),
        "candles": len(df),
        "first_price": first_price,
        "last_price": last_price,
        "high_price": high_price,
        "low_price": low_price,
        "change_percent": change_percent,
        "volatility_percent": volatility_percent,
        "source": "Binance API",
        "data_file": csv_file.name
    }
    
    logger.info(f"💾 Aktualizuję metadata: {metadata_file}")
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.success("✅ Metadata zaktualizowane")
    
    # Wyświetl podsumowanie
    print("\n" + "=" * 70)
    print("📊 PODSUMOWANIE ZAKTUALIZOWANYCH DANYCH")
    print("=" * 70)
    print(f"Rok: {year}")
    print(f"Symbol: {metadata['symbol']}")
    print(f"Timeframe: {metadata['timeframe']}")
    print(f"Świece: {metadata['candles']}")
    print(f"Okres: {metadata['start_date']} → {metadata['end_date']}")
    print(f"Cena początkowa: ${metadata['first_price']:,.2f}")
    print(f"Cena końcowa: ${metadata['last_price']:,.2f}")
    print(f"Zmiana: {metadata['change_percent']:+.2f}%")
    print(f"Volatility: {metadata['volatility_percent']:.2f}%")
    print("=" * 70)


def main():
    """Główna funkcja."""
    # Ścieżki plików
    data_dir = Path("data/backtest_periods/binance")
    csv_file = data_dir / "BTCUSDC_2025_1h.csv"
    metadata_file = data_dir / "BTCUSDC_2025_1h_metadata.json"
    
    # Sprawdź czy pliki istnieją
    if not csv_file.exists():
        logger.error(f"Plik CSV nie istnieje: {csv_file}")
        logger.info("Uruchom najpierw skrypt do pobrania danych z 2025 roku")
        sys.exit(1)
    
    # Wczytaj istniejące dane
    existing_df = load_existing_data(csv_file)
    
    if existing_df.empty:
        logger.error("Nie udało się wczytać istniejących danych")
        sys.exit(1)
    
    # Określ datę początkową dla nowych danych (ostatnia świeca + 1h)
    last_timestamp = existing_df.index[-1]
    if isinstance(last_timestamp, pd.Timestamp):
        start_date = last_timestamp.to_pydatetime()
    else:
        start_date = pd.to_datetime(last_timestamp).to_pydatetime()
    
    # Dodaj 1 godzinę (następna świeca)
    from datetime import timedelta
    start_date = start_date + timedelta(hours=1)
    
    # Data końcowa: dzisiaj 23:59:59
    end_date = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=0)
    
    logger.info(f"📅 Okres do uzupełnienia: {start_date} → {end_date}")
    
    # Sprawdź czy są dane do pobrania
    if start_date >= end_date:
        logger.info("✅ Wszystkie dane są już aktualne!")
        logger.info(f"   Ostatnia świeca: {last_timestamp}")
        return
    
    # Pobierz brakujące dane
    collector = BinanceCollector(sandbox=False)
    new_df = fetch_missing_data(
        collector=collector,
        start_date=start_date,
        end_date=end_date,
        symbol="BTC/USDC",
        timeframe="1h"
    )
    
    if new_df.empty:
        logger.warning("⚠️  Nie pobrano nowych danych - możliwe że dane są już aktualne")
        return
    
    # Połącz dane
    combined_df = merge_data(existing_df, new_df)
    
    # Zapisz zaktualizowane dane
    save_data(combined_df, csv_file, metadata_file, year="2025")
    
    logger.success("\n🎉 Dane zaktualizowane pomyślnie!")


if __name__ == "__main__":
    main()

