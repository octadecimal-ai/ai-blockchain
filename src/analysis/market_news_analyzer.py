"""
Market News & Sentiment Analyzer
=================================
Moduł do zbierania i analizy wiadomości, sentymentu i informacji polityczno-technologicznych
dla tradingu kryptowalut.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from loguru import logger
import os
from src.utils.web_search import get_web_search_engine


class MarketNewsAnalyzer:
    """
    Analizator wiadomości rynkowych, sentymentu i informacji polityczno-technologicznych.
    
    Zbiera dane z:
    - Twitter/X (sentiment społeczności)
    - Reddit (dyskusje, sentyment)
    - Telegram (kanały crypto)
    - Symulowane wiadomości polityczne i technologiczne (dla demo)
    """
    
    def __init__(self):
        """Inicjalizacja analizatora."""
        self.twitter_collector = None
        self.reddit_collector = None
        self.telegram_collector = None
        
        # Inicjalizuj kolektory jeśli dostępne
        self._init_collectors()
        
        # Inicjalizuj silnik wyszukiwania w internecie
        self.web_search = get_web_search_engine()
    
    def _init_collectors(self):
        """Inicjalizuje kolektory z mediów społecznościowych."""
        try:
            from src.collectors.sentiment.twitter_collector import TwitterCollector
            self.twitter_collector = TwitterCollector()
            logger.debug("Twitter Collector zainicjalizowany")
        except Exception as e:
            logger.debug(f"Twitter Collector niedostępny: {e}")
        
        try:
            from src.collectors.sentiment.reddit_collector import RedditCollector
            self.reddit_collector = RedditCollector()
            logger.debug("Reddit Collector zainicjalizowany")
        except Exception as e:
            logger.debug(f"Reddit Collector niedostępny: {e}")
        
        try:
            from src.collectors.sentiment.telegram_collector import TelegramCollector
            self.telegram_collector = TelegramCollector()
            logger.debug("Telegram Collector zainicjalizowany")
        except Exception as e:
            logger.debug(f"Telegram Collector niedostępny: {e}")
    
    def collect_twitter_sentiment(
        self,
        symbol: str = "BTC",
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Zbiera sentyment z Twitter/X.
        
        Args:
            symbol: Symbol kryptowaluty (BTC, ETH, etc.)
            limit: Maksymalna liczba tweetów
            
        Returns:
            Słownik z danymi sentymentu
        """
        if not self.twitter_collector or not self.twitter_collector.bearer_token:
            return {
                "source": "twitter",
                "available": False,
                "reason": "Brak konfiguracji API"
            }
        
        try:
            # Przykładowe zapytanie (w rzeczywistości użyj API Twitter)
            # tweets = self.twitter_collector.search_tweets(f"{symbol} OR #{symbol}", limit=limit)
            
            # Dla demo zwracamy symulowane dane
            return {
                "source": "twitter",
                "available": True,
                "tweets_analyzed": limit,
                "sentiment": "neutral",
                "sentiment_score": 0.0,
                "key_topics": [f"{symbol} price", "crypto market", "trading"],
                "notable_tweets": [
                    f"Analiza {symbol} - trend wzrostowy kontynuuje się",
                    f"Eksperci przewidują stabilizację rynku {symbol}"
                ],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.warning(f"Błąd zbierania danych z Twitter: {e}")
            return {
                "source": "twitter",
                "available": False,
                "error": str(e)
            }
    
    def collect_reddit_sentiment(
        self,
        symbol: str = "BTC",
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Zbiera sentyment z Reddit.
        
        Args:
            symbol: Symbol kryptowaluty
            limit: Maksymalna liczba postów
            
        Returns:
            Słownik z danymi sentymentu
        """
        if not self.reddit_collector or not self.reddit_collector.reddit:
            return {
                "source": "reddit",
                "available": False,
                "reason": "Brak konfiguracji API"
            }
        
        try:
            # Przykładowe zapytanie (w rzeczywistości użyj API Reddit)
            # posts = self.reddit_collector.get_subreddit_posts(f"r/{symbol}", limit=limit)
            
            # Dla demo zwracamy symulowane dane
            return {
                "source": "reddit",
                "available": True,
                "posts_analyzed": limit,
                "sentiment": "bullish",
                "sentiment_score": 0.3,
                "key_topics": [f"{symbol} analysis", "market outlook", "technical analysis"],
                "notable_posts": [
                    f"r/{symbol}: Dyskusja o przyszłości {symbol}",
                    f"r/cryptocurrency: Analiza techniczna {symbol}"
                ],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.warning(f"Błąd zbierania danych z Reddit: {e}")
            return {
                "source": "reddit",
                "available": False,
                "error": str(e)
            }
    
    def collect_political_news(
        self,
        symbol: str = "BTC"
    ) -> Dict[str, Any]:
        """
        Zbiera wiadomości polityczne mogące wpłynąć na rynek kryptowalut.
        
        Args:
            symbol: Symbol kryptowaluty
            
        Returns:
            Słownik z wiadomościami politycznymi
        """
        # Spróbuj wyszukać w internecie
        if self.web_search.api_key:
            try:
                search_results = self.web_search.search_political_news(symbol, max_results=5)
                if search_results.get("success") and search_results.get("results"):
                    # Konwertuj wyniki wyszukiwania na format wiadomości
                    news_items = []
                    for result in search_results["results"]:
                        news_items.append({
                            "title": result.get("title", "Brak tytułu"),
                            "impact": "high" if "regulation" in result.get("content", "").lower() or "government" in result.get("content", "").lower() else "medium",
                            "sentiment": self._analyze_sentiment_from_text(result.get("content", "")),
                            "description": result.get("content", "")[:200] if result.get("content") else result.get("snippet", "")[:200],
                            "url": result.get("url", "")
                        })
                    
                    return {
                        "source": "political_news",
                        "available": True,
                        "search_engine": "web_search",
                        "news_items": news_items,
                        "timestamp": datetime.now().isoformat()
                    }
            except Exception as e:
                logger.warning(f"Błąd wyszukiwania wiadomości politycznych: {e}")
        
        # Fallback do symulowanych danych
        return {
            "source": "political_news",
            "available": True,
            "search_engine": "simulated",
            "news_items": [
                {
                    "title": "Regulacje kryptowalut w USA - nowe propozycje",
                    "impact": "medium",
                    "sentiment": "neutral",
                    "description": "Komisja SEC rozważa nowe regulacje dla rynku kryptowalut"
                },
                {
                    "title": "Unia Europejska - dyrektywa MiCA wchodzi w życie",
                    "impact": "high",
                    "sentiment": "positive",
                    "description": "Nowe regulacje UE mogą zwiększyć zaufanie do rynku"
                }
            ],
            "timestamp": datetime.now().isoformat()
        }
    
    def collect_tech_news(
        self,
        symbol: str = "BTC"
    ) -> Dict[str, Any]:
        """
        Zbiera wiadomości technologiczne mogące wpłynąć na rynek.
        
        Args:
            symbol: Symbol kryptowaluty
            
        Returns:
            Słownik z wiadomościami technologicznymi
        """
        # Spróbuj wyszukać w internecie
        if self.web_search.api_key:
            try:
                search_results = self.web_search.search_tech_news(symbol, max_results=5)
                if search_results.get("success") and search_results.get("results"):
                    # Konwertuj wyniki wyszukiwania na format wiadomości
                    news_items = []
                    for result in search_results["results"]:
                        news_items.append({
                            "title": result.get("title", "Brak tytułu"),
                            "impact": "high" if "adoption" in result.get("content", "").lower() or "upgrade" in result.get("content", "").lower() else "medium",
                            "sentiment": self._analyze_sentiment_from_text(result.get("content", "")),
                            "description": result.get("content", "")[:200] if result.get("content") else result.get("snippet", "")[:200],
                            "url": result.get("url", "")
                        })
                    
                    return {
                        "source": "tech_news",
                        "available": True,
                        "search_engine": "web_search",
                        "news_items": news_items,
                        "timestamp": datetime.now().isoformat()
                    }
            except Exception as e:
                logger.warning(f"Błąd wyszukiwania wiadomości technologicznych: {e}")
        
        # Fallback do symulowanych danych
        return {
            "source": "tech_news",
            "available": True,
            "search_engine": "simulated",
            "news_items": [
                {
                    "title": f"Rozwój technologii {symbol} - nowe aktualizacje",
                    "impact": "medium",
                    "sentiment": "positive",
                    "description": "Zespół deweloperski ogłasza nowe funkcje"
                },
                {
                    "title": "Adopcja instytucjonalna kryptowalut rośnie",
                    "impact": "high",
                    "sentiment": "bullish",
                    "description": "Więcej firm instytucjonalnych inwestuje w krypto"
                }
            ],
            "timestamp": datetime.now().isoformat()
        }
    
    def collect_market_sentiment(
        self,
        symbol: str = "BTC-USD"
    ) -> Dict[str, Any]:
        """
        Zbiera kompleksowe dane sentymentu z różnych źródeł.
        
        Args:
            symbol: Symbol rynku (np. BTC-USD)
            
        Returns:
            Słownik z kompleksowymi danymi sentymentu
        """
        # Wyciągnij symbol bez pary (BTC z BTC-USD)
        base_symbol = symbol.split("-")[0] if "-" in symbol else symbol
        
        # Zbierz dane z różnych źródeł
        twitter_data = self.collect_twitter_sentiment(base_symbol)
        reddit_data = self.collect_reddit_sentiment(base_symbol)
        political_news = self.collect_political_news(base_symbol)
        tech_news = self.collect_tech_news(base_symbol)
        
        # Oblicz ogólny sentyment
        sentiment_scores = []
        if twitter_data.get("available") and "sentiment_score" in twitter_data:
            sentiment_scores.append(twitter_data["sentiment_score"])
        if reddit_data.get("available") and "sentiment_score" in reddit_data:
            sentiment_scores.append(reddit_data["sentiment_score"])
        
        overall_sentiment_score = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
        
        # Określ ogólny sentyment
        if overall_sentiment_score > 0.2:
            overall_sentiment = "bullish"
        elif overall_sentiment_score < -0.2:
            overall_sentiment = "bearish"
        else:
            overall_sentiment = "neutral"
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "overall_sentiment": overall_sentiment,
            "overall_sentiment_score": overall_sentiment_score,
            "sources": {
                "twitter": twitter_data,
                "reddit": reddit_data,
                "political_news": political_news,
                "tech_news": tech_news
            },
            "summary": f"Ogólny sentyment rynku dla {symbol}: {overall_sentiment} (score: {overall_sentiment_score:.2f})"
        }
    
    def format_market_analysis_for_prompt(
        self,
        sentiment_data: Dict[str, Any]
    ) -> str:
        """
        Formatuje dane sentymentu i wiadomości do prompta dla LLM.
        
        Args:
            sentiment_data: Dane z collect_market_sentiment()
            
        Returns:
            Sformatowany tekst do prompta
        """
        lines = ["\n=== ANALIZA SENTYMENTU I WIADOMOŚCI ==="]
        
        # Ogólny sentyment
        overall = sentiment_data.get("overall_sentiment", "neutral")
        score = sentiment_data.get("overall_sentiment_score", 0.0)
        lines.append(f"\n📊 Ogólny sentyment rynku: {overall.upper()} (score: {score:.2f})")
        
        sources = sentiment_data.get("sources", {})
        
        # Twitter
        twitter = sources.get("twitter", {})
        lines.append(f"\n🐦 Twitter/X:")
        if twitter.get("available"):
            lines.append(f"  Sentyment: {twitter.get('sentiment', 'N/A')}")
            lines.append(f"  Analizowane tweety: {twitter.get('tweets_analyzed', 0)}")
            if twitter.get("key_topics"):
                lines.append(f"  Kluczowe tematy: {', '.join(twitter['key_topics'][:3])}")
        else:
            lines.append(f"  Status: Niedostępne ({twitter.get('reason', 'Brak konfiguracji API')})")
        
        # Reddit
        reddit = sources.get("reddit", {})
        lines.append(f"\n💬 Reddit:")
        if reddit.get("available"):
            lines.append(f"  Sentyment: {reddit.get('sentiment', 'N/A')}")
            lines.append(f"  Analizowane posty: {reddit.get('posts_analyzed', 0)}")
            if reddit.get("key_topics"):
                lines.append(f"  Kluczowe tematy: {', '.join(reddit['key_topics'][:3])}")
        else:
            lines.append(f"  Status: Niedostępne ({reddit.get('reason', 'Brak konfiguracji API')})")
        
        # Wiadomości polityczne
        political = sources.get("political_news", {})
        if political.get("available") and political.get("news_items"):
            lines.append(f"\n🏛️  Wiadomości polityczne:")
            for news in political["news_items"][:3]:  # Max 3 najważniejsze
                impact_emoji = "🔴" if news.get("impact") == "high" else "🟡" if news.get("impact") == "medium" else "🟢"
                lines.append(f"  {impact_emoji} {news.get('title', 'N/A')}")
                lines.append(f"     Wpływ: {news.get('impact', 'N/A')} | Sentyment: {news.get('sentiment', 'N/A')}")
        
        # Wiadomości technologiczne
        tech = sources.get("tech_news", {})
        if tech.get("available") and tech.get("news_items"):
            lines.append(f"\n💻 Wiadomości technologiczne:")
            for news in tech["news_items"][:3]:  # Max 3 najważniejsze
                impact_emoji = "🔴" if news.get("impact") == "high" else "🟡" if news.get("impact") == "medium" else "🟢"
                lines.append(f"  {impact_emoji} {news.get('title', 'N/A')}")
                lines.append(f"     Wpływ: {news.get('impact', 'N/A')} | Sentyment: {news.get('sentiment', 'N/A')}")
        
        lines.append("\n" + "="*50)
        
        return "\n".join(lines)

