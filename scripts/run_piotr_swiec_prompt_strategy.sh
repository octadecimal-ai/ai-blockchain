#!/bin/bash

# ============================================================================
# Strategia Piotra Święsa z LLM (Prompt Strategy)
# ============================================================================
# Strategia oparta na LLM używającym Metody Piotra Święsa:
# - RSI > 70 + gwałtowny ruch UP -> SHORT
# - RSI < 30 + gwałtowny ruch DOWN -> LONG
# - LLM podejmuje decyzję na podstawie obliczonych wskaźników
#
# Użycie:
#   ./scripts/run_piotr_swiec_prompt_strategy.sh
#   ./scripts/run_piotr_swiec_prompt_strategy.sh --symbols=BTC-USD,ETH-USD
#
# Autor: AI Assistant na podstawie strategii Piotra Święsa
# Data: 2025-12-13
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
INTERVAL="30s"                  # Szybki interwał (30 sekund)
BALANCE=10000
TIME_LIMIT="8h"
MODE="paper"
MAX_LOSS=1000                   # Łączna max strata dla sesji
SYMBOLS="BTC-USD"
ACCOUNT="piotr_swiec_llm_bot"
LEVERAGE=10.0
PROMPT_FILE="prompts/trading/piotr_swiec_method.txt"

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
            echo -e "${MAGENTA}🤖 Strategia Piotra Święsa z LLM${NC}"
            echo ""
            echo "Użycie: $0 [OPCJE]"
            echo ""
            echo "Domyślne parametry:"
            echo "  --interval=30s       (szybki interwał)"
            echo "  --balance=10000"
            echo "  --time-limit=8h"
            echo "  --max-loss=1000       (10% kapitału)"
            echo "  --symbols=BTC-USD"
            echo "  --account=piotr_swiec_llm_bot"
            echo "  --leverage=3.0"
            echo "  --prompt-file=prompts/trading/piotr_swiec_method.txt"
            echo ""
            echo "Przykłady:"
            echo "  $0"
            echo "  $0 --symbols=BTC-USD,ETH-USD --time-limit=24h"
            echo "  $0 --interval=1min --max-loss=500"
            echo ""
            echo -e "${YELLOW}LOGIKA STRATEGII (LLM):${NC}"
            echo "  1. RSI > 70 + gwałtowny pump -> SHORT (LLM decyduje)"
            echo "  2. RSI < 30 + gwałtowny dump -> LONG (LLM decyduje)"
            echo "  3. Target zysku: \$800 | Max strata: \$500 per trade"
            echo "  4. Max hold: 15 min | Cooldown: 2 min"
            echo "  5. LLM analizuje kontekst i podejmuje ostateczną decyzję"
            echo ""
            exit 0
            ;;
        *)
            log_error "Nieznany parametr: $1"
            echo "Użyj --help aby zobaczyć dostępne opcje"
            exit 1
            ;;
    esac
done

# === Sprawdzenie środowiska ===
log_info "Sprawdzam środowisko..."

# Sprawdź czy jesteśmy w katalogu projektu
if [ ! -f "scripts/trade.sh" ]; then
    log_error "Musisz uruchomić skrypt z katalogu głównego projektu!"
    exit 1
fi

# Sprawdź czy venv jest aktywne
if [ -z "$VIRTUAL_ENV" ]; then
    log_warning "Venv nie jest aktywne, próbuję aktywować..."
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        log_success "Venv aktywowane"
    else
        log_error "Nie znaleziono venv! Uruchom: python -m venv venv"
        exit 1
    fi
fi

# Sprawdź czy plik prompta istnieje
if [ ! -f "$PROMPT_FILE" ]; then
    log_error "Plik prompta nie istnieje: $PROMPT_FILE"
    exit 1
fi

# Sprawdź czy baza danych istnieje
if [ ! -f "data/paper_trading.db" ]; then
    log_warning "Baza danych paper trading nie istnieje, tworzę..."
    python scripts/init_trading_db.py --db=sqlite:///data/paper_trading.db
    log_success "Baza danych utworzona"
fi

# Sprawdź klucze API
if [ -z "$ANTHROPIC_API_KEY" ]; then
    if [ -f ".env" ]; then
        export $(cat .env | grep ANTHROPIC_API_KEY | xargs)
    fi
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    log_warning "Brak ANTHROPIC_API_KEY - sprawdź plik .env"
fi

# === Wyświetl banner ===
echo ""
echo -e "${MAGENTA}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║${NC}  ${WHITE}🤖 STRATEGIA PIOTRA ŚWIĘSA z LLM${NC}                              ${MAGENTA}║${NC}"
echo -e "${MAGENTA}╠══════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${MAGENTA}║${NC}  ${GREEN}LOGIKA:${NC}                                                          ${MAGENTA}║${NC}"
echo -e "${MAGENTA}║${NC}  • RSI > 70 + gwałtowny pump → SHORT (LLM decyduje)             ${MAGENTA}║${NC}"
echo -e "${MAGENTA}║${NC}  • RSI < 30 + gwałtowny dump → LONG (LLM decyduje)              ${MAGENTA}║${NC}"
echo -e "${MAGENTA}║${NC}  • Target: \$800 | Max Loss: \$500 per trade                      ${MAGENTA}║${NC}"
echo -e "${MAGENTA}║${NC}  • LLM analizuje kontekst i podejmuje decyzję                   ${MAGENTA}║${NC}"
echo -e "${MAGENTA}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

log_info "Parametry uruchomienia:"
echo -e "  ${WHITE}Strategia:${NC}    piotr_swiec_prompt_strategy (LLM + RSI)"
echo -e "  ${WHITE}Tryb:${NC}         $MODE"
echo -e "  ${WHITE}Symbole:${NC}      $SYMBOLS"
echo -e "  ${WHITE}Kapitał:${NC}      \$$BALANCE"
echo -e "  ${WHITE}Interwał:${NC}     $INTERVAL"
echo -e "  ${WHITE}Limit czasu:${NC}  $TIME_LIMIT"
echo -e "  ${WHITE}Max strata:${NC}   \$$MAX_LOSS (sesja)"
echo -e "  ${WHITE}Konto:${NC}        $ACCOUNT"
echo -e "  ${WHITE}Dźwignia:${NC}     ${LEVERAGE}x"
echo -e "  ${WHITE}Prompt:${NC}       $PROMPT_FILE"
echo ""
echo -e "  ${YELLOW}LLM:${NC}           anthropic/claude-3-5-haiku-20241022"
echo -e "  ${YELLOW}RSI:${NC}           14 (overbought: 70, oversold: 30)"
echo -e "  ${YELLOW}Sharp move:${NC}    0.8% w 5 świecach"
echo -e "  ${YELLOW}Target profit:${NC} \$800 per trade"
echo -e "  ${YELLOW}Max loss:${NC}      \$500 per trade"
echo ""

# === Potwierdzenie ===
echo -e "${YELLOW}⚠️  UWAGA: To jest paper trading - brak rzeczywistych transakcji${NC}"
echo -e "${YELLOW}⚠️  LLM będzie podejmował decyzje - może generować koszty API${NC}"
echo ""
read -p "$(echo -e ${YELLOW}Czy chcesz uruchomić strategię? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Anulowano"
    exit 0
fi

# === Uruchomienie ===
echo ""
log_info "Uruchamiam Strategię Piotra Święsa z LLM..."
echo ""

# Uruchom run_paper_trading_enhanced.py z parametrami
python scripts/run_paper_trading_enhanced.py \
    --account="$ACCOUNT" \
    --balance="$BALANCE" \
    --symbols="$SYMBOLS" \
    --strategy="piotr_swiec_prompt_strategy" \
    --prompt-file="$PROMPT_FILE" \
    --interval="$INTERVAL" \
    --time-limit="$TIME_LIMIT" \
    --max-loss="$MAX_LOSS" \
    --leverage="$LEVERAGE"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    log_success "Strategia zakończona pomyślnie!"
    echo ""
    log_info "📊 Sprawdź wyniki:"
    echo "  sqlite3 data/paper_trading.db \"SELECT * FROM paper_trades ORDER BY created_at DESC LIMIT 10;\""
    echo ""
    log_info "📈 Status konta:"
    echo "  sqlite3 data/paper_trading.db \"SELECT name, current_balance, total_trades, win_rate, roi FROM paper_accounts WHERE name='$ACCOUNT';\""
    echo ""
    log_info "📋 Logi API LLM:"
    echo "  tail -100 logs/api_llm_requests_$(date +%Y-%m-%d).log"
else
    log_error "Strategia zakończona z błędem (kod: $EXIT_CODE)"
    exit $EXIT_CODE
fi

