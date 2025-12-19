#!/usr/bin/env python3
"""
Sprawdza czy tabele regions i słowników zostały utworzone w bazie danych
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from loguru import logger

# Dodaj ścieżkę projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Załaduj .env
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)

def main():
    """Sprawdź tabele w bazie."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ Brak DATABASE_URL w .env")
        sys.exit(1)
    
    logger.info(f"🔗 Łączę z bazą danych: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    
    engine = create_engine(database_url)
    inspector = inspect(engine)
    
    # Lista tabel do sprawdzenia
    expected_tables = [
        'regions',
        'dictionary_region_events',
        'dictionary_global_events',
        'dictionary_macro_events',
        'dictionary_options_events',
        'dictionary_algo_events',
        'dictionary_special_events',
        'dictionary_social_events'
    ]
    
    logger.info("\n📊 Sprawdzam tabele w bazie danych...\n")
    
    # Pobierz wszystkie tabele z bazy (schemat public jest domyślny)
    all_tables = inspector.get_table_names()
    
    # Sprawdź też schemat crypto jeśli istnieje (dla kompatybilności)
    schemas = inspector.get_schema_names()
    if 'crypto' in schemas:
        crypto_tables = inspector.get_table_names(schema='crypto')
        if crypto_tables:
            logger.warning(f"⚠ Znaleziono tabele w schemacie 'crypto' - uruchom migrację 17-move-tables-to-public.sql")
            all_tables.extend(crypto_tables)
    
    found_tables = []
    missing_tables = []
    
    for table_name in expected_tables:
        if table_name in all_tables:
            found_tables.append(table_name)
            # Sprawdź liczbę rekordów (sprawdź w schemacie public)
            try:
                with engine.connect() as conn:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM public.{table_name}"))
                    count = result.scalar()
                    logger.success(f"✓ {table_name:40} - istnieje w schemacie 'public' ({count} rekordów)")
            except Exception as e:
                logger.warning(f"⚠ {table_name:40} - istnieje, ale błąd przy sprawdzaniu rekordów: {e}")
        else:
            missing_tables.append(table_name)
            logger.error(f"✗ {table_name:40} - NIE ISTNIEJE")
    
    # Pokaż wszystkie tabele w bazie
    logger.info(f"\n📋 Wszystkie tabele w bazie ({len(all_tables)}):")
    for table in sorted(all_tables):
        if table.startswith('dictionary_') or table == 'regions':
            logger.info(f"  • {table}")
        else:
            logger.debug(f"  • {table}")
    
    # Podsumowanie
    logger.info(f"\n📊 Podsumowanie:")
    logger.info(f"  Znaleziono: {len(found_tables)}/{len(expected_tables)}")
    logger.info(f"  Brakuje: {len(missing_tables)}/{len(expected_tables)}")
    
    if missing_tables:
        logger.error(f"\n❌ Brakujące tabele: {', '.join(missing_tables)}")
        
        # Sprawdź czy schemat jest poprawny
        logger.info("\n🔍 Sprawdzam schemat bazy danych...")
        with engine.connect() as conn:
            # Sprawdź search_path
            result = conn.execute(text("SHOW search_path"))
            search_path = result.scalar()
            logger.info(f"  search_path: {search_path}")
            
            # Sprawdź czy istnieje schemat crypto
            result = conn.execute(text("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name IN ('crypto', 'public')
            """))
            schemas = [row[0] for row in result]
            logger.info(f"  Dostępne schematy: {', '.join(schemas)}")
            
            # Sprawdź tabele w różnych schematach
            for schema in schemas:
                result = conn.execute(text(f"""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = '{schema}' 
                    AND table_name IN {tuple(expected_tables)}
                """))
                schema_tables = [row[0] for row in result]
                if schema_tables:
                    logger.info(f"  Tabele w schemacie '{schema}': {', '.join(schema_tables)}")
        
        return 1
    else:
        logger.success("\n✅ Wszystkie tabele istnieją w bazie!")
        return 0

if __name__ == '__main__':
    sys.exit(main())

