"""
BTC/USDC Data Loader
====================
Klasa do pobierania danych BTC/USDC z Binance i zapisywania do bazy danych.
Zastępuje użycie plików CSV.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import pandas as pd
from loguru import logger

# Dodaj ścieżkę projektu
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.collectors.exchange.binance_collector import BinanceCollector
from src.database.manager import DatabaseManager


class BTCUSDCDataLoader:
    """
    Klasa do pobierania i zarządzania danymi BTC/USDC z Binance.
    
    Obsługuje:
    - Pobieranie danych historycznych od 2020 roku
    - Aktualizację o najnowsze dane
    - Zapis do bazy danych (tabela ohlcv)
    - Kompatybilność z istniejącymi klasami używającymi CSV
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        use_timescale: bool = False,
        timeframe: str = "1h"
    ):
        """
        Inicjalizacja loadera.
        
        Args:
            database_url: URL bazy danych (domyślnie z .env lub SQLite)
            use_timescale: Czy użyć TimescaleDB (wymaga PostgreSQL)
            timeframe: Interwał czasowy (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M)
        """
        self.collector = BinanceCollector(sandbox=False)
        self.db = DatabaseManager(database_url=database_url, use_timescale=use_timescale)
        self.symbol = "BTC/USDC"
        self.exchange = "binance"
        self.timeframe = timeframe
        
        # Walidacja timeframe
        valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
        if timeframe not in valid_timeframes:
            logger.warning(f"Nieznany timeframe {timeframe}, używam 1h. Dostępne: {valid_timeframes}")
            self.timeframe = "1h"
        
        logger.info(f"BTCUSDCDataLoader zainicjalizowany dla {self.symbol} {self.timeframe}")
    
    def load_historical_data(
        self,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> int:
        """
        Pobiera dane historyczne z Binance i zapisuje do bazy.
        
        Args:
            start_date: Data początkowa (domyślnie 2020-01-01)
            end_date: Data końcowa (domyślnie teraz)
            
        Returns:
            Liczba zapisanych świec
        """
        if start_date is None:
            start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        
        logger.info(f"Pobieram dane historyczne {self.symbol} od {start_date} do {end_date}")
        
        # Pobierz dane z Binance
        df = self.collector.fetch_historical(
            symbol=self.symbol,
            timeframe=self.timeframe,
            start_date=start_date,
            end_date=end_date
        )
        
        if df.empty:
            logger.warning("Nie pobrano żadnych danych")
            return 0
        
        logger.info(f"Pobrano {len(df)} świec z Binance")
        
        # Zapisz do bazy danych
        saved_count = self.db.save_ohlcv(
            df=df,
            exchange=self.exchange,
            symbol=self.symbol,
            timeframe=self.timeframe
        )
        
        logger.success(f"Zapisano {saved_count} świec do bazy danych")
        return saved_count
    
    def update_latest_data(
        self,
        days_back: int = 7
    ) -> int:
        """
        Aktualizuje bazę o najnowsze dane.
        
        Args:
            days_back: Ile dni wstecz sprawdzić (domyślnie 7)
            
        Returns:
            Liczba zapisanych świec
        """
        # Sprawdź ostatnią datę w bazie
        latest_in_db = self.get_latest_timestamp()
        
        if latest_in_db:
            # Upewnij się że latest_in_db jest tz-aware
            if latest_in_db.tzinfo is None:
                latest_in_db = latest_in_db.replace(tzinfo=timezone.utc)
            
            start_date = latest_in_db + timedelta(hours=1)  # Od następnej godziny
            logger.info(f"Ostatnia świeca w bazie: {latest_in_db}")
        else:
            # Jeśli baza jest pusta, pobierz ostatnie N dni
            start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            logger.info(f"Baza jest pusta, pobieram ostatnie {days_back} dni")
        
        # Upewnij się że start_date jest tz-aware
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        
        end_date = datetime.now(timezone.utc)
        
        if start_date >= end_date:
            logger.info("Baza jest aktualna, brak nowych danych")
            return 0
        
        return self.load_historical_data(start_date=start_date, end_date=end_date)
    
    def get_latest_timestamp(self) -> Optional[datetime]:
        """
        Zwraca timestamp ostatniej świecy w bazie.
        
        Returns:
            Ostatni timestamp lub None jeśli baza jest pusta
        """
        df = self.db.get_ohlcv(
            exchange=self.exchange,
            symbol=self.symbol,
            timeframe=self.timeframe,
            limit=1
        )
        
        if df.empty:
            return None
        
        # Konwertuj na datetime i upewnij się że jest tz-aware
        dt = df.index[0].to_pydatetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    
    def get_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Pobiera dane z bazy danych w formacie kompatybilnym z CSV.
        
        Args:
            start_date: Data początkowa
            end_date: Data końcowa
            limit: Limit rekordów
            
        Returns:
            DataFrame z kolumnami: open, high, low, close, volume
            Index: timestamp (datetime)
        """
        logger.info(f"Szukam danych: {self.exchange}:{self.symbol} {self.timeframe}")
        
        df = self.db.get_ohlcv(
            exchange=self.exchange,
            symbol=self.symbol,
            timeframe=self.timeframe,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        if df.empty:
            logger.warning(f"Brak danych w bazie dla {self.exchange}:{self.symbol} {self.timeframe}")
            
            # Sprawdź jakie dane są dostępne w bazie
            try:
                available = self.db.get_available_data()
                if not available.empty:
                    logger.info("Dostępne dane w bazie:")
                    for _, row in available.iterrows():
                        logger.info(f"  - {row['exchange']}:{row['symbol']} {row['timeframe']} "
                                  f"({row['first_date']} → {row['last_date']}, {row['candle_count']} świec)")
                else:
                    logger.warning("Baza danych jest pusta - brak jakichkolwiek danych OHLCV")
                    logger.info("Aby załadować dane, użyj: loader.load_historical_data()")
            except Exception as e:
                logger.debug(f"Nie można sprawdzić dostępnych danych: {e}")
            
            return pd.DataFrame()
        
        # Dodaj kolumnę timestamp dla kompatybilności z istniejącymi klasami
        if 'timestamp' not in df.columns:
            df['timestamp'] = df.index
        
        logger.info(f"Pobrano {len(df)} świec z bazy danych")
        if not df.empty:
            logger.info(f"  Okres: {df.index.min()} → {df.index.max()}")
        return df
    
    def get_data_as_csv_format(self, **kwargs) -> pd.DataFrame:
        """
        Pobiera dane w formacie identycznym z CSV (dla kompatybilności).
        
        Returns:
            DataFrame z kolumnami: open, high, low, close, volume
            Index: timestamp (datetime)
        """
        return self.get_data(**kwargs)


def load_btcusdc_from_db(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: Optional[int] = None,
    limit_days: Optional[int] = None
) -> pd.DataFrame:
    """
    Funkcja pomocnicza do wczytywania danych BTC/USDC z bazy.
    Kompatybilna z istniejącymi funkcjami load_csv_data.
    
    Args:
        start_date: Data początkowa
        end_date: Data końcowa
        limit: Limit rekordów
        limit_days: Ograniczenie do ostatnich N dni (jeśli podane, ignoruje start_date)
        
    Returns:
        DataFrame z danymi OHLCV
    """
    # Pobierz DATABASE_URL z .env
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    database_url = os.getenv('DATABASE_URL')
    use_timescale = os.getenv('USE_TIMESCALE', 'false').lower() == 'true'
    
    # Jeśli podano limit_days, ustaw zakres dat
    if limit_days is not None:
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=limit_days)
        logger.info(f"Ograniczam dane do ostatnich {limit_days} dni: {start_date.date()} → {end_date.date()}")
    
    loader = BTCUSDCDataLoader(
        database_url=database_url,
        use_timescale=use_timescale,
        timeframe="1m"  # Używamy danych minutowych
    )
    return loader.get_data(start_date=start_date, end_date=end_date, limit=limit)


# === Przykład użycia ===
if __name__ == "__main__":
    from dotenv import load_dotenv
    
    # Załaduj .env
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    # Inicjalizacja
    loader = BTCUSDCDataLoader()
    
    # Utwórz tabele jeśli nie istnieją
    loader.db.create_tables()
    
    # Pobierz dane historyczne od 2020
    print("\n=== Pobieranie danych historycznych ===")
    count = loader.load_historical_data()
    print(f"Zapisano {count} świec")
    
    # Aktualizuj o najnowsze dane
    print("\n=== Aktualizacja najnowszych danych ===")
    count = loader.update_latest_data()
    print(f"Zaktualizowano {count} świec")
    
    # Pobierz dane z bazy
    print("\n=== Pobieranie danych z bazy ===")
    df = loader.get_data(limit=10)
    print(df)

