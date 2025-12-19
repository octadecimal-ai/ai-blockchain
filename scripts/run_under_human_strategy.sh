#!/bin/bash

# ============================================================================
# Underhuman Strategy
# ============================================================================
# Strategia handlująca zmianę stanu rynku poprzez wykrywanie anomalii strukturalnych:
# - impulse_failure
# - energy_divergence
# - asymmetric_response
# - reaction_delay
#
# Wymaga danych z dYdX:
# - Historia funding rates (doklejana do DataFrame)
# - Open Interest (aktualna wartość)
# - Orderbook (top N poziomów)
#
# Użycie:
#   ./scripts/run_under_human_strategy.sh
#   ./scripts/run_under_human_strategy.sh --symbols=BTC-USD,ETH-USD
#
# Autor: AI Assistant na podstawie strategii GPT 5.1
# Data: 2025-12-17
# ============================================================================

set -e  # Exit on error

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
INTERVAL="30s"                  # Interwał sprawdzania
BALANCE=10000
TIME_LIMIT="8h"
MODE="paper"
MAX_LOSS=1000                   # Łączna max strata dla sesji
SYMBOLS="BTC-USD"
ACCOUNT="under_human_bot"
LEVERAGE=10.0

# === Parsowanie argumentów ===
while [[ $# -gt 0 ]]; do
    case $1 in
        --interval=*)
            INTERVAL="${1#*=}"
            shift
            ;;
        --balance=*)
            BALANCE="${1#*=}"
            shift
            ;;
        --time-limit=*)
            TIME_LIMIT="${1#*=}"
            shift
            ;;
        --mode=*)
            MODE="${1#*=}"
            shift
            ;;
        --max-loss=*)
            MAX_LOSS="${1#*=}"
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
        --leverage=*)
            LEVERAGE="${1#*=}"
            shift
            ;;
        --help|-h)
            echo ""
            echo -e "${MAGENTA}🤖 Underhuman Strategy${NC}"
            echo ""
            echo "Strategia handlująca zmianę stanu rynku poprzez wykrywanie anomalii:"
            echo "  - impulse_failure: Duży wolumen bez kontynuacji"
            echo "  - energy_divergence: Cena vs OI/funding"
            echo "  - asymmetric_response: Różna reakcja na wzrosty/spadki"
            echo "  - reaction_delay: Spowolnienie reakcji rynku"
            echo ""
            echo "Użycie:"
            echo "  $0 [opcje]"
            echo ""
            echo "Opcje:"
            echo "  --interval=INTERVAL      Interwał sprawdzania (domyślnie: 30s)"
            echo "  --balance=BALANCE       Początkowy kapitał (domyślnie: 10000)"
            echo "  --time-limit=TIME       Limit czasu (np. 8h)"
            echo "  --mode=MODE             Tryb (paper/live, domyślnie: paper)"
            echo "  --max-loss=LOSS          Maksymalna strata w USD (domyślnie: 1000)"
            echo "  --symbols=SYMBOLS       Symbole oddzielone przecinkami (domyślnie: BTC-USD)"
            echo "  --account=ACCOUNT       Nazwa konta (domyślnie: under_human_bot)"
            echo "  --leverage=LEVERAGE     Dźwignia (domyślnie: 10.0)"
            echo "  --help, -h              Pokaż tę pomoc"
            echo ""
            echo "Przykłady:"
            echo "  $0"
            echo "  $0 --symbols=BTC-USD,ETH-USD --time-limit=4h"
            echo "  $0 --balance=50000 --max-loss=2000"
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
if [ ! -f "scripts/run_paper_trading_enhanced.py" ]; then
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

# === Wyświetl konfigurację ===
echo ""
log_info "═══════════════════════════════════════════════════════════════"
log_info "🤖 Underhuman Strategy"
log_info "═══════════════════════════════════════════════════════════════"
log_info "Konto:              $ACCOUNT"
log_info "Kapitał:            \$$BALANCE"
log_info "Symbole:            $SYMBOLS"
log_info "Interwał:           $INTERVAL"
log_info "Limit czasu:        $TIME_LIMIT"
log_info "Max strata:         \$$MAX_LOSS"
log_info "Dźwignia:           ${LEVERAGE}x"
log_info "Tryb:               $MODE"
log_info ""
log_info "Wykrywane anomalie:"
log_info "  • impulse_failure"
log_info "  • energy_divergence (OI/funding vs cena)"
log_info "  • asymmetric_response"
log_info "  • reaction_delay"
log_info ""
log_info "Parametry:"
log_info "  • Min anomalii do trade: 2"
log_info "  • Min confidence: 7.0"
log_info "  • Profit: \$400-\$1000 USD"
log_info "  • Loss: max \$500 USD"
log_info "  • Max hold: 15 min"
log_info "═══════════════════════════════════════════════════════════════"
echo ""

# === Uruchom strategię ===
log_info "🚀 Uruchamiam strategię..."
echo ""

python scripts/run_paper_trading_enhanced.py \
    --account="$ACCOUNT" \
    --balance="$BALANCE" \
    --symbols="$SYMBOLS" \
    --leverage="$LEVERAGE" \
    --strategy="under_human_strategy_1.0" \
    --time-limit="$TIME_LIMIT" \
    --interval="$INTERVAL" \
    --max-loss="$MAX_LOSS"

EXIT_CODE=$?

# === Podsumowanie ===
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    log_success "✅ Strategia zakończona pomyślnie"
else
    log_error "❌ Strategia zakończona z błędem (kod: $EXIT_CODE)"
fi

exit $EXIT_CODE

