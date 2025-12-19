"""
Binance Data Collector
======================
Moduł do pobierania danych historycznych i real-time z giełdy Binance.
Wykorzystuje bibliotekę ccxt dla ujednoliconego dostępu do API.
"""

import os
import ccxt
import pandas as pd
from datetime import datetime, timedelta, timezone
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
    
    def __init__(
        self, 
        sandbox: bool = False,
        api_key: Optional[str] = None,
        secret: Optional[str] = None
    ):
        """
        Inicjalizacja kolektora.
        
        Args:
            sandbox: Czy używać testnet (zalecane na początek)
            api_key: Klucz API Binance (opcjonalnie, lub z BINANCE_API_KEY)
            secret: Secret API Binance (opcjonalnie, lub z BINANCE_SECRET)
            
        Note:
            API keys nie są wymagane do pobierania danych publicznych (OHLCV, ticker).
            Są potrzebne do operacji prywatnych (trading, balanse).
        """
        # Pobierz klucze z parametrów lub zmiennych środowiskowych
        api_key = api_key or os.getenv('BINANCE_API_KEY')
        secret = secret or os.getenv('BINANCE_SECRET')
        
        config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',  # Domyślnie spot dla OHLCV
            }
        }
        
        # Dodaj API keys tylko jeśli są poprawne (niepuste i nie są placeholderami)
        # Dla publicznych danych (OHLCV) API keys nie są wymagane
        if api_key and secret and api_key.strip() and secret.strip():
            # Sprawdź czy to nie są placeholder wartości
            if api_key.lower() not in ['your_api_key', 'your_key', ''] and secret.lower() not in ['your_secret', 'your_secret_key', '']:
                config['apiKey'] = api_key
                config['secret'] = secret
                logger.info("Binance Collector: API keys skonfigurowane")
            else:
                logger.info("Binance Collector: tryb publiczny (nieprawidłowe API keys w .env)")
        else:
            logger.info("Binance Collector: tryb publiczny (bez API keys)")
        
        self.exchange = ccxt.binance(config)
        
        # Osobny exchange dla futures (funding rates, open interest)
        futures_config = config.copy()
        futures_config['options'] = {'defaultType': 'future'}
        self.futures_exchange = ccxt.binance(futures_config)
        
        if sandbox:
            self.exchange.set_sandbox_mode(True)
            self.futures_exchange.set_sandbox_mode(True)
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
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        df = df[~df.index.duplicated(keep='first')]  # Usuń duplikaty
        # Ogranicz do end_date (upewnij się że oba są tz-aware)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        end_date_ts = pd.Timestamp(end_date)
        if end_date_ts.tz is None:
            end_date_ts = end_date_ts.tz_localize('UTC')
        df = df[df.index <= end_date_ts]  # Ogranicz do end_date
        
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
    
    def get_funding_rates(
        self,
        symbol: str = "BTC/USDT:USDT",  # Perpetual futures symbol
        since: Optional[datetime] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Pobiera historię funding rates z Binance Futures.
        
        Args:
            symbol: Symbol perpetual futures (np. "BTC/USDT:USDT")
            since: Data początkowa (domyślnie 30 dni wstecz)
            limit: Maksymalna liczba rekordów
            
        Returns:
            DataFrame z kolumnami: timestamp, funding_rate, price
        """
        if since is None:
            since = datetime.now() - timedelta(days=30)
        
        since_ms = int(since.timestamp() * 1000)
        
        logger.info(f"Pobieram funding rates dla {symbol} od {since}")
        
        try:
            # Użyj futures_exchange dla funding rates
            # Binance zwraca maksymalnie 1000 rekordów, więc pobieramy w partiach
            all_rates = []
            max_limit = 1000  # Binance limit
            current_since = since_ms
            max_iterations = 100  # Zabezpieczenie przed nieskończoną pętlą
            
            logger.info(f"Pobieram funding rates w partiach (max {max_limit} rekordów na partię)")
            
            for iteration in range(max_iterations):
                try:
                    # Pobierz partię danych
                    if current_since:
                        batch = self.futures_exchange.fetch_funding_rate_history(
                            symbol=symbol,
                            since=current_since,
                            limit=max_limit
                        )
                    else:
                        batch = self.futures_exchange.fetch_funding_rate_history(
                            symbol=symbol,
                            limit=max_limit
                        )
                except Exception as e:
                    # Jeśli błąd z since, spróbuj bez since (pobierze najnowsze)
                    if 'since' in str(e).lower() or 'illegal' in str(e).lower() or 'invalid' in str(e).lower():
                        if iteration == 0:  # Tylko dla pierwszej iteracji
                            logger.debug(f"Błąd z parametrem since, próbuję bez since")
                            batch = self.futures_exchange.fetch_funding_rate_history(
                                symbol=symbol,
                                limit=max_limit
                            )
                        else:
                            break  # Dla kolejnych iteracji, przerwij jeśli błąd
                    else:
                        raise
                
                if not batch or len(batch) == 0:
                    break
                
                # Dodaj partię do listy
                all_rates.extend(batch)
                
                # Jeśli pobraliśmy mniej niż max_limit, znaczy że to koniec danych
                if len(batch) < max_limit:
                    break
                
                # Binance zwraca dane od NAJSTARSZYCH do NAJNOWSZYCH (indeks 0 = najstarszy, -1 = najnowszy)
                oldest_timestamp = batch[0]['timestamp']  # Pierwszy rekord = najstarszy
                newest_timestamp = batch[-1]['timestamp']  # Ostatni rekord = najnowszy
                
                # Sprawdź czy osiągnęliśmy start_date (jeśli najstarszy rekord jest starszy niż start_date, przerwij)
                if since_ms and oldest_timestamp < since_ms:
                    # Usuń rekordy starsze niż start_date
                    batch = [r for r in batch if r['timestamp'] >= since_ms]
                    if batch:
                        all_rates.extend(batch)
                    break
                
                # Aby pobrać kolejne dane (nowsze), ustaw since na timestamp najnowszego rekordu + 1ms
                current_since = newest_timestamp + 1
                
                # Sprawdź czy nie przekroczyliśmy aktualnej daty
                now_ms = int(datetime.now().timestamp() * 1000)
                if current_since > now_ms:
                    break
                
                # Jeśli mamy limit, sprawdź czy już go osiągnęliśmy
                if limit and len(all_rates) >= limit:
                    all_rates = all_rates[:limit]
                    break
                
                logger.debug(f"Pobrano partię {iteration + 1}: {len(batch)} rekordów (łącznie: {len(all_rates)})")
            
            funding_rates = all_rates
            
            if not funding_rates:
                logger.warning(f"Brak funding rates dla {symbol}")
                return pd.DataFrame()
            
            df = pd.DataFrame(funding_rates)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df.rename(columns={'fundingRate': 'funding_rate'}, inplace=True)
            
            # Dodaj cenę jeśli dostępna
            if 'markPrice' in df.columns:
                df.rename(columns={'markPrice': 'price'}, inplace=True)
            
            # Zostaw tylko potrzebne kolumny
            columns_to_keep = ['funding_rate', 'price']
            df = df[[col for col in columns_to_keep if col in df.columns]]
            
            logger.success(f"Pobrano {len(df)} funding rates dla {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Błąd pobierania funding rates: {e}")
            return pd.DataFrame()
    
    def get_open_interest(
        self,
        symbol: str = "BTC/USDT:USDT",  # Perpetual futures symbol
        since: Optional[datetime] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Pobiera historię open interest z Binance Futures.
        
        Args:
            symbol: Symbol perpetual futures (np. "BTC/USDT:USDT")
            since: Data początkowa (domyślnie 30 dni wstecz)
            limit: Maksymalna liczba rekordów
            
        Returns:
            DataFrame z kolumnami: timestamp, open_interest
        """
        if since is None:
            since = datetime.now() - timedelta(days=30)
        
        since_ms = int(since.timestamp() * 1000)
        
        logger.info(f"Pobieram open interest dla {symbol} od {since}")
        
        try:
            # Użyj futures_exchange dla open interest
            # Binance może mieć ograniczenia, więc pobieramy w partiach
            all_oi = []
            max_limit = 500  # Binance limit dla open interest
            current_since = since_ms
            max_iterations = 100  # Zabezpieczenie przed nieskończoną pętlą
            
            logger.info(f"Pobieram open interest w partiach (max {max_limit} rekordów na partię)")
            
            for iteration in range(max_iterations):
                try:
                    # Pobierz partię danych
                    if current_since:
                        batch = self.futures_exchange.fetch_open_interest_history(
                            symbol=symbol,
                            since=current_since,
                            limit=max_limit
                        )
                    else:
                        batch = self.futures_exchange.fetch_open_interest_history(
                            symbol=symbol,
                            limit=max_limit
                        )
                except Exception as e:
                    # Jeśli błąd z parametrami, spróbuj bez since/limit
                    if 'limit' in str(e).lower() or 'startTime' in str(e).lower() or 'invalid' in str(e).lower() or 'since' in str(e).lower():
                        if iteration == 0:  # Tylko dla pierwszej iteracji
                            logger.debug(f"Błąd z parametrami, próbuję bez since/limit")
                            batch = self.futures_exchange.fetch_open_interest_history(
                                symbol=symbol
                            )
                        else:
                            break  # Dla kolejnych iteracji, przerwij jeśli błąd
                    else:
                        raise
                
                if not batch or len(batch) == 0:
                    break
                
                # Dodaj partię do listy
                all_oi.extend(batch)
                
                # Jeśli pobraliśmy mniej niż max_limit, znaczy że to koniec danych
                if len(batch) < max_limit:
                    break
                
                # Binance zwraca dane od NAJSTARSZYCH do NAJNOWSZYCH (indeks 0 = najstarszy, -1 = najnowszy)
                oldest_timestamp = batch[0]['timestamp']  # Pierwszy rekord = najstarszy
                newest_timestamp = batch[-1]['timestamp']  # Ostatni rekord = najnowszy
                
                # Sprawdź czy osiągnęliśmy start_date (jeśli najstarszy rekord jest starszy niż start_date, przerwij)
                if since_ms and oldest_timestamp < since_ms:
                    # Usuń rekordy starsze niż start_date
                    batch = [r for r in batch if r['timestamp'] >= since_ms]
                    if batch:
                        all_rates.extend(batch)
                    break
                
                # Aby pobrać kolejne dane (nowsze), ustaw since na timestamp najnowszego rekordu + 1ms
                current_since = newest_timestamp + 1
                
                # Sprawdź czy nie przekroczyliśmy aktualnej daty
                now_ms = int(datetime.now().timestamp() * 1000)
                if current_since > now_ms:
                    break
                
                # Jeśli mamy limit, sprawdź czy już go osiągnęliśmy
                if limit and len(all_oi) >= limit:
                    all_oi = all_oi[:limit]
                    break
                
                logger.debug(f"Pobrano partię {iteration + 1}: {len(batch)} rekordów (łącznie: {len(all_oi)})")
            
            oi_data = all_oi
            
            if not oi_data:
                logger.warning(f"Brak open interest dla {symbol}")
                return pd.DataFrame()
            
            df = pd.DataFrame(oi_data)
            if df.empty:
                return pd.DataFrame()
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Sprawdź różne możliwe nazwy kolumny
            if 'openInterestAmount' in df.columns:
                df.rename(columns={'openInterestAmount': 'open_interest'}, inplace=True)
            elif 'openInterest' in df.columns:
                df.rename(columns={'openInterest': 'open_interest'}, inplace=True)
            elif 'open_interest' not in df.columns:
                logger.warning(f"Brak kolumny open_interest w danych dla {symbol}, dostępne kolumny: {df.columns.tolist()}")
                return pd.DataFrame()
            
            # Zostaw tylko open_interest
            if 'open_interest' in df.columns:
                df = df[['open_interest']]
            else:
                logger.warning(f"Brak kolumny open_interest w danych dla {symbol}")
                return pd.DataFrame()
            
            logger.success(f"Pobrano {len(df)} rekordów open interest dla {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Błąd pobierania open interest: {e}")
            return pd.DataFrame()


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

