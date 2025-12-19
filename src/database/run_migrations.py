"""
Run Database Migrations
=======================
Wykonuje migracje SQL na bazie danych.
"""

import os
import sys
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine, text
from loguru import logger

from .migrations import MIGRATIONS, get_migration_path


def run_migrations(
    database_url: Optional[str] = None,
    use_timescale: bool = False
) -> bool:
    """
    Wykonuje wszystkie migracje SQL na bazie danych.
    
    Args:
        database_url: URL bazy danych (domyślnie z .env lub SQLite)
        use_timescale: Czy użyć TimescaleDB (wymaga PostgreSQL)
        
    Returns:
        True jeśli migracje zakończyły się sukcesem
    """
    from dotenv import load_dotenv
    
    # Załaduj .env
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    # Pobierz URL bazy danych
    if database_url is None:
        database_url = os.getenv('DATABASE_URL')
    
    # Jeśli brak URL, użyj SQLite
    if database_url is None:
        db_path = Path(__file__).parent.parent.parent / 'data' / 'ai_blockchain.db'
        database_url = f"sqlite:///{db_path.absolute()}"
        logger.info(f"Używam domyślnej bazy SQLite: {database_url}")
    
    # Utwórz engine
    engine = create_engine(database_url, echo=False)
    
    # Sprawdź czy to PostgreSQL
    is_postgresql = 'postgresql' in database_url.lower()
    
    logger.info(f"Wykonuję migracje na bazie: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    
    try:
        # Wykonaj każdą migrację w osobnej transakcji
        for migration_file in MIGRATIONS:
            migration_path = get_migration_path(migration_file)
            
            if not migration_path.exists():
                logger.warning(f"Plik migracji nie istnieje: {migration_path}")
                continue
            
            logger.info(f"Wykonuję migrację: {migration_file}")
            
            # Wczytaj zawartość pliku SQL
            with open(migration_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Podziel na pojedyncze komendy (dla SQLite)
            if not is_postgresql:
                # SQLite nie obsługuje niektórych komend PostgreSQL
                # Pomiń migracje specyficzne dla PostgreSQL
                if 'timescaledb' in sql_content.lower() or 'CREATE EXTENSION' in sql_content:
                    logger.info(f"Pomijam migrację {migration_file} (wymaga PostgreSQL)")
                    continue
                if 'CREATE OR REPLACE VIEW' in sql_content:
                    logger.info(f"Pomijam migrację {migration_file} (SQLite nie obsługuje VIEW)")
                    continue
            
            # Wykonaj SQL w osobnej transakcji dla każdej migracji
            try:
                with engine.begin() as conn:  # begin() automatycznie commit/rollback
                    # Dla PostgreSQL wykonaj cały plik jako jeden blok
                    if is_postgresql:
                        conn.execute(text(sql_content))
                    else:
                        # Dla SQLite podziel na komendy
                        commands = [cmd.strip() for cmd in sql_content.split(';') if cmd.strip() and not cmd.strip().startswith('--')]
                        for command in commands:
                            if command:
                                conn.execute(text(command))
                    
                    logger.success(f"Migracja {migration_file} wykonana pomyślnie")
                    
            except Exception as e:
                # Niektóre komendy mogą już istnieć (np. CREATE EXTENSION IF NOT EXISTS)
                error_msg = str(e).lower()
                if 'already exists' in error_msg or 'duplicate' in error_msg:
                    logger.info(f"Migracja {migration_file} już wykonana (pomijam)")
                elif 'undefinedtable' in error_msg or 'does not exist' in error_msg:
                    # Ignoruj błędy związane z nieistniejącymi tabelami (np. timescaledb_information)
                    logger.warning(f"Migracja {migration_file}: Pomijam błąd związanym z nieistniejącą tabelą/view")
                else:
                    logger.error(f"Błąd podczas wykonywania migracji {migration_file}: {e}")
                    # Nie przerywaj - kontynuuj z następnymi migracjami
                    continue
                
        logger.success("Wszystkie migracje wykonane")
        return True
        
    except Exception as e:
        logger.error(f"Błąd podczas wykonywania migracji: {e}")
        return False


if __name__ == "__main__":
    from dotenv import load_dotenv
    
    # Załaduj .env
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    database_url = os.getenv('DATABASE_URL')
    use_timescale = os.getenv('USE_TIMESCALE', 'false').lower() == 'true'
    
    success = run_migrations(database_url=database_url, use_timescale=use_timescale)
    sys.exit(0 if success else 1)

