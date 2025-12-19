#!/usr/bin/env python3
"""
GDELT Sentiment Collector Daemon
=================================
Skrypt działający w tle, który zbiera dane sentymentu z GDELT API
i zapisuje je do tabeli gdelt_sentiment.

Użycie:
    python scripts/gdelt_sentiment_daemon.py
    python scripts/gdelt_sentiment_daemon.py --interval=60 --query="bitcoin OR cryptocurrency"

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
                value = value.strip('"').strip("'")
                os.environ.setdefault(key, value)

from loguru import logger
from src.database.manager import DatabaseManager
from src.collectors.sentiment.gdelt_collector import GDELTCollector

# Mapowanie krajów na języki
COUNTRY_LANGUAGES = {
    "US": "en",
    "GB": "en",
    "CN": "zh",
    "JP": "ja",
    "KR": "ko",
    "DE": "de",
    "RU": "ru",
    "SG": "en",
    "AU": "en",
    "FR": "fr",
    "ES": "es",
    "IT": "it",
    "NL": "nl",
    "CA": "en",
    "BR": "pt",
    "IN": "en",
    "HK": "zh",
    "CH": "de",
    "AE": "ar",
    "PL": "pl",
}

COUNTRY_NAMES = {
    "US": "United States",
    "GB": "United Kingdom",
    "CN": "China",
    "JP": "Japan",
    "KR": "South Korea",
    "DE": "Germany",
    "RU": "Russia",
    "SG": "Singapore",
    "AU": "Australia",
    "FR": "France",
    "ES": "Spain",
    "IT": "Italy",
    "NL": "Netherlands",
    "CA": "Canada",
    "BR": "Brazil",
    "IN": "India",
    "HK": "Hong Kong",
    "CH": "Switzerland",
    "AE": "UAE",
    "PL": "Poland",
}


class GDELTSentimentDaemon:
    """
    Daemon do zbierania danych sentymentu z GDELT API.
    """
    
    def __init__(
        self,
        countries: List[str],
        query: str,
        interval: int,
        database_url: Optional[str] = None,
        days_back: int = 1,
        resolution: str = "hour"
    ):
        """
        Inicjalizuje daemon.
        
        Args:
            countries: Lista kodów krajów do monitorowania
            query: Zapytanie wyszukiwania GDELT
            interval: Interwał zbierania danych w sekundach
            database_url: URL bazy danych (opcjonalnie, użyje DATABASE_URL z .env)
            days_back: Ile dni wstecz pobierać dane (domyślnie 1)
            resolution: Rozdzielczość czasowa (hour, day)
        """
        self.countries = countries
        self.query = query
        self.interval = interval
        self.days_back = days_back
        self.resolution = resolution
        self.running = False
        
        # Inicjalizuj bazę danych
        # Użyj DATABASE_URL z .env jeśli nie podano explicite
        if not database_url:
            database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            self.db = DatabaseManager(database_url=database_url)
            # Pokaż bezpieczny URL (bez hasła)
            safe_url = database_url.split('@')[-1] if '@' in database_url else database_url
            logger.info(f"Połączono z bazą danych: {safe_url}")
        else:
            self.db = DatabaseManager()
            logger.info("Używam domyślnej bazy danych (SQLite)")
        
        try:
            self.db.create_tables()
            logger.info("Tabele utworzone/sprawdzone")
        except Exception as e:
            # Jeśli tabele już istnieją, to nie jest błąd
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                logger.info("Tabele już istnieją w bazie danych")
            else:
                logger.warning(f"Ostrzeżenie przy tworzeniu tabel: {e}")
                # Kontynuuj - tabele mogą już istnieć
        
        # Inicjalizuj GDELT collector
        try:
            self.gdelt_collector = GDELTCollector()
            logger.info("GDELTCollector zainicjalizowany")
        except Exception as e:
            logger.error(f"Nie można zainicjalizować GDELTCollector: {e}")
            raise
        
        # Statystyki
        self.stats = {
            "cycles_count": 0,
            "records_saved": 0,
            "errors_count": 0,
            "last_update": None
        }
        
        # Obsługa sygnałów
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Obsługuje sygnały zatrzymania."""
        logger.info(f"Otrzymano sygnał {signum} - zatrzymywanie...")
        self.running = False
    
    def _collect_and_save(self, country: str) -> bool:
        """
        Zbiera dane sentymentu dla danego kraju i zapisuje do bazy.
        
        Args:
            country: Kod kraju
            
        Returns:
            True jeśli sukces, False w przeciwnym razie
        """
        try:
            country_name = COUNTRY_NAMES.get(country, country)
            language = COUNTRY_LANGUAGES.get(country, "en")
            
            logger.info(f"📊 Zbieram dane GDELT dla {country_name} ({country})...")
            
            # Próba 1: Pobierz dane tone timeseries z GDELT (Timeline API)
            df = self.gdelt_collector.fetch_tone_timeseries(
                query=self.query,
                days_back=self.days_back,
                resolution=self.resolution,
                source_country=country
            )
            
            # Próba 2: Fallback - pobierz globalne artykuły i filtruj po source_country
            if df.empty:
                logger.debug(f"Timeline API nie zwrócił danych dla {country_name}, próbuję fallback z globalnych artykułów...")
                try:
                    # Pobierz globalne artykuły (bez filtrowania po kraju)
                    # GDELT API często nie obsługuje sourcecountry: dla wielu krajów
                    articles_df = self.gdelt_collector.fetch_articles(
                        query=self.query,
                        days_back=self.days_back,
                        max_records=500,  # Więcej rekordów, bo filtrujemy później
                        source_country=None  # Globalne zapytanie
                    )
                    
                    # Filtruj artykuły po kraju źródłowym
                    if not articles_df.empty and 'source_country' in articles_df.columns:
                        country_articles = articles_df[articles_df['source_country'] == country].copy()
                        
                        if not country_articles.empty and 'timestamp' in country_articles.columns and 'tone' in country_articles.columns:
                            # Agreguj do przedziałów czasowych (hour lub day)
                            country_articles['timestamp'] = pd.to_datetime(country_articles['timestamp'])
                            country_articles = country_articles.set_index('timestamp').sort_index()
                            
                            # Resample do odpowiedniej rozdzielczości
                            if self.resolution == "hour":
                                freq = "1H"
                            else:  # day
                                freq = "1D"
                            
                            # Agreguj tone (średnia) i volume (liczba artykułów)
                            df = country_articles['tone'].resample(freq).mean().to_frame()
                            df['volume'] = country_articles['tone'].resample(freq).count()
                            
                            logger.info(f"Fallback: Znaleziono {len(country_articles)} artykułów z {country_name}, agregowano do {len(df)} punktów czasowych")
                        else:
                            logger.debug(f"⚠️  Brak artykułów z source_country={country} w globalnych wynikach")
                    else:
                        logger.debug(f"⚠️  Brak kolumny 'source_country' w wynikach lub brak artykułów")
                except Exception as e:
                    logger.debug(f"Błąd fallback dla {country_name}: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
            
            if df.empty:
                logger.warning(f"⚠️  Brak danych GDELT dla {country_name} (ani Timeline, ani artykuły)")
                return False
            
            # Sprawdź czy mamy kolumny tone i volume
            if 'tone' not in df.columns:
                logger.warning(f"⚠️  Brak kolumny 'tone' w danych dla {country_name}")
                return False
            
            # Zapisz do bazy
            saved = self.db.save_gdelt_sentiment(
                df=df,
                query=self.query,
                region=country,
                language=language,
                resolution=self.resolution
            )
            
            if saved > 0:
                self.stats["records_saved"] += saved
                logger.success(
                    f"✅ Zapisano {saved} rekordów GDELT dla {country_name} "
                    f"(okres: {df.index.min()} → {df.index.max()})"
                )
                return True
            else:
                logger.warning(f"⚠️  Nie zapisano żadnych rekordów dla {country_name}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Błąd podczas zbierania danych dla {country}: {e}")
            logger.debug(traceback.format_exc())
            self.stats["errors_count"] += 1
            return False
    
    def run(self):
        """Główna pętla daemona."""
        logger.info("=" * 60)
        logger.info("🚀 GDELT Sentiment Daemon uruchomiony")
        logger.info("=" * 60)
        logger.info(f"Kraje: {', '.join(self.countries)}")
        logger.info(f"Query: {self.query}")
        logger.info(f"Interwał: {self.interval} sekund")
        logger.info(f"Dni wstecz: {self.days_back}")
        logger.info(f"Rozdzielczość: {self.resolution}")
        logger.info("=" * 60)
        
        self.running = True
        
        while self.running:
            try:
                cycle_start = datetime.now(timezone.utc)
                
                logger.info(f"\n🔄 Cykl #{self.stats['cycles_count'] + 1} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                
                # Zbierz dane dla każdego kraju
                for country in self.countries:
                    self._collect_and_save(country)
                    time.sleep(1)  # Rate limiting między krajami
                
                self.stats["cycles_count"] += 1
                self.stats["last_update"] = cycle_start
                
                # Podsumowanie cyklu
                logger.info(
                    f"✅ Cykl zakończony: {self.stats['records_saved']} rekordów łącznie, "
                    f"{self.stats['errors_count']} błędów"
                )
                
                # Czekaj do następnego cyklu
                if self.running:
                    logger.info(f"⏳ Czekam {self.interval} sekund do następnego cyklu...")
                    time.sleep(self.interval)
                    
            except KeyboardInterrupt:
                logger.info("Otrzymano KeyboardInterrupt - zatrzymywanie...")
                self.running = False
            except Exception as e:
                logger.error(f"❌ Błąd w głównej pętli: {e}")
                logger.debug(traceback.format_exc())
                self.stats["errors_count"] += 1
                if self.running:
                    time.sleep(60)  # Czekaj 1 minutę przed ponowną próbą
        
        logger.info("=" * 60)
        logger.info("🛑 GDELT Sentiment Daemon zatrzymany")
        logger.info("=" * 60)
        logger.info(f"Statystyki końcowe:")
        logger.info(f"  Cykle: {self.stats['cycles_count']}")
        logger.info(f"  Zapisane rekordy: {self.stats['records_saved']}")
        logger.info(f"  Błędy: {self.stats['errors_count']}")
        logger.info("=" * 60)


def main():
    """Główna funkcja."""
    parser = argparse.ArgumentParser(
        description="GDELT Sentiment Collector Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--countries",
        default="US,CN,JP,KR,DE,GB",
        help="Lista kodów krajów oddzielonych przecinkami (domyślnie: US,CN,JP,KR,DE,GB)"
    )
    parser.add_argument(
        "--query",
        default="bitcoin OR cryptocurrency",
        help="Zapytanie wyszukiwania GDELT (domyślnie: bitcoin OR cryptocurrency)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,  # 1 godzina
        help="Interwał zbierania danych w sekundach (domyślnie: 3600 = 1h)"
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=1,
        help="Ile dni wstecz pobierać dane (domyślnie: 1)"
    )
    parser.add_argument(
        "--resolution",
        default="hour",
        choices=["hour", "day"],
        help="Rozdzielczość czasowa (domyślnie: hour)"
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="URL bazy danych (domyślnie: DATABASE_URL z .env)"
    )
    
    args = parser.parse_args()
    
    # Parsuj kraje
    countries = [c.strip() for c in args.countries.split(",")]
    
    # Konfiguruj logowanie
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Log do pliku
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"gdelt_sentiment_daemon_{datetime.now().strftime('%Y%m%d')}.log"
    logger.add(
        log_file,
        rotation="00:00",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG"
    )
    
    # Utwórz i uruchom daemon
    try:
        daemon = GDELTSentimentDaemon(
            countries=countries,
            query=args.query,
            interval=args.interval,
            database_url=args.database_url,
            days_back=args.days_back,
            resolution=args.resolution
        )
        daemon.run()
    except Exception as e:
        logger.error(f"Błąd uruchomienia daemona: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

