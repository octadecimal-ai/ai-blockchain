"""
Reddit Collector
================
Kolektor danych z Reddit API (PRAW) do analizy sentymentu.

Uwaga: Reddit nie ma sandbox/testnet, więc testy używają mocków.
"""

import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from loguru import logger

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    logger.warning("praw nie jest zainstalowany. Użyj: pip install praw")


class RedditCollector:
    """
    Kolektor danych z Reddit API.
    
    Wymaga: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
    """
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        Inicjalizacja kolektora Reddit.
        
        Args:
            client_id: Client ID (lub z REDDIT_CLIENT_ID)
            client_secret: Client Secret (lub z REDDIT_CLIENT_SECRET)
            user_agent: User Agent (lub z REDDIT_USER_AGENT)
        """
        if not PRAW_AVAILABLE:
            raise ImportError("Zainstaluj praw: pip install praw")
        
        self.client_id = client_id or os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = user_agent or os.getenv('REDDIT_USER_AGENT', 'ai-blockchain-bot/1.0')
        
        if not self.client_id or not self.client_secret:
            logger.warning("Brak REDDIT_CLIENT_ID lub REDDIT_CLIENT_SECRET - niektóre funkcje mogą nie działać")
            self.reddit = None
        else:
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )
            logger.info("Reddit Collector zainicjalizowany")
    
    def get_subreddit_posts(
        self,
        subreddit: str,
        limit: int = 25,
        time_filter: str = 'day'
    ) -> List[Dict]:
        """
        Pobiera posty z subreddita.
        
        Args:
            subreddit: Nazwa subreddita (np. "Bitcoin", "CryptoCurrency")
            limit: Maksymalna liczba postów
            time_filter: 'hour', 'day', 'week', 'month', 'year', 'all'
            
        Returns:
            Lista postów
        """
        if not self.reddit:
            raise ValueError("Reddit nie jest skonfigurowany (brak credentials)")
        
        try:
            sub = self.reddit.subreddit(subreddit)
            posts = []
            
            for post in sub.top(time_filter=time_filter, limit=limit):
                posts.append({
                    'id': post.id,
                    'title': post.title,
                    'selftext': post.selftext,
                    'score': post.score,
                    'upvote_ratio': post.upvote_ratio,
                    'num_comments': post.num_comments,
                    'created_utc': datetime.fromtimestamp(post.created_utc),
                    'author': str(post.author) if post.author else None,
                    'url': post.url,
                    'permalink': post.permalink
                })
            
            return posts
        except Exception as e:
            logger.error(f"Błąd pobierania postów z r/{subreddit}: {e}")
            return []
    
    def search_posts(
        self,
        query: str,
        subreddit: Optional[str] = None,
        limit: int = 25,
        sort: str = 'relevance'
    ) -> List[Dict]:
        """
        Wyszukuje posty.
        
        Args:
            query: Zapytanie wyszukiwania
            subreddit: Ograniczenie do subreddita (opcjonalnie)
            limit: Maksymalna liczba wyników
            sort: 'relevance', 'hot', 'top', 'new', 'comments'
            
        Returns:
            Lista postów
        """
        if not self.reddit:
            raise ValueError("Reddit nie jest skonfigurowany (brak credentials)")
        
        try:
            if subreddit:
                sub = self.reddit.subreddit(subreddit)
                results = sub.search(query, sort=sort, limit=limit)
            else:
                results = self.reddit.subreddit('all').search(query, sort=sort, limit=limit)
            
            posts = []
            for post in results:
                posts.append({
                    'id': post.id,
                    'title': post.title,
                    'selftext': post.selftext,
                    'score': post.score,
                    'upvote_ratio': post.upvote_ratio,
                    'num_comments': post.num_comments,
                    'created_utc': datetime.fromtimestamp(post.created_utc),
                    'subreddit': str(post.subreddit),
                    'author': str(post.author) if post.author else None
                })
            
            return posts
        except Exception as e:
            logger.error(f"Błąd wyszukiwania postów: {e}")
            return []
    
    def get_crypto_posts(
        self,
        symbol: str = "BTC",
        limit: int = 50
    ) -> List[Dict]:
        """
        Wyszukuje posty związane z kryptowalutą.
        
        Args:
            symbol: Symbol kryptowaluty (BTC, ETH, etc.)
            limit: Maksymalna liczba wyników
            
        Returns:
            Lista postów
        """
        query = f"{symbol} OR {symbol.lower()} OR bitcoin"
        subreddits = ['Bitcoin', 'CryptoCurrency', 'ethereum', 'CryptoMarkets']
        
        all_posts = []
        for subreddit in subreddits:
            posts = self.search_posts(query, subreddit=subreddit, limit=limit // len(subreddits))
            all_posts.extend(posts)
        
        # Usuń duplikaty
        seen_ids = set()
        unique_posts = []
        for post in all_posts:
            if post['id'] not in seen_ids:
                seen_ids.add(post['id'])
                unique_posts.append(post)
        
        return unique_posts[:limit]
    
    def get_post_comments(self, post_id: str, limit: int = 100) -> List[Dict]:
        """
        Pobiera komentarze do posta.
        
        Args:
            post_id: ID posta
            limit: Maksymalna liczba komentarzy
            
        Returns:
            Lista komentarzy
        """
        if not self.reddit:
            raise ValueError("Reddit nie jest skonfigurowany (brak credentials)")
        
        try:
            submission = self.reddit.submission(id=post_id)
            submission.comments.replace_more(limit=0)
            
            comments = []
            for comment in submission.comments.list()[:limit]:
                comments.append({
                    'id': comment.id,
                    'body': comment.body,
                    'score': comment.score,
                    'created_utc': datetime.fromtimestamp(comment.created_utc),
                    'author': str(comment.author) if comment.author else None
                })
            
            return comments
        except Exception as e:
            logger.error(f"Błąd pobierania komentarzy dla posta {post_id}: {e}")
            return []

