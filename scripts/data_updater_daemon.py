#!/usr/bin/env python3
"""
Data Updater Daemon
===================
Skrypt działający w tle, który aktualizuje dane OHLCV i tickers co 1 minutę.

Użycie:
    python scripts/data_updater_daemon.py
    python scripts/data_updater_daemon.py --symbols=BTC/USDC,ETH/USDC --exchanges=binance,dydx

Autor: AI Assistant
Data: 2025-12-18
"""

import os
import sys
import time
import signal
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import traceback

# Dodaj ścieżkę projektu
sys.path.insert(0, str(Path(__file__).parent.parent))

# Załaduj zmienne środowiskowe z .env jeśli istnieje
env_file = Path(__file__).parent.parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Usuń cudzysłowy jeśli są
                value = value.strip('"').strip("'")
                os.environ.setdefault(key, value)

from loguru import logger
import pandas as pd
from src.database.manager import DatabaseManager
from src.collectors.exchange.binance_collector import BinanceCollector

# Spróbuj zaimportować dYdX collector
try:
    from src.collectors.exchange.dydx_collector import DydxCollector
    DYDX_AVAILABLE = True
except ImportError:
    DYDX_AVAILABLE = False
    logger.warning("DydxCollector niedostępny - używam tylko Binance")


class DataUpdaterDaemon:
    """
    Daemon do aktualizacji danych OHLCV i tickers.
    """
    
    def __init__(
        self,
        symbols: List[str] = None,
        exchanges: List[str] = None,
        update_interval: int = 60,  # sekundy
        database_url: Optional[str] = None
    ):
        """
        Inicjalizuje daemon.
        
        Args:
            symbols: Lista symboli do aktualizacji (domyślnie: BTC/USDC)
            exchanges: Lista giełd (domyślnie: binance, dydx)
            update_interval: Interwał aktualizacji w sekundach (domyślnie: 60)
            database_url: URL bazy danych (domyślnie: z .env lub SQLite)
        """
        # Domyślnie używamy BTC/USDC (spójne z strategiami i testami)
        # Daemon automatycznie znormalizuje to do odpowiedniego formatu dla każdej giełdy
        self.symbols = symbols or ["BTC/USDC"]
        self.exchanges = exchanges or ["binance", "dydx"]
        self.update_interval = update_interval
        self.running = False
        
        # Inicjalizuj bazę danych
        # Jeśli database_url nie jest podane, sprawdź zmienną środowiskową DATABASE_URL
        if database_url is None:
            database_url = os.getenv('DATABASE_URL')
        
        self.db = DatabaseManager(database_url=database_url)
        self.db.create_tables()
        logger.info(f"Połączono z bazą: {self.db._safe_url()}")
        
        # Inicjalizuj kolektory
        self.collectors: Dict[str, any] = {}
        
        if "binance" in self.exchanges:
            try:
                self.collectors["binance"] = BinanceCollector()
                logger.info("BinanceCollector zainicjalizowany")
            except Exception as e:
                logger.error(f"Nie można zainicjalizować BinanceCollector: {e}")
                self.exchanges.remove("binance")
        
        if "dydx" in self.exchanges and DYDX_AVAILABLE:
            try:
                self.collectors["dydx"] = DydxCollector()
                logger.info("DydxCollector zainicjalizowany")
            except Exception as e:
                logger.error(f"Nie można zainicjalizować DydxCollector: {e}")
                if "dydx" in self.exchanges:
                    self.exchanges.remove("dydx")
        
        if not self.collectors:
            raise RuntimeError("Brak dostępnych kolektorów!")
        
        # Statystyki
        self.stats = {
            "start_time": datetime.now(timezone.utc),
            "updates_count": 0,
            "ohlcv_saved": 0,
            "tickers_saved": 0,
            "errors_count": 0,
            "last_update": None
        }
        
        # Obsługa sygnałów
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"DataUpdaterDaemon zainicjalizowany: {len(self.collectors)} kolektorów, {len(self.symbols)} symboli")
    
    def _signal_handler(self, signum, frame):
        """Obsługuje sygnały zatrzymania."""
        logger.info(f"Otrzymano sygnał {signum} - zatrzymywanie...")
        self.running = False
    
    def _normalize_symbol(self, symbol: str, exchange: str) -> str:
        """
        Normalizuje symbol dla danej giełdy.
        
        Binance używa: BTC/USDC (spójne z strategiami i testami)
        dYdX używa: BTC-USD
        
        W bazie danych:
        - Binance: BTC/USDC
        - dYdX: BTC-USD
        """
        if exchange == "binance":
            # Konwertuj BTC-USD lub BTC/USDT -> BTC/USDC
            if symbol.endswith("-USD"):
                base = symbol.replace("-USD", "")
                return f"{base}/USDC"
            elif "/USDT" in symbol:
                base = symbol.split("/")[0]
                return f"{base}/USDC"
            return symbol
        elif exchange == "dydx":
            # Konwertuj BTC/USDC lub BTC/USDT -> BTC-USD
            if "/" in symbol:
                base = symbol.split("/")[0]
                return f"{base}-USD"
            return symbol
        return symbol
    
    def _update_ohlcv(self, exchange: str, symbol: str) -> int:
        """
        Aktualizuje dane OHLCV dla danego symbolu, uzupełniając brakujące dane.
        
        Args:
            exchange: Nazwa giełdy
            symbol: Symbol pary
            
        Returns:
            Liczba zapisanych świec
        """
        if exchange not in self.collectors:
            return 0
        
        collector = self.collectors[exchange]
        normalized_symbol = self._normalize_symbol(symbol, exchange)
        timeframe = "1m"
        
        try:
            # Sprawdź ostatni timestamp w bazie
            existing_df = self.db.get_ohlcv(
                exchange=exchange,
                symbol=normalized_symbol,
                timeframe=timeframe,
                limit=1
            )
            
            now = datetime.now(timezone.utc)
            
            if existing_df.empty:
                # Baza jest pusta - pobierz dane z ostatnich 7 dni
                logger.info(f"Baza pusta dla {exchange}:{normalized_symbol}, pobieram dane z ostatnich 7 dni")
                since_date = now - timedelta(days=7)
            else:
                # Pobierz dane od ostatniego timestamp + 1 minuta
                last_timestamp = existing_df.index[-1]
                # Konwertuj na datetime jeśli potrzeba
                if isinstance(last_timestamp, pd.Timestamp):
                    last_timestamp_dt = last_timestamp.to_pydatetime()
                else:
                    last_timestamp_dt = last_timestamp
                
                if last_timestamp_dt.tzinfo is None:
                    last_timestamp_dt = last_timestamp_dt.replace(tzinfo=timezone.utc)
                
                # Pobierz dane od ostatniego timestamp + 1 minuta do teraz
                since_date = last_timestamp_dt + timedelta(minutes=1)
                
                # Upewnij się że since_date nie jest w przyszłości
                if since_date > now:
                    logger.debug(f"Ostatni timestamp ({last_timestamp_dt}) jest bardzo świeży, pobieram tylko ostatnie 5 minut")
                    since_date = now - timedelta(minutes=5)
                
                # Jeśli ostatni timestamp jest bardzo stary (> 7 dni), ogranicz do 7 dni wstecz
                max_age = now - timedelta(days=7)
                if since_date < max_age:
                    logger.warning(f"Ostatni timestamp ({last_timestamp_dt}) jest bardzo stary, ograniczam do 7 dni wstecz")
                    since_date = max_age
            
            # Oblicz ile minut brakuje (maksymalnie 1000 świec dla Binance, 100 dla dYdX)
            minutes_diff = (now - since_date).total_seconds() / 60
            max_candles = 1000 if exchange == "binance" else 100
            
            if minutes_diff > max_candles:
                logger.warning(f"Za dużo brakujących minut ({minutes_diff:.0f}), ograniczam do {max_candles} świec")
                since_date = now - timedelta(minutes=max_candles)
            
            logger.info(f"Pobieram {exchange}:{normalized_symbol} {timeframe} od {since_date} do {now}")
            
            # Różne giełdy używają różnych metod
            if exchange == "dydx":
                # dYdX używa fetch_candles
                from_iso = since_date.isoformat()
                to_iso = now.isoformat()
                df = collector.fetch_candles(
                    ticker=normalized_symbol,
                    resolution=timeframe,
                    from_iso=from_iso,
                    to_iso=to_iso,
                    limit=max_candles
                )
            else:
                # Binance i inne używają fetch_ohlcv
                df = collector.fetch_ohlcv(
                    symbol=normalized_symbol,
                    timeframe=timeframe,
                    since=since_date,
                    limit=max_candles
                )
            
            if df.empty:
                logger.debug(f"Brak nowych danych OHLCV dla {exchange}:{normalized_symbol}")
                return 0
            
            # Filtruj tylko dane nowsze niż ostatni timestamp (jeśli istnieje)
            if not existing_df.empty:
                last_timestamp = existing_df.index[-1]
                # Konwertuj na pandas Timestamp jeśli potrzeba
                if isinstance(last_timestamp, pd.Timestamp):
                    last_timestamp_pd = last_timestamp
                else:
                    last_timestamp_pd = pd.Timestamp(last_timestamp)
                # Upewnij się że oba są w UTC
                if last_timestamp_pd.tz is None:
                    last_timestamp_pd = last_timestamp_pd.tz_localize('UTC')
                elif last_timestamp_pd.tz != timezone.utc:
                    last_timestamp_pd = last_timestamp_pd.tz_convert('UTC')
                
                # Upewnij się że df.index też jest w UTC
                if df.index.tz is None:
                    df.index = df.index.tz_localize('UTC')
                elif df.index.tz != timezone.utc:
                    df.index = df.index.tz_convert('UTC')
                
                df = df[df.index > last_timestamp_pd]
            
            if df.empty:
                logger.debug(f"Wszystkie dane już są w bazie dla {exchange}:{normalized_symbol}")
                return 0
            
            # Zapisz do bazy
            saved = self.db.save_ohlcv(
                df=df,
                exchange=exchange,
                symbol=normalized_symbol,
                timeframe=timeframe
            )
            
            if saved > 0:
                logger.info(f"✅ Zapisano {saved}/{len(df)} świec OHLCV: {exchange}:{normalized_symbol} (okres: {df.index.min()} → {df.index.max()})")
            else:
                logger.debug(f"Nie zapisano nowych świec (wszystkie były duplikatami)")
            
            return saved
            
        except Exception as e:
            logger.error(f"Błąd aktualizacji OHLCV {exchange}:{normalized_symbol}: {e}")
            logger.debug(traceback.format_exc())
            self.stats["errors_count"] += 1
            return 0
    
    def _update_ticker(self, exchange: str, symbol: str) -> int:
        """
        Aktualizuje dane tickera dla danego symbolu.
        
        Args:
            exchange: Nazwa giełdy
            symbol: Symbol pary
            
        Returns:
            Liczba zapisanych tickerów
        """
        if exchange not in self.collectors:
            return 0
        
        collector = self.collectors[exchange]
        normalized_symbol = self._normalize_symbol(symbol, exchange)
        
        try:
            # Pobierz aktualny ticker
            ticker_dict = collector.get_ticker(normalized_symbol)
            
            if not ticker_dict:
                logger.debug(f"Brak danych tickera dla {exchange}:{normalized_symbol}")
                return 0
            
            # Konwertuj dict na DataFrame
            timestamp = datetime.now(timezone.utc)
            
            # Różne giełdy mają różne formaty tickera
            if exchange == "binance":
                ticker_df = pd.DataFrame([{
                    'timestamp': timestamp,
                    'price': ticker_dict.get('last', 0),
                    'bid': ticker_dict.get('bid', 0),
                    'ask': ticker_dict.get('ask', 0),
                    'volume_24h': ticker_dict.get('quoteVolume', 0),
                    'high_24h': ticker_dict.get('high', 0),
                    'low_24h': ticker_dict.get('low', 0),
                    'change_24h': ticker_dict.get('percentage', 0),
                }])
            elif exchange == "dydx":
                ticker_df = pd.DataFrame([{
                    'timestamp': timestamp,
                    'price': ticker_dict.get('oracle_price', 0),
                    'volume_24h': ticker_dict.get('volume_24h', 0),
                    'change_24h': ticker_dict.get('price_change_24h', 0),
                    'open_interest': ticker_dict.get('open_interest', 0),
                    'funding_rate': ticker_dict.get('next_funding_rate', 0),
                }])
            else:
                # Domyślny format
                ticker_df = pd.DataFrame([{
                    'timestamp': timestamp,
                    'price': ticker_dict.get('price', ticker_dict.get('last', 0)),
                }])
            
            ticker_df.set_index('timestamp', inplace=True)
            
            # Zapisz do bazy
            saved = self.db.save_tickers(
                df=ticker_df,
                exchange=exchange,
                symbol=normalized_symbol
            )
            
            if saved > 0:
                logger.debug(f"✅ Zapisano ticker: {exchange}:{normalized_symbol}")
            
            return saved
            
        except Exception as e:
            logger.error(f"Błąd aktualizacji tickera {exchange}:{normalized_symbol}: {e}")
            logger.debug(traceback.format_exc())
            self.stats["errors_count"] += 1
            return 0
    
    def _update_cycle(self):
        """Wykonuje jeden cykl aktualizacji."""
        cycle_start = datetime.now(timezone.utc)
        ohlcv_total = 0
        tickers_total = 0
        
        logger.info(f"🔄 Rozpoczynam cykl aktualizacji ({cycle_start.strftime('%Y-%m-%d %H:%M:%S')})")
        
        for exchange in self.exchanges:
            if exchange not in self.collectors:
                continue
            
            for symbol in self.symbols:
                # Aktualizuj OHLCV
                ohlcv_saved = self._update_ohlcv(exchange, symbol)
                ohlcv_total += ohlcv_saved
                
                # Małe opóźnienie między requestami
                time.sleep(0.5)
                
                # Aktualizuj ticker
                ticker_saved = self._update_ticker(exchange, symbol)
                tickers_total += ticker_saved
                
                # Małe opóźnienie między symbolami
                time.sleep(0.5)
        
        # Aktualizuj statystyki
        self.stats["updates_count"] += 1
        self.stats["ohlcv_saved"] += ohlcv_total
        self.stats["tickers_saved"] += tickers_total
        self.stats["last_update"] = cycle_start
        
        cycle_duration = (datetime.now(timezone.utc) - cycle_start).total_seconds()
        
        logger.success(
            f"✅ Cykl zakończony: {ohlcv_total} świec OHLCV, {tickers_total} tickerów "
            f"(czas: {cycle_duration:.1f}s)"
        )
    
    def _print_stats(self):
        """Drukuje statystyki daemona."""
        uptime = datetime.now(timezone.utc) - self.stats["start_time"]
        uptime_str = str(uptime).split('.')[0]  # Usuń mikrosekundy
        
        logger.info(
            f"\n📊 STATYSTYKI DAEMONA:\n"
            f"   Uptime: {uptime_str}\n"
            f"   Cykle: {self.stats['updates_count']}\n"
            f"   OHLCV zapisane: {self.stats['ohlcv_saved']}\n"
            f"   Tickers zapisane: {self.stats['tickers_saved']}\n"
            f"   Błędy: {self.stats['errors_count']}\n"
            f"   Ostatnia aktualizacja: {self.stats['last_update']}\n"
        )
    
    def run(self):
        """Uruchamia daemon."""
        self.running = True
        logger.info("🚀 Data Updater Daemon uruchomiony")
        logger.info(f"   Interwał: {self.update_interval}s")
        logger.info(f"   Giełdy: {', '.join(self.exchanges)}")
        logger.info(f"   Symbole: {', '.join(self.symbols)}")
        logger.info("   Naciśnij Ctrl+C aby zatrzymać\n")
        
        try:
            while self.running:
                try:
                    self._update_cycle()
                    
                    # Pokaż statystyki co 10 cykli
                    if self.stats["updates_count"] % 10 == 0:
                        self._print_stats()
                    
                except Exception as e:
                    logger.error(f"Błąd w cyklu aktualizacji: {e}")
                    logger.debug(traceback.format_exc())
                    self.stats["errors_count"] += 1
                
                # Czekaj do następnego cyklu
                if self.running:
                    time.sleep(self.update_interval)
                    
        except KeyboardInterrupt:
            logger.info("Otrzymano sygnał przerwania")
        finally:
            logger.info("Zatrzymywanie daemona...")
            self._print_stats()
            logger.info("✅ Daemon zatrzymany")


def main():
    parser = argparse.ArgumentParser(
        description="Data Updater Daemon - aktualizuje OHLCV i tickers co 1 minutę"
    )
    
    parser.add_argument(
        "--symbols",
        default="BTC/USDC",
        help="Symbole do aktualizacji (oddzielone przecinkami, domyślnie: BTC/USDC)"
    )
    
    parser.add_argument(
        "--exchanges",
        default="binance,dydx",
        help="Giełdy (oddzielone przecinkami, domyślnie: binance,dydx)"
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Interwał aktualizacji w sekundach (domyślnie: 60)"
    )
    
    parser.add_argument(
        "--database-url",
        default=None,
        help="URL bazy danych (domyślnie: z .env lub SQLite)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Szczegółowe logowanie"
    )
    
    args = parser.parse_args()
    
    # Konfiguruj logowanie
    logger.remove()
    level = "DEBUG" if args.verbose else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=level,
        colorize=True
    )
    
    # Log do pliku
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "data_updater_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
    )
    
    # Parsuj argumenty
    symbols = [s.strip() for s in args.symbols.split(",")]
    exchanges = [e.strip() for e in args.exchanges.split(",")]
    
    # Utwórz i uruchom daemon
    daemon = DataUpdaterDaemon(
        symbols=symbols,
        exchanges=exchanges,
        update_interval=args.interval,
        database_url=args.database_url
    )
    
    daemon.run()


if __name__ == "__main__":
    main()

