"""
Testy integracyjne dla RedditCollector.

UWAGA: Reddit nie ma sandbox/testnet.
Testy wymagają REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET w .env.
Jeśli brak - testy są pomijane.
"""

import pytest
import os

from src.collectors.sentiment.reddit_collector import RedditCollector


@pytest.mark.integration
class TestRedditIntegration:
    """Testy integracyjne z Reddit API."""
    
    @pytest.fixture
    def collector(self):
        """Inicjalizacja kolektora."""
        client_id = os.getenv('REDDIT_CLIENT_ID')
        client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        user_agent = os.getenv('REDDIT_USER_AGENT', 'ai-blockchain-bot/1.0')
        
        if not client_id or not client_secret:
            pytest.skip("Brak REDDIT_CLIENT_ID lub REDDIT_CLIENT_SECRET w .env")
        
        return RedditCollector(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
    
    def test_get_subreddit_posts_real(self, collector):
        """Test pobierania rzeczywistych postów z subreddita."""
        posts = collector.get_subreddit_posts("Bitcoin", limit=5, time_filter='day')
        
        assert isinstance(posts, list)
        assert len(posts) > 0
        
        # Sprawdź strukturę posta
        post = posts[0]
        assert 'id' in post
        assert 'title' in post
        assert 'score' in post
        assert 'created_utc' in post
    
    def test_search_posts_real(self, collector):
        """Test wyszukiwania postów."""
        posts = collector.search_posts("bitcoin", subreddit="Bitcoin", limit=5)
        
        assert isinstance(posts, list)
        
        if posts:
            # Sprawdź strukturę
            post = posts[0]
            assert 'id' in post
            assert 'title' in post
    
    def test_get_crypto_posts_real(self, collector):
        """Test pobierania postów o kryptowalutach."""
        posts = collector.get_crypto_posts("BTC", limit=10)
        
        assert isinstance(posts, list)
        
        if posts:
            # Sprawdź czy są unikalne (bez duplikatów)
            post_ids = [p['id'] for p in posts]
            assert len(post_ids) == len(set(post_ids))  # Wszystkie unikalne
    
    def test_get_post_comments_real(self, collector):
        """Test pobierania komentarzy (wymaga prawdziwego ID posta)."""
        # Najpierw znajdź post
        posts = collector.get_subreddit_posts("Bitcoin", limit=1, time_filter='day')
        
        if not posts:
            pytest.skip("Brak postów do testowania")
        
        post_id = posts[0]['id']
        comments = collector.get_post_comments(post_id, limit=10)
        
        assert isinstance(comments, list)
        
        if comments:
            # Sprawdź strukturę komentarza
            comment = comments[0]
            assert 'id' in comment
            assert 'body' in comment
            assert 'score' in comment

