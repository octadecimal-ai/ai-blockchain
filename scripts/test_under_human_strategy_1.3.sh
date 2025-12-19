#!/bin/bash

# ============================================================================
# Test Backtestowy UnderhumanStrategy v1.3 - OPUS AI EDGE
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Funkcje logowania
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_ai() {
    echo -e "${CYAN}[OPUS AI]${NC} $1"
}

# Parametry domyślne
LIMIT_DAYS=""
BALANCE=10000
LEVERAGE=10.0
POSITION_SIZE=15.0
VERBOSE=false

# Parsowanie argumentów
while [[ $# -gt 0 ]]; do
    case $1 in
        --limit-days=*)
            LIMIT_DAYS="${1#*=}"
            shift
            ;;
        --balance=*)
            BALANCE="${1#*=}"
            shift
            ;;
        --leverage=*)
            LEVERAGE="${1#*=}"
            shift
            ;;
        --position-size=*)
            POSITION_SIZE="${1#*=}"
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            echo "Użycie: $0 [opcje]"
            echo ""
            echo "UNDERHUMAN STRATEGY v1.3 - OPUS AI EDGE"
            echo "Wykorzystuje unikalne możliwości AI:"
            echo "  - Regime Detection (Trending/Ranging/Volatile/Calm)"
            echo "  - Kelly Criterion Position Sizing"
            echo "  - Multi-timeframe Confluence"
            echo "  - Anti-Whipsaw Filter"
            echo "  - Smart Entry Timing"
            echo ""
            echo "Opcje:"
            echo "  --limit-days=DNI    Limit danych do ostatnich N dni (domyślnie: wszystkie dane)"
            echo "  --balance=KWOTA     Początkowy kapitał (domyślnie: 10000)"
            echo "  --leverage=WSP       Dźwignia (domyślnie: 10.0)"
            echo "  --position-size=PROC Rozmiar pozycji w % (domyślnie: 15.0)"
            echo "  --verbose, -v       Szczegółowe logowanie"
            echo "  -h, --help          Pokaż tę pomoc"
            echo ""
            echo "Przykłady:"
            echo "  $0                              # Test wszystkich danych z bazy"
            echo "  $0 --limit-days=30              # Test ostatnich 30 dni"
            echo "  $0 --balance=50000 --leverage=5.0"
            exit 0
            ;;
        *)
            log_error "Nieznany argument: $1"
            echo "Użyj --help aby zobaczyć dostępne opcje"
            exit 1
            ;;
    esac
done

# Sprawdź czy venv istnieje
if [ ! -d "venv" ]; then
    log_error "Środowisko wirtualne nie istnieje. Uruchom: python -m venv venv"
    exit 1
fi

# Aktywuj venv
log_info "Aktywuję środowisko wirtualne..."
source venv/bin/activate

# Sprawdź czy .env istnieje
if [ ! -f ".env" ]; then
    log_warning "Plik .env nie istnieje. Upewnij się, że DATABASE_URL jest ustawiony."
fi

log_info "═══════════════════════════════════════════════════════════════"
log_ai "🧠 UNDERHUMAN STRATEGY v1.3 - OPUS AI EDGE"
log_info "═══════════════════════════════════════════════════════════════"
log_info "Źródło danych:      Baza danych PostgreSQL"
log_info "Kapitał:             \$$BALANCE"
log_info "Dźwignia:            ${LEVERAGE}x"
log_info "Rozmiar pozycji:     ${POSITION_SIZE}%"
if [ -n "$LIMIT_DAYS" ]; then
    log_info "Ograniczenie:        Ostatnie ${LIMIT_DAYS} dni"
else
    log_info "Ograniczenie:        Wszystkie dane"
fi
log_info "═══════════════════════════════════════════════════════════════"
echo ""

VERBOSE_FLAG=""
if [ "$VERBOSE" = true ]; then
    VERBOSE_FLAG="--verbose"
fi

LIMIT_DAYS_FLAG=""
if [ -n "$LIMIT_DAYS" ]; then
    LIMIT_DAYS_FLAG="--limit-days=$LIMIT_DAYS"
fi

python tests/integration/test_under_human_strategy_1.3.py \
    $LIMIT_DAYS_FLAG \
    --balance="$BALANCE" \
    --leverage="$LEVERAGE" \
    --position-size="$POSITION_SIZE" \
    $VERBOSE_FLAG

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log_success "✅ Test zakończony pomyślnie"
else
    log_error "❌ Test zakończony z błędem (kod: $EXIT_CODE)"
fi

exit $EXIT_CODE
