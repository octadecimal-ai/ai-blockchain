#!/usr/bin/env python3
"""
Initialize Trading Database
============================
Skrypt do inicjalizacji bazy danych tradingowej.
Tworzy wszystkie tabele i dodaje domyślne strategie.

Obsługuje:
- PostgreSQL + TimescaleDB (produkcja)
- SQLite (development)
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from loguru import logger

from src.database.models import Base as DatabaseBase, create_timescale_hypertables
from src.trading.models import Base as TradingBase
from src.trading.models_extended import Strategy, Base

# Import wszystkich modeli
from src.trading.models import (
    PaperAccount, PaperPosition, PaperOrder, PaperTrade
)
from src.trading.models_extended import (
    Strategy, TradeRegister, TradingSession
)

# Załaduj .env jeśli istnieje
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    logger.info(f"Załadowano konfigurację z {env_path}")


def get_database_url(default: str = None) -> str:
    """
    Pobiera URL bazy danych z zmiennej środowiskowej lub używa domyślnej.
    
    Returns:
        URL bazy danych
    """
    db_url = os.getenv('DATABASE_URL')
    
    if db_url:
        logger.info(f"Używam DATABASE_URL z .env: {db_url.split('@')[-1] if '@' in db_url else db_url}")
        return db_url
    
    if default:
        logger.info(f"Używam domyślnej bazy: {default}")
        return default
    
    # Fallback do SQLite
    default_sqlite = "sqlite:///data/paper_trading.db"
    logger.warning(f"Brak DATABASE_URL w .env - używam SQLite: {default_sqlite}")
    return default_sqlite


def init_database(database_url: str = None):
    """
    Inicjalizuje bazę danych tradingową.
    
    Args:
        database_url: URL bazy danych (opcjonalnie, jeśli None - używa .env lub SQLite)
    """
    if database_url is None:
        database_url = get_database_url()
    
    logger.info(f"Inicjalizacja bazy danych: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    
    # Utwórz katalog jeśli SQLite
    if database_url.startswith("sqlite"):
        db_path = database_url.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    
    # Połącz z bazą
    is_postgresql = 'postgresql' in database_url.lower()
    engine = create_engine(database_url, echo=False)
    
    # Sprawdź połączenie
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.success("✓ Połączenie z bazą danych OK")
    except Exception as e:
        logger.error(f"❌ Błąd połączenia z bazą: {e}")
        if is_postgresql:
            logger.error("   Sprawdź czy PostgreSQL jest uruchomiony i czy DATABASE_URL jest poprawny")
        raise
    
    # Utwórz wszystkie tabele
    logger.info("Tworzenie tabel...")
    DatabaseBase.metadata.create_all(engine)
    TradingBase.metadata.create_all(engine)
    
    logger.success("✓ Tabele utworzone")
    
    # TimescaleDB hypertables (tylko dla PostgreSQL)
    if is_postgresql and os.getenv('USE_TIMESCALE', 'false').lower() == 'true':
        logger.info("Tworzenie hypertables TimescaleDB...")
        try:
            create_timescale_hypertables(engine)
            logger.success("✓ Hypertables TimescaleDB utworzone")
        except Exception as e:
            logger.warning(f"⚠ Nie udało się utworzyć hypertables: {e}")
            logger.warning("   (To normalne jeśli TimescaleDB nie jest zainstalowany)")
    
    # Dodaj domyślne strategie
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Strategia Piotrka
        strategy = session.query(Strategy).filter_by(name="piotrek_breakout_strategy").first()
        if not strategy:
            strategy = Strategy(
                name="piotrek_breakout_strategy",
                display_name="Strategia Breakout Piotrka",
                version="1.0.0",
                description="Breakout z exit na konsolidacji. Bazowana na rzeczywistych transakcjach Piotrka.",
                author="Piotr Adamczyk",
                default_config={
                    'breakout_threshold': 0.8,
                    'consolidation_threshold': 0.4,
                    'min_confidence': 5,
                    'risk_reward_ratio': 2.0,
                    'lookback_period': 20,
                    'consolidation_candles': 3
                },
                min_confidence=5.0,
                risk_reward_ratio=2.0,
                max_drawdown_percent=20.0,
                is_active=True
            )
            session.add(strategy)
            session.commit()
            logger.success(f"✓ Dodano strategię: {strategy.display_name}")
        else:
            logger.info(f"Strategia już istnieje: {strategy.display_name}")
        
        # Pokaż wszystkie strategie
        strategies = session.query(Strategy).all()
        logger.info(f"\n📊 Zarejestrowane strategie ({len(strategies)}):")
        for s in strategies:
            logger.info(f"   - {s.name} v{s.version}: {s.display_name}")
        
    except Exception as e:
        logger.error(f"Błąd podczas dodawania strategii: {e}")
        session.rollback()
    finally:
        session.close()
    
    logger.success("\n✅ Baza danych zainicjalizowana pomyślnie!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Inicjalizacja bazy danych tradingowej",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  # Użyj DATABASE_URL z .env (PostgreSQL)
  python scripts/init_trading_db.py

  # Wymuś SQLite
  python scripts/init_trading_db.py --db=sqlite:///data/paper_trading.db

  # Własny PostgreSQL
  python scripts/init_trading_db.py --db=postgresql://user:pass@localhost:5432/ai_blockchain
        """
    )
    parser.add_argument(
        "--db",
        default=None,
        help="URL bazy danych (domyślnie: DATABASE_URL z .env lub SQLite)"
    )
    
    args = parser.parse_args()
    
    init_database(args.db)

