"""
Binance Data Collector
======================
Moduł do pobierania danych historycznych i real-time z giełdy Binance.
Wykorzystuje bibliotekę ccxt dla ujednoliconego dostępu do API.
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import time
from loguru import logger


class BinanceCollector:
    """
    Kolektor danych z giełdy Binance.
    
    Obsługuje:
    - Pobieranie danych OHLCV (Open, High, Low, Close, Volume)
    - Wiele timeframe'ów
    - Zapis do CSV/Parquet
    - Rate limiting
    """
    
    # Mapowanie timeframe'ów na milisekundy
    TIMEFRAME_MS = {
        '1m': 60 * 1000,
        '5m': 5 * 60 * 1000,
        '15m': 15 * 60 * 1000,
        '1h': 60 * 60 * 1000,
        '4h': 4 * 60 * 60 * 1000,
        '1d': 24 * 60 * 60 * 1000,
        '1w': 7 * 24 * 60 * 60 * 1000,
    }
    
    def __init__(self, sandbox: bool = False):
        """
        Inicjalizacja kolektora.
        
        Args:
            sandbox: Czy używać testnet (zalecane na początek)
        """
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        })
        
        if sandbox:
            self.exchange.set_sandbox_mode(True)
            logger.info("Binance Collector uruchomiony w trybie SANDBOX")
        else:
            logger.info("Binance Collector uruchomiony w trybie PRODUKCYJNYM")
    
    def fetch_ohlcv(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        since: Optional[datetime] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Pobiera dane OHLCV dla danego symbolu.
        
        Args:
            symbol: Para handlowa (np. "BTC/USDT")
            timeframe: Interwał czasowy (1m, 5m, 15m, 1h, 4h, 1d, 1w)
            since: Data początkowa (domyślnie 7 dni wstecz)
            limit: Maksymalna liczba świec do pobrania (max 1000)
            
        Returns:
            DataFrame z kolumnami: timestamp, open, high, low, close, volume
        """
        if since is None:
            since = datetime.now() - timedelta(days=7)
        
        since_ms = int(since.timestamp() * 1000)
        
        logger.info(f"Pobieram {symbol} {timeframe} od {since}")
        
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since_ms,
                limit=limit
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Konwersja timestamp na datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            logger.success(f"Pobrano {len(df)} świec dla {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Błąd pobierania danych: {e}")
            raise
    
    def fetch_historical(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        start_date: datetime = None,
        end_date: datetime = None
    ) -> pd.DataFrame:
        """
        Pobiera pełne dane historyczne (z paginacją).
        
        Binance zwraca max 1000 świec na request, więc dla dłuższych
        okresów potrzebna jest paginacja.
        
        Args:
            symbol: Para handlowa
            timeframe: Interwał czasowy
            start_date: Data początkowa
            end_date: Data końcowa (domyślnie teraz)
            
        Returns:
            DataFrame z pełnymi danymi historycznymi
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now()
        
        logger.info(f"Pobieram historię {symbol} {timeframe}: {start_date} -> {end_date}")
        
        all_data = []
        current_since = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000)
        
        while current_since < end_ms:
            try:
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=current_since,
                    limit=1000
                )
                
                if not ohlcv:
                    break
                
                all_data.extend(ohlcv)
                
                # Przesuwamy since na ostatni timestamp + 1 interwał
                current_since = ohlcv[-1][0] + self.TIMEFRAME_MS.get(timeframe, 60000)
                
                logger.debug(f"Pobrano {len(ohlcv)} świec, łącznie: {len(all_data)}")
                
                # Rate limiting - czekaj między requestami
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Błąd podczas paginacji: {e}")
                break
        
        if not all_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(
            all_data,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df = df[~df.index.duplicated(keep='first')]  # Usuń duplikaty
        df = df[df.index <= pd.Timestamp(end_date)]  # Ogranicz do end_date
        
        logger.success(f"Pobrano łącznie {len(df)} świec dla {symbol}")
        return df
    
    def save_to_csv(self, df: pd.DataFrame, filename: str) -> Path:
        """Zapisuje DataFrame do pliku CSV."""
        path = Path(f"data/raw/{filename}")
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path)
        logger.info(f"Zapisano dane do {path}")
        return path
    
    def save_to_parquet(self, df: pd.DataFrame, filename: str) -> Path:
        """Zapisuje DataFrame do pliku Parquet (bardziej wydajny format)."""
        path = Path(f"data/raw/{filename}")
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path)
        logger.info(f"Zapisano dane do {path}")
        return path
    
    def get_available_symbols(self) -> List[str]:
        """Zwraca listę dostępnych par handlowych."""
        self.exchange.load_markets()
        return list(self.exchange.symbols)
    
    def get_ticker(self, symbol: str = "BTC/USDT") -> dict:
        """Pobiera aktualny ticker (cenę) dla symbolu."""
        return self.exchange.fetch_ticker(symbol)


# === Przykład użycia ===
if __name__ == "__main__":
    from loguru import logger
    import sys
    
    # Konfiguracja loggera
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    # Inicjalizacja kolektora
    collector = BinanceCollector(sandbox=False)
    
    # Pobierz ostatnie dane BTC
    print("\n=== Pobieranie danych BTC/USDT ===")
    df = collector.fetch_ohlcv(
        symbol="BTC/USDT",
        timeframe="1h",
        limit=100
    )
    
    print(f"\nOstatnich 5 świec:")
    print(df.tail())
    
    print(f"\nStatystyki:")
    print(df.describe())
    
    # Zapisz do pliku
    collector.save_to_csv(df, "btc_usdt_1h.csv")
    
    # Pobierz aktualną cenę
    ticker = collector.get_ticker("BTC/USDT")
    print(f"\n💰 Aktualna cena BTC: ${ticker['last']:,.2f}")

