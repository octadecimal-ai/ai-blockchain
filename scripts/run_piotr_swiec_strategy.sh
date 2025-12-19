#!/bin/bash

# ============================================================================
# Strategia Piotra Święsa - Impulse Trading z RSI
# ============================================================================
# Strategia oparta na:
# - RSI > 70 + impuls wzrostowy -> SHORT
# - RSI < 30 + impuls spadkowy -> LONG
# - Target zysku i max straty w USD
# - Cooldown między transakcjami
#
# Użycie:
#   ./scripts/run_piotr_swiec_strategy.sh
#   ./scripts/run_piotr_swiec_strategy.sh --target-profit=1000 --max-loss=300
#   ./scripts/run_piotr_swiec_strategy.sh --symbols=BTC-USD,ETH-USD
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
INTERVAL="1min"                 # Szybki interwał dla impulse trading
BALANCE=10000
TIME_LIMIT="8h"
MODE="paper"
MAX_LOSS=1000                   # Łączna max strata dla sesji (10% kapitału)
SYMBOLS="BTC-USD"
ACCOUNT="piotr_swiec_bot"
LEVERAGE=3.0

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
            echo -e "${MAGENTA}📈 Strategia Piotra Święsa - Impulse Trading z RSI${NC}"
            echo ""
            echo "Użycie: $0 [OPCJE]"
            echo ""
            echo "Domyślne parametry:"
            echo "  --interval=1min       (szybki interwał)"
            echo "  --balance=10000"
            echo "  --time-limit=8h"
            echo "  --max-loss=1000       (10% kapitału)"
            echo "  --symbols=BTC-USD"
            echo "  --account=piotr_swiec_bot"
            echo "  --leverage=3.0"
            echo ""
            echo "Przykłady:"
            echo "  $0"
            echo "  $0 --symbols=BTC-USD,ETH-USD --time-limit=24h"
            echo "  $0 --interval=5min --max-loss=500"
            echo ""
            echo -e "${YELLOW}LOGIKA STRATEGII:${NC}"
            echo "  1. RSI > 70 + impuls wzrostowy -> SHORT"
            echo "  2. RSI < 30 + impuls spadkowy -> LONG"
            echo "  3. Target zysku: \$500 (per trade)"
            echo "  4. Max strata: \$500 (per trade)"
            echo "  5. Max hold: 15 min"
            echo "  6. Cooldown: 2 min między transakcjami"
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

# Sprawdź czy baza danych istnieje
if [ ! -f "data/paper_trading.db" ]; then
    log_warning "Baza danych paper trading nie istnieje, tworzę..."
    python scripts/init_trading_db.py --db=sqlite:///data/paper_trading.db
    log_success "Baza danych utworzona"
fi

# === Wyświetl banner i parametry ===
echo ""
echo -e "${MAGENTA}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║${NC}  ${WHITE}📈 STRATEGIA PIOTRA ŚWIĘSA - IMPULSE TRADING${NC}                    ${MAGENTA}║${NC}"
echo -e "${MAGENTA}╠══════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${MAGENTA}║${NC}  ${GREEN}LOGIKA:${NC}                                                          ${MAGENTA}║${NC}"
echo -e "${MAGENTA}║${NC}  • RSI > 70 + impuls UP  → SHORT (oczekiwana korekta)            ${MAGENTA}║${NC}"
echo -e "${MAGENTA}║${NC}  • RSI < 30 + impuls DOWN → LONG (oczekiwane odbicie)            ${MAGENTA}║${NC}"
echo -e "${MAGENTA}║${NC}  • Target: \$500 | Max Loss: \$500 per trade                       ${MAGENTA}║${NC}"
echo -e "${MAGENTA}║${NC}  • Max hold: 15 min | Cooldown: 2 min                            ${MAGENTA}║${NC}"
echo -e "${MAGENTA}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

log_info "Parametry uruchomienia:"
echo -e "  ${WHITE}Strategia:${NC}    piotr_swiec_strategy (Impulse + RSI)"
echo -e "  ${WHITE}Tryb:${NC}         $MODE"
echo -e "  ${WHITE}Symbole:${NC}      $SYMBOLS"
echo -e "  ${WHITE}Kapitał:${NC}      \$$BALANCE"
echo -e "  ${WHITE}Interwał:${NC}     $INTERVAL"
echo -e "  ${WHITE}Limit czasu:${NC}  $TIME_LIMIT"
echo -e "  ${WHITE}Max strata:${NC}   \$$MAX_LOSS (sesja)"
echo -e "  ${WHITE}Konto:${NC}        $ACCOUNT"
echo -e "  ${WHITE}Dźwignia:${NC}     ${LEVERAGE}x"
echo ""
echo -e "  ${YELLOW}Target profit (trade):${NC} \$500"
echo -e "  ${YELLOW}Max loss (trade):${NC}      \$500"
echo -e "  ${YELLOW}RSI overbought:${NC}        70"
echo -e "  ${YELLOW}RSI oversold:${NC}          30"
echo ""

# === Potwierdzenie ===
echo -e "${YELLOW}⚠️  UWAGA: To jest paper trading - brak rzeczywistych transakcji${NC}"
echo ""
read -p "$(echo -e ${YELLOW}Czy chcesz uruchomić strategię? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Anulowano"
    exit 0
fi

# === Uruchomienie ===
echo ""
log_info "Uruchamiam Strategię Piotra Święsa..."
echo ""

# Uruchom run_paper_trading_enhanced.py z parametrami
python scripts/run_paper_trading_enhanced.py \
    --account="$ACCOUNT" \
    --balance="$BALANCE" \
    --symbols="$SYMBOLS" \
    --strategy="piotr_swiec_strategy" \
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
    log_info "📋 Otwarte pozycje:"
    echo "  sqlite3 data/paper_trading.db \"SELECT * FROM paper_positions WHERE status='open';\""
else
    log_error "Strategia zakończona z błędem (kod: $EXIT_CODE)"
    exit $EXIT_CODE
fi

