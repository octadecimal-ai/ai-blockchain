#!/bin/bash

# ============================================================================
# Test Backtestowy UnderhumanStrategy v1.4 (Optimized Profit)
# ============================================================================
# Bazuje na sprawdzonej V1.1 (+3.50% ROI) z optymalizacjami:
# - Lepszy risk/reward (ATR TP 3.5 zamiast 3.0)
# - Wyższe min TP (4.0% zamiast 3.0%)
# - Wyższy próg pewności (8.5 zamiast 8.0)
# - Wcześniejszy trailing stop ($100 zamiast $200)
# - RSI confirmation i extreme filter
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

# Parametry domyślne
BALANCE=10000
LEVERAGE=10.0
POSITION_SIZE=15.0
VERBOSE=false

# Parsowanie argumentów
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
        -h|--help)
            echo "Użycie: $0 [opcje]"
            echo ""
            echo "Opcje:"
            echo "  --balance=KWOTA         Początkowy kapitał (domyślnie: 10000)"
            echo "  --leverage=WSP         Dźwignia (domyślnie: 10.0)"
            echo "  --position-size=PROC    Rozmiar pozycji w % (domyślnie: 15.0)"
            echo "  --verbose, -v           Szczegółowe logowanie"
            echo "  -h, --help              Pokaż tę pomoc"
            echo ""
            echo "Przykłady:"
            echo "  $0                      # Test z domyślnymi parametrami"
            echo "  $0 --balance=50000 --leverage=5.0"
            echo ""
            echo "Uwaga: Dane są pobierane z bazy danych PostgreSQL."
            echo "       Upewnij się, że baza jest dostępna i zawiera dane BTC/USDC."
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

log_info "═══════════════════════════════════════════════════════════════"
log_info "🧪 Test Backtestowy UnderhumanStrategy v1.4"
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

python tests/integration/test_under_human_strategy_1.4.py \
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
    log_info "📝 Sprawdź logi w: .dev/logs/strategies/under_human_strategy_1.4.log"
else
    log_error "❌ Test zakończony z błędem (kod: $EXIT_CODE)"
    log_error "   Sprawdź połączenie z PostgreSQL i czy dane są dostępne"
fi

exit $EXIT_CODE

