"""
Kolektory danych sentymentu z mediów społecznościowych.
"""

from .twitter_collector import TwitterCollector
from .reddit_collector import RedditCollector
from .telegram_collector import TelegramCollector
from .gdelt_collector import GDELTCollector
from .sentiment_propagation_analyzer import (
    SentimentPropagationAnalyzer,
    PropagationDirection,
    LagResult,
    PropagationWave
)
from .sentiment_wave_tracker import SentimentWaveTracker

# Import LLM sentiment analyzer (opcjonalnie)
try:
    from .llm_sentiment_analyzer import (
        LLMSentimentAnalyzer,
        analyze_sentiment as analyze_sentiment_llm
    )
    LLM_SENTIMENT_AVAILABLE = True
except ImportError:
    LLM_SENTIMENT_AVAILABLE = False
    LLMSentimentAnalyzer = None
    analyze_sentiment_llm = None

# Import timezone-aware analyzer (opcjonalnie)
try:
    from .timezone_aware_analyzer import (
        TimezoneAwareAnalyzer,
        TimezoneAwareLag,
        RegionConfig,
        ActivityType,
        REGION_CONFIGS
    )
    TIMEZONE_AWARE_AVAILABLE = True
except ImportError:
    TIMEZONE_AWARE_AVAILABLE = False
    TimezoneAwareAnalyzer = None
    TimezoneAwareLag = None
    RegionConfig = None
    ActivityType = None
    REGION_CONFIGS = None

__all__ = [
    'TwitterCollector',
    'RedditCollector',
    'TelegramCollector',
    'GDELTCollector',
    'SentimentPropagationAnalyzer',
    'PropagationDirection',
    'LagResult',
    'PropagationWave',
    'SentimentWaveTracker',
]

# Dodaj timezone-aware do __all__ jeśli dostępne
if TIMEZONE_AWARE_AVAILABLE:
    __all__.extend([
        'TimezoneAwareAnalyzer',
        'TimezoneAwareLag',
        'RegionConfig',
        'ActivityType',
        'REGION_CONFIGS'
    ])

# Dodaj LLM sentiment analyzer do __all__ jeśli dostępne
if LLM_SENTIMENT_AVAILABLE:
    __all__.extend([
        'LLMSentimentAnalyzer',
        'analyze_sentiment_llm'
    ])

