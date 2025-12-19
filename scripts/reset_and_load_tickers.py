#!/usr/bin/env python3
"""
Skrypt do resetu i ponownego załadowania tickerów z obu giełd
=============================================================
1. Czyści wszystkie tickery z bazy (Binance i dYdX)
2. Pobiera funding rates i open interest (Binance od 2017, dYdX od 2023)
3. Generuje tickery z danych OHLCV, funding rates i open interest
4. Wyświetla paski postępu i szczegółowe logi
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
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

from scripts.generate_historical_tickers import generate_tickers_from_ohlcv


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


def clear_tickers_data(database_url: str, exchange: Optional[str] = None, symbol: Optional[str] = None) -> int:
    """
    Czyści tickery z bazy danych używając TRUNCATE i resetuje sekwencję.
    
    Args:
        database_url: URL bazy danych
        exchange: Opcjonalnie, usuń tylko tickery dla konkretnej giełdy (binance/dydx)
        symbol: Opcjonalnie, usuń tylko tickery dla konkretnego symbolu
        
    Returns:
        Liczba usuniętych rekordów (0 dla TRUNCATE, ale zwracamy 1 dla sukcesu)
    """
    logger.info("🔗 Łączę z bazę danych...")
    engine = create_engine(database_url)
    
    # Sprawdź czy to PostgreSQL
    is_postgresql = 'postgresql' in database_url.lower() or 'postgres' in database_url.lower()
    
    # Mapowanie symboli dla różnych giełd
    symbols = {
        'binance': 'BTC/USDC',
        'dydx': 'BTC-USD'
    }
    
    try:
        with engine.begin() as conn:
            # Jeśli podano symbol, nie możemy użyć TRUNCATE - użyj DELETE
            if symbol:
                logger.warning("⚠️  TRUNCATE nie obsługuje WHERE - używam DELETE dla symbolu")
                total_deleted = 0
                exchanges_to_clear = [exchange] if exchange else ['binance', 'dydx']
                
                for exch in exchanges_to_clear:
                    logger.info(f"🗑️  Usuwam tickery {exch}:{symbol} z bazy...")
                    result = conn.execute(text(
                        "DELETE FROM tickers WHERE exchange = :exchange AND symbol = :symbol"
                    ), {"exchange": exch, "symbol": symbol})
                    
                    deleted_count = result.rowcount
                    total_deleted += deleted_count
                    if deleted_count > 0:
                        logger.success(f"✅ Usunięto {deleted_count:,} rekordów tickerów z {exch}")
                
                logger.success(f"✅ Łącznie usunięto {total_deleted:,} rekordów tickerów")
                return total_deleted
            
            # Użyj TRUNCATE dla pełnego czyszczenia
            exchanges_to_clear = [exchange] if exchange else ['binance', 'dydx']
            
            for exch in exchanges_to_clear:
                default_symbol = symbols.get(exch)
                if default_symbol:
                    logger.info(f"🗑️  TRUNCATE tickerów {exch}:{default_symbol} z bazy...")
                else:
                    logger.info(f"🗑️  TRUNCATE wszystkich tickerów {exch} z bazy...")
                
                # TRUNCATE nie obsługuje WHERE, więc używamy DELETE, ale resetujemy sekwencję
                if default_symbol:
                    # Usuń dane dla konkretnego symbolu
                    conn.execute(text(
                        "DELETE FROM tickers WHERE exchange = :exchange AND symbol = :symbol"
                    ), {"exchange": exch, "symbol": default_symbol})
                else:
                    # Usuń wszystkie dane dla exchange
                    conn.execute(text(
                        "DELETE FROM tickers WHERE exchange = :exchange"
                    ), {"exchange": exch})
                
                # Zresetuj sekwencję/autoincrement
                if is_postgresql:
                    # PostgreSQL - reset sekwencji
                    conn.execute(text(
                        "SELECT setval(pg_get_serial_sequence('tickers', 'id'), 1, false)"
                    ))
                    logger.info(f"✅ Zresetowano sekwencję dla tickers.id (zacznie od 1)")
                else:
                    # SQLite - reset autoincrement
                    conn.execute(text("DELETE FROM sqlite_sequence WHERE name = 'tickers'"))
                    logger.info(f"✅ Zresetowano autoincrement dla tickers (zacznie od 1)")
                
                if default_symbol:
                    logger.success(f"✅ Wyczyszczono wszystkie tickery {exch}:{default_symbol}")
                else:
                    logger.success(f"✅ Wyczyszczono wszystkie tickery {exch}")
            
            logger.success(f"✅ Wyczyszczono wszystkie tickery")
            return 1  # TRUNCATE nie zwraca liczby rekordów
            
    except Exception as e:
        logger.error(f"❌ Błąd podczas czyszczenia: {e}")
        raise


def load_funding_rates_and_oi(
    collector,
    db: DatabaseManager,
    start_date: datetime,
    end_date: datetime,
    exchange: str,
    symbol_perpetual: str,
    symbol_spot: str,
    exchange_name: str
) -> tuple[int, int]:
    """
    Pobiera i zapisuje funding rates i open interest do bazy.
    
    Args:
        collector: Collector (BinanceCollector lub DydxCollector)
        db: Database manager
        start_date: Data początkowa
        end_date: Data końcowa
        exchange: Nazwa giełdy (binance/dydx)
        symbol_perpetual: Symbol perpetual futures
        symbol_spot: Symbol spot (dla tickers)
        exchange_name: Nazwa giełdy dla bazy
        
    Returns:
        Tuple (liczba funding rates, liczba open interest)
    """
    logger.info(f"📊 Pobieram funding rates i open interest dla {exchange_name}...")
    logger.info(f"   Okres: {start_date.date()} → {end_date.date()}")
    
    funding_saved = 0
    oi_saved = 0
    
    if exchange == "binance":
        # Binance: pobierz funding rates i open interest
        logger.info("📊 Pobieram funding rates z Binance...")
        funding_df = collector.get_funding_rates(
            symbol=symbol_perpetual,
            since=start_date,
            limit=10000
        )
        
        if not funding_df.empty:
            logger.info(f"Pobrano {len(funding_df)} funding rates")
            funding_saved = db.save_funding_rates(
                df=funding_df,
                exchange=exchange_name,
                symbol=symbol_spot
            )
            logger.success(f"✅ Zapisano {funding_saved} funding rates do tickers")
        else:
            logger.warning("Brak funding rates do zapisania")
        
        # Pobierz open interest
        logger.info("📊 Pobieram open interest z Binance...")
        oi_df = collector.get_open_interest(
            symbol=symbol_perpetual,
            since=start_date,
            limit=10000
        )
        
        if not oi_df.empty:
            logger.info(f"Pobrano {len(oi_df)} rekordów open interest")
            # Dodaj cenę z OHLCV dla lepszego dopasowania
            ohlcv_df = db.get_ohlcv(
                exchange=exchange_name,
                symbol=symbol_spot,
                timeframe="1m",
                start_date=start_date,
                end_date=end_date
            )
            
            if not ohlcv_df.empty:
                # Merge open interest z ceną
                oi_df = oi_df.join(ohlcv_df[['close']], how='left')
                oi_df.rename(columns={'close': 'price'}, inplace=True)
            
            oi_saved = db.save_open_interest(
                df=oi_df,
                exchange=exchange_name,
                symbol=symbol_perpetual
            )
            logger.success(f"✅ Zapisano {oi_saved} rekordów open interest do bazy")
        else:
            logger.warning("Brak open interest do zapisania")
    
    elif exchange == "dydx":
        # dYdX: pobierz funding rates
        logger.info("📊 Pobieram funding rates z dYdX...")
        try:
            funding_df = collector.get_funding_rates(
                ticker=symbol_spot,
                limit=10000
            )
            
            if not funding_df.empty:
                logger.info(f"Pobrano {len(funding_df)} funding rates")
                funding_saved = db.save_funding_rates(
                    df=funding_df,
                    exchange=exchange_name,
                    symbol=symbol_spot
                )
                logger.success(f"✅ Zapisano {funding_saved} funding rates do tickers")
            else:
                logger.warning("Brak funding rates do zapisania")
        except Exception as e:
            logger.warning(f"⚠️  Nie udało się pobrać funding rates z dYdX: {e}")
        
        # dYdX: open interest jest w tickerze, będzie pobrane podczas generowania tickerów
        logger.info("📊 dYdX: open interest będzie pobrane podczas generowania tickerów")
    
    return funding_saved, oi_saved


def generate_tickers(
    db: DatabaseManager,
    start_date: datetime,
    end_date: datetime,
    symbol: str = "BTC/USDC",
    timeframe: str = "1h",
    exchange: str = "binance",
    exchange_name: str = "binance"
) -> int:
    """
    Generuje tickery z danych OHLCV, funding rates i open interest.
    
    Args:
        db: Database manager
        start_date: Data początkowa
        end_date: Data końcowa
        symbol: Symbol pary
        timeframe: Timeframe OHLCV
        exchange: Nazwa giełdy w bazie
        exchange_name: Nazwa giełdy dla tickerów
        
    Returns:
        Liczba wygenerowanych tickerów
    """
    logger.info(f"📊 Generuję tickery dla {exchange_name}:{symbol}...")
    logger.info(f"   Okres: {start_date.date()} → {end_date.date()}")
    logger.info(f"   Timeframe: {timeframe}")
    
    try:
        generate_tickers_from_ohlcv(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            exchange_name=exchange_name
        )
        
        # Sprawdź ile tickerów zostało wygenerowanych
        with db.get_session() as session:
            from src.database.models import Ticker
            count = session.query(Ticker).filter(
                Ticker.exchange == exchange_name,
                Ticker.symbol == symbol,
                Ticker.timestamp >= start_date,
                Ticker.timestamp <= end_date
            ).count()
        
        logger.success(f"✅ Wygenerowano {count:,} tickerów")
        return count
        
    except Exception as e:
        logger.error(f"❌ Błąd podczas generowania tickerów: {e}")
        raise


def main():
    """Główna funkcja."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Reset i ponowne załadowanie tickerów z obu giełd (Binance od 2017, dYdX od 2023)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  # Reset i załadowanie tickerów z obu giełd
  python scripts/reset_and_load_tickers.py --confirm
  
  # Reset i załadowanie tickerów z timeframe 1h
  python scripts/reset_and_load_tickers.py --confirm --timeframe 1h
  
  # Tylko wyczyść tickery (bez ładowania)
  python scripts/reset_and_load_tickers.py --clear-only --confirm
  
  # Tylko Binance
  python scripts/reset_and_load_tickers.py --exchanges binance --confirm
  
  # Tylko dYdX
  python scripts/reset_and_load_tickers.py --exchanges dydx --confirm
        """
    )
    
    parser.add_argument(
        '--timeframe',
        type=str,
        default='1h',
        help='Timeframe dla tickerów (domyślnie: 1h)'
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
        help='Tylko wyczyść tickery, bez ładowania'
    )
    
    parser.add_argument(
        '--skip-funding-oi',
        action='store_true',
        help='Pomiń pobieranie funding rates i open interest (użyj istniejących danych)'
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
        logger.info("Przykład: python scripts/reset_and_load_tickers.py --confirm")
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
    
    try:
        print()
        print("=" * 70)
        print("🔄 RESET I PONOWNE ZAŁADOWANIE TICKERÓW")
        print("=" * 70)
        print()
        
        # Inicjalizuj bazę
        db = DatabaseManager(database_url=database_url, use_timescale=use_timescale)
        
        # Upewnij się, że tabele istnieją
        logger.info("🔧 Sprawdzam i tworzę tabele w bazie danych...")
        if is_postgresql:
            logger.info("   Używam PostgreSQL" + (" z TimescaleDB" if use_timescale else ""))
        else:
            logger.info("   Używam SQLite")
        
        db.create_tables()
        logger.success("✅ Tabele gotowe")
        
        # Parsuj giełdy
        exchanges = [e.strip() for e in args.exchanges.split(',')]
        
        # KROK 1: Wyczyść tickery
        logger.info("📋 KROK 1: Czyszczenie starych tickerów...")
        exchanges_to_clear = exchanges if args.clear_only else None
        deleted_count = clear_tickers_data(
            database_url, 
            exchange=exchanges_to_clear[0] if exchanges_to_clear and len(exchanges_to_clear) == 1 else None
        )
        
        if args.clear_only:
            logger.success("✅ Tylko czyszczenie - zakończono")
            return 0
        
        print()
        
        # Konfiguracja dla każdej giełdy
        # Uwaga: symbol_perpetual jest używany tylko do pobierania funding rates z perpetual futures API
        # Funding rates są zapisywane do tickerów z symbolem spot (BTC/USDC dla Binance, BTC-USD dla dYdX)
        exchange_configs = {
            'binance': {
                'symbol': 'BTC/USDC',  # Symbol spot używany w bazie danych (spójny z strategiami i testami)
                'symbol_perpetual': 'BTC/USDT:USDT',  # Symbol perpetual futures do pobierania funding rates z API
                'start_date': datetime(2017, 1, 1, tzinfo=timezone.utc),
                'collector_class': BinanceCollector,
                'collector_kwargs': {'sandbox': False}
            },
            'dydx': {
                'symbol': 'BTC-USD',  # Symbol używany w bazie danych (spójny z strategiami i testami)
                'symbol_perpetual': 'BTC-USD',  # dYdX używa tego samego symbolu dla spot i perpetual
                'start_date': datetime(2023, 1, 1, tzinfo=timezone.utc),
                'collector_class': DydxCollector if DYDX_AVAILABLE else None,
                'collector_kwargs': {'testnet': False}
            }
        }
        
        end_date = datetime.now(timezone.utc)
        total_tickers_all = 0
        start_time = time.time()
        
        # Przetwarzaj każdą giełdę
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
            
            # Inicjalizuj kolektor
            collector = config['collector_class'](**config['collector_kwargs'])
            
            # KROK 2: Pobierz funding rates i open interest
            if not args.skip_funding_oi:
                logger.info(f"📋 KROK 2: Pobieranie funding rates i open interest dla {exchange.upper()}...")
                funding_saved, oi_saved = load_funding_rates_and_oi(
                    collector=collector,
                    db=db,
                    start_date=config['start_date'],
                    end_date=end_date,
                    exchange=exchange,
                    symbol_perpetual=config['symbol_perpetual'],
                    symbol_spot=config['symbol'],
                    exchange_name=exchange
                )
                logger.info(f"   Funding rates: {funding_saved:,} rekordów")
                logger.info(f"   Open interest: {oi_saved:,} rekordów")
                print()
            else:
                logger.info(f"📋 KROK 2: Pomijam pobieranie funding rates i open interest (używam istniejących danych)")
                print()
            
            # KROK 3: Generuj tickery
            logger.info(f"📋 KROK 3: Generowanie tickerów dla {exchange.upper()}...")
            exchange_start_time = time.time()
            
            tickers_count = generate_tickers(
                db=db,
                start_date=config['start_date'],
                end_date=end_date,
                symbol=config['symbol'],
                timeframe=args.timeframe,
                exchange=exchange,
                exchange_name=exchange
            )
            
            exchange_elapsed = time.time() - exchange_start_time
            total_tickers_all += tickers_count
            
            logger.info(f"\n✅ {exchange.upper()}: Wygenerowano {tickers_count:,} tickerów w {exchange_elapsed:.1f}s ({exchange_elapsed/60:.1f} min)")
        
        elapsed_time = time.time() - start_time
        
        print()
        print("=" * 70)
        logger.success(f"✅ SUKCES! Łącznie wygenerowano {total_tickers_all:,} tickerów")
        logger.info(f"⏱️  Całkowity czas wykonania: {elapsed_time:.1f} sekund ({elapsed_time/60:.1f} minut)")
        
        # Sprawdź statystyki dla każdej giełdy
        logger.info("\n📊 Statystyki tickerów:")
        with db.get_session() as session:
            from src.database.models import Ticker
            for exchange in exchanges:
                if exchange not in exchange_configs:
                    continue
                config = exchange_configs[exchange]
                
                total_tickers = session.query(Ticker).filter(
                    Ticker.exchange == exchange,
                    Ticker.symbol == config['symbol']
                ).count()
                
                if total_tickers > 0:
                    with_funding = session.query(Ticker).filter(
                        Ticker.exchange == exchange,
                        Ticker.symbol == config['symbol'],
                        Ticker.funding_rate.isnot(None)
                    ).count()
                    
                    with_oi = session.query(Ticker).filter(
                        Ticker.exchange == exchange,
                        Ticker.symbol == config['symbol'],
                        Ticker.open_interest.isnot(None)
                    ).count()
                    
                    logger.info(f"\n   {exchange.upper()}:{config['symbol']}:")
                    logger.info(f"      Łącznie: {total_tickers:,}")
                    if total_tickers > 0:
                        logger.info(f"      Z funding_rate: {with_funding:,} ({with_funding/total_tickers*100:.1f}%)")
                        logger.info(f"      Z open_interest: {with_oi:,} ({with_oi/total_tickers*100:.1f}%)")
        
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
    sys.exit(main())

