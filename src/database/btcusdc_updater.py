"""
BTC/USDC Data Updater
=====================
Mechanizm automatycznej aktualizacji danych BTC/USDC w bazie danych.
Uruchamia się w pętli i aktualizuje dane co określony interwał.
"""

import os
import sys
import time
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from loguru import logger

# Dodaj ścieżkę projektu
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.database.btcusdc_loader import BTCUSDCDataLoader


class BTCUSDCUpdater:
    """
    Klasa do automatycznej aktualizacji danych BTC/USDC.
    
    Działa w pętli i aktualizuje dane co określony interwał czasu.
    """
    
    def __init__(
        self,
        update_interval: int = 60,  # sekundy
        database_url: Optional[str] = None,
        use_timescale: bool = False
    ):
        """
        Inicjalizacja updatera.
        
        Args:
            update_interval: Interwał aktualizacji w sekundach (domyślnie 60 = 1 minuta)
            database_url: URL bazy danych
            use_timescale: Czy użyć TimescaleDB
        """
        self.update_interval = update_interval
        self.running = False
        self.loader = BTCUSDCDataLoader(
            database_url=database_url,
            use_timescale=use_timescale
        )
        
        # Obsługa sygnałów do graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"BTCUSDCUpdater zainicjalizowany (interwał: {update_interval}s)")
    
    def _signal_handler(self, signum, frame):
        """Obsługa sygnałów do zatrzymania updatera."""
        logger.info(f"Otrzymano sygnał {signum}, zatrzymuję updater...")
        self.running = False
    
    def update_once(self) -> bool:
        """
        Wykonuje jedną aktualizację danych.
        
        Returns:
            True jeśli aktualizacja się powiodła
        """
        try:
            logger.info("Aktualizuję dane BTC/USDC...")
            count = self.loader.update_latest_data(days_back=1)
            
            if count > 0:
                logger.success(f"Zaktualizowano {count} świec")
            else:
                logger.info("Brak nowych danych do aktualizacji")
            
            latest = self.loader.get_latest_timestamp()
            if latest:
                logger.info(f"Ostatnia świeca w bazie: {latest}")
            
            return True
        except Exception as e:
            logger.error(f"Błąd podczas aktualizacji: {e}")
            return False
    
    def run(self, daemon: bool = False):
        """
        Uruchamia pętlę aktualizacji.
        
        Args:
            daemon: Czy uruchomić jako daemon (w tle)
        """
        if daemon:
            # Fork do tła (tylko na Unix)
            try:
                pid = os.fork()
                if pid > 0:
                    # Proces rodzicielski
                    logger.info(f"Updater uruchomiony jako daemon (PID: {pid})")
                    return
            except OSError:
                logger.error("Nie można uruchomić jako daemon (wymaga Unix)")
                return
        
        self.running = True
        logger.info(f"🚀 BTC/USDC Updater uruchomiony (interwał: {self.update_interval}s)")
        logger.info("Naciśnij Ctrl+C aby zatrzymać")
        
        # Pierwsza aktualizacja od razu
        self.update_once()
        
        # Pętla główna
        while self.running:
            try:
                time.sleep(self.update_interval)
                if self.running:
                    self.update_once()
            except KeyboardInterrupt:
                logger.info("Otrzymano przerwanie, zatrzymuję...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Błąd w pętli głównej: {e}")
                # Kontynuuj mimo błędu
                time.sleep(self.update_interval)
        
        logger.info("✅ BTC/USDC Updater zatrzymany")


def main():
    """Główna funkcja do uruchomienia z linii poleceń."""
    import argparse
    
    parser = argparse.ArgumentParser(description="BTC/USDC Data Updater")
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Interwał aktualizacji w sekundach (domyślnie: 60)'
    )
    parser.add_argument(
        '--daemon',
        action='store_true',
        help='Uruchom jako daemon (w tle)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Wykonaj jedną aktualizację i zakończ'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Szczegółowe logi'
    )
    
    args = parser.parse_args()
    
    # Konfiguracja loggera
    logger.remove()
    level = "DEBUG" if args.verbose else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level=level,
        colorize=True
    )
    
    # Załaduj .env
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    # Inicjalizacja
    database_url = os.getenv('DATABASE_URL')
    use_timescale = os.getenv('USE_TIMESCALE', 'false').lower() == 'true'
    
    updater = BTCUSDCUpdater(
        update_interval=args.interval,
        database_url=database_url,
        use_timescale=use_timescale
    )
    
    if args.once:
        # Jedna aktualizacja i koniec
        success = updater.update_once()
        sys.exit(0 if success else 1)
    else:
        # Pętla ciągła
        updater.run(daemon=args.daemon)


if __name__ == "__main__":
    main()

