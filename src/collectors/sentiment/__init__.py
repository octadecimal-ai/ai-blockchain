"""
Kolektory danych sentymentu z mediów społecznościowych.
"""

from .twitter_collector import TwitterCollector
from .reddit_collector import RedditCollector
from .telegram_collector import TelegramCollector

__all__ = [
    'TwitterCollector',
    'RedditCollector',
    'TelegramCollector'
]

