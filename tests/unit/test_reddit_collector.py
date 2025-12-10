"""
Testy jednostkowe dla RedditCollector.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.collectors.sentiment.reddit_collector import RedditCollector


class TestRedditCollector:
    """Testy dla klasy RedditCollector."""
    
    def test_init_with_credentials(self):
        """Test inicjalizacji z credentials."""
        with patch('src.collectors.sentiment.reddit_collector.praw') as mock_praw:
            mock_reddit = MagicMock()
            mock_praw.Reddit.return_value = mock_reddit
            
            collector = RedditCollector(
                client_id="test_id",
                client_secret="test_secret",
                user_agent="test_agent"
            )
            
            assert collector.client_id == "test_id"
            assert collector.client_secret == "test_secret"
            assert collector.reddit is not None
    
    def test_init_without_credentials(self, monkeypatch):
        """Test inicjalizacji bez credentials."""
        monkeypatch.delenv('REDDIT_CLIENT_ID', raising=False)
        monkeypatch.delenv('REDDIT_CLIENT_SECRET', raising=False)
        
        with patch('src.collectors.sentiment.reddit_collector.praw'):
            collector = RedditCollector()
            
            assert collector.reddit is None
    
    def test_init_from_env(self, monkeypatch):
        """Test inicjalizacji z zmiennych środowiskowych."""
        monkeypatch.setenv('REDDIT_CLIENT_ID', 'env_id')
        monkeypatch.setenv('REDDIT_CLIENT_SECRET', 'env_secret')
        monkeypatch.setenv('REDDIT_USER_AGENT', 'env_agent')
        
        with patch('src.collectors.sentiment.reddit_collector.praw') as mock_praw:
            mock_reddit = MagicMock()
            mock_praw.Reddit.return_value = mock_reddit
            
            collector = RedditCollector()
            
            assert collector.client_id == 'env_id'
            assert collector.client_secret == 'env_secret'
            assert collector.user_agent == 'env_agent'
    
    def test_get_subreddit_posts(self):
        """Test pobierania postów z subreddita."""
        with patch('src.collectors.sentiment.reddit_collector.praw') as mock_praw:
            mock_reddit = MagicMock()
            mock_praw.Reddit.return_value = mock_reddit
            
            # Mock post
            mock_post = MagicMock()
            mock_post.id = '123'
            mock_post.title = 'Bitcoin News'
            mock_post.selftext = 'Content'
            mock_post.score = 100
            mock_post.upvote_ratio = 0.95
            mock_post.num_comments = 50
            mock_post.created_utc = 1609459200.0
            mock_post.author = MagicMock()
            mock_post.author.__str__ = Mock(return_value='user123')
            mock_post.url = 'https://reddit.com/test'
            mock_post.permalink = '/r/test/123'
            
            mock_subreddit = MagicMock()
            mock_subreddit.top.return_value = [mock_post]
            mock_reddit.subreddit.return_value = mock_subreddit
            
            collector = RedditCollector(
                client_id="test_id",
                client_secret="test_secret"
            )
            
            posts = collector.get_subreddit_posts("Bitcoin", limit=1)
            
            assert len(posts) == 1
            assert posts[0]['id'] == '123'
            assert posts[0]['title'] == 'Bitcoin News'
            assert posts[0]['score'] == 100
    
    def test_get_subreddit_posts_error_handling(self):
        """Test obsługi błędów przy pobieraniu postów."""
        with patch('src.collectors.sentiment.reddit_collector.praw') as mock_praw:
            mock_reddit = MagicMock()
            mock_praw.Reddit.return_value = mock_reddit
            mock_reddit.subreddit.side_effect = Exception("API Error")
            
            collector = RedditCollector(
                client_id="test_id",
                client_secret="test_secret"
            )
            
            posts = collector.get_subreddit_posts("Bitcoin")
            
            assert posts == []
    
    def test_search_posts(self):
        """Test wyszukiwania postów."""
        with patch('src.collectors.sentiment.reddit_collector.praw') as mock_praw:
            mock_reddit = MagicMock()
            mock_praw.Reddit.return_value = mock_reddit
            
            mock_post = MagicMock()
            mock_post.id = '456'
            mock_post.title = 'Search Result'
            mock_post.selftext = 'Content'
            mock_post.score = 50
            mock_post.upvote_ratio = 0.9
            mock_post.num_comments = 25
            mock_post.created_utc = 1609459200.0
            mock_post.subreddit = MagicMock()
            mock_post.subreddit.__str__ = Mock(return_value='Bitcoin')
            mock_post.author = MagicMock()
            mock_post.author.__str__ = Mock(return_value='user456')
            
            mock_subreddit = MagicMock()
            mock_subreddit.search.return_value = [mock_post]
            mock_reddit.subreddit.return_value = mock_subreddit
            
            collector = RedditCollector(
                client_id="test_id",
                client_secret="test_secret"
            )
            
            posts = collector.search_posts("bitcoin", subreddit="Bitcoin")
            
            assert len(posts) == 1
            assert posts[0]['id'] == '456'
    
    def test_get_crypto_posts(self):
        """Test pobierania postów o kryptowalutach."""
        with patch.object(RedditCollector, 'search_posts') as mock_search:
            mock_search.return_value = [
                {'id': '1', 'title': 'BTC post'},
                {'id': '2', 'title': 'Bitcoin discussion'}
            ]
            
            with patch('src.collectors.sentiment.reddit_collector.praw') as mock_praw:
                mock_reddit = MagicMock()
                mock_praw.Reddit.return_value = mock_reddit
                
                collector = RedditCollector(
                    client_id="test_id",
                    client_secret="test_secret"
                )
                
                posts = collector.get_crypto_posts("BTC", limit=10)
                
                # Sprawdź czy search_posts zostało wywołane
                assert mock_search.called
    
    def test_get_post_comments(self):
        """Test pobierania komentarzy."""
        with patch('src.collectors.sentiment.reddit_collector.praw') as mock_praw:
            mock_reddit = MagicMock()
            mock_praw.Reddit.return_value = mock_reddit
            
            mock_comment = MagicMock()
            mock_comment.id = 'comment123'
            mock_comment.body = 'Great post!'
            mock_comment.score = 10
            mock_comment.created_utc = 1609459200.0
            mock_comment.author = MagicMock()
            mock_comment.author.__str__ = Mock(return_value='user789')
            
            mock_submission = MagicMock()
            mock_submission.comments.list.return_value = [mock_comment]
            mock_submission.comments.replace_more = Mock()
            mock_reddit.submission.return_value = mock_submission
            
            collector = RedditCollector(
                client_id="test_id",
                client_secret="test_secret"
            )
            
            comments = collector.get_post_comments("post123", limit=10)
            
            assert len(comments) == 1
            assert comments[0]['id'] == 'comment123'
            assert comments[0]['body'] == 'Great post!'
    
    def test_get_subreddit_posts_without_credentials(self):
        """Test pobierania postów bez credentials."""
        collector = RedditCollector()
        
        with pytest.raises(ValueError, match="nie jest skonfigurowany"):
            collector.get_subreddit_posts("Bitcoin")

