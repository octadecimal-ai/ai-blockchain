#!/bin/bash
# Skrypt do wyczyszczenia starych danych i wczytania nowych z gradacją 1-minutową
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# Kolorowe logi
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔄 Wyczyszczenie i przeładowanie danych BTC/USDC (1m)${NC}"
echo "=============================================================================="

# Aktywuj venv jeśli istnieje
if [ -d venv ]; then
    source venv/bin/activate
fi

# Krok 1: Wyczyść stare dane
echo ""
echo -e "${YELLOW}Krok 1: Czyszczenie starych danych...${NC}"
python3 scripts/clear_btcusdc_data.py --confirm

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Błąd podczas czyszczenia danych${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Stare dane wyczyszczone${NC}"

# Krok 2: Wczytaj nowe dane 1-minutowe
echo ""
echo -e "${YELLOW}Krok 2: Wczytywanie danych 1-minutowych z Binance...${NC}"
echo "To może zająć kilka minut (dużo danych dla 1m)..."
echo ""

python3 << 'PYTHON_EOF'
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from loguru import logger

# Dodaj ścieżkę projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Załaduj .env
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)

from src.database.btcusdc_loader import BTCUSDCDataLoader

# Konfiguracja loggera
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="INFO",
    colorize=True
)

# Inicjalizacja loadera z timeframe 1m
database_url = os.getenv('DATABASE_URL')
use_timescale = os.getenv('USE_TIMESCALE', 'false').lower() == 'true'

logger.info("🚀 Inicjalizacja BTCUSDCDataLoader z timeframe=1m")
loader = BTCUSDCDataLoader(
    database_url=database_url,
    use_timescale=use_timescale,
    timeframe="1m"
)

# Pobierz dane od 2020 roku
start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
logger.info(f"📥 Pobieranie danych 1-minutowych od {start_date}...")
logger.warning("⚠️  To może zająć dużo czasu - dla 1m jest ~525,600 świec rocznie!")

try:
    count = loader.load_historical_data(start_date=start_date)
    logger.success(f"✅ Zapisano {count} świec 1-minutowych do bazy danych")
    
    # Sprawdź ostatnią świecę
    latest = loader.get_latest_timestamp()
    if latest:
        logger.info(f"📊 Ostatnia świeca w bazie: {latest}")
    
except Exception as e:
    logger.error(f"❌ Błąd podczas wczytywania danych: {e}")
    sys.exit(1)
PYTHON_EOF

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Dane 1-minutowe wczytane pomyślnie!${NC}"
    echo ""
    echo "Możesz teraz używać danych 1-minutowych w testach:"
    echo "  python tests/integration/test_under_human_strategy_1.0.py"
    echo ""
else
    echo -e "${RED}❌ Błąd podczas wczytywania danych${NC}"
    exit 1
fi

