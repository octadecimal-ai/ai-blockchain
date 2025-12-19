"""
Database Migrations
===================
Migracje SQL dla bazy danych projektu.
"""

from pathlib import Path

# Ścieżka do katalogu migracji
MIGRATIONS_DIR = Path(__file__).parent

# Lista migracji w kolejności wykonania
MIGRATIONS = [
    '01-init-timescale.sql',
    '02-create-btcusdc-view.sql',
    '03-create-llm-sentiment-analysis.sql',
    '04-add-prompt-response-to-llm-sentiment.sql',
    '05-add-tavily-to-llm-sentiment.sql',
    '06-create-gdelt-sentiment.sql',
    '07-rename-tavily-to-web-search.sql',
    '08-create-regions-table.sql',
    '09-create-dictionary-tables.sql',
    '10-insert-region-events-data.sql',
    '11-insert-global-events-data.sql',
    '12-insert-macro-events-data.sql',
    '13-insert-options-events-data.sql',
    '14-insert-algo-events-data.sql',
    '15-insert-special-events-data.sql',
    '16-insert-social-events-data.sql',
    '17-move-tables-to-public.sql',
]


def get_migration_path(filename: str) -> Path:
    """Zwraca pełną ścieżkę do pliku migracji."""
    return MIGRATIONS_DIR / filename

