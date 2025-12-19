"""
CryptoDataDownload Collector
============================
Moduł do pobierania danych historycznych z CryptoDataDownload.com.

CryptoDataDownload.com oferuje darmowe dane historyczne w formacie CSV
dla wielu giełd kryptowalutowych, w tym Binance, Coinbase, Kraken, itp.

Źródło: https://www.cryptodatadownload.com/data/
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import requests
from pathlib import Path
from loguru import logger
import time


class CryptoDataDownloadCollector:
    """
    Kolektor danych z CryptoDataDownload.com.
    
    Obsługuje:
    - Pobieranie danych OHLCV w formacie CSV
    - Różne giełdy (Binance, Coinbase, Kraken, itp.)
    - Różne timeframe'y (1m, 5m, 1h, 1d, itp.)
    - Automatyczne pobieranie i parsowanie plików CSV
    """
    
    BASE_URL = "https://www.cryptodatadownload.com/cdd"
    
    # Mapowanie timeframe'ów na format CryptoDataDownload
    TIMEFRAME_MAP = {
        '1m': '1min',
        '5m': '5min',
        '15m': '15min',
        '30m': '30min',
        '1h': '1hour',
        '4h': '4hour',
        '1d': '1day',
    }
    
    # Mapowanie symboli (BTC-USD -> BTCUSDT)
    SYMBOL_MAP = {
        'BTC-USD': 'BTCUSDT',
        'ETH-USD': 'ETHUSDT',
        'LTC-USD': 'LTCUSDT',
        'XRP-USD': 'XRPUSDT',
        'SOL-USD': 'SOLUSDT',
        'DOGE-USD': 'DOGEUSDT',
        'BNB-USD': 'BNBUSDT',
        'BCH-USD': 'BCHUSDT',
    }
    
    def __init__(self, exchange: str = "Binance", cache_dir: Optional[Path] = None):
        """
        Inicjalizuje kolektor.
        
        Args:
            exchange: Nazwa giełdy (Binance, Coinbase, Kraken, itp.)
            cache_dir: Katalog do cache'owania pobranych plików
        """
        self.exchange = exchange
        self.cache_dir = cache_dir or Path("data/cache/cryptodatadownload")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"CryptoDataDownload Collector uruchomiony dla giełdy: {exchange}")
    
    def _get_symbol_for_exchange(self, symbol: str) -> str:
        """Konwertuje symbol na format używany przez CryptoDataDownload."""
        # Domyślnie używamy mapowania, ale można rozszerzyć
        return self.SYMBOL_MAP.get(symbol, symbol.replace('-', ''))
    
    def _get_url(self, symbol: str, timeframe: str) -> str:
        """
        Generuje URL do pobrania danych.
        
        Format URL dla Binance:
        https://www.cryptodatadownload.com/cdd/Binance_BTCUSDT_1hour.csv
        """
        symbol_cdd = self._get_symbol_for_exchange(symbol)
        timeframe_cdd = self.TIMEFRAME_MAP.get(timeframe, timeframe)
        
        # Format: Exchange_Symbol_Timeframe.csv
        filename = f"{self.exchange}_{symbol_cdd}_{timeframe_cdd}.csv"
        url = f"{self.BASE_URL}/{filename}"
        
        return url
    
    def _download_file(self, url: str, cache_file: Path) -> Optional[Path]:
        """Pobiera plik CSV i zapisuje w cache."""
        if cache_file.exists():
            logger.info(f"Używam cache'owanego pliku: {cache_file}")
            return cache_file
        
        try:
            logger.info(f"Pobieram dane z: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Zapisz do cache
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(response.content)
            
            logger.success(f"Pobrano i zapisano: {cache_file}")
            return cache_file
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Plik nie istnieje: {url}")
            else:
                logger.error(f"Błąd HTTP przy pobieraniu {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Błąd przy pobieraniu {url}: {e}")
            return None
    
    def _parse_csv(self, file_path: Path) -> pd.DataFrame:
        """
        Parsuje plik CSV z CryptoDataDownload.
        
        Format CSV:
        - Pierwsza linia może zawierać nagłówek z metadanymi
        - Druga linia może być pusta
        - Trzecia linia zawiera nagłówki kolumn
        - Dane zaczynają się od czwartej linii
        
        Kolumny: unix, date, symbol, open, high, low, close, Volume BTC/Volume USDT
        """
        try:
            # Wczytaj plik i znajdź linię z nagłówkami
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Znajdź linię z nagłówkami (zazwyczaj zawiera "date" lub "unix")
            header_line = 0
            for i, line in enumerate(lines):
                if 'date' in line.lower() or 'unix' in line.lower():
                    header_line = i
                    break
            
            # Wczytaj DataFrame, pomijając pierwsze linie
            df = pd.read_csv(
                file_path,
                skiprows=header_line,
                header=0,
                parse_dates=['date'],
                index_col='date'
            )
            
            # Standaryzuj nazwy kolumn
            column_mapping = {
                'unix': 'timestamp',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
            }
            
            # Znajdź kolumnę z wolumenem
            volume_cols = [col for col in df.columns if 'volume' in col.lower()]
            if volume_cols:
                column_mapping[volume_cols[0]] = 'volume'
            
            # Zmień nazwy kolumn
            df = df.rename(columns=column_mapping)
            
            # Zostaw tylko potrzebne kolumny
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            available_cols = [col for col in required_cols if col in df.columns]
            df = df[available_cols]
            
            # Upewnij się, że wszystkie kolumny są numeryczne
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Usuń wiersze z NaN
            df = df.dropna()
            
            # Sortuj po dacie
            df = df.sort_index()
            
            logger.success(f"Wczytano {len(df)} świec z {file_path}")
            return df
            
        except Exception as e:
            logger.error(f"Błąd parsowania pliku {file_path}: {e}")
            return pd.DataFrame()
    
    def fetch_historical(
        self,
        symbol: str = "BTC-USD",
        timeframe: str = "1h",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Pobiera dane historyczne z CryptoDataDownload.
        
        Args:
            symbol: Symbol pary (np. BTC-USD)
            timeframe: Timeframe (1m, 5m, 1h, 1d)
            start_date: Data początkowa (opcjonalnie, do filtrowania)
            end_date: Data końcowa (opcjonalnie, do filtrowania)
            
        Returns:
            DataFrame z danymi OHLCV
        """
        if timeframe not in self.TIMEFRAME_MAP:
            logger.warning(f"Timeframe {timeframe} nie jest obsługiwany. Używam domyślnego.")
            timeframe = '1h'
        
        # Pobierz URL
        url = self._get_url(symbol, timeframe)
        
        # Przygotuj ścieżkę cache
        symbol_cdd = self._get_symbol_for_exchange(symbol)
        timeframe_cdd = self.TIMEFRAME_MAP.get(timeframe, timeframe)
        cache_file = self.cache_dir / f"{self.exchange}_{symbol_cdd}_{timeframe_cdd}.csv"
        
        # Pobierz plik
        file_path = self._download_file(url, cache_file)
        if file_path is None:
            return pd.DataFrame()
        
        # Parsuj CSV
        df = self._parse_csv(file_path)
        
        if df.empty:
            return df
        
        # Filtruj po datach jeśli podano
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        logger.info(f"Zwracam {len(df)} świec dla {symbol} ({timeframe})")
        return df
    
    def get_available_exchanges(self) -> List[str]:
        """Zwraca listę dostępnych giełd."""
        return [
            "Binance",
            "Coinbase",
            "Kraken",
            "Bitstamp",
            "Gemini",
            "Bitfinex",
            "CEX.io",
            "Poloniex",
            "Bittrex",
            "DeriBit",
            "HitBTC",
            "Kucoin",
            "FTX",
            "OKCoin",
            "Okex",
        ]

