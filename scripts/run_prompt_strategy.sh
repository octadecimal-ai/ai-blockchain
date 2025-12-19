#!/bin/bash

# ============================================================================
# Prompt Strategy - Paper Trading (Domyślne Parametry)
# ============================================================================
# Skrypt do uruchomienia strategii Prompt Strategy (LLM-based) na dYdX
# w trybie paper trading z domyślnymi parametrami.
#
# Użycie:
#   ./scripts/run_prompt_strategy.sh
#   ./scripts/run_prompt_strategy.sh --symbols=BTC-USD,ETH-USD
#   ./scripts/run_prompt_strategy.sh --prompt-file=prompts/trading/my_prompt.txt
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

# === Domyślne parametry ===
INTERVAL="1min"
BALANCE=10000
TIME_LIMIT="8h"
MODE="paper"
MAX_LOSS=100
PROMPT_FILE="prompts/trading/prompt_strategy_example.txt"
SYMBOLS="BTC-USD"
ACCOUNT="prompt_strategy_default"
LEVERAGE=2.0

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
        --prompt-file=*)
            PROMPT_FILE="${1#*=}"
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
            echo "Użycie: $0 [OPCJE]"
            echo ""
            echo "Domyślne parametry:"
            echo "  --interval=1min"
            echo "  --balance=10000"
            echo "  --time-limit=8h"
            echo "  --mode=paper"
            echo "  --max-loss=1000"
            echo "  --prompt-file=prompts/trading/prompt_strategy_example.txt"
            echo "  --symbols=BTC-USD"
            echo "  --account=prompt_strategy_default"
            echo "  --leverage=2.0"
            echo ""
            echo "Przykłady:"
            echo "  $0"
            echo "  $0 --symbols=BTC-USD,ETH-USD"
            echo "  $0 --prompt-file=prompts/trading/my_prompt.txt --time-limit=12h"
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

# Sprawdź czy plik promptu istnieje
if [ ! -f "$PROMPT_FILE" ]; then
    log_error "Plik promptu nie istnieje: $PROMPT_FILE"
    log_info "Użycie: $0 --prompt-file=<ścieżka-do-pliku-promptu>"
    exit 1
fi

# Załaduj zmienne z .env jeśli istnieje
if [ -f .env ]; then
    # Bezpieczne ładowanie .env - użyj Pythona do parsowania
    # (python-dotenv obsługuje wszystkie przypadki brzegowe)
    if command -v python3 &> /dev/null; then
        # Użyj Pythona do załadowania i wyeksportowania
        while IFS='=' read -r key value; do
            # Pomiń komentarze i puste linie
            [[ "$key" =~ ^#.*$ ]] && continue
            [[ -z "$key" ]] && continue
            
            # Usuń cudzysłowy z wartości jeśli są
            value=$(echo "$value" | sed -e "s/^['\"]//" -e "s/['\"]$//")
            
            # Eksportuj tylko ANTHROPIC_API_KEY i OPENAI_API_KEY
            if [[ "$key" == "ANTHROPIC_API_KEY" ]] || [[ "$key" == "OPENAI_API_KEY" ]]; then
                export "$key=$value"
            fi
        done < <(python3 << 'PYEOF'
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path('.env')
if env_path.exists():
    load_dotenv(env_path)
    for key in ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY']:
        value = os.getenv(key)
        if value:
            print(f"{key}={value}")
PYEOF
)
        if [ -n "$ANTHROPIC_API_KEY" ] || [ -n "$OPENAI_API_KEY" ]; then
            log_info "Załadowano zmienne z .env"
        fi
    fi
fi

# Sprawdź czy API key jest ustawiony
if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    log_warning "Brak API key dla LLM!"
    log_info "Ustaw ANTHROPIC_API_KEY lub OPENAI_API_KEY w zmiennych środowiskowych"
    log_info "Przykład: export ANTHROPIC_API_KEY=sk-ant-..."
    log_info "Lub dodaj do pliku .env"
    read -p "$(echo -e "${YELLOW}Kontynuuj bez API key? (nie będzie działać) [y/N]: ${NC}")" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        log_success "Znaleziono ANTHROPIC_API_KEY (długość: ${#ANTHROPIC_API_KEY} znaków)"
    elif [ -n "$OPENAI_API_KEY" ]; then
        log_success "Znaleziono OPENAI_API_KEY (długość: ${#OPENAI_API_KEY} znaków)"
    fi
fi

# === Wyświetl parametry ===
log_info "Parametry uruchomienia:"
echo "  Strategia: prompt_strategy (LLM-based)"
echo "  Tryb: $MODE"
echo "  Symbole: $SYMBOLS"
echo "  Kapitał: \$$BALANCE"
echo "  Interwał: $INTERVAL"
echo "  Limit czasu: $TIME_LIMIT"
echo "  Max strata: \$$MAX_LOSS"
echo "  Plik promptu: $PROMPT_FILE"
echo "  Konto: $ACCOUNT"
echo "  Dźwignia: ${LEVERAGE}x"
echo ""

# === Potwierdzenie ===
read -p "$(echo -e ${YELLOW}Czy chcesz uruchomić strategię? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Anulowano"
    exit 0
fi

# === Uruchomienie ===
log_info "Uruchamiam Prompt Strategy (LLM-based)..."
echo ""
if [ -n "$ANTHROPIC_API_KEY" ] || [ -n "$OPENAI_API_KEY" ]; then
    log_warning "UWAGA: Strategia używa LLM API - mogą wystąpić opłaty!"
fi
echo ""

# Uruchom run_paper_trading_enhanced.py z parametrami
python scripts/run_paper_trading_enhanced.py \
    --account="$ACCOUNT" \
    --balance="$BALANCE" \
    --symbols="$SYMBOLS" \
    --strategy="prompt_strategy" \
    --prompt-file="$PROMPT_FILE" \
    --interval="$INTERVAL" \
    --time-limit="$TIME_LIMIT" \
    --max-loss="$MAX_LOSS" \
    --leverage="$LEVERAGE"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log_success "Strategia zakończona pomyślnie!"
    echo ""
    log_info "Sprawdź wyniki w bazie danych:"
    echo "  sqlite3 data/paper_trading.db \"SELECT * FROM paper_trades ORDER BY created_at DESC LIMIT 10;\""
    echo ""
    log_info "Sprawdź status konta:"
    echo "  sqlite3 data/paper_trading.db \"SELECT name, current_balance, total_trades, win_rate, roi FROM paper_accounts WHERE name='$ACCOUNT';\""
    echo ""
    log_info "Sprawdź otwarte pozycje:"
    echo "  sqlite3 data/paper_trading.db \"SELECT * FROM paper_positions WHERE status='open';\""
else
    log_error "Strategia zakończona z błędem (kod: $EXIT_CODE)"
    exit $EXIT_CODE
fi

