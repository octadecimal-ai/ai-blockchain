"""
dYdX Data Collector
====================
Moduł do pobierania danych z zdecentralizowanej giełdy dYdX v4.
Obsługuje kontrakty perpetual oraz dane rynkowe.

dYdX v4 działa na własnym blockchainie (Cosmos SDK) i oferuje:
- Handel perpetual z dźwignią do 20x
- Niskie opłaty transakcyjne
- Pełną decentralizację (non-custodial)

Dokumentacja API: https://docs.dydx.exchange/
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import time
import requests
from loguru import logger

# dYdX v4 API endpoints
# Base URL dla publicznych endpointów (candles, markets, orderbook, etc.)
DYDX_INDEXER_API = "https://indexer.dydx.trade/v4"
DYDX_TESTNET_API = "https://indexer.v4testnet.dydx.exchange/v4"


class DydxCollector:
    """
    Kolektor danych z giełdy dYdX v4.
    
    dYdX v4 to zdecentralizowana giełda działająca na własnym blockchainie
    w ekosystemie Cosmos. Specjalizuje się w kontraktach perpetual.
    
    Obsługuje:
    - Pobieranie danych cenowych (candles/OHLCV)
    - Orderbook w czasie rzeczywistym
    - Dane historyczne transakcji
    - Informacje o rynkach
    """
    
    # Dostępne interwały czasowe
    RESOLUTIONS = {
        '1m': '1MIN',
        '5m': '5MINS',
        '15m': '15MINS',
        '30m': '30MINS',
        '1h': '1HOUR',
        '4h': '4HOURS',
        '1d': '1DAY',
    }
    
    def __init__(self, testnet: bool = False):
        """
        Inicjalizacja kolektora dYdX.
        
        Args:
            testnet: Czy używać testnet (zalecane na początek)
        """
        self.base_url = DYDX_TESTNET_API if testnet else DYDX_INDEXER_API
        self.testnet = testnet
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        mode = "TESTNET" if testnet else "MAINNET"
        logger.info(f"dYdX Collector uruchomiony w trybie {mode}")
        logger.info(f"Base URL: {self.base_url}")
    
    def _make_request(
        self, 
        endpoint: str, 
        params: dict = None, 
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> dict:
        """
        Wykonuje request do API dYdX z retry logic.
        
        Args:
            endpoint: Endpoint API
            params: Parametry zapytania
            max_retries: Maksymalna liczba prób
            retry_delay: Opóźnienie między próbami (w sekundach)
            
        Returns:
            Odpowiedź JSON
        """
        url = f"{self.base_url}{endpoint}"
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Błąd API dYdX (próba {attempt + 1}/{max_retries}): {e}. Ponawiam za {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Błąd API dYdX po {max_retries} próbach: {e}")
        
        raise last_exception
    
    def get_markets(self) -> pd.DataFrame:
        """
        Pobiera listę wszystkich dostępnych rynków na dYdX.
        
        Returns:
            DataFrame z informacjami o rynkach
        """
        data = self._make_request("/perpetualMarkets")
        
        markets = []
        for ticker, info in data.get('markets', {}).items():
            markets.append({
                'ticker': ticker,
                'status': info.get('status'),
                'base_asset': info.get('baseAsset'),
                'quote_asset': info.get('quoteAsset', 'USD'),
                'initial_margin': float(info.get('initialMarginFraction', 0)),
                'maintenance_margin': float(info.get('maintenanceMarginFraction', 0)),
                'tick_size': float(info.get('tickSize', 0)),
                'step_size': float(info.get('stepSize', 0)),
                'oracle_price': float(info.get('oraclePrice', 0)),
            })
        
        df = pd.DataFrame(markets)
        logger.success(f"Pobrano {len(df)} rynków z dYdX")
        return df
    
    def get_orderbook(self, ticker: str = "BTC-USD") -> dict:
        """
        Pobiera aktualny orderbook dla danego rynku.
        
        Args:
            ticker: Symbol rynku (np. "BTC-USD", "ETH-USD")
            
        Returns:
            Słownik z bids i asks
        """
        data = self._make_request(f"/orderbooks/perpetualMarket/{ticker}")
        
        orderbook = {
            'ticker': ticker,
            'bids': [(float(b['price']), float(b['size'])) for b in data.get('bids', [])],
            'asks': [(float(a['price']), float(a['size'])) for a in data.get('asks', [])],
            'timestamp': datetime.now()
        }
        
        logger.debug(f"Orderbook {ticker}: {len(orderbook['bids'])} bids, {len(orderbook['asks'])} asks")
        return orderbook
    
    def get_ticker(self, ticker: str = "BTC-USD") -> dict:
        """
        Pobiera aktualny ticker (cenę) dla rynku.
        
        Args:
            ticker: Symbol rynku
            
        Returns:
            Słownik z danymi tickera
        """
        data = self._make_request(f"/perpetualMarkets")
        market = data.get('markets', {}).get(ticker, {})
        
        return {
            'ticker': ticker,
            'oracle_price': float(market.get('oraclePrice', 0)),
            'price_change_24h': float(market.get('priceChange24H', 0)),
            'volume_24h': float(market.get('volume24H', 0)),
            'trades_24h': int(market.get('trades24H', 0)),
            'open_interest': float(market.get('openInterest', 0)),
            'next_funding_rate': float(market.get('nextFundingRate', 0)),
        }
    
    def fetch_candles(
        self,
        ticker: str = "BTC-USD",
        resolution: str = "1h",
        limit: int = 100,
        from_iso: Optional[str] = None,
        to_iso: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Pobiera dane świecowe (OHLCV) dla danego rynku.
        
        Args:
            ticker: Symbol rynku (np. "BTC-USD")
            resolution: Interwał czasowy (1m, 5m, 15m, 30m, 1h, 4h, 1d)
            limit: Maksymalna liczba świec (max 100 per request)
            from_iso: Data początkowa w formacie ISO
            to_iso: Data końcowa w formacie ISO
            
        Returns:
            DataFrame z kolumnami: timestamp, open, high, low, close, volume
        """
        dydx_resolution = self.RESOLUTIONS.get(resolution, '1HOUR')
        
        params = {
            'resolution': dydx_resolution,
            'limit': min(limit, 100)
        }
        
        if from_iso:
            params['fromISO'] = from_iso
        if to_iso:
            params['toISO'] = to_iso
        
        logger.info(f"Pobieram {ticker} {resolution} z dYdX (limit={limit})")
        
        data = self._make_request(f"/candles/perpetualMarkets/{ticker}", params)
        
        candles = []
        for candle in data.get('candles', []):
            candles.append({
                'timestamp': pd.to_datetime(candle['startedAt']),
                'open': float(candle['open']),
                'high': float(candle['high']),
                'low': float(candle['low']),
                'close': float(candle['close']),
                'volume': float(candle['baseTokenVolume']),
                'usd_volume': float(candle['usdVolume']),
                'trades': int(candle['trades']),
            })
        
        df = pd.DataFrame(candles)
        if not df.empty:
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
        
        logger.success(f"Pobrano {len(df)} świec dla {ticker}")
        return df
    
    def fetch_historical_candles(
        self,
        ticker: str = "BTC-USD",
        resolution: str = "1h",
        start_date: datetime = None,
        end_date: datetime = None
    ) -> pd.DataFrame:
        """
        Pobiera pełne dane historyczne z paginacją.
        
        Args:
            ticker: Symbol rynku
            resolution: Interwał czasowy
            start_date: Data początkowa
            end_date: Data końcowa
            
        Returns:
            DataFrame z pełnymi danymi historycznymi
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()
        
        # Upewnij się, że daty są timezone-aware lub naive (spójne)
        if start_date.tzinfo is None and end_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=end_date.tzinfo)
        elif start_date.tzinfo is not None and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=start_date.tzinfo)
        
        logger.info(f"Pobieram historię {ticker}: {start_date} -> {end_date}")
        
        all_candles = []
        # Konwertuj na pd.Timestamp i upewnij się, że są naive (bez timezone)
        # dYdX API zwraca daty w UTC, ale bez timezone info w index
        current_end = pd.Timestamp(end_date)
        start_ts = pd.Timestamp(start_date)
        
        # Upewnij się, że oba są naive (bez timezone) dla porównań
        if current_end.tz is not None:
            current_end = current_end.tz_localize(None)
        if start_ts.tz is not None:
            start_ts = start_ts.tz_localize(None)
        
        while current_end > start_ts:
            # Konwertuj current_end na datetime dla API
            if isinstance(current_end, pd.Timestamp):
                current_end_dt = current_end.to_pydatetime()
            else:
                current_end_dt = current_end
            
            df = self.fetch_candles(
                ticker=ticker,
                resolution=resolution,
                limit=100,
                to_iso=current_end_dt.isoformat() + 'Z'
            )
            
            if df.empty:
                break
            
            all_candles.append(df)
            
            # Przesuń end na najstarszy timestamp
            oldest = df.index.min()
            
            # Upewnij się, że oldest jest naive (bez timezone) dla porównań
            if isinstance(oldest, pd.Timestamp):
                if oldest.tz is not None:
                    oldest = oldest.tz_localize(None)
            
            if oldest >= current_end:
                break
            current_end = oldest
            
            # Rate limiting
            time.sleep(0.2)
        
        if not all_candles:
            return pd.DataFrame()
        
        result = pd.concat(all_candles)
        result = result[~result.index.duplicated(keep='first')]
        
        # Filtruj daty - upewnij się, że timezone jest spójne
        start_ts = pd.Timestamp(start_date)
        if result.index.tz is not None:
            # Jeśli index ma timezone, upewnij się, że start_ts też ma
            if start_ts.tz is None:
                start_ts = start_ts.tz_localize(result.index.tz)
        elif start_ts.tz is not None:
            # Jeśli start_ts ma timezone, ale index nie - usuń timezone z start_ts
            start_ts = start_ts.tz_localize(None)
        
        result = result[result.index >= start_ts]
        result.sort_index(inplace=True)
        
        logger.success(f"Pobrano łącznie {len(result)} świec dla {ticker}")
        return result
    
    def get_funding_rates(self, ticker: str = "BTC-USD", limit: int = 100) -> pd.DataFrame:
        """
        Pobiera historię funding rates.
        
        Funding rate to opłata wymieniana między long i short co 8 godzin.
        Pozwala na arbitraż i ocenę sentymentu rynku.
        
        Args:
            ticker: Symbol rynku
            limit: Liczba rekordów
            
        Returns:
            DataFrame z funding rates
        """
        params = {'limit': min(limit, 100)}
        data = self._make_request(f"/historicalFunding/{ticker}", params)
        
        rates = []
        for item in data.get('historicalFunding', []):
            rates.append({
                'timestamp': pd.to_datetime(item['effectiveAt']),
                'funding_rate': float(item['rate']),
                'price': float(item['price']),
            })
        
        df = pd.DataFrame(rates)
        if not df.empty:
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
        
        return df
    
    def get_trades(self, ticker: str = "BTC-USD", limit: int = 100) -> pd.DataFrame:
        """
        Pobiera ostatnie transakcje.
        
        Args:
            ticker: Symbol rynku
            limit: Liczba transakcji
            
        Returns:
            DataFrame z transakcjami
        """
        params = {'limit': min(limit, 100)}
        data = self._make_request(f"/trades/perpetualMarket/{ticker}", params)
        
        trades = []
        for trade in data.get('trades', []):
            trades.append({
                'timestamp': pd.to_datetime(trade['createdAt']),
                'side': trade['side'],
                'price': float(trade['price']),
                'size': float(trade['size']),
            })
        
        df = pd.DataFrame(trades)
        if not df.empty:
            df.set_index('timestamp', inplace=True)
        
        return df
    
    def compare_with_cex(
        self,
        ticker: str = "BTC-USD",
        cex_price: float = None
    ) -> dict:
        """
        Porównuje cenę dYdX z ceną na CEX (np. Binance).
        Przydatne do wykrywania okazji arbitrażowych.
        
        Args:
            ticker: Symbol rynku
            cex_price: Cena na scentralizowanej giełdzie
            
        Returns:
            Słownik z informacjami o spreadzie
        """
        dydx_ticker = self.get_ticker(ticker)
        dydx_price = dydx_ticker['oracle_price']
        
        if cex_price is None:
            return {
                'dydx_price': dydx_price,
                'spread_info': 'Podaj cenę CEX do porównania'
            }
        
        spread = ((dydx_price - cex_price) / cex_price) * 100
        
        return {
            'ticker': ticker,
            'dydx_price': dydx_price,
            'cex_price': cex_price,
            'spread_percent': spread,
            'spread_usd': dydx_price - cex_price,
            'funding_rate': dydx_ticker['next_funding_rate'],
            'opportunity': 'ARBITRAGE' if abs(spread) > 0.1 else 'NO_OPPORTUNITY'
        }


# === Przykład użycia ===
if __name__ == "__main__":
    from loguru import logger
    import sys
    
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    # Użyj mainnet (testnet może mieć ograniczone dane)
    collector = DydxCollector(testnet=False)
    
    print("\n" + "="*60)
    print("📊 dYdX - PRZEGLĄD RYNKÓW")
    print("="*60)
    
    # Lista rynków
    markets = collector.get_markets()
    print(f"\nDostępne rynki ({len(markets)}):")
    print(markets[['ticker', 'oracle_price', 'status']].head(10))
    
    # Ticker BTC
    print("\n" + "-"*40)
    btc_ticker = collector.get_ticker("BTC-USD")
    print(f"💰 BTC-USD:")
    print(f"   Cena: ${btc_ticker['oracle_price']:,.2f}")
    print(f"   Zmiana 24h: {btc_ticker['price_change_24h']:.2f}%")
    print(f"   Wolumen 24h: ${btc_ticker['volume_24h']:,.0f}")
    print(f"   Funding Rate: {btc_ticker['next_funding_rate']*100:.4f}%")
    
    # Świece
    print("\n" + "-"*40)
    candles = collector.fetch_candles("BTC-USD", "1h", limit=10)
    print("Ostatnie świece BTC-USD (1h):")
    print(candles.tail())
    
    # Funding rates
    print("\n" + "-"*40)
    funding = collector.get_funding_rates("BTC-USD", limit=5)
    print("Funding Rates (ostatnie 5):")
    print(funding)

