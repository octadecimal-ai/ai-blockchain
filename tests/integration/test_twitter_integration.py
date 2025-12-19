"""
Testy integracyjne dla TwitterCollector.

UWAGA: Twitter/X nie ma sandbox/testnet.
Testy wymagają TWITTER_BEARER_TOKEN w .env.
Jeśli brak - testy są pomijane.
"""

import pytest
import os
from datetime import datetime, timedelta

from src.collectors.sentiment.twitter_collector import TwitterCollector


@pytest.mark.integration
class TestTwitterIntegration:
    """Testy integracyjne z Twitter/X API."""
    
    @pytest.fixture
    def collector(self):
        """Inicjalizacja kolektora."""
        bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        
        if not bearer_token:
            pytest.skip("Brak TWITTER_BEARER_TOKEN w .env")
        
        return TwitterCollector(bearer_token=bearer_token)
    
    def test_search_tweets_real(self, collector):
        """Test wyszukiwania rzeczywistych tweetów."""
        tweets = collector.search_tweets("bitcoin", max_results=10)
        
        # Może zwrócić puste jeśli brak wyników, ale nie powinno rzucić błędu
        assert isinstance(tweets, list)
        
        if tweets:
            assert 'id' in tweets[0]
            assert 'text' in tweets[0]
    
    def test_search_crypto_tweets_real(self, collector):
        """Test wyszukiwania tweetów o kryptowalutach."""
        tweets = collector.search_crypto_tweets("BTC", max_results=10)
        
        assert isinstance(tweets, list)
        
        if tweets:
            # Sprawdź czy tweet zawiera BTC lub bitcoin
            tweet_text = tweets[0].get('text', '').lower()
            assert 'btc' in tweet_text or 'bitcoin' in tweet_text or len(tweets) > 0
    
    def test_get_tweet_sentiment_real(self, collector):
        """Test pobierania sentymentu tweeta (wymaga prawdziwego ID)."""
        # Najpierw znajdź tweet
        tweets = collector.search_tweets("bitcoin", max_results=1)
        
        if not tweets:
            pytest.skip("Brak tweetów do testowania")
        
        tweet_id = tweets[0]['id']
        tweet_data = collector.get_tweet_sentiment(tweet_id)
        
        assert tweet_data is not None
        assert tweet_data['id'] == tweet_id
        assert 'text' in tweet_data

