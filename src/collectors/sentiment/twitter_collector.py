"""
Twitter/X Collector
===================
Kolektor danych z Twitter/X API v2 do analizy sentymentu.

Uwaga: Twitter/X nie ma sandbox/testnet, więc testy używają mocków.
"""

import os
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from loguru import logger

try:
    from tenacity import retry, stop_after_attempt, wait_exponential
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    logger.warning("tenacity nie jest zainstalowany. Retry logic nie będzie działać.")


class TwitterCollector:
    """
    Kolektor danych z Twitter/X API v2.
    
    Wymaga: TWITTER_BEARER_TOKEN w zmiennych środowiskowych.
    """
    
    BASE_URL = "https://api.twitter.com/2"
    
    def __init__(self, bearer_token: Optional[str] = None):
        """
        Inicjalizacja kolektora Twitter/X.
        
        Args:
            bearer_token: Bearer token (lub z TWITTER_BEARER_TOKEN)
        """
        self.bearer_token = bearer_token or os.getenv('TWITTER_BEARER_TOKEN')
        
        if not self.bearer_token:
            logger.warning("Brak TWITTER_BEARER_TOKEN - niektóre funkcje mogą nie działać")
        
        self.headers = {
            'Authorization': f'Bearer {self.bearer_token}',
            'Content-Type': 'application/json'
        } if self.bearer_token else {}
        
        logger.info("Twitter Collector zainicjalizowany")
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Wykonuje request do Twitter API.
        
        Args:
            endpoint: Endpoint API
            params: Parametry zapytania
            
        Returns:
            Odpowiedź JSON
        """
        if not self.bearer_token:
            raise ValueError("TWITTER_BEARER_TOKEN jest wymagany")
        
        url = f"{self.BASE_URL}{endpoint}"
        
        if TENACITY_AVAILABLE:
            @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
            def _request():
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            return _request()
        else:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
    
    def search_tweets(
        self,
        query: str,
        max_results: int = 10,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Wyszukuje tweety.
        
        Args:
            query: Zapytanie wyszukiwania (np. "bitcoin OR BTC")
            max_results: Maksymalna liczba wyników (10-100)
            start_time: Data początkowa
            end_time: Data końcowa
            
        Returns:
            Lista tweetów
        """
        params = {
            'query': query,
            'max_results': min(max_results, 100),
            'tweet.fields': 'created_at,author_id,public_metrics,text'
        }
        
        if start_time:
            params['start_time'] = start_time.isoformat()
        if end_time:
            params['end_time'] = end_time.isoformat()
        
        try:
            response = self._make_request('/tweets/search/recent', params)
            return response.get('data', [])
        except Exception as e:
            logger.error(f"Błąd wyszukiwania tweetów: {e}")
            return []
    
    def get_tweet_sentiment(self, tweet_id: str) -> Optional[Dict]:
        """
        Pobiera tweet i jego metryki (do analizy sentymentu).
        
        Args:
            tweet_id: ID tweeta
            
        Returns:
            Dane tweeta z metrykami
        """
        params = {
            'tweet.fields': 'created_at,author_id,public_metrics,text,context_annotations'
        }
        
        try:
            response = self._make_request(f'/tweets/{tweet_id}', params)
            return response.get('data')
        except Exception as e:
            logger.error(f"Błąd pobierania tweeta {tweet_id}: {e}")
            return None
    
    def search_crypto_tweets(
        self,
        symbol: str = "BTC",
        max_results: int = 50
    ) -> List[Dict]:
        """
        Wyszukuje tweety związane z kryptowalutą.
        
        Args:
            symbol: Symbol kryptowaluty (BTC, ETH, etc.)
            max_results: Maksymalna liczba wyników
            
        Returns:
            Lista tweetów
        """
        query = f"{symbol} OR #{symbol} OR ${symbol} -is:retweet lang:en"
        return self.search_tweets(query, max_results=max_results)
    
    def get_trending_topics(self, woeid: int = 1) -> List[Dict]:
        """
        Pobiera trendy (wymaga Twitter API v1.1 - nie jest dostępne w v2).
        
        Args:
            woeid: Where On Earth ID (1 = worldwide)
            
        Returns:
            Lista trendów
        """
        logger.warning("get_trending_topics wymaga Twitter API v1.1 - nie jest dostępne w v2")
        return []

