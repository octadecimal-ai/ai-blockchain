#!/bin/bash
# Skrypt do aktualizacji danych BTC/USDC w bazie danych
# =====================================================
# Pobiera najnowsze dane z Binance i aktualizuje bazę danych

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
logger.info('Sprawdzam strukturę bazy danych...')
loader.db.create_tables()

# Aktualizuj dane
logger.info('Aktualizuję dane BTC/USDC...')
count = loader.update_latest_data(days_back=7)

if count > 0:
    logger.success(f'Zaktualizowano {count} świec')
else:
    logger.info('Brak nowych danych do aktualizacji')

# Pokaż statystyki
latest = loader.get_latest_timestamp()
if latest:
    logger.info(f'Ostatnia świeca w bazie: {latest}')
"

echo ""
echo "✅ Aktualizacja zakończona"

