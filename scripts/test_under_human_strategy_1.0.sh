#!/bin/bash

# ============================================================================
# Test Backtestowy UnderhumanStrategy v1.0
# ============================================================================
# Testuje strategię UnderhumanStrategy na danych historycznych z bazy danych PostgreSQL.
# Działa w trybie ekspresowym - najszybciej jak się da.
#
# Użycie:
#   ./scripts/test_under_human_strategy_1.0.sh
#   ./scripts/test_under_human_strategy_1.0.sh --balance=50000 --leverage=5.0
#
# Autor: AI Assistant
# Data: 2025-12-18
# ============================================================================

# Nie używamy set -e, aby móc uruchomić wszystkie testy nawet jeśli niektóre się nie powiodą

# === Kolory ===
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
WHITE='\033[1;37m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# === Funkcje ===
log_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# === Domyślne parametry ===
BALANCE=10000
LEVERAGE=10.0
POSITION_SIZE=15.0
VERBOSE=false

# === Parsowanie argumentów ===
while [[ $# -gt 0 ]]; do
    case $1 in
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
        --help|-h)
            echo ""
            echo -e "${MAGENTA}🧪 Test Backtestowy UnderhumanStrategy${NC}"
            echo ""
            echo "Testuje strategię UnderhumanStrategy na danych historycznych z bazy danych PostgreSQL."
            echo "Działa w trybie ekspresowym - najszybciej jak się da."
            echo ""
            echo "Użycie:"
            echo "  $0 [opcje]"
            echo ""
            echo "Opcje:"
            echo "  --balance=BALANCE        Początkowy kapitał (domyślnie: 10000)"
            echo "  --leverage=LEVERAGE      Dźwignia (domyślnie: 10.0)"
            echo "  --position-size=SIZE     Rozmiar pozycji w %% (domyślnie: 15.0)"
            echo "  --verbose, -v            Szczegółowe logowanie"
            echo "  --help, -h               Pokaż tę pomoc"
            echo ""
            echo "Przykłady:"
            echo "  $0                    # Test z domyślnymi parametrami"
            echo "  $0 --balance=50000 --leverage=5.0"
            echo "  $0 --verbose          # Test z szczegółowym logowaniem"
            echo ""
            echo "Uwaga: Dane są pobierane z bazy danych PostgreSQL."
            echo "       Upewnij się, że baza jest dostępna i zawiera dane BTC/USDC."
            echo ""
            exit 0
            ;;
        *)
            log_error "Nieznana opcja: $1"
            echo "Użyj --help aby zobaczyć dostępne opcje"
            exit 1
            ;;
    esac
done

# === Sprawdź czy jesteśmy w katalogu projektu ===
if [ ! -f "tests/integration/test_under_human_strategy_1.0.py" ]; then
    log_error "Uruchom skrypt z katalogu głównego projektu!"
    exit 1
fi

# === Aktywuj środowisko wirtualne ===
if [ -d "venv" ]; then
    log_info "Aktywuję środowisko wirtualne..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    log_info "Aktywuję środowisko wirtualne..."
    source .venv/bin/activate
else
    log_warning "Nie znaleziono środowiska wirtualnego (venv/.venv)"
fi

log_info "═══════════════════════════════════════════════════════════════"
log_info "🧪 Test Backtestowy UnderhumanStrategy v1.0"
log_info "═══════════════════════════════════════════════════════════════"
log_info "Źródło danych:       PostgreSQL (baza danych)"
log_info "Kapitał:             \$$BALANCE"
log_info "Dźwignia:            ${LEVERAGE}x"
log_info "Rozmiar pozycji:     ${POSITION_SIZE}%"
log_info "═══════════════════════════════════════════════════════════════"
echo ""

TOTAL_START_TIME=$(date +%s)

VERBOSE_FLAG=""
if [ "$VERBOSE" = true ]; then
    VERBOSE_FLAG="--verbose"
fi

python tests/integration/test_under_human_strategy_1.0.py \
    --balance="$BALANCE" \
    --leverage="$LEVERAGE" \
    --position-size="$POSITION_SIZE" \
    $VERBOSE_FLAG

EXIT_CODE=$?

TOTAL_END_TIME=$(date +%s)
TOTAL_DURATION=$((TOTAL_END_TIME - TOTAL_START_TIME))

echo ""
log_info "⏱️  Całkowity czas wykonania: ${TOTAL_DURATION} sekund"

if [ $EXIT_CODE -eq 0 ]; then
    log_success "✅ Test zakończony pomyślnie"
else
    log_error "❌ Test zakończony z błędem (kod: $EXIT_CODE)"
    log_error "   Sprawdź połączenie z PostgreSQL i czy dane są dostępne"
fi

exit $EXIT_CODE

