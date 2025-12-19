#!/usr/bin/env python3
"""
LLM Sentiment Collector Daemon
===============================
Skrypt działający w tle, który zbiera dane sentymentu z Reddit/Twitter (główne źródła)
i analizuje je używając LLM. GDELT używany tylko jako fallback.

Użycie:
    python scripts/llm_sentiment_daemon.py
    python scripts/llm_sentiment_daemon.py --interval=600 --symbols=BTC/USDC

Autor: AI Assistant
Data: 2025-12-18
"""

import os
import sys
import time
import signal
import argparse
import json
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
from src.database.manager import DatabaseManager

# Spróbuj zaimportować web search engine
try:
    from src.utils.web_search import WebSearchEngine
    WEB_SEARCH_AVAILABLE = True
except ImportError:
    WEB_SEARCH_AVAILABLE = False
    logger.warning("WebSearchEngine niedostępny")

# Spróbuj zaimportować Tavily Query Manager
try:
    from prompts.tavily_queries.query_manager import (
        TavilyQueryManager,
        QueryRotator
    )
    TAVILY_QUERY_MANAGER_AVAILABLE = True
except ImportError:
    TAVILY_QUERY_MANAGER_AVAILABLE = False
    logger.warning("TavilyQueryManager niedostępny - używam generycznych zapytań")

# Spróbuj zaimportować inne kolektory (jako fallback)
# GDELT ma swój osobny daemon (gdelt_sentiment_daemon.py) - nie używamy go tutaj

try:
    from src.collectors.sentiment import TwitterCollector
    TWITTER_AVAILABLE = True
except ImportError:
    TWITTER_AVAILABLE = False

try:
    from src.collectors.sentiment import RedditCollector
    REDDIT_AVAILABLE = True
except ImportError:
    REDDIT_AVAILABLE = False

# Spróbuj zaimportować LLM analyzer
try:
    from src.collectors.sentiment import LLMSentimentAnalyzer
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    logger.error("LLMSentimentAnalyzer niedostępny - zainstaluj: pip install anthropic")

# Mapowanie krajów na języki (używane tylko jako fallback jeśli query_manager niedostępny)
# UWAGA: Jeśli query_manager jest dostępny, używa on REGION_TO_LANGUAGE z query_manager.py
# które ma pełniejsze mapowanie (np. SG -> sg, nie en)
COUNTRY_LANGUAGES = {
    "US": "en",
    "GB": "en",
    "CN": "zh",
    "JP": "ja",
    "KR": "ko",
    "DE": "de",
    "RU": "ru",
    "SG": "sg",  # Poprawione: SG używa sg.txt, nie en.txt
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
}

# Mapowanie krajów na regiony DuckDuckGo (format: 'region-language')
# Używane do wymuszenia lokalizacji i języka wyników wyszukiwania
COUNTRY_TO_DUCKDUCKGO_REGION = {
    "US": "us-en",
    "GB": "uk-en",  # Wielka Brytania
    "CN": "cn-zh",
    "JP": "jp-jp",
    "KR": "kr-ko",
    "DE": "de-de",
    "RU": "ru-ru",
    "SG": "sg-en",  # Singapur - angielski
    "AU": "au-en",
    "FR": "fr-fr",
    "ES": "es-es",
    "IT": "it-it",
    "NL": "nl-nl",
    "CA": "ca-en",
    "BR": "br-pt",
    "IN": "in-en",
    "HK": "hk-zh",
    "CH": "ch-de",  # Szwajcaria - niemiecki
    "AE": "ae-ar",
    "PL": "pl-pl",
}

# Mapowanie krajów na języki dla HTML scraping (format: 'language-COUNTRY')
# Używane jako parametr 'kl' w DuckDuckGo HTML scraping
COUNTRY_TO_DUCKDUCKGO_LANGUAGE = {
    "US": "en-US",
    "GB": "en-GB",
    "CN": "zh-CN",
    "JP": "ja-JP",
    "KR": "ko-KR",
    "DE": "de-DE",
    "RU": "ru-RU",
    "SG": "en-SG",
    "AU": "en-AU",
    "FR": "fr-FR",
    "ES": "es-ES",
    "IT": "it-IT",
    "NL": "nl-NL",
    "CA": "en-CA",
    "BR": "pt-BR",
    "IN": "en-IN",
    "HK": "zh-HK",
    "CH": "de-CH",
    "AE": "ar-AE",
    "PL": "pl-PL",
    "PL": "pl",
}

# Mapowanie kodów krajów na nazwy (dla web search)
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
    "AE": "United Arab Emirates",
    "PL": "Poland",
}


class LLMSentimentDaemon:
    """
    Daemon do zbierania i analizy sentymentu używając LLM.
    """
    
    def __init__(
        self,
        symbols: List[str] = None,
        countries: List[str] = None,
        query: str = "bitcoin OR BTC OR cryptocurrency",
        update_interval: int = 600,  # 10 minut w sekundach (zalecane: 600-1800 dla wystarczającej ilości danych)
        database_url: Optional[str] = None,
        llm_model: str = "claude-3-5-haiku-20241022"  # Claude Haiku - tańszy model ($0.25 vs $3.00/MTok)
    ):
        """
        Inicjalizuje daemon.
        
        Args:
            symbols: Lista symboli do analizy (domyślnie: BTC/USDC)
            countries: Lista krajów do analizy (domyślnie: top crypto markets)
            query: Zapytanie do GDELT
            update_interval: Interwał aktualizacji w sekundach (domyślnie: 600 = 10 min)
            database_url: URL bazy danych (domyślnie: z .env lub SQLite)
            llm_model: Model LLM do użycia
        """
        self.symbols = symbols or ["BTC/USDC"]
        self.countries = countries or ["US", "CN", "JP", "KR", "DE", "GB", "RU", "SG"]
        self.query = query
        self.update_interval = update_interval
        self.running = False
        self.llm_model = llm_model
        
        # Inicjalizuj bazę danych
        if database_url is None:
            database_url = os.getenv('DATABASE_URL')
        
        self.db = DatabaseManager(database_url=database_url)
        self.db.create_tables()
        logger.info(f"Połączono z bazą: {self.db._safe_url()}")
        
        # Inicjalizuj web search engine (główne źródło)
        self.web_search = None
        if WEB_SEARCH_AVAILABLE:
            try:
                # DuckDuckGo jako domyślny provider (z fallback do Tavily/Google)
                # Fallback: najpierw Tavily, potem Google (jeśli DuckDuckGo nie powiedzie się)
                provider = os.getenv('WEB_SEARCH_PROVIDER', 'duckduckgo')  # Domyślnie DuckDuckGo
                
                self.web_search = WebSearchEngine(provider=provider)
                # DuckDuckGo nie wymaga API key, więc sprawdzamy tylko czy web_search został utworzony
                if self.web_search:
                    if provider == 'duckduckgo':
                        logger.info(f"WebSearchEngine zainicjalizowany (provider: {provider} - darmowe, bez API key)")
                    elif self.web_search.api_key:
                        logger.info(f"WebSearchEngine zainicjalizowany (provider: {provider})")
                    else:
                        logger.warning(f"WebSearchEngine niedostępny - brak API key dla {provider}")
                        self.web_search = None
                else:
                    logger.warning(f"WebSearchEngine nie został utworzony dla {provider}")
            except Exception as e:
                logger.warning(f"WebSearchEngine niedostępny: {e}")
                self.web_search = None
        
        # Inicjalizuj Tavily Query Manager dla spersonalizowanych zapytań regionalnych
        self.query_manager = None
        self.query_rotator = None
        if TAVILY_QUERY_MANAGER_AVAILABLE:
            try:
                # Ścieżka do katalogu z zapytaniami (względem root projektu)
                queries_dir = Path(__file__).parent.parent / "prompts" / "tavily_queries"
                self.query_manager = TavilyQueryManager(str(queries_dir))
                self.query_rotator = QueryRotator(self.query_manager, reset_after_hours=24)
                logger.info(f"TavilyQueryManager zainicjalizowany: {queries_dir}")
            except Exception as e:
                logger.warning(f"TavilyQueryManager niedostępny: {e}")
                self.query_manager = None
                self.query_rotator = None
        
        # Inicjalizuj inne kolektory jako fallback (jeśli web search niedostępny)
        # GDELT ma swój osobny daemon (gdelt_sentiment_daemon.py)
        # Nie używamy GDELT w tym daemonie
        
        self.twitter_collector = None
        if TWITTER_AVAILABLE:
            try:
                self.twitter_collector = TwitterCollector()
                logger.info("TwitterCollector zainicjalizowany (fallback)")
            except Exception as e:
                logger.warning(f"TwitterCollector niedostępny: {e}")
        
        self.reddit_collector = None
        if REDDIT_AVAILABLE:
            try:
                self.reddit_collector = RedditCollector()
                logger.info("RedditCollector zainicjalizowany (fallback)")
            except Exception as e:
                logger.warning(f"RedditCollector niedostępny: {e}")
        
        # Inicjalizuj LLM analyzer
        if not LLM_AVAILABLE:
            raise ImportError("LLMSentimentAnalyzer niedostępny - zainstaluj: pip install anthropic")
        
        try:
            self.llm_analyzer = LLMSentimentAnalyzer(
                model=self.llm_model,
                database_url=database_url,
                save_to_db=True
            )
            logger.info(f"LLMSentimentAnalyzer zainicjalizowany: {self.llm_model}")
        except Exception as e:
            logger.error(f"Nie można zainicjalizować LLMSentimentAnalyzer: {e}")
            raise
        
        # Statystyki
        self.stats = {
            "cycles_count": 0,
            "analyses_count": 0,
            "errors_count": 0,
            "total_cost_pln": 0.0,
            "last_update": None
        }
        
        # Obsługa sygnałów
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Obsługuje sygnały zatrzymania."""
        logger.info(f"Otrzymano sygnał {signum} - zatrzymywanie...")
        self.running = False
    
    def _update_web_search_data_in_db(
        self,
        symbol: str,
        region: str,
        timestamp: datetime,
        web_search_query: str,
        web_search_response: str,
        web_search_answer: Optional[str],
        web_search_results_count: int
    ):
        """
        Aktualizuje rekord w bazie danych o dane Web Search.
        
        Args:
            symbol: Symbol kryptowaluty
            region: Kod regionu
            timestamp: Timestamp analizy
            web_search_query: Zapytanie do web search
            web_search_response: Pełna odpowiedź z web search (JSON)
            web_search_answer: Podsumowanie AI z web search
            web_search_results_count: Liczba wyników
        """
        try:
            from src.database.models import LLMSentimentAnalysis
            from sqlalchemy import and_
            
            with self.db.get_session() as session:
                # Znajdź ostatni rekord dla danego symbolu i regionu z tym timestampem
                # (lub najbliższym, jeśli dokładny timestamp nie istnieje)
                record = session.query(LLMSentimentAnalysis).filter(
                    and_(
                        LLMSentimentAnalysis.symbol == symbol,
                        LLMSentimentAnalysis.region == region,
                        LLMSentimentAnalysis.timestamp >= timestamp - timedelta(seconds=30),  # 30 sekund tolerancji
                        LLMSentimentAnalysis.timestamp <= timestamp + timedelta(seconds=30)
                    )
                ).order_by(LLMSentimentAnalysis.timestamp.desc()).first()
                
                if record:
                    # Zaktualizuj dane Web Search
                    record.web_search_query = web_search_query
                    record.web_search_response = web_search_response
                    record.web_search_answer = web_search_answer
                    record.web_search_results_count = web_search_results_count
                    session.commit()
                    logger.debug(f"Zaktualizowano dane Web Search dla {symbol} @ {region} @ {timestamp}")
                else:
                    logger.warning(f"Nie znaleziono rekordu do aktualizacji danych Web Search: {symbol} @ {region} @ {timestamp}")
        except Exception as e:
            logger.error(f"Błąd aktualizacji danych Web Search w bazie: {e}")
            raise
    
    def _execute_web_search(self, search_query: str, country: str) -> Optional[tuple]:
        """
        Wykonuje pojedyncze zapytanie Web Search (fallback gdy QueryManager niedostępny).
        
        Args:
            search_query: Zapytanie wyszukiwania
            country: Kod kraju (dla logowania)
        
        Returns:
            Tuple (texts, web_search_query, web_search_response, web_search_answer, web_search_results_count) lub None
        """
        try:
            logger.info(f"🔍 Wyszukuję w internecie: {search_query}")
            
            # Pobierz region i język dla DuckDuckGo na podstawie kraju
            region = COUNTRY_TO_DUCKDUCKGO_REGION.get(country)
            language = COUNTRY_TO_DUCKDUCKGO_LANGUAGE.get(country)
            
            if region:
                logger.debug(f"   Używam region DuckDuckGo: {region}, język: {language}")
            
            search_results = self.web_search.search(
                query=search_query,
                max_results=5,
                search_depth="basic",
                include_answer=False,
                region=region,  # Region DuckDuckGo (np. 'us-en', 'de-de')
                language=language  # Język dla HTML scraping (np. 'en-US', 'de-DE')
            )
            
            texts = []
            if search_results.get("success") and search_results.get("results"):
                for result in search_results["results"]:
                    if "title" in result:
                        texts.append(result["title"])
                    if "content" in result:
                        texts.append(result["content"])
                    elif "snippet" in result:
                        texts.append(result["snippet"])
                
                logger.info(f"🌐 Web Search: {len(texts)} tekstów z {len(search_results['results'])} wyników")
                
                web_search_query = search_query
                # Zapisz pełną odpowiedź z DuckDuckGo (zawiera results, query, timestamp, etc.)
                web_search_response = json.dumps(search_results, ensure_ascii=False)
                # DuckDuckGo nie zwraca "answer" jak Tavily - zawsze None
                web_search_answer = None
                web_search_results_count = len(search_results.get("results", []))
                
                return (texts, web_search_query, web_search_response, web_search_answer, web_search_results_count)
            else:
                error_msg = search_results.get("error", "Nieznany błąd")
                if "usage limit" in error_msg.lower() or "432" in str(error_msg):
                    logger.warning(f"⚠️  Tavily: Przekroczono limit planu dla {country}")
                else:
                        logger.warning(f"⚠️  Web Search nie zwrócił wyników: {error_msg}")
                return None
                
        except Exception as e:
            error_str = str(e)
            if "432" in error_str or "usage limit" in error_str.lower():
                logger.warning(f"⚠️  Tavily: Przekroczono limit planu dla {country}")
            else:
                logger.error(f"Błąd wyszukiwania Web Search: {e}")
            return None
    
    def _collect_and_analyze(self, country: str, symbol: str) -> bool:
        """
        Zbiera dane sentymentu używając:
        1. Web Search (DuckDuckGo/Google/Serper) - główne źródło - LLM sam pobiera aktualne dane z internetu
        2. Twitter/Reddit (fallback) - jeśli Web Search nie zwróci wyników
        
        GDELT ma swój osobny daemon (gdelt_sentiment_daemon.py) i nie jest używany tutaj.
        
        Args:
            country: Kod kraju
            symbol: Symbol kryptowaluty
            
        Returns:
            True jeśli sukces, False w przeciwnym razie
        """
        try:
            # Użyj query_manager.get_language() jeśli dostępny (ma pełniejsze mapowanie)
            # W przeciwnym razie użyj COUNTRY_LANGUAGES jako fallback
            if self.query_manager:
                language = self.query_manager.get_language(country)
            else:
                language = COUNTRY_LANGUAGES.get(country, "en")
            country_name = COUNTRY_NAMES.get(country, country)
            
            logger.info(f"📊 Zbieram dane sentymentu dla {country} ({language})...")
            
            texts = []
            
            # 1. Główne źródło: Web Search (DuckDuckGo/Google/Serper) - LLM sam pobiera dane z internetu
            tavily_query = None
            tavily_response = None
            tavily_answer = None
            tavily_results_count = 0
            
            # DuckDuckGo nie wymaga API key, więc sprawdzamy tylko czy web_search istnieje
            if self.web_search:
                try:
                    # Użyj spersonalizowanych zapytań regionalnych jeśli dostępne
                    if self.query_rotator and self.query_manager:
                        # Użyj query_manager.get_language() - on ma pełne mapowanie REGION_TO_LANGUAGE
                        # NIE używaj COUNTRY_LANGUAGES z daemona, bo może być nieaktualne
                        lang = self.query_manager.get_language(country)
                        logger.debug(f"   Mapowanie {country} -> {lang} (przez query_manager)")
                        
                        # Pobierz zapytania dla języka (manager ładuje z pliku {lang}.txt)
                        queries = self.query_rotator.get_fresh(lang, count=2)
                        
                        # Jeśli brak zapytań dla języka, spróbuj użyć regionu bezpośrednio
                        if not queries:
                            logger.debug(f"   Brak zapytań dla {lang}, próbuję region {country}")
                            queries = self.query_rotator.get_fresh(country, count=2)
                        
                        if queries:
                            logger.info(f"🔍 Używam {len(queries)} spersonalizowanych zapytań dla {country_name} ({language})")
                            all_results = []
                            all_queries_text = []
                            
                            # Pobierz region i język dla DuckDuckGo na podstawie kraju
                            # UWAGA: language dla promptów (np. 'en', 'sg', 'de') jest już ustawiony wcześniej
                            # Tutaj pobieramy język dla DuckDuckGo HTML scraping (np. 'en-US', 'de-DE')
                            duckduckgo_region = COUNTRY_TO_DUCKDUCKGO_REGION.get(country)
                            duckduckgo_language = COUNTRY_TO_DUCKDUCKGO_LANGUAGE.get(country)
                            
                            # Wykonaj każde zapytanie osobno
                            for query in queries:
                                try:
                                    logger.debug(f"   → {query}")
                                    search_results = self.web_search.search(
                                        query=query,
                                        max_results=3,  # Mniej wyników na zapytanie, ale więcej zapytań
                                        search_depth="basic",
                                        include_answer=False,
                                        region=duckduckgo_region,  # Region DuckDuckGo (np. 'us-en', 'de-de')
                                        language=duckduckgo_language  # Język dla HTML scraping (np. 'en-US', 'de-DE')
                                    )
                                    
                                    if search_results.get("success") and search_results.get("results"):
                                        all_results.extend(search_results.get("results", []))
                                        all_queries_text.append(query)
                                    
                                    # Rate limiting - czekaj między zapytaniami
                                    time.sleep(1.0)
                                    
                                except Exception as e:
                                    logger.debug(f"   Błąd zapytania '{query}': {e}")
                                    continue
                            
                            # Połącz wyniki z wszystkich zapytań
                            if all_results:
                                # Usuń duplikaty (po URL)
                                seen_urls = set()
                                unique_results = []
                                for result in all_results:
                                    url = result.get("url", "")
                                    if url and url not in seen_urls:
                                        seen_urls.add(url)
                                        unique_results.append(result)
                                
                                # Wyciągnij teksty z unikalnych wyników
                                for result in unique_results:
                                    if "title" in result:
                                        texts.append(result["title"])
                                    if "content" in result:
                                        texts.append(result["content"])
                                    elif "snippet" in result:
                                        texts.append(result["snippet"])
                                
                                logger.info(f"🌐 Web Search: {len(texts)} tekstów z {len(unique_results)} unikalnych wyników ({len(all_queries_text)} zapytań)")
                                
                                # Zapisz zapytania i odpowiedzi
                                web_search_query = " | ".join(all_queries_text)  # Wszystkie zapytania oddzielone |
                                # Zapisz pełną odpowiedź z wynikami (nie tylko metadane)
                                web_search_response = json.dumps({
                                    "queries": all_queries_text,
                                    "results_count": len(unique_results),
                                    "total_results": len(all_results),
                                    "results": unique_results  # Dodaj pełne wyniki
                                }, ensure_ascii=False)
                                web_search_answer = None  # DuckDuckGo nie zwraca "answer" jak Tavily
                                web_search_results_count = len(unique_results)
                            else:
                                logger.warning(f"⚠️  Web Search: Brak wyników z {len(queries)} zapytań dla {country}")
                                web_search_query = " | ".join(queries)
                                web_search_response = json.dumps({"queries": queries, "results": []}, ensure_ascii=False)
                                web_search_answer = None
                                web_search_results_count = 0
                        else:
                            # Fallback do generycznego zapytania
                            logger.debug(f"Brak spersonalizowanych zapytań dla {country}, używam generycznego")
                            search_query = f"{symbol} cryptocurrency news {country_name}"
                            search_results = self._execute_web_search(search_query, country)
                            if search_results:
                                texts, web_search_query, web_search_response, web_search_answer, web_search_results_count = search_results
                    else:
                        # Fallback: użyj generycznego zapytania jeśli QueryManager niedostępny
                        logger.debug(f"QueryManager niedostępny, używam generycznego zapytania dla {country}")
                        search_query = f"{symbol} cryptocurrency news {country_name}"
                        search_results = self._execute_web_search(search_query, country)
                        if search_results:
                            texts, web_search_query, web_search_response, web_search_answer, web_search_results_count = search_results
                    
                except Exception as e:
                    error_str = str(e)
                    if "432" in error_str or "usage limit" in error_str.lower():
                        logger.warning(f"⚠️  Web Search: Przekroczono limit planu. Używam fallback do Twitter/Reddit dla {country}")
                    else:
                        logger.error(f"Błąd wyszukiwania w internecie: {e}")
                        logger.debug(traceback.format_exc())
                    web_search_query = None
                    web_search_response = None
                    web_search_answer = None
                    web_search_results_count = 0
            
            # 2. Fallback: użyj Twitter/Reddit jeśli Tavily nie zwrócił wystarczającej ilości danych
            # (lub jeśli Tavily zwrócił błąd limitu)
            if len(texts) < 5:
                logger.info(f"📱 Używam Twitter/Reddit jako fallback dla {country} (Web Search: {len(texts)} tekstów)...")
                
                # Reddit
                if self.reddit_collector:
                    try:
                        reddit_posts = self.reddit_collector.get_subreddit_posts(
                            subreddit="cryptocurrency",
                            limit=20  # Zwiększono limit
                        )
                        if reddit_posts and len(reddit_posts) > 0:
                            # Reddit zwraca listę dict, nie DataFrame
                            reddit_texts = [post.get('title', '') for post in reddit_posts if post.get('title')]
                            if reddit_posts[0].get('selftext'):
                                reddit_texts.extend([post.get('selftext', '') for post in reddit_posts if post.get('selftext')])
                            texts.extend(reddit_texts)
                            logger.info(f"📱 Reddit (fallback): {len(reddit_texts)} tekstów z {len(reddit_posts)} postów")
                        else:
                            logger.debug(f"Reddit: brak danych (posts={len(reddit_posts) if reddit_posts else 0})")
                    except Exception as e:
                        logger.warning(f"Reddit niedostępny: {e}")
                
                # Twitter
                if self.twitter_collector and len(texts) < 10:
                    try:
                        tweets = self.twitter_collector.search_tweets(
                            query=f"{symbol} OR cryptocurrency",
                            max_results=20  # Zwiększono limit
                        )
                        if tweets and len(tweets) > 0:
                            # Twitter zwraca listę dict, nie DataFrame
                            twitter_texts = [tweet.get('text', '') for tweet in tweets if tweet.get('text')]
                            texts.extend(twitter_texts)
                            logger.info(f"🐦 Twitter (fallback): {len(twitter_texts)} tekstów z {len(tweets)} tweetów")
                        else:
                            logger.debug(f"Twitter: brak danych (tweets={len(tweets) if tweets else 0})")
                    except Exception as e:
                        logger.warning(f"Twitter niedostępny: {e}")
                
            
            if not texts:
                logger.warning(f"⚠️  Brak tekstów do analizy dla {country} (ze wszystkich źródeł)")
                return False
            
            logger.info(f"📝 Znaleziono {len(texts)} tekstów do analizy dla {country}")
            
            # Analizuj używając LLM
            logger.info(f"🤖 Analizuję sentyment używając LLM ({self.llm_model})...")
            result = self.llm_analyzer.analyze_sentiment(
                texts=texts,
                region=country,
                language=language,
                symbol=symbol
            )
            
            # Dodaj dane Web Search do wyniku (jeśli były użyte)
            if web_search_query is not None:
                result["web_search_query"] = web_search_query
                result["web_search_response"] = web_search_response
                result["web_search_answer"] = web_search_answer
                result["web_search_results_count"] = web_search_results_count
            
            # Zaktualizuj rekord w bazie z danymi Web Search (jeśli były zapisane)
            if self.llm_analyzer.save_to_db and symbol and web_search_query is not None:
                try:
                    self._update_web_search_data_in_db(
                        symbol=symbol,
                        region=country,
                        timestamp=result["timestamp"],
                        web_search_query=web_search_query,
                        web_search_response=web_search_response,
                        web_search_answer=web_search_answer,
                        web_search_results_count=web_search_results_count
                    )
                except Exception as e:
                    logger.warning(f"⚠️  Błąd aktualizacji danych Web Search w bazie: {e}")
            
            # Aktualizuj statystyki
            self.stats["analyses_count"] += 1
            self.stats["total_cost_pln"] += result["cost_pln"]
            
            logger.success(
                f"✅ Analiza zakończona: {country} - {result['sentiment']} "
                f"(score: {result['score']:+.2f}, cost: {result['cost_pln']:.4f} PLN)"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Błąd podczas analizy {country}: {e}")
            logger.debug(traceback.format_exc())
            self.stats["errors_count"] += 1
            return False
    
    def _update_cycle(self):
        """Wykonuje jeden cykl aktualizacji."""
        logger.info(f"\n{'='*70}")
        logger.info(f"🔄 CYKL AKTUALIZACJI #{self.stats['cycles_count'] + 1}")
        logger.info(f"{'='*70}\n")
        
        start_time = time.time()
        success_count = 0
        
        # Dla każdego symbolu i kraju
        for symbol in self.symbols:
            for country in self.countries:
                if not self.running:
                    break
                
                if self._collect_and_analyze(country, symbol):
                    success_count += 1
                
                # Małe opóźnienie między krajami, żeby nie przeciążać API
                time.sleep(2)
        
        elapsed_time = time.time() - start_time
        self.stats["cycles_count"] += 1
        self.stats["last_update"] = datetime.now(timezone.utc)
        
        logger.info(f"\n{'='*70}")
        logger.success(
            f"✅ Cykl zakończony: {success_count}/{len(self.symbols) * len(self.countries)} analiz, "
            f"czas: {elapsed_time:.1f}s"
        )
        logger.info(f"📊 Statystyki: {self.stats['analyses_count']} analiz, "
                   f"koszt łączny: {self.stats['total_cost_pln']:.2f} PLN, "
                   f"błędy: {self.stats['errors_count']}")
        
        # Raport synchronizacji - sprawdź ile danych jest w bazie
        self._report_data_status()
        
        logger.info(f"{'='*70}\n")
    
    def _report_data_status(self):
        """Raportuje status danych w bazie dla synchronizacji ze strategią."""
        try:
            from datetime import timedelta
            
            # Sprawdź ile unikalnych punktów czasowych mamy w ostatnich 24h
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(hours=24)
            
            # Pobierz dane z bazy
            df = self.db.get_llm_sentiment_analysis(
                symbol=self.symbols[0] if self.symbols else "BTC/USDC",
                start_date=start_date,
                end_date=end_date
            )
            
            if df.empty:
                data_points = 0
                regions_count = 0
            else:
                # Policz unikalne punkty czasowe (godzinowe)
                if hasattr(df.index, 'floor'):
                    hourly_points = df.index.floor('H').nunique()
                else:
                    hourly_points = len(df)
                data_points = hourly_points
                regions_count = df['region'].nunique() if 'region' in df.columns else 0
            
            min_required = 24  # Strategia wymaga minimum 24 punktów
            percentage = min(100, (data_points / min_required) * 100)
            
            if data_points >= min_required:
                logger.success(f"🔄 SYNCHRONIZACJA: {data_points}/{min_required} punktów ({percentage:.0f}%) - GOTOWE do pełnej analizy!")
            else:
                hours_remaining = max(0, min_required - data_points)
                logger.warning(f"🔄 SYNCHRONIZACJA: {data_points}/{min_required} punktów ({percentage:.0f}%) - jeszcze ~{hours_remaining}h do pełnej analizy")
            
            logger.info(f"   Regiony z danymi: {regions_count}/{len(self.countries)}")
            
        except Exception as e:
            logger.debug(f"Nie można sprawdzić statusu danych: {e}")
    
    def run(self):
        """Uruchamia daemon."""
        logger.info("🚀 Uruchamiam LLM Sentiment Daemon...")
        logger.info(f"   Symbole: {', '.join(self.symbols)}")
        logger.info(f"   Kraje: {', '.join(self.countries)}")
        logger.info(f"   Query: {self.query}")
        logger.info(f"   Model LLM: {self.llm_model}")
        logger.info(f"   Interwał: {self.update_interval}s ({self.update_interval/60:.1f} min)")
        logger.info(f"   Baza: {self.db._safe_url()}")
        
        # Informacja o synchronizacji z strategią
        logger.info("")
        logger.info("📊 SYNCHRONIZACJA ZE STRATEGIĄ:")
        logger.info("   • Strategia wymaga minimum 24 punktów czasowych (24h przy resolution 1h)")
        logger.info(f"   • Przy interwale {self.update_interval/60:.0f} min i {len(self.countries)} krajach:")
        hours_to_24_points = 24  # Resolution 1h, potrzeba 24 punktów
        logger.info(f"   • Potrzeba ~{hours_to_24_points}h zbierania danych do pełnej analizy")
        logger.info(f"   • Strategia będzie działać z ograniczoną dokładnością do tego czasu")
        logger.info("")
        
        self.running = True
        
        try:
            while self.running:
                self._update_cycle()
                
                if not self.running:
                    break
                
                # Poczekaj na następny cykl
                logger.info(f"⏳ Czekam {self.update_interval}s do następnego cyklu...")
                for _ in range(self.update_interval):
                    if not self.running:
                        break
                    time.sleep(1)
        
        except KeyboardInterrupt:
            logger.warning("Przerwano przez użytkownika")
        except Exception as e:
            logger.error(f"Błąd w głównej pętli: {e}")
            logger.debug(traceback.format_exc())
        finally:
            logger.info("\n" + "="*70)
            logger.info("🛑 Zatrzymywanie daemona...")
            logger.info(f"📊 Końcowe statystyki:")
            logger.info(f"   Cykle: {self.stats['cycles_count']}")
            logger.info(f"   Analizy: {self.stats['analyses_count']}")
            logger.info(f"   Błędy: {self.stats['errors_count']}")
            logger.info(f"   Koszt łączny: {self.stats['total_cost_pln']:.2f} PLN")
            logger.info("="*70)


def main():
    """Główna funkcja."""
    parser = argparse.ArgumentParser(
        description="LLM Sentiment Collector Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  # Uruchom z domyślnymi ustawieniami (co 10 min)
  python scripts/llm_sentiment_daemon.py
  
  # Uruchom z niestandardowym interwałem (5 min)
  python scripts/llm_sentiment_daemon.py --interval=300
  
  # Uruchom dla konkretnych krajów
  python scripts/llm_sentiment_daemon.py --countries=US,CN,JP
        """
    )
    
    parser.add_argument(
        '--symbols',
        type=str,
        default='BTC/USDC',
        help='Symbole do analizy (oddzielone przecinkami, domyślnie: BTC/USDC)'
    )
    
    parser.add_argument(
        '--countries',
        type=str,
        default='US,CN,JP,KR,DE,GB,RU,SG',
        help='Kraje do analizy (oddzielone przecinkami)'
    )
    
    parser.add_argument(
        '--query',
        type=str,
        default='bitcoin OR BTC OR cryptocurrency',
        help='Zapytanie do GDELT (domyślnie: bitcoin OR BTC OR cryptocurrency)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=600,
        help='Interwał aktualizacji w sekundach (domyślnie: 600 = 10 min)'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default='claude-3-5-haiku-20241022',
        help='Model LLM do użycia (domyślnie: claude-3-5-haiku-20241022 - tańszy)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Szczegółowe logowanie'
    )
    
    args = parser.parse_args()
    
    # Konfiguruj logowanie
    logger.remove()
    level = "DEBUG" if args.verbose else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level=level,
        colorize=True
    )
    
    # Parsuj argumenty
    symbols = [s.strip() for s in args.symbols.split(",")]
    countries = [c.strip() for c in args.countries.split(",")]
    
    # Utwórz i uruchom daemon
    daemon = LLMSentimentDaemon(
        symbols=symbols,
        countries=countries,
        query=args.query,
        update_interval=args.interval,
        llm_model=args.model
    )
    
    daemon.run()


if __name__ == "__main__":
    main()

