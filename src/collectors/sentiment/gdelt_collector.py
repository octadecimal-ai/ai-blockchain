"""
GDELT Collector
===============
Kolektor danych z GDELT (Global Database of Events, Language, and Tone).

GDELT monitoruje media z całego świata w 65+ językach i dostarcza:
- Tone/sentiment artykułów
- Geolokalizację źródeł
- Timestamp publikacji
- Wolumen pokrycia medialnego

Źródło: https://www.gdeltproject.org/
API Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/

Bez klucza API - GDELT jest w pełni darmowy i otwarty.
"""

import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path
import time
import json
from loguru import logger

try:
    from io import StringIO
    STRINGIO_AVAILABLE = True
except ImportError:
    STRINGIO_AVAILABLE = False


class GDELTCollector:
    """
    Kolektor danych z GDELT API.
    
    Obsługuje:
    - Pobieranie artykułów związanych z kryptowalutami
    - Filtrowanie po kraju/języku źródła
    - Agregacja tone/sentiment w oknach czasowych
    - Cache'owanie wyników
    
    Przykład użycia:
    
        collector = GDELTCollector()
        
        # Pobierz dane o Bitcoin z ostatnich 7 dni
        df = collector.fetch_articles(
            query="bitcoin OR BTC OR cryptocurrency",
            days_back=7
        )
        
        # Pobierz dane pogrupowane po krajach
        df_by_country = collector.fetch_by_source_country(
            query="bitcoin",
            countries=["US", "CN", "JP", "KR", "DE", "GB"]
        )
    """
    
    # GDELT DOC 2.0 API endpoint
    DOC_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    
    # GDELT GEO 2.0 API endpoint (dla geolokalizacji)
    GEO_API_URL = "https://api.gdeltproject.org/api/v2/geo/geo"
    
    # Mapowanie kodów krajów na nazwy (najważniejsze dla crypto)
    COUNTRY_NAMES = {
        "US": "United States",
        "CN": "China", 
        "JP": "Japan",
        "KR": "South Korea",
        "DE": "Germany",
        "GB": "United Kingdom",
        "RU": "Russia",
        "IN": "India",
        "BR": "Brazil",
        "AU": "Australia",
        "CA": "Canada",
        "SG": "Singapore",
        "HK": "Hong Kong",
        "CH": "Switzerland",
        "NL": "Netherlands",
        "FR": "France",
        "AE": "UAE",
        "ES": "Spain",
        "IT": "Italy",
        "PL": "Poland",
    }
    
    # Mapowanie kodów języków GDELT
    LANGUAGE_CODES = {
        "english": "eng",
        "chinese": "zho", 
        "japanese": "jpn",
        "korean": "kor",
        "german": "deu",
        "russian": "rus",
        "spanish": "spa",
        "french": "fra",
        "portuguese": "por",
        "arabic": "ara",
        "hindi": "hin",
        "polish": "pol",
    }
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Inicjalizuje kolektor GDELT.
        
        Args:
            cache_dir: Katalog do cache'owania wyników (opcjonalnie)
        """
        self.cache_dir = cache_dir or Path("data/cache/gdelt")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Rate limiting - GDELT zaleca max 1 request/sec
        self.last_request_time = 0
        self.min_request_interval = 1.0  # sekundy
        
        logger.info("GDELT Collector zainicjalizowany")
    
    def _rate_limit(self):
        """Implementacja rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, url: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Wykonuje request do GDELT API z rate limiting.
        
        Args:
            url: URL endpoint
            params: Parametry zapytania
            
        Returns:
            Odpowiedź jako string lub None przy błędzie
        """
        self._rate_limit()
        
        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            
            # Sprawdź czy odpowiedź to JSON
            content_type = response.headers.get('content-type', '').lower()
            if 'application/json' not in content_type:
                # Sprawdź czy to błąd HTML lub tekst
                text_preview = response.text[:500]
                if 'error' in text_preview.lower() or '<html' in text_preview.lower():
                    logger.warning(f"GDELT zwrócił nie-JSON odpowiedź (pierwsze 200 znaków): {text_preview[:200]}")
                    return None
            
            return response.text
        except requests.exceptions.HTTPError as e:
            # Loguj szczegóły odpowiedzi przy błędzie HTTP
            try:
                error_text = e.response.text[:500] if hasattr(e, 'response') and e.response else str(e)
                logger.error(f"GDELT HTTP error {e.response.status_code if hasattr(e, 'response') else 'N/A'}: {error_text[:200]}")
            except:
                logger.error(f"GDELT HTTP error: {e}")
            return None
        except requests.exceptions.Timeout:
            logger.error("GDELT request timeout")
            return None
        except Exception as e:
            logger.error(f"GDELT request error: {e}")
            return None
    
    def fetch_articles(
        self,
        query: str = "bitcoin OR cryptocurrency",
        days_back: int = 7,
        max_records: int = 250,
        source_country: Optional[str] = None,
        source_language: Optional[str] = None,
        sort: str = "DateDesc"
    ) -> pd.DataFrame:
        """
        Pobiera artykuły z GDELT DOC API.
        
        Args:
            query: Zapytanie wyszukiwania (obsługuje OR, AND, NOT)
            days_back: Ile dni wstecz szukać (max 90 dla free tier)
            max_records: Maksymalna liczba rekordów (max 250)
            source_country: Filtr kraju źródła (np. "US", "CN")
            source_language: Filtr języka (np. "english", "chinese")
            sort: Sortowanie - "DateDesc", "DateAsc", "ToneDesc", "ToneAsc"
            
        Returns:
            DataFrame z artykułami i ich tone/sentiment
        """
        # Przygotuj zakres czasowy
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        
        # Format daty dla GDELT: YYYYMMDDHHMMSS
        start_str = start_date.strftime("%Y%m%d%H%M%S")
        end_str = end_date.strftime("%Y%m%d%H%M%S")
        
        # GDELT API wymaga, żeby zapytania z OR były otoczone nawiasami
        # Normalizuj query: jeśli zawiera OR i nie ma nawiasów, dodaj je
        normalized_query = query
        if " OR " in query.upper() and not (query.strip().startswith("(") and query.strip().endswith(")")):
            # Sprawdź czy już nie jest w nawiasach (może być część większego wyrażenia)
            if not (query.strip().startswith("(")):
                normalized_query = f"({query})"
        
        # Buduj zapytanie
        params = {
            "query": normalized_query,
            "mode": "ArtList",  # Lista artykułów
            "format": "json",
            "maxrecords": min(max_records, 250),
            "startdatetime": start_str,
            "enddatetime": end_str,
            "sort": sort,
        }
        
        # Dodaj filtry jeśli podano
        if source_country:
            params["query"] += f" sourcecountry:{source_country}"
        if source_language:
            lang_code = self.LANGUAGE_CODES.get(source_language.lower(), source_language)
            params["query"] += f" sourcelang:{lang_code}"
        
        logger.info(f"GDELT query: {params['query'][:100]}... ({days_back} dni)")
        
        # Wykonaj request
        response = self._make_request(self.DOC_API_URL, params)
        
        if not response:
            return pd.DataFrame()
        
        # Parsuj JSON
        try:
            data = json.loads(response)
            articles = data.get("articles", [])
        except json.JSONDecodeError as e:
            # Loguj szczegóły odpowiedzi przy błędzie parsowania
            response_preview = response[:500] if response else "Brak odpowiedzi"
            
            # Jeśli to błąd "Invalid/Unsupported Country", loguj jako WARNING zamiast ERROR
            if "Invalid/Unsupported Country" in response_preview:
                logger.warning(f"GDELT: Kraj nie jest obsługiwany. Response: {response_preview[:200]}")
            else:
                logger.error(f"GDELT JSON parse error: {e}. Response text (pierwsze 500 znaków): {response_preview}")
            return pd.DataFrame()
        
        if not articles:
            logger.warning(f"Brak artykułów dla query: {query}")
            return pd.DataFrame()
        
        # Konwertuj na DataFrame
        records = []
        for article in articles:
            records.append({
                "url": article.get("url", ""),
                "title": article.get("title", ""),
                "seendate": article.get("seendate", ""),
                "source": article.get("domain", ""),
                "source_country": article.get("sourcecountry", ""),
                "language": article.get("language", ""),
                "tone": article.get("tone", 0),  # -100 do +100
                "positive_score": article.get("positivescore", 0),
                "negative_score": article.get("negativescore", 0),
                "polarity": article.get("polarity", 0),
                "activity_density": article.get("activitydensity", 0),
                "self_density": article.get("selfdensity", 0),
                "word_count": article.get("wordcount", 0),
            })
        
        df = pd.DataFrame(records)
        
        # Konwertuj timestamp
        if "seendate" in df.columns and not df.empty:
            df["timestamp"] = pd.to_datetime(df["seendate"], format="%Y%m%dT%H%M%SZ", errors="coerce")
            df.drop(columns=["seendate"], inplace=True)
        
        logger.success(f"Pobrano {len(df)} artykułów z GDELT")
        return df
    
    def fetch_by_source_country(
        self,
        query: str = "bitcoin OR cryptocurrency",
        countries: List[str] = None,
        days_back: int = 7,
        max_per_country: int = 100
    ) -> pd.DataFrame:
        """
        Pobiera artykuły pogrupowane po krajach źródłowych.
        
        Args:
            query: Zapytanie wyszukiwania
            countries: Lista kodów krajów (domyślnie top crypto markets)
            days_back: Ile dni wstecz
            max_per_country: Max artykułów per kraj
            
        Returns:
            DataFrame z artykułami ze wszystkich krajów
        """
        if countries is None:
            # Domyślne kraje - główne rynki crypto
            countries = ["US", "CN", "JP", "KR", "DE", "GB", "RU", "SG"]
        
        all_articles = []
        
        for country in countries:
            logger.info(f"Pobieram artykuły z {self.COUNTRY_NAMES.get(country, country)}...")
            
            df = self.fetch_articles(
                query=query,
                days_back=days_back,
                max_records=max_per_country,
                source_country=country
            )
            
            if not df.empty:
                all_articles.append(df)
            
            # Dodatkowe rate limiting między krajami
            time.sleep(0.5)
        
        if not all_articles:
            return pd.DataFrame()
        
        combined = pd.concat(all_articles, ignore_index=True)
        logger.success(f"Pobrano łącznie {len(combined)} artykułów z {len(countries)} krajów")
        
        return combined
    
    def fetch_tone_timeseries(
        self,
        query: str = "bitcoin",
        days_back: int = 30,
        resolution: str = "day",
        source_country: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Pobiera szereg czasowy tone/sentiment z GDELT.
        
        Args:
            query: Zapytanie wyszukiwania
            days_back: Ile dni wstecz
            resolution: "day" lub "hour" (uwaga: hour tylko dla ostatnich 7 dni)
            source_country: Opcjonalny filtr kraju
            
        Returns:
            DataFrame z agregowanym tone w czasie
        """
        # Dla timeline używamy innego mode
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        
        # GDELT API wymaga, żeby zapytania z OR były otoczone nawiasami
        normalized_query = query
        if " OR " in query.upper() and not (query.strip().startswith("(") and query.strip().endswith(")")):
            if not (query.strip().startswith("(")):
                normalized_query = f"({query})"
        
        params = {
            "query": normalized_query,
            "mode": "TimelineTone",  # Timeline tone
            "format": "json",
            "startdatetime": start_date.strftime("%Y%m%d%H%M%S"),
            "enddatetime": end_date.strftime("%Y%m%d%H%M%S"),
            "timelinesmooth": 0,  # Bez wygładzania
        }
        
        if source_country:
            params["query"] += f" sourcecountry:{source_country}"
        
        logger.info(f"GDELT timeline query: {query} ({days_back} dni)")
        
        response = self._make_request(self.DOC_API_URL, params)
        
        if not response:
            return pd.DataFrame()
        
        try:
            data = json.loads(response)
            timeline = data.get("timeline", [])
        except json.JSONDecodeError as e:
            # Loguj szczegóły odpowiedzi przy błędzie parsowania
            response_preview = response[:500] if response else "Brak odpowiedzi"
            
            # Jeśli to błąd "Invalid/Unsupported Country", loguj jako WARNING zamiast ERROR
            if "Invalid/Unsupported Country" in response_preview:
                logger.warning(f"GDELT timeline: Kraj nie jest obsługiwany. Response: {response_preview[:200]}")
            else:
                logger.error(f"GDELT timeline JSON parse error: {e}. Response text (pierwsze 500 znaków): {response_preview}")
            return pd.DataFrame()
        
        if not timeline or len(timeline) == 0:
            logger.warning(f"Brak danych timeline dla: {query}")
            return pd.DataFrame()
        
        # Timeline zwraca listę serii, bierzemy pierwszą
        series_data = timeline[0].get("data", [])
        
        records = []
        for point in series_data:
            records.append({
                "timestamp": pd.to_datetime(point.get("date", ""), errors="coerce"),
                "tone": point.get("value", 0),
                "volume": point.get("norm", 0),  # Znormalizowany wolumen
            })
        
        df = pd.DataFrame(records)
        df = df.dropna(subset=["timestamp"])
        df = df.set_index("timestamp").sort_index()
        
        logger.success(f"Pobrano {len(df)} punktów timeline")
        return df
    
    def fetch_volume_timeseries(
        self,
        query: str = "bitcoin",
        days_back: int = 30,
        source_country: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Pobiera szereg czasowy wolumenu pokrycia medialnego.
        
        Args:
            query: Zapytanie wyszukiwania
            days_back: Ile dni wstecz
            source_country: Opcjonalny filtr kraju
            
        Returns:
            DataFrame z wolumenem artykułów w czasie
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        
        # GDELT API wymaga, żeby zapytania z OR były otoczone nawiasami
        normalized_query = query
        if " OR " in query.upper() and not (query.strip().startswith("(") and query.strip().endswith(")")):
            if not (query.strip().startswith("(")):
                normalized_query = f"({query})"
        
        params = {
            "query": normalized_query,
            "mode": "TimelineVol",  # Timeline volume
            "format": "json",
            "startdatetime": start_date.strftime("%Y%m%d%H%M%S"),
            "enddatetime": end_date.strftime("%Y%m%d%H%M%S"),
            "timelinesmooth": 0,
        }
        
        if source_country:
            params["query"] += f" sourcecountry:{source_country}"
        
        response = self._make_request(self.DOC_API_URL, params)
        
        if not response:
            return pd.DataFrame()
        
        try:
            data = json.loads(response)
            timeline = data.get("timeline", [])
        except json.JSONDecodeError:
            return pd.DataFrame()
        
        if not timeline:
            return pd.DataFrame()
        
        series_data = timeline[0].get("data", [])
        
        records = []
        for point in series_data:
            records.append({
                "timestamp": pd.to_datetime(point.get("date", ""), errors="coerce"),
                "volume": point.get("value", 0),
                "volume_norm": point.get("norm", 0),
            })
        
        df = pd.DataFrame(records)
        df = df.dropna(subset=["timestamp"])
        df = df.set_index("timestamp").sort_index()
        
        return df
    
    def fetch_multi_country_timeseries(
        self,
        query: str = "bitcoin OR cryptocurrency",
        countries: List[str] = None,
        days_back: int = 30,
        metric: str = "tone"  # "tone" lub "volume"
    ) -> pd.DataFrame:
        """
        Pobiera szeregi czasowe dla wielu krajów.
        
        Kluczowa funkcja do analizy propagacji sentymentu!
        
        Args:
            query: Zapytanie wyszukiwania
            countries: Lista kodów krajów
            days_back: Ile dni wstecz
            metric: "tone" lub "volume"
            
        Returns:
            DataFrame z kolumnami dla każdego kraju
        """
        if countries is None:
            countries = ["US", "CN", "JP", "KR", "DE", "GB", "RU"]
        
        all_series = {}
        
        for country in countries:
            logger.info(f"Pobieram {metric} timeline dla {country}...")
            
            # Próba 1: Timeline API
            if metric == "tone":
                df = self.fetch_tone_timeseries(
                    query=query,
                    days_back=days_back,
                    source_country=country
                )
                if not df.empty and "tone" in df.columns:
                    all_series[country] = df["tone"]
            else:
                df = self.fetch_volume_timeseries(
                    query=query,
                    days_back=days_back,
                    source_country=country
                )
                if not df.empty and "volume" in df.columns:
                    all_series[country] = df["volume"]
            
            # Próba 2: Fallback - agregacja z artykułów
            if country not in all_series:
                logger.info(f"Timeline niedostępny dla {country}, próbuję fallback...")
                df_fallback = self._fetch_aggregated_from_articles(
                    query=query,
                    source_country=country,
                    days_back=days_back,
                    metric=metric
                )
                if not df_fallback.empty:
                    all_series[country] = df_fallback[metric]
            
            time.sleep(1.0)  # Rate limiting
        
        if not all_series:
            return pd.DataFrame()
        
        # Połącz wszystkie serie w jeden DataFrame
        combined = pd.DataFrame(all_series)
        combined = combined.sort_index()
        
        # Wypełnij brakujące wartości interpolacją
        combined = combined.interpolate(method="time", limit=3)
        
        logger.success(f"Pobrano {metric} timeseries dla {len(all_series)} krajów")
        return combined
    
    def _fetch_aggregated_from_articles(
        self,
        query: str,
        source_country: str,
        days_back: int = 7,
        metric: str = "tone"
    ) -> pd.DataFrame:
        """
        Fallback: Pobiera artykuły i agreguje do dziennych wartości.
        
        Używane gdy Timeline API nie zwraca danych dla danego kraju.
        """
        df = self.fetch_articles(
            query=query,
            days_back=days_back,
            max_records=250,
            source_country=source_country
        )
        
        if df.empty or "timestamp" not in df.columns:
            return pd.DataFrame()
        
        # Agreguj do dni
        df["date"] = df["timestamp"].dt.date
        
        if metric == "tone":
            aggregated = df.groupby("date").agg({
                "tone": "mean"
            })
        else:
            aggregated = df.groupby("date").agg({
                "tone": "count"
            }).rename(columns={"tone": "volume"})
        
        aggregated.index = pd.to_datetime(aggregated.index)
        
        if not aggregated.empty:
            logger.info(f"Fallback dla {source_country}: {len(aggregated)} punktów")
        
        return aggregated
    
    def aggregate_sentiment_hourly(
        self,
        df: pd.DataFrame,
        tone_column: str = "tone"
    ) -> pd.DataFrame:
        """
        Agreguje sentiment do przedziałów godzinowych.
        
        Args:
            df: DataFrame z artykułami (musi mieć kolumnę 'timestamp')
            tone_column: Nazwa kolumny z tone
            
        Returns:
            DataFrame z agregowanym sentiment per godzina
        """
        if df.empty or tone_column not in df.columns:
            return pd.DataFrame()
        
        df = df.copy()
        df["hour"] = df["timestamp"].dt.floor("H")
        
        aggregated = df.groupby("hour").agg({
            tone_column: ["mean", "std", "count"],
            "source_country": lambda x: x.mode().iloc[0] if len(x) > 0 else None
        }).reset_index()
        
        # Spłaszcz kolumny
        aggregated.columns = ["timestamp", "tone_mean", "tone_std", "article_count", "dominant_country"]
        aggregated = aggregated.set_index("timestamp")
        
        return aggregated


# === Przykład użycia ===
if __name__ == "__main__":
    import sys
    
    # Konfiguracja loggera
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    # Inicjalizacja kolektora
    collector = GDELTCollector()
    
    print("\n" + "="*60)
    print("🌍 GDELT COLLECTOR - TEST")
    print("="*60)
    
    # Test 1: Pobierz artykuły o Bitcoin
    print("\n📰 Test 1: Artykuły o Bitcoin (ostatnie 3 dni)")
    df = collector.fetch_articles(
        query="bitcoin OR BTC",
        days_back=3,
        max_records=50
    )
    
    if not df.empty:
        print(f"   Pobrano: {len(df)} artykułów")
        print(f"   Średni tone: {df['tone'].mean():.2f}")
        print(f"   Kraje źródłowe: {df['source_country'].value_counts().head()}")
    
    # Test 2: Porównanie krajów
    print("\n🌐 Test 2: Porównanie sentymentu między krajami")
    df_countries = collector.fetch_by_source_country(
        query="bitcoin",
        countries=["US", "CN", "JP", "DE"],
        days_back=3,
        max_per_country=30
    )
    
    if not df_countries.empty:
        country_sentiment = df_countries.groupby("source_country")["tone"].mean()
        print(f"   Sentiment per kraj:")
        for country, tone in country_sentiment.items():
            print(f"   {country}: {tone:+.2f}")
    
    # Test 3: Timeline
    print("\n📈 Test 3: Timeline sentymentu (7 dni)")
    df_timeline = collector.fetch_tone_timeseries(
        query="bitcoin",
        days_back=7
    )
    
    if not df_timeline.empty:
        print(f"   Punkty danych: {len(df_timeline)}")
        print(f"   Zakres tone: {df_timeline['tone'].min():.2f} do {df_timeline['tone'].max():.2f}")
    
    # Test 4: Multi-country timeseries
    print("\n🔄 Test 4: Multi-country timeseries (do analizy propagacji)")
    df_multi = collector.fetch_multi_country_timeseries(
        query="bitcoin",
        countries=["US", "CN", "JP"],
        days_back=7,
        metric="tone"
    )
    
    if not df_multi.empty:
        print(f"   Kraje: {list(df_multi.columns)}")
        print(f"   Punkty czasowe: {len(df_multi)}")
        print(f"\n   Pierwsze 5 wierszy:")
        print(df_multi.head())
    
    print("\n" + "="*60)
    print("✅ Testy zakończone!")
    print("="*60)
