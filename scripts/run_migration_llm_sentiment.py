#!/usr/bin/env python3
"""
Wykonaj migrację dla llm_sentiment_analysis
===========================================
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

# Załaduj .env
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)

def main():
    """Wykonaj migrację."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ Brak DATABASE_URL w .env")
        sys.exit(1)
    
    migration_file = project_root / 'src/database/migrations/03-create-llm-sentiment-analysis.sql'
    
    if not migration_file.exists():
        logger.error(f"❌ Plik migracji nie istnieje: {migration_file}")
        sys.exit(1)
    
    logger.info(f"🔗 Łączę z bazą danych...")
    engine = create_engine(database_url)
    
    try:
        with engine.begin() as conn:
            logger.info(f"📄 Wczytuję migrację: {migration_file}")
            content = migration_file.read_text()
            
            # Wykonaj migrację
            logger.info("🚀 Wykonuję migrację...")
            conn.execute(text(content))
            
            logger.success("✅ Migracja wykonana pomyślnie")
            return 0
            
    except Exception as e:
        logger.error(f"❌ Błąd podczas migracji: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

