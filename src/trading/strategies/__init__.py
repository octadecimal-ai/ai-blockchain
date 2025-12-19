"""
Strategie tradingowe.
"""

from .piotrek_strategy import PiotrekBreakoutStrategy
from .scalping_strategy import ScalpingStrategy
from .improved_breakout_strategy import ImprovedBreakoutStrategy
from .funding_rate_arbitrage_strategy import FundingRateArbitrageStrategy
from .sentiment_propagation_strategy import SentimentPropagationStrategy
from .prompt_strategy import PromptStrategy
from .prompt_strategy_v11 import PromptStrategyV11
from .prompt_strategy_v12 import PromptStrategyV12
from .piotr_swiec_strategy import PiotrSwiecStrategy
from .piotr_swiec_prompt_strategy import PiotrSwiecPromptStrategy
from .ultra_short_prompt_strategy import UltraShortPromptStrategy
from .test_prompt_strategy import TestPromptStrategy
# Import strategii - Python używa podkreśleń w importach nawet gdy plik ma kropki
# Pliki: under_human_strategy_1.0.py → import jako under_human_strategy_1_0
import importlib.util
import sys
from pathlib import Path

_strategies_dir = Path(__file__).parent

# Helper do importowania plików z kropkami w nazwach
def _import_strategy_module(module_name, file_name):
    """Importuje moduł z kropką w nazwie pliku używając importlib."""
    file_path = _strategies_dir / file_name
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec and spec.loader:
        # Ustaw parent package dla relative importów
        parent_name = __name__
        if module_name not in sys.modules:
            module = importlib.util.module_from_spec(spec)
            module.__package__ = parent_name
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return module
    return None

# Import wszystkich wersji under_human_strategy
_module_1_0 = _import_strategy_module('under_human_strategy_1_0', 'under_human_strategy_1.0.py')
_module_1_1 = _import_strategy_module('under_human_strategy_1_1', 'under_human_strategy_1.1.py')
_module_1_2 = _import_strategy_module('under_human_strategy_1_2', 'under_human_strategy_1.2.py')
_module_1_3 = _import_strategy_module('under_human_strategy_1_3', 'under_human_strategy_1.3.py')
_module_1_4 = _import_strategy_module('under_human_strategy_1_4', 'under_human_strategy_1.4.py')
_module_2_0 = _import_strategy_module('under_human_strategy_2_0', 'under_human_strategy_2.0.py')

UnderhumanStrategyV10 = _module_1_0.UnderhumanStrategyV10 if _module_1_0 else None
UnderhumanStrategyV11 = _module_1_1.UnderhumanStrategyV11 if _module_1_1 else None
UnderhumanStrategyV12 = _module_1_2.UnderhumanStrategyV12 if _module_1_2 else None
UnderhumanStrategyV13 = _module_1_3.UnderhumanStrategyV13 if _module_1_3 else None
UnderhumanStrategyV14 = _module_1_4.UnderhumanStrategyV14 if _module_1_4 else None
UnderhumanStrategyV2 = _module_2_0.UnderhumanStrategyV2 if _module_2_0 else None
from .base_strategy import BaseStrategy

__all__ = [
    'BaseStrategy',
    'PiotrekBreakoutStrategy',
    'ScalpingStrategy',
    'ImprovedBreakoutStrategy',
    'FundingRateArbitrageStrategy',
    'SentimentPropagationStrategy',
    'PromptStrategy',
    'PromptStrategyV11',
    'PromptStrategyV12',
    'PiotrSwiecStrategy',
    'PiotrSwiecPromptStrategy',
    'UltraShortPromptStrategy',
    'TestPromptStrategy',
    'UnderhumanStrategyV10',
    'UnderhumanStrategyV11',
    'UnderhumanStrategyV12',
    'UnderhumanStrategyV13',
    'UnderhumanStrategyV14',
    'UnderhumanStrategyV2',
]

