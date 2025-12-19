#!/usr/bin/env python3
"""
Generate Historical Tickers from OHLCV Data
===========================================
Generuje historyczne dane tickerów z danych OHLCV, funding rates i open interest.

Tabela tickers wymaga:
- price (z OHLCV.close)
- bid, ask, spread (z orderbook lub symulacja)
- volume_24h, change_24h, high_24h, low_24h (z OHLCV)
- funding_rate (z funding_rates)
- open_interest (z tickers lub symulacja)

Użycie:
    python scripts/generate_historical_tickers.py --symbol=BTC/USDC --start-date=2020-01-01
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
import argparse
import pandas as pd
from loguru import logger

# Dodaj ścieżkę projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.manager import DatabaseManager


def calculate_24h_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Oblicza metryki 24h z danych OHLCV.
    
    Args:
        df: DataFrame z OHLCV (index: timestamp, kolumny: open, high, low, close, volume)
        
    Returns:
        DataFrame z kolumnami: high_24h, low_24h, volume_24h, change_24h
    """
    result = pd.DataFrame(index=df.index)
    
    # Użyj pandas rolling window dla lepszej wydajności
    # Okno 24h - musimy dostosować do timeframe
    # Dla 1h: 24 okna, dla 1m: 1440 okien
    timeframe_hours = {
        '1m': 1/60,
        '5m': 5/60,
        '15m': 15/60,
        '30m': 30/60,
        '1h': 1,
        '4h': 4,
        '1d': 24
    }
    
    # Szacuj timeframe na podstawie różnicy między timestampami
    if len(df) > 1:
        time_diff = (df.index[1] - df.index[0]).total_seconds() / 3600
        # Okno 24h w jednostkach timeframe
        window_size = int(24 / time_diff) if time_diff > 0 else 24
    else:
        window_size = 24
    
    # Użyj rolling window
    result['high_24h'] = df['high'].rolling(window=window_size, min_periods=1).max()
    result['low_24h'] = df['low'].rolling(window=window_size, min_periods=1).min()
    result['volume_24h'] = df['volume'].rolling(window=window_size, min_periods=1).sum()
    
    # Change 24h = (close_now - close_24h_ago) / close_24h_ago * 100
    close_24h_ago = df['close'].shift(window_size)
    result['change_24h'] = ((df['close'] - close_24h_ago) / close_24h_ago * 100).fillna(0.0)
    
    return result


# Funkcja estimate_bid_ask_spread została usunięta
# Zgodnie z zasadą projektu: NIE używamy szacowanych danych
# Bid/Ask/Spread muszą pochodzić z rzeczywistego orderbook API


def generate_tickers_from_ohlcv(
    exchange: str,
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    exchange_name: str = "binance"
):
    """
    Generuje tickery z danych OHLCV, funding rates i open interest.
    
    Args:
        exchange: Nazwa giełdy w bazie
        symbol: Symbol pary (np. "BTC/USDC")
        timeframe: Timeframe OHLCV (np. "1h")
        start_date: Data początkowa
        end_date: Data końcowa
        exchange_name: Nazwa giełdy dla tickerów
    """
    # Załaduj .env
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    database_url = os.getenv('DATABASE_URL')
    use_timescale = os.getenv('USE_TIMESCALE', 'false').lower() == 'true'
    
    db = DatabaseManager(database_url=database_url, use_timescale=use_timescale)
    
    logger.info(f"Generuję tickery dla {exchange_name}:{symbol} od {start_date.date()} do {end_date.date()}")
    
    # 1. Pobierz dane OHLCV
    logger.info("📊 Pobieram dane OHLCV...")
    ohlcv_df = db.get_ohlcv(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date
    )
    
    if ohlcv_df.empty:
        logger.warning(f"Brak danych OHLCV dla {exchange}:{symbol} {timeframe}")
        # Spróbuj użyć 1m i zagregować do żądanego timeframe
        if timeframe != "1m":
            logger.info(f"Próbuję użyć 1m i zagregować do {timeframe}...")
            ohlcv_1m = db.get_ohlcv(
                exchange=exchange,
                symbol=symbol,
                timeframe="1m",
                start_date=start_date,
                end_date=end_date
            )
            
            if not ohlcv_1m.empty:
                # Agreguj do żądanego timeframe
                timeframe_map = {
                    '1h': '1H',
                    '4h': '4H',
                    '1d': '1D'
                }
                resample_rule = timeframe_map.get(timeframe, '1H')
                ohlcv_df = ohlcv_1m.resample(resample_rule).agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()
                logger.info(f"Zagregowano {len(ohlcv_1m)} świec 1m do {len(ohlcv_df)} świec {timeframe}")
            else:
                logger.error(f"Brak danych OHLCV nawet dla 1m")
                return
        else:
            logger.error(f"Brak danych OHLCV dla {exchange}:{symbol} {timeframe}")
            return
    
    logger.info(f"Pobrano {len(ohlcv_df)} rekordów OHLCV")
    
    # 2. Oblicz metryki 24h
    logger.info("📊 Obliczam metryki 24h...")
    metrics_24h = calculate_24h_metrics(ohlcv_df)
    
    # 3. Pobierz funding rates z tickers (jeśli już istnieją)
    logger.info("📊 Pobieram funding rates z tickers...")
    funding_df = db.get_funding_rates(
        exchange=exchange_name,
        symbol=symbol,  # Używamy tego samego symbolu co tickers
        start_date=start_date,
        end_date=end_date
    )
    
    # 4. Pobierz open interest
    logger.info("📊 Pobieram open interest...")
    oi_df = db.get_open_interest(
        exchange=exchange_name,
        symbol="BTC/USDT:USDT",  # Open interest jest dla perpetual
        start_date=start_date,
        end_date=end_date
    )
    
    # 5. Zbuduj DataFrame z tickerami
    logger.info("📊 Generuję tickery...")
    tickers = []
    
    for timestamp, row in ohlcv_df.iterrows():
        ticker = {
            'timestamp': timestamp,
            'exchange': exchange_name,
            'symbol': symbol,
            'price': row['close'],
        }
        
        # Metryki 24h
        if timestamp in metrics_24h.index:
            ticker['high_24h'] = metrics_24h.loc[timestamp, 'high_24h']
            ticker['low_24h'] = metrics_24h.loc[timestamp, 'low_24h']
            ticker['volume_24h'] = metrics_24h.loc[timestamp, 'volume_24h']
            ticker['change_24h'] = metrics_24h.loc[timestamp, 'change_24h']
        else:
            ticker['high_24h'] = row['high']
            ticker['low_24h'] = row['low']
            ticker['volume_24h'] = row['volume']
            ticker['change_24h'] = 0.0
        
        # Bid/Ask/Spread - tylko rzeczywiste dane z orderbook
        # Zgodnie z zasadą projektu: NIE używamy szacowanych danych
        # Jeśli nie mamy rzeczywistych danych z orderbook, pozostawiamy NULL
        ticker['bid'] = None
        ticker['ask'] = None
        ticker['spread'] = None
        
        # Funding rate (jeśli dostępny)
        if not funding_df.empty:
            # Znajdź najbliższy funding rate
            funding_match = funding_df.index[funding_df.index <= timestamp]
            if len(funding_match) > 0:
                fr_value = funding_df.loc[funding_match[-1], 'funding_rate']
                # Konwertuj NaN na None (zgodnie z zasadą projektu)
                ticker['funding_rate'] = fr_value if pd.notna(fr_value) else None
            else:
                ticker['funding_rate'] = None
        else:
            ticker['funding_rate'] = None
        
        # Open interest (jeśli dostępny)
        # Zgodnie z zasadą: używamy tylko rzeczywistych danych
        # Open interest jest dostępny tylko dla ostatnich ~2 dni, więc dla starszych danych zostawiamy None
        if not oi_df.empty:
            # Znajdź najbliższy open interest (tylko jeśli jest w zakresie dostępnych danych)
            oi_match = oi_df.index[oi_df.index <= timestamp]
            if len(oi_match) > 0:
                oi_value = oi_df.loc[oi_match[-1], 'open_interest']
                # Konwertuj NaN na None (zgodnie z zasadą projektu)
                if pd.notna(oi_value) and oi_value > 0:
                    ticker['open_interest'] = float(oi_value)
                else:
                    ticker['open_interest'] = None
            else:
                ticker['open_interest'] = None
        else:
            ticker['open_interest'] = None
        
        tickers.append(ticker)
    
    tickers_df = pd.DataFrame(tickers)
    tickers_df.set_index('timestamp', inplace=True)
    
    # Konwertuj wszystkie NaN na None (zgodnie z zasadą projektu)
    tickers_df = tickers_df.where(pd.notna(tickers_df), None)
    
    logger.info(f"Wygenerowano {len(tickers_df)} tickerów")
    
    # 6. Zapisz do bazy
    logger.info("💾 Zapisuję tickery do bazy...")
    saved = db.save_tickers(
        df=tickers_df,
        exchange=exchange_name,
        symbol=symbol
    )
    
    logger.success(f"✅ Zapisano {saved} tickerów do bazy")
    
    # Podsumowanie
    logger.info("\n📈 Podsumowanie:")
    logger.info(f"   Wygenerowano: {len(tickers_df)} tickerów")
    logger.info(f"   Zakres dat: {tickers_df.index.min()} → {tickers_df.index.max()}")
    logger.info(f"   Kolumny: {', '.join(tickers_df.columns.tolist())}")


def main():
    parser = argparse.ArgumentParser(
        description="Generuje historyczne tickery z danych OHLCV"
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default="BTC/USDC",
        help='Symbol pary (domyślnie: BTC/USDC)'
    )
    parser.add_argument(
        '--timeframe',
        type=str,
        default="1h",
        help='Timeframe OHLCV (domyślnie: 1h)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default="2020-01-01",
        help='Data początkowa (format: YYYY-MM-DD, domyślnie: 2020-01-01)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        help='Data końcowa (format: YYYY-MM-DD, domyślnie: teraz)'
    )
    parser.add_argument(
        '--exchange',
        type=str,
        default="binance",
        help='Nazwa giełdy (domyślnie: binance)'
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
    
    # Parsuj daty
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    else:
        end_date = datetime.now(timezone.utc)
    
    try:
        generate_tickers_from_ohlcv(
            exchange=args.exchange,
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_date=start_date,
            end_date=end_date,
            exchange_name=args.exchange
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

