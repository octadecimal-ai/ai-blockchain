#!/bin/bash

# ============================================================================
# Uruchomienie UnderhumanStrategy w trybie live trading
# ============================================================================
# Uruchamia strategię UnderhumanStrategy na aktualnych danych z dYdX
# w trybie paper trading (wirtualne pieniądze).
#
# Użycie:
#   ./scripts/run_underhuman_strategy.sh --v=1.0
#   ./scripts/run_underhuman_strategy.sh --v=1.4 --balance=50000 --interval=60
#
# Autor: AI Assistant
# Data: 2025-12-18
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

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
VERSION="1.0"
BALANCE=10000
INTERVAL=60
LEVERAGE=10.0
POSITION_SIZE=15.0
SYMBOLS="BTC-USD"
ACCOUNT="underhuman_bot"
VERBOSE=false
STATUS=false
RESET=false

# === Parsowanie argumentów ===
while [[ $# -gt 0 ]]; do
    case $1 in
        --v=*|--version=*)
            VERSION="${1#*=}"
            shift
            ;;
        --balance=*)
            BALANCE="${1#*=}"
            shift
            ;;
        --interval=*)
            INTERVAL="${1#*=}"
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
        --symbols=*)
            SYMBOLS="${1#*=}"
            shift
            ;;
        --account=*)
            ACCOUNT="${1#*=}"
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --status|-s)
            STATUS=true
            shift
            ;;
        --reset)
            RESET=true
            shift
            ;;
        --help|-h)
            echo ""
            echo -e "${MAGENTA}🚀 Uruchomienie UnderhumanStrategy w trybie live trading${NC}"
            echo ""
            echo "Uruchamia strategię UnderhumanStrategy na aktualnych danych z dYdX"
            echo "w trybie paper trading (wirtualne pieniądze)."
            echo ""
            echo "Użycie:"
            echo "  $0 [opcje]"
            echo ""
            echo "Opcje:"
            echo "  --v=VERSION, --version=VERSION"
            echo "                        Wersja strategii (1.0, 1.1, 1.2, 1.3, 1.4)"
            echo "                        Domyślnie: 1.0"
            echo ""
            echo "  --balance=KWOTA        Początkowy kapitał w USD (domyślnie: 10000)"
            echo "  --interval=SEKUNDY     Interwał sprawdzania w sekundach (domyślnie: 60)"
            echo "  --leverage=WSP         Dźwignia (domyślnie: 10.0)"
            echo "  --position-size=PROC   Rozmiar pozycji w % (domyślnie: 15.0)"
            echo "  --symbols=SYMBOL       Symbole do monitorowania (domyślnie: BTC-USD)"
            echo "  --account=NAZWA        Nazwa konta paper trading (domyślnie: underhuman_bot)"
            echo "  --status, -s           Pokaż status konta i wyjdź"
            echo "  --reset                Zresetuj konto do stanu początkowego"
            echo "  --verbose, -v          Szczegółowe logowanie"
            echo "  --help, -h             Pokaż tę pomoc"
            echo ""
            echo "Przykłady:"
            echo "  # Uruchom v1.0 z domyślnymi ustawieniami"
            echo "  $0 --v=1.0"
            echo ""
            echo "  # Uruchom v1.4 z własną konfiguracją"
            echo "  $0 --v=1.4 --balance=50000 --interval=60"
            echo ""
            echo "  # Pokaż status konta"
            echo "  $0 --v=1.0 --status"
            echo ""
            echo "  # Resetuj konto"
            echo "  $0 --v=1.0 --reset"
            echo ""
            exit 0
            ;;
        *)
            log_error "Nieznany argument: $1"
            echo "Użyj --help aby zobaczyć dostępne opcje"
            exit 1
            ;;
    esac
done

# === Sprawdź czy venv istnieje ===
if [ ! -d "venv" ]; then
    log_error "Środowisko wirtualne nie istnieje. Uruchom: python -m venv venv"
    exit 1
fi

# === Aktywuj venv ===
log_info "Aktywuję środowisko wirtualne..."
source venv/bin/activate

# === Sprawdź czy .env istnieje ===
if [ ! -f ".env" ]; then
    log_warning "Plik .env nie istnieje. Upewnij się, że zmienne środowiskowe są ustawione."
fi

# === Walidacja wersji ===
VALID_VERSIONS=("1.0" "1.1" "1.2" "1.3" "1.4")
if [[ ! " ${VALID_VERSIONS[@]} " =~ " ${VERSION} " ]]; then
    log_error "Nieprawidłowa wersja: $VERSION"
    log_info "Dostępne wersje: ${VALID_VERSIONS[*]}"
    exit 1
fi

# === Wyświetl informacje ===
log_info "═══════════════════════════════════════════════════════════════"
log_info "🚀 UNDERHUMAN STRATEGY v${VERSION} - LIVE TRADING"
log_info "═══════════════════════════════════════════════════════════════"
log_info "Wersja strategii:    v${VERSION}"
log_info "Kapitał:             \$${BALANCE}"
log_info "Interwał:             ${INTERVAL}s"
log_info "Dźwignia:             ${LEVERAGE}x"
log_info "Rozmiar pozycji:     ${POSITION_SIZE}%"
log_info "Symbole:              ${SYMBOLS}"
log_info "Konto:                ${ACCOUNT}"
if [ "$VERBOSE" = true ]; then
    log_info "Tryb:                 Verbose (szczegółowe logi)"
fi
log_info "═══════════════════════════════════════════════════════════════"
echo ""

# === Przygotuj argumenty dla skryptu Python ===
PYTHON_ARGS=(
    "--v=${VERSION}"
    "--balance=${BALANCE}"
    "--interval=${INTERVAL}"
    "--leverage=${LEVERAGE}"
    "--position-size=${POSITION_SIZE}"
    "--symbols=${SYMBOLS}"
    "--account=${ACCOUNT}"
)

if [ "$VERBOSE" = true ]; then
    PYTHON_ARGS+=("--verbose")
fi

if [ "$STATUS" = true ]; then
    PYTHON_ARGS+=("--status")
fi

if [ "$RESET" = true ]; then
    PYTHON_ARGS+=("--reset")
fi

# === Uruchom skrypt Python ===
python scripts/run_underhuman_strategy.py "${PYTHON_ARGS[@]}"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log_success "✅ Zakończono pomyślnie"
else
    log_error "❌ Zakończono z błędem (kod: $EXIT_CODE)"
fi

exit $EXIT_CODE

