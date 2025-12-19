#!/usr/bin/env python3
"""
Uruchom migrację: Zmiana nazw kolumn z tavily_* na web_search_*
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from loguru import logger

# Dodaj ścieżkę projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Załaduj zmienne środowiskowe
load_dotenv(project_root / '.env')

def main():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL nie jest ustawiony w .env")
        return 1
    
    engine = create_engine(database_url)
    migration_file = project_root / 'src/database/migrations/07-rename-tavily-to-web-search.sql'
    
    if not migration_file.exists():
        logger.error(f"Plik migracji nie istnieje: {migration_file}")
        return 1
    
    content = migration_file.read_text()
    
    logger.info("🚀 Wykonuję migrację: Zmiana nazw kolumn z tavily_* na web_search_*...")
    try:
        with engine.begin() as conn:
            conn.execute(text(content))
        logger.success("✅ Migracja wykonana pomyślnie")
        return 0
    except Exception as e:
        logger.error(f"❌ Błąd migracji: {e}")
        # Sprawdź czy kolumny już zostały zmienione
        if "does not exist" in str(e) or "already exists" in str(e).lower():
            logger.warning("Kolumny mogą już być zmienione. Sprawdź ręcznie.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

