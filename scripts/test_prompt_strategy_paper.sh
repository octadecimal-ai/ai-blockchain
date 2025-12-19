#!/bin/bash

# ============================================================================
# Prompt Strategy - Paper Trading Test Script
# ============================================================================
# Skrypt do testowania strategii Prompt Strategy (LLM-based) na dYdX
# w trybie paper trading (wirtualne pieniądze).
#
# Użycie:
#   ./scripts/test_prompt_strategy_paper.sh --prompt-file=prompts/trading/prompt_strategy_example.txt
#
# Autor: AI Assistant
# Data: 2025-12-12
# ============================================================================

set -e  # Exit on error

# === Kolory ===
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
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
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}

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

# === Parametry ===
STRATEGY="prompt_strategy"
MODE="paper"
SYMBOLS="BTC-USD"  # Zacznij od jednego symbolu
BALANCE=10000      # $10,000 początkowego kapitału
INTERVAL="1h"      # Sprawdzanie co godzinę
TIME_LIMIT="12h"   # Test przez 12 godzin
MAX_LOSS="1000"    # Maksymalna strata $1000 (10% kapitału)

# Prompt file (domyślnie przykład)
PROMPT_FILE="${1:-prompts/trading/prompt_strategy_example.txt}"

# Sprawdź czy plik promptu istnieje
if [ ! -f "$PROMPT_FILE" ]; then
    log_error "Plik promptu nie istnieje: $PROMPT_FILE"
    log_info "Użycie: $0 <ścieżka-do-pliku-promptu>"
    log_info "Przykład: $0 prompts/trading/prompt_strategy_example.txt"
    exit 1
fi

# Sprawdź czy API key jest ustawiony
if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    log_warning "Brak API key dla LLM!"
    log_info "Ustaw ANTHROPIC_API_KEY lub OPENAI_API_KEY w zmiennych środowiskowych"
    log_info "Przykład: export ANTHROPIC_API_KEY=sk-ant-..."
    log_info "Lub dodaj do pliku .env"
    read -p "$(echo -e ${YELLOW}Kontynuuj bez API key? (nie będzie działać) [y/N]: ${NC})" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

log_info "Parametry testu:"
echo "  Strategia: $STRATEGY (LLM-based)"
echo "  Tryb: $MODE (paper trading)"
echo "  Symbol: $SYMBOLS"
echo "  Kapitał: \$$BALANCE"
echo "  Interwał: $INTERVAL"
echo "  Limit czasu: $TIME_LIMIT"
echo "  Max strata: \$$MAX_LOSS"
echo "  Plik promptu: $PROMPT_FILE"
echo ""

# === Potwierdzenie ===
read -p "$(echo -e ${YELLOW}Czy chcesz uruchomić test? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Anulowano"
    exit 0
fi

# === Uruchomienie ===
log_info "Uruchamiam test Prompt Strategy (LLM-based)..."
echo ""
log_warning "UWAGA: Strategia używa LLM API - mogą wystąpić opłaty!"
echo ""

# Uruchom run_paper_trading_enhanced.py bezpośrednio z parametrami
python scripts/run_paper_trading_enhanced.py \
    --account="prompt_strategy_test" \
    --balance="$BALANCE" \
    --symbols="$SYMBOLS" \
    --strategy="prompt_strategy" \
    --prompt-file="$PROMPT_FILE" \
    --interval="$INTERVAL" \
    --time-limit="$TIME_LIMIT" \
    --max-loss="$MAX_LOSS" \
    --leverage=2.0

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log_success "Test zakończony pomyślnie!"
    echo ""
    log_info "Sprawdź wyniki w bazie danych:"
    echo "  sqlite3 data/paper_trading.db \"SELECT * FROM paper_trades ORDER BY created_at DESC LIMIT 10;\""
    echo ""
    log_info "Sprawdź status konta:"
    echo "  sqlite3 data/paper_trading.db \"SELECT name, current_balance, total_trades, win_rate, roi FROM paper_accounts WHERE name='prompt_strategy_test';\""
    echo ""
    log_info "Sprawdź otwarte pozycje:"
    echo "  sqlite3 data/paper_trading.db \"SELECT * FROM paper_positions WHERE status='open';\""
else
    log_error "Test zakończony z błędem (kod: $EXIT_CODE)"
    exit $EXIT_CODE
fi

