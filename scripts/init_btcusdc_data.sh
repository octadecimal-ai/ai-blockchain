#!/bin/bash
# Skrypt do inicjalizacji danych BTC/USDC w bazie danych
# =====================================================
# Pobiera wszystkie dane historyczne od 2020 roku z Binance

set -e  # Zatrzymaj przy błędzie

# Katalog projektu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Przejdź do katalogu projektu
cd "$PROJECT_DIR"

# Aktywuj venv jeśli istnieje
if [ -d venv ]; then
    source venv/bin/activate
fi

# Uruchom skrypt Python
python3 -c "
import sys
import os
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath('$PROJECT_DIR')))

from dotenv import load_dotenv
from pathlib import Path
from loguru import logger
from src.database.btcusdc_loader import BTCUSDCDataLoader

# Konfiguracja loggera
logger.remove()
logger.add(
    sys.stderr,
    format='<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}',
    level='INFO',
    colorize=True
)

# Załaduj .env
env_path = Path('$PROJECT_DIR') / '.env'
if env_path.exists():
    load_dotenv(env_path)

# Inicjalizacja loadera
database_url = os.getenv('DATABASE_URL')
use_timescale = os.getenv('USE_TIMESCALE', 'false').lower() == 'true'

loader = BTCUSDCDataLoader(
    database_url=database_url,
    use_timescale=use_timescale
)

# Utwórz tabele jeśli nie istnieją
logger.info('Tworzenie struktury bazy danych...')
loader.db.create_tables()

# Pobierz dane historyczne od 2020
logger.info('Pobieranie danych historycznych BTC/USDC od 2020 roku...')
start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
count = loader.load_historical_data(start_date=start_date)

logger.success(f'Zapisano {count} świec do bazy danych')

# Pokaż statystyki
latest = loader.get_latest_timestamp()
if latest:
    logger.info(f'Ostatnia świeca w bazie: {latest}')
"

echo ""
echo "✅ Inicjalizacja zakończona"

