#!/bin/bash

# ============================================================================
# Ultra Short Strategy - VWAP Fakeout Strategy
# ============================================================================
# Strategia oparta na VWAP fakeoutach (mean reversion):
# - SHORT: Cena wybija powyżej VWAP (≥+0.5-1.0%), brak kontynuacji, powrót pod VWAP
# - LONG: Cena spada poniżej VWAP (≥-0.5-1.0%), brak kontynuacji, powrót nad VWAP
# - RSI jako filtr (SHORT: ≥65, LONG: ≤35)
# - Mean reversion - oczekiwanie powrotu do VWAP
# - Krótkie timeframe (10-15 minut)
# - Parametry pozycji w USD (300-800 profit, 300-500 loss)
#
# Użycie:
#   ./scripts/run_ultra_short_strategy.sh
#   ./scripts/run_ultra_short_strategy.sh --symbols=BTC-USD,ETH-USD
#
# Autor: AI Assistant
# Data: 2025-12-16
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
INTERVAL="10s"                  # Szybki interwał (10 sekund)
BALANCE=10000
TIME_LIMIT="8h"
MODE="paper"
MAX_LOSS=1000                   # Łączna max strata dla sesji
SYMBOLS="BTC-USD"
ACCOUNT="ultra_short_bot"
LEVERAGE=100.0
PROMPT_FILE="prompts/trading/ultra_short_strategy_prompt.txt"

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
        --prompt-file=*)
            PROMPT_FILE="${1#*=}"
            shift
            ;;
        --help|-h)
            echo ""
            echo -e "${MAGENTA}📊 Ultra Short Strategy - VWAP Fakeout${NC}"
            echo ""
            echo "Strategia oparta na VWAP fakeoutach (mean reversion):"
            echo "  - SHORT: Wybicie powyżej VWAP (≥+0.5-1.0%), brak kontynuacji, powrót pod VWAP"
            echo "  - LONG: Spadek poniżej VWAP (≥-0.5-1.0%), brak kontynuacji, powrót nad VWAP"
            echo "  - RSI jako filtr (SHORT: ≥65, LONG: ≤35)"
            echo "  - Mean reversion - oczekiwanie powrotu do VWAP"
            echo "  - Krótkie timeframe (10-15 minut)"
            echo "  - Parametry pozycji w USD (300-800 profit, 300-500 loss)"
            echo ""
            echo "Użycie:"
            echo "  $0 [opcje]"
            echo ""
            echo "Opcje:"
            echo "  --interval=INTERVAL      Interwał sprawdzania (domyślnie: 30s)"
            echo "  --balance=BALANCE       Początkowy kapitał (domyślnie: 10000)"
            echo "  --time-limit=TIME       Limit czasu (np. 8h, 30min)"
            echo "  --mode=MODE             Tryb (paper/live, domyślnie: paper)"
            echo "  --max-loss=LOSS          Maksymalna strata w USD (domyślnie: 1000)"
            echo "  --symbols=SYMBOLS       Symbole oddzielone przecinkami (domyślnie: BTC-USD)"
            echo "  --account=ACCOUNT       Nazwa konta (domyślnie: ultra_short_bot)"
            echo "  --leverage=LEVERAGE     Dźwignia (domyślnie: 10.0)"
            echo "  --prompt-file=FILE      Ścieżka do pliku z promptem"
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

# === Sprawdź czy plik promptu istnieje ===
if [ ! -f "$PROMPT_FILE" ]; then
    log_error "Plik promptu nie istnieje: $PROMPT_FILE"
    exit 1
fi

# === Sprawdź zmienne środowiskowe ===
if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    log_warning "Brak klucza API (ANTHROPIC_API_KEY lub OPENAI_API_KEY)"
    log_warning "Strategia wymaga klucza API do LLM!"
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
log_info "📊 Ultra Short Strategy - VWAP Fakeout"
log_info "═══════════════════════════════════════════════════════════════"
log_info "Konto:              $ACCOUNT"
log_info "Kapitał:            \$$BALANCE"
log_info "Symbole:            $SYMBOLS"
log_info "Interwał:           $INTERVAL"
log_info "Limit czasu:        $TIME_LIMIT"
log_info "Max strata:         \$$MAX_LOSS"
log_info "Dźwignia:           ${LEVERAGE}x"
log_info "Prompt:             $PROMPT_FILE"
log_info "Tryb:               $MODE"
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
    --strategy="ultra_short_prompt_strategy" \
    --prompt-file="$PROMPT_FILE" \
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

