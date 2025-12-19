#!/usr/bin/env python3
"""
Skrypt do resetu i ponownego załadowania danych BTC z obu giełd
================================================================
1. Czyści wszystkie dane BTC z bazy (Binance i dYdX)
2. Zaczytuje dane z Binance od 2017 roku
3. Zaczytuje dane z dYdX od 2023 roku
4. Wyświetla paski postępu i szczegółowe logi
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

# Dodaj ścieżkę projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from src.database.manager import DatabaseManager
from src.collectors.exchange.binance_collector import BinanceCollector

# Spróbuj zaimportować dYdX collector
try:
    from src.collectors.exchange.dydx_collector import DydxCollector
    DYDX_AVAILABLE = True
except ImportError:
    DYDX_AVAILABLE = False
    logger.warning("DydxCollector niedostępny - używam tylko Binance")


def setup_logging(verbose: bool = False):
    """Konfiguruje logowanie."""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level=level,
        colorize=True
    )


def clear_btc_data(database_url: str, exchange: Optional[str] = None, timeframe: Optional[str] = None) -> int:
    """
    Czyści dane BTC z bazy danych używając TRUNCATE i resetuje sekwencję.
    
    Args:
        database_url: URL bazy danych
        exchange: Opcjonalnie, usuń tylko dane dla konkretnej giełdy (binance/dydx)
        timeframe: Opcjonalnie, usuń tylko dane dla konkretnego timeframe (nie obsługiwane z TRUNCATE)
        
    Returns:
        Liczba usuniętych rekordów (0 dla TRUNCATE, ale zwracamy 1 dla sukcesu)
    """
    logger.info("🔗 Łączę z bazę danych...")
    engine = create_engine(database_url)
    
    # Sprawdź czy to PostgreSQL
    is_postgresql = 'postgresql' in database_url.lower() or 'postgres' in database_url.lower()
    
    try:
        with engine.begin() as conn:
            # Mapowanie symboli dla różnych giełd
            symbols = {
                'binance': 'BTC/USDC',
                'dydx': 'BTC-USD'
            }
            
            # Jeśli podano timeframe, nie możemy użyć TRUNCATE - użyj DELETE
            if timeframe:
                logger.warning("⚠️  TRUNCATE nie obsługuje WHERE - używam DELETE dla timeframe")
                total_deleted = 0
                exchanges_to_clear = [exchange] if exchange else ['binance', 'dydx']
                
                for exch in exchanges_to_clear:
                    symbol = symbols.get(exch)
                    if not symbol:
                        continue
                    
                    logger.info(f"🗑️  Usuwam dane {exch}:{symbol} dla timeframe: {timeframe}")
                    result = conn.execute(text(
                        "DELETE FROM ohlcv WHERE exchange = :exchange AND symbol = :symbol AND timeframe = :timeframe"
                    ), {"exchange": exch, "symbol": symbol, "timeframe": timeframe})
                    
                    deleted_count = result.rowcount
                    total_deleted += deleted_count
                    if deleted_count > 0:
                        logger.success(f"✅ Usunięto {deleted_count:,} rekordów z {exch}")
                
                logger.success(f"✅ Łącznie usunięto {total_deleted:,} rekordów")
                return total_deleted
            
            # Użyj TRUNCATE dla pełnego czyszczenia
            exchanges_to_clear = [exchange] if exchange else ['binance', 'dydx']
            
            for exch in exchanges_to_clear:
                symbol = symbols.get(exch)
                if not symbol:
                    continue
                
                logger.info(f"🗑️  TRUNCATE danych {exch}:{symbol} z bazy...")
                
                # TRUNCATE nie obsługuje WHERE, więc używamy DELETE, ale resetujemy sekwencję
                # Najpierw usuń dane
                conn.execute(text(
                    "DELETE FROM ohlcv WHERE exchange = :exchange AND symbol = :symbol"
                ), {"exchange": exch, "symbol": symbol})
                
                # Zresetuj sekwencję/autoincrement
                if is_postgresql:
                    # PostgreSQL - reset sekwencji
                    conn.execute(text(
                        "SELECT setval(pg_get_serial_sequence('ohlcv', 'id'), 1, false)"
                    ))
                    logger.info(f"✅ Zresetowano sekwencję dla ohlcv.id (zacznie od 1)")
                else:
                    # SQLite - reset autoincrement
                    conn.execute(text("DELETE FROM sqlite_sequence WHERE name = 'ohlcv'"))
                    logger.info(f"✅ Zresetowano autoincrement dla ohlcv (zacznie od 1)")
                
                logger.success(f"✅ Wyczyszczono wszystkie dane {exch}:{symbol}")
            
            logger.success(f"✅ Wyczyszczono wszystkie dane BTC")
            return 1  # TRUNCATE nie zwraca liczby rekordów
            
    except Exception as e:
        logger.error(f"❌ Błąd podczas czyszczenia: {e}")
        raise


def estimate_total_candles(start_date: datetime, end_date: datetime, timeframe: str) -> int:
    """
    Szacuje łączną liczbę świec dla danego okresu.
    
    Args:
        start_date: Data początkowa
        end_date: Data końcowa
        timeframe: Interwał czasowy
        
    Returns:
        Szacowana liczba świec
    """
    timeframe_minutes = {
        '1m': 1,
        '3m': 3,
        '5m': 5,
        '15m': 15,
        '30m': 30,
        '1h': 60,
        '2h': 120,
        '4h': 240,
        '6h': 360,
        '8h': 480,
        '12h': 720,
        '1d': 1440,
        '3d': 4320,
        '1w': 10080,
        '1M': 43200,
    }
    
    minutes_per_candle = timeframe_minutes.get(timeframe, 60)
    total_minutes = (end_date - start_date).total_seconds() / 60
    estimated = int(total_minutes / minutes_per_candle)
    
    # Dodaj 10% marginesu
    return int(estimated * 1.1)


def load_data_with_progress(
    db: DatabaseManager,
    exchange: str,
    symbol: str,
    start_date: datetime,
    end_date: Optional[datetime] = None,
    timeframe: str = "1m"
) -> int:
    """
    Zaczytuje dane z paskiem postępu dla danej giełdy.
    
    Args:
        db: Database manager
        exchange: Nazwa giełdy (binance/dydx)
        symbol: Symbol pary (BTC/USDC dla Binance, BTC-USD dla dYdX)
        start_date: Data początkowa
        end_date: Data końcowa (domyślnie teraz)
        timeframe: Interwał czasowy
        
    Returns:
        Liczba zapisanych świec
    """
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    
    logger.info(f"📥 Rozpoczynam pobieranie danych {exchange}:{symbol} ({timeframe})...")
    logger.info(f"   Okres: {start_date.date()} → {end_date.date()}")
    
    # Szacuj łączną liczbę świec
    estimated_total = estimate_total_candles(start_date, end_date, timeframe)
    logger.info(f"   Szacowana liczba świec: ~{estimated_total:,}")
    
    # Inicjalizuj odpowiedni kolektor
    if exchange == "binance":
        collector = BinanceCollector(sandbox=False)
        fetch_method = collector.fetch_historical
        fetch_kwargs = {"symbol": symbol, "timeframe": timeframe}
    elif exchange == "dydx":
        if not DYDX_AVAILABLE:
            logger.error("❌ DydxCollector niedostępny")
            return 0
        collector = DydxCollector(testnet=False)
        fetch_method = collector.fetch_historical_candles
        fetch_kwargs = {"ticker": symbol, "resolution": timeframe}
    else:
        logger.error(f"❌ Nieznana giełda: {exchange}")
        return 0
    
    total_saved = 0
    current_date = start_date
    batch_size_days = 30  # Pobieraj po 30 dni
    
    # Utwórz pasek postępu
    with tqdm(
        total=estimated_total,
        desc=f"📊 {exchange.upper()}",
        unit=" świec",
        ncols=100,
        bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
        miniters=100  # Aktualizuj co 100 świec
    ) as pbar:
        while current_date < end_date:
            batch_end = min(
                current_date + timedelta(days=batch_size_days),
                end_date
            )
            
            try:
                logger.info(f"📦 {exchange.upper()} partia: {current_date.date()} → {batch_end.date()}")
                
                # Pobierz dane dla partii
                if exchange == "binance":
                    df = fetch_method(
                        start_date=current_date,
                        end_date=batch_end,
                        **fetch_kwargs
                    )
                else:  # dydx
                    df = fetch_method(
                        start_date=current_date,
                        end_date=batch_end,
                        **fetch_kwargs
                    )
                
                if not df.empty:
                    # Zapisz do bazy
                    saved = db.save_ohlcv(
                        df=df,
                        exchange=exchange,
                        symbol=symbol,
                        timeframe=timeframe
                    )
                    total_saved += saved
                    pbar.update(len(df))
                    if saved > 0:
                        logger.success(f"✅ {exchange.upper()}: Zapisano {saved:,}/{len(df):,} świec (partia: {current_date.date()})")
                    else:
                        logger.warning(f"⚠️  {exchange.upper()}: Zapisano 0/{len(df):,} świec - możliwe duplikaty (partia: {current_date.date()})")
                else:
                    logger.warning(f"⚠️  {exchange.upper()}: Brak danych dla partii: {current_date.date()} → {batch_end.date()}")
                
                # Przejdź do następnej partii
                current_date = batch_end
                
                # Małe opóźnienie, żeby nie przeciążać API
                time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"❌ {exchange.upper()}: Błąd podczas pobierania partii {current_date.date()}: {e}")
                # Spróbuj kontynuować z następną partią
                current_date = batch_end
                continue
    
    return total_saved


def main():
    """Główna funkcja."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Reset i ponowne załadowanie danych BTC z obu giełd (Binance od 2017, dYdX od 2023)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  # Reset i załadowanie danych 1-minutowych z obu giełd
  python scripts/reset_and_load_btcusdc.py --timeframe 1m --confirm
  
  # Reset i załadowanie danych 5-minutowych z obu giełd
  python scripts/reset_and_load_btcusdc.py --timeframe 5m --confirm
  
  # Tylko wyczyść dane (bez ładowania)
  python scripts/reset_and_load_btcusdc.py --clear-only --confirm
  
  # Tylko Binance
  python scripts/reset_and_load_btcusdc.py --exchanges binance --confirm
  
  # Tylko dYdX
  python scripts/reset_and_load_btcusdc.py --exchanges dydx --confirm
        """
    )
    
    parser.add_argument(
        '--timeframe',
        type=str,
        default='1m',
        help='Interwał czasowy (1m, 5m, 15m, 1h, itd.) - domyślnie: 1m'
    )
    
    parser.add_argument(
        '--exchanges',
        type=str,
        default='binance,dydx',
        help='Giełdy do załadowania (binance,dydx) - domyślnie: obie'
    )
    
    parser.add_argument(
        '--clear-only',
        action='store_true',
        help='Tylko wyczyść dane, bez ładowania'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Szczegółowe logi'
    )
    
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Potwierdź operację (wymagane)'
    )
    
    args = parser.parse_args()
    
    # Konfiguruj logowanie
    setup_logging(args.verbose)
    
    # Sprawdź potwierdzenie
    if not args.confirm:
        logger.warning("⚠️  Użyj --confirm aby potwierdzić operację")
        logger.info("Przykład: python scripts/reset_and_load_btcusdc.py --confirm --timeframe 1m")
        sys.exit(1)
    
    # Załaduj .env
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ Brak DATABASE_URL w .env")
        sys.exit(1)
    
    # Sprawdź czy używa PostgreSQL
    use_timescale = os.getenv('USE_TIMESCALE', 'false').lower() == 'true'
    is_postgresql = 'postgresql' in database_url.lower() or 'postgres' in database_url.lower()
    
    if not is_postgresql:
        logger.warning("⚠️  Wykryto SQLite. Dla dużych ilości danych zalecany jest PostgreSQL.")
        logger.info("Ustaw DATABASE_URL na PostgreSQL w .env aby użyć TimescaleDB")
    
    # Walidacja timeframe
    valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
    if args.timeframe not in valid_timeframes:
        logger.error(f"❌ Nieprawidłowy timeframe: {args.timeframe}")
        logger.info(f"Dostępne: {', '.join(valid_timeframes)}")
        sys.exit(1)
    
    try:
        print()
        print("=" * 70)
        print("🔄 RESET I PONOWNE ZAŁADOWANIE DANYCH BTC Z OBU GIELD")
        print("=" * 70)
        print()
        
        # KROK 1: Wyczyść dane
        logger.info("📋 KROK 1: Czyszczenie starych danych...")
        exchanges_to_clear = args.exchanges.split(',') if args.clear_only else None
        deleted_count = clear_btc_data(
            database_url, 
            exchange=exchanges_to_clear[0] if exchanges_to_clear and len(exchanges_to_clear) == 1 else None,
            timeframe=args.timeframe if args.clear_only else None
        )
        
        if args.clear_only:
            logger.success("✅ Tylko czyszczenie - zakończono")
            return 0
        
        print()
        logger.info("📋 KROK 2: Ładowanie nowych danych...")
        
        # Parsuj giełdy
        exchanges = [e.strip() for e in args.exchanges.split(',')]
        
        # Upewnij się, że tabele istnieją
        db = DatabaseManager(database_url=database_url, use_timescale=use_timescale)
        logger.info("🔧 Sprawdzam i tworzę tabele w bazie danych...")
        if is_postgresql:
            logger.info("   Używam PostgreSQL" + (" z TimescaleDB" if use_timescale else ""))
        else:
            logger.info("   Używam SQLite")
        
        db.create_tables()
        logger.success("✅ Tabele gotowe")
        
        # Konfiguracja dla każdej giełdy
        exchange_configs = {
            'binance': {
                'symbol': 'BTC/USDC',
                'start_year': 2017,
                'start_date': datetime(2017, 1, 1, tzinfo=timezone.utc)
            },
            'dydx': {
                'symbol': 'BTC-USD',
                'start_year': 2023,
                'start_date': datetime(2023, 1, 1, tzinfo=timezone.utc)  # dYdX v4 startował w listopadzie, ale zaczynamy od początku roku
            }
        }
        
        end_date = datetime.now(timezone.utc)
        total_saved_all = 0
        start_time = time.time()
        
        # Zaczytaj dane dla każdej giełdy
        for exchange in exchanges:
            if exchange not in exchange_configs:
                logger.warning(f"⚠️  Nieznana giełda: {exchange}, pomijam")
                continue
            
            if exchange == 'dydx' and not DYDX_AVAILABLE:
                logger.warning(f"⚠️  dYdX niedostępny, pomijam")
                continue
            
            config = exchange_configs[exchange]
            logger.info(f"\n{'='*70}")
            logger.info(f"📊 {exchange.upper()}: {config['symbol']}")
            logger.info(f"   Okres: {config['start_date'].date()} → {end_date.date()}")
            logger.info(f"{'='*70}\n")
            
            exchange_start_time = time.time()
            saved = load_data_with_progress(
                db=db,
                exchange=exchange,
                symbol=config['symbol'],
                start_date=config['start_date'],
                end_date=end_date,
                timeframe=args.timeframe
            )
            exchange_elapsed = time.time() - exchange_start_time
            total_saved_all += saved
            
            logger.info(f"\n✅ {exchange.upper()}: Zapisano {saved:,} świec w {exchange_elapsed:.1f}s ({exchange_elapsed/60:.1f} min)")
        
        elapsed_time = time.time() - start_time
        
        print()
        print("=" * 70)
        logger.success(f"✅ SUKCES! Łącznie zapisano {total_saved_all:,} świec {args.timeframe}")
        logger.info(f"⏱️  Całkowity czas wykonania: {elapsed_time:.1f} sekund ({elapsed_time/60:.1f} minut)")
        
        # Sprawdź ostatnie świece dla każdej giełdy
        logger.info("\n📊 Ostatnie świece w bazie:")
        for exchange in exchanges:
            if exchange not in exchange_configs:
                continue
            config = exchange_configs[exchange]
            latest_df = db.get_ohlcv(
                exchange=exchange,
                symbol=config['symbol'],
                timeframe=args.timeframe,
                limit=1
            )
            if not latest_df.empty:
                logger.info(f"   {exchange.upper()}:{config['symbol']} - {latest_df.index[-1]}")
        
        print("=" * 70)
        return 0
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Przerwano przez użytkownika")
        return 1
    except Exception as e:
        logger.error(f"❌ Błąd: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    from datetime import timedelta
    sys.exit(main())

