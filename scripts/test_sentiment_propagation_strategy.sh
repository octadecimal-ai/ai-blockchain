#!/bin/bash

# ============================================================================
# Test Strategii Propagacji Sentymentu
# ============================================================================
# Uruchamia wszystkie testy dla SentimentPropagationStrategy
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
MAGENTA='\033[0;35m'
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

log_test() {
    echo -e "${CYAN}[TEST]${NC} $1"
}

log_strategy() {
    echo -e "${MAGENTA}[STRATEGY]${NC} $1"
}

# Parametry domyślne
VERBOSE=false
COVERAGE=false
MARKERS=""
TEST_PATH="tests/integration/test_sentiment_propagation_strategy.py"

# Parsowanie argumentów
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --coverage|-c)
            COVERAGE=true
            shift
            ;;
        --markers=*)
            MARKERS="${1#*=}"
            shift
            ;;
        --unit)
            TEST_PATH="tests/integration/test_sentiment_propagation_strategy.py::TestSentimentPropagationStrategy"
            shift
            ;;
        --integration)
            TEST_PATH="tests/integration/test_sentiment_propagation_strategy.py::TestSentimentPropagationStrategyIntegration"
            shift
            ;;
        -h|--help)
            echo "Użycie: $0 [opcje]"
            echo ""
            echo "SENTIMENT PROPAGATION STRATEGY - Testy"
            echo "Uruchamia testy jednostkowe i integracyjne dla strategii propagacji sentymentu."
            echo ""
            echo "Opcje:"
            echo "  --verbose, -v          Szczegółowe logowanie (pytest -v)"
            echo "  --coverage, -c          Uruchom z pokryciem kodu"
            echo "  --markers=MARKERS       Uruchom tylko testy z określonymi markerami"
            echo "  --unit                  Uruchom tylko testy jednostkowe"
            echo "  --integration           Uruchom tylko testy integracyjne"
            echo "  -h, --help              Pokaż tę pomoc"
            echo ""
            echo "Przykłady:"
            echo "  $0                      # Wszystkie testy"
            echo "  $0 --verbose            # Wszystkie testy z szczegółowym logowaniem"
            echo "  $0 --unit               # Tylko testy jednostkowe"
            echo "  $0 --integration        # Tylko testy integracyjne"
            echo "  $0 --coverage           # Z pokryciem kodu"
            echo "  $0 --markers=slow       # Tylko testy oznaczone jako 'slow'"
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

# Sprawdź czy pytest jest zainstalowany
if ! command -v pytest &> /dev/null; then
    log_error "pytest nie jest zainstalowany. Uruchom: pip install pytest"
    exit 1
fi

log_info "═══════════════════════════════════════════════════════════════"
log_strategy "🌊 SENTIMENT PROPAGATION STRATEGY - Testy"
log_info "═══════════════════════════════════════════════════════════════"
log_info "Plik testowy:      $TEST_PATH"
if [ "$VERBOSE" = true ]; then
    log_info "Tryb:              Verbose"
fi
if [ "$COVERAGE" = true ]; then
    log_info "Pokrycie kodu:     Włączone"
fi
if [ -n "$MARKERS" ]; then
    log_info "Markery:           $MARKERS"
fi
log_info "═══════════════════════════════════════════════════════════════"
echo ""

# Przygotuj argumenty pytest
PYTEST_ARGS=()

if [ "$VERBOSE" = true ]; then
    PYTEST_ARGS+=("-v")
else
    PYTEST_ARGS+=("-q")
fi

if [ "$COVERAGE" = true ]; then
    PYTEST_ARGS+=("--cov=src.trading.strategies.sentiment_propagation_strategy")
    PYTEST_ARGS+=("--cov=src.collectors.sentiment")
    PYTEST_ARGS+=("--cov-report=term-missing")
    PYTEST_ARGS+=("--cov-report=html:htmlcov/sentiment_propagation")
fi

if [ -n "$MARKERS" ]; then
    PYTEST_ARGS+=("-m" "$MARKERS")
fi

# Dodaj ścieżkę do testów
PYTEST_ARGS+=("$TEST_PATH")

# Uruchom testy
log_test "Uruchamiam pytest..."
echo ""

pytest "${PYTEST_ARGS[@]}"

EXIT_CODE=$?

echo ""
log_info "═══════════════════════════════════════════════════════════════"

if [ $EXIT_CODE -eq 0 ]; then
    log_success "✅ Wszystkie testy zakończone pomyślnie"
    if [ "$COVERAGE" = true ]; then
        log_info "📊 Raport pokrycia kodu: htmlcov/sentiment_propagation/index.html"
    fi
else
    log_error "❌ Niektóre testy zakończone z błędem (kod: $EXIT_CODE)"
fi

log_info "═══════════════════════════════════════════════════════════════"

exit $EXIT_CODE

