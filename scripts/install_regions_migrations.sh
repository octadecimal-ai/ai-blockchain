#!/bin/bash
# Skrypt instalacyjny migracji dla tabel regions i słowników wydarzeń
# ===================================================================

set -e  # Zatrzymaj przy błędzie

# Kolory dla outputu
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funkcje pomocnicze
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Sprawdź czy jesteśmy w katalogu projektu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

print_info "Instalacja migracji dla tabel regions i słowników wydarzeń"
echo ""

# Sprawdź czy istnieje .env
if [ ! -f .env ]; then
    print_warning "Plik .env nie istnieje. Używam domyślnej bazy SQLite."
    export DATABASE_URL=""
else
    print_success "Znaleziono plik .env"
fi

# Sprawdź czy Python jest dostępny
if ! command -v python3 &> /dev/null; then
    print_error "Python3 nie jest zainstalowany"
    exit 1
fi

# Sprawdź czy wirtualne środowisko jest aktywne
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "venv" ]; then
        print_info "Aktywuję wirtualne środowisko..."
        source venv/bin/activate
    else
        print_warning "Wirtualne środowisko nie jest aktywne i nie znaleziono venv/"
        print_warning "Kontynuuję bez wirtualnego środowiska..."
    fi
fi

# Sprawdź czy wymagane pakiety są zainstalowane
print_info "Sprawdzam wymagane pakiety..."
python3 -c "import sqlalchemy" 2>/dev/null || {
    print_error "SQLAlchemy nie jest zainstalowany. Zainstaluj: pip install sqlalchemy"
    exit 1
}

python3 -c "import loguru" 2>/dev/null || {
    print_error "Loguru nie jest zainstalowany. Zainstaluj: pip install loguru"
    exit 1
}

print_success "Wszystkie wymagane pakiety są zainstalowane"
echo ""

# Wykonaj migracje
print_info "Wykonuję migracje SQL..."
echo ""

python3 << PYTHON_EOF
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Konfiguracja logowania
logger.remove()
logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")

# Załaduj .env
project_root = Path(__file__).parent.parent if '__file__' in dir() else Path.cwd()
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)
    logger.info("Załadowano konfigurację z .env")

# Import modułu migracji
sys.path.insert(0, str(project_root))
from src.database.run_migrations import run_migrations

database_url = os.getenv('DATABASE_URL')
use_timescale = os.getenv('USE_TIMESCALE', 'false').lower() == 'true'

logger.info(f"URL bazy danych: {database_url if database_url else 'SQLite (domyślna)'}")
logger.info(f"TimescaleDB: {'Tak' if use_timescale else 'Nie'}")

# Wykonaj migracje
try:
    success = run_migrations(database_url=database_url, use_timescale=use_timescale)
    if success:
        logger.success("Wszystkie migracje wykonane pomyślnie!")
        sys.exit(0)
    else:
        logger.warning("Niektóre migracje mogły się nie powieść")
        sys.exit(1)
except Exception as e:
    logger.error(f"Błąd podczas wykonywania migracji: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_EOF

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    print_success "Migracje wykonane pomyślnie!"
    echo ""
    print_info "Utworzone tabele:"
    echo "  - regions (16 regionów)"
    echo "  - dictionary_region_events (47 wydarzeń)"
    echo "  - dictionary_global_events (14 wydarzeń)"
    echo "  - dictionary_macro_events (10 wydarzeń)"
    echo "  - dictionary_options_events (6 wydarzeń)"
    echo "  - dictionary_algo_events (4 wydarzenia)"
    echo "  - dictionary_special_events (7 wydarzeń)"
    echo "  - dictionary_social_events (3 wydarzenia)"
    echo ""
    print_info "Możesz teraz używać modeli SQLAlchemy z src.database.models"
else
    echo ""
    print_error "Migracje zakończyły się błędem (kod: $EXIT_CODE)"
    exit $EXIT_CODE
fi

