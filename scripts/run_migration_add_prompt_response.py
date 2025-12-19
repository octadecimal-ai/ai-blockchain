#!/usr/bin/env python3
"""
Uruchom migrację: Dodanie kolumn prompt i response do llm_sentiment_analysis
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
env_file = project_root / '.env'
if env_file.exists():
    load_dotenv(env_file)

def main():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("Brak DATABASE_URL w zmiennych środowiskowych")
        return 1
    
    engine = create_engine(database_url)
    migration_file = project_root / 'src/database/migrations/04-add-prompt-response-to-llm-sentiment.sql'
    
    if not migration_file.exists():
        logger.error(f"Plik migracji nie istnieje: {migration_file}")
        return 1
    
    content = migration_file.read_text()
    
    logger.info("🚀 Wykonuję migrację: Dodanie kolumn prompt i response...")
    try:
        with engine.begin() as conn:
            conn.execute(text(content))
        logger.success("✅ Migracja wykonana pomyślnie")
        return 0
    except Exception as e:
        logger.error(f"❌ Błąd podczas migracji: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

