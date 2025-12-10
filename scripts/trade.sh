#!/bin/bash

# ============================================================================
# AI Blockchain - Trading Script
# ============================================================================
# Skrypt do uruchamiania tradingu na dYdX z parametrami CLI
#
# Użycie:
#   ./scripts/trade.sh --strategy=piotrek_breakout_strategy --mode=paper
#
# Autor: Piotr Adamczyk
# Data: 2024-12-10
# ============================================================================

set -e  # Exit on error

# === Kolory dla outputu ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# === Funkcje pomocnicze ===
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

log_trade() {
    echo -e "${MAGENTA}[TRADE]${NC} $1"
}

show_help() {
    # Zawsze używaj kolorów (terminal je zignoruje jeśli nie wspiera)
    # Chyba że NO_COLOR jest ustawione
    # Wyświetlaj na stderr aby kolory działały nawet przy przekierowaniu
    if [ -z "$NO_COLOR" ]; then
        # Użyj bezpośrednich kodów ANSI - wyświetlaj na stderr
        echo -e "\033[0;36m═══════════════════════════════════════════════════════════════════\033[0m" >&2
        echo -e "\033[1;37mAI Blockchain Trading Script\033[0m" >&2
        echo -e "\033[0;36m═══════════════════════════════════════════════════════════════════\033[0m" >&2
        echo "" >&2
        echo -e "\033[1;33mUŻYCIE:\033[0m" >&2
        echo "    ./scripts/trade.sh [OPCJE]" >&2
        echo "" >&2
        echo -e "\033[1;33mOPCJE:\033[0m" >&2
        echo -e "    \033[0;32m--strategy=NAZWA\033[0m" >&2
        echo "        Nazwa strategii tradingowej" >&2
        echo "        Domyślnie: piotrek_breakout_strategy" >&2
        echo "        Dostępne: piotrek_breakout_strategy" >&2
        echo "" >&2
        echo -e "    \033[0;32m--mode=MODE\033[0m" >&2
        echo "        Tryb tradingu: paper (wirtualne pieniądze) lub real (prawdziwe)" >&2
        echo "        Domyślnie: paper" >&2
        echo "        UWAGA: Tryb 'real' wymaga konfiguracji API keys!" >&2
        echo "" >&2
        echo -e "    \033[0;32m--time-limit=CZAS\033[0m" >&2
        echo "        Maksymalny czas trwania sesji" >&2
        echo "        Format: 10h, 30min, 45sek, lub kombinacja: 2h 30min 15sek" >&2
        echo "        Przykład: --time-limit=10h" >&2
        echo "        Domyślnie: brak limitu" >&2
        echo "" >&2
        echo -e "    \033[0;32m--interval=CZAS\033[0m" >&2
        echo "        Interwał sprawdzania rynku" >&2
        echo "        Format: jak wyżej" >&2
        echo "        Przykład: --interval=5min" >&2
        echo "        Domyślnie: 5min (300 sekund)" >&2
        echo "" >&2
        echo -e "    \033[0;32m--max-loss=KWOTA\033[0m" >&2
        echo "        Maksymalna strata w USD (po osiągnięciu bot się zatrzyma)" >&2
        echo "        Format: liczba z opcjonalną jednostką (USDC/USD)" >&2
        echo "        Przykład: --max-loss=100, --max-loss=50.50USDC" >&2
        echo "        Domyślnie: brak limitu" >&2
        echo "" >&2
        echo -e "    \033[0;32m--symbols=LISTA\033[0m" >&2
        echo "        Lista symboli do monitorowania (oddzielone przecinkami)" >&2
        echo "        Przykład: --symbols=BTC-USD,ETH-USD,SOL-USD" >&2
        echo "        Domyślnie: BTC-USD,ETH-USD" >&2
        echo "" >&2
        echo -e "    \033[0;32m--balance=KWOTA\033[0m" >&2
        echo "        Początkowy kapitał (tylko dla paper trading)" >&2
        echo "        Przykład: --balance=50000" >&2
        echo "        Domyślnie: 10000" >&2
        echo "" >&2
        echo -e "    \033[0;32m--leverage=LICZBA\033[0m" >&2
        echo "        Domyślna dźwignia (1-20x)" >&2
        echo "        Przykład: --leverage=2" >&2
        echo "        Domyślnie: 2" >&2
        echo "" >&2
        echo -e "    \033[0;32m--account=NAZWA\033[0m" >&2
        echo "        Nazwa konta tradingowego" >&2
        echo "        Przykład: --account=my_bot" >&2
        echo "        Domyślnie: piotrek_bot" >&2
        echo "" >&2
        echo -e "    \033[0;32m--verbose, -v\033[0m" >&2
        echo "        Szczegółowe logi (DEBUG level)" >&2
        echo "" >&2
        echo -e "    \033[0;32m--help, -h\033[0m" >&2
        echo "        Pokaż tę pomoc" >&2
        echo "" >&2
        echo -e "\033[1;33mPRZYKŁADY:\033[0m" >&2
        echo -e "    \033[1;37m# Podstawowe uruchomienie (paper trading, 10min)\033[0m" >&2
        echo "    ./scripts/trade.sh --time-limit=10min" >&2
        echo "" >&2
        echo -e "    \033[1;37m# Agresywny trading z małym interwałem\033[0m" >&2
        echo "    ./scripts/trade.sh --interval=1min --leverage=5 --time-limit=1h" >&2
        echo "" >&2
        echo -e "    \033[1;37m# Monitorowanie wielu par z limitem straty\033[0m" >&2
        echo "    ./scripts/trade.sh --symbols=BTC-USD,ETH-USD,SOL-USD --max-loss=100" >&2
        echo "" >&2
        echo -e "    \033[1;37m# Długa sesja z dużym kapitałem\033[0m" >&2
        echo "    ./scripts/trade.sh --balance=100000 --time-limit=24h --max-loss=1000" >&2
        echo "" >&2
        echo -e "    \033[1;37m# Verbose mode dla debugowania\033[0m" >&2
        echo "    ./scripts/trade.sh --verbose --interval=30sek --time-limit=5min" >&2
        echo "" >&2
        echo -e "\033[0;36m═══════════════════════════════════════════════════════════════════\033[0m" >&2./trade
        echo ""
        echo -e "\033[1;33mUŻYCIE:\033[0m"
        echo "    ./scripts/trade.sh [OPCJE]"
        echo ""
        echo -e "\033[1;33mOPCJE:\033[0m"
        echo -e "    \033[0;32m--strategy=NAZWA\033[0m"
        echo "        Nazwa strategii tradingowej"
        echo "        Domyślnie: piotrek_breakout_strategy"
        echo "        Dostępne: piotrek_breakout_strategy"
        echo ""
        echo -e "    \033[0;32m--mode=MODE\033[0m"
        echo "        Tryb tradingu: paper (wirtualne pieniądze) lub real (prawdziwe)"
        echo "        Domyślnie: paper"
        echo "        UWAGA: Tryb 'real' wymaga konfiguracji API keys!"
        echo ""
        echo -e "    \033[0;32m--time-limit=CZAS\033[0m"
        echo "        Maksymalny czas trwania sesji"
        echo "        Format: 10h, 30min, 45sek, lub kombinacja: 2h 30min 15sek"
        echo "        Przykład: --time-limit=10h"
        echo "        Domyślnie: brak limitu"
        echo ""
        echo -e "    \033[0;32m--interval=CZAS\033[0m"
        echo "        Interwał sprawdzania rynku"
        echo "        Format: jak wyżej"
        echo "        Przykład: --interval=5min"
        echo "        Domyślnie: 5min (300 sekund)"
        echo ""
        echo -e "    \033[0;32m--max-loss=KWOTA\033[0m"
        echo "        Maksymalna strata w USD (po osiągnięciu bot się zatrzyma)"
        echo "        Format: liczba z opcjonalną jednostką (USDC/USD)"
        echo "        Przykład: --max-loss=100, --max-loss=50.50USDC"
        echo "        Domyślnie: brak limitu"
        echo ""
        echo -e "    \033[0;32m--symbols=LISTA\033[0m"
        echo "        Lista symboli do monitorowania (oddzielone przecinkami)"
        echo "        Przykład: --symbols=BTC-USD,ETH-USD,SOL-USD"
        echo "        Domyślnie: BTC-USD,ETH-USD"
        echo ""
        echo -e "    \033[0;32m--balance=KWOTA\033[0m"
        echo "        Początkowy kapitał (tylko dla paper trading)"
        echo "        Przykład: --balance=50000"
        echo "        Domyślnie: 10000"
        echo ""
        echo -e "    \033[0;32m--leverage=LICZBA\033[0m"
        echo "        Domyślna dźwignia (1-20x)"
        echo "        Przykład: --leverage=2"
        echo "        Domyślnie: 2"
        echo ""
        echo -e "    \033[0;32m--account=NAZWA\033[0m"
        echo "        Nazwa konta tradingowego"
        echo "        Przykład: --account=my_bot"
        echo "        Domyślnie: piotrek_bot"
        echo ""
        echo -e "    \033[0;32m--verbose, -v\033[0m"
        echo "        Szczegółowe logi (DEBUG level)"
        echo ""
        echo -e "    \033[0;32m--help, -h\033[0m"
        echo "        Pokaż tę pomoc"
        echo ""
        echo -e "\033[1;33mPRZYKŁADY:\033[0m"
        echo -e "    \033[1;37m# Podstawowe uruchomienie (paper trading, 10min)\033[0m"
        echo "    ./scripts/trade.sh --time-limit=10min"
        echo ""
        echo -e "    \033[1;37m# Agresywny trading z małym interwałem\033[0m"
        echo "    ./scripts/trade.sh --interval=1min --leverage=5 --time-limit=1h"
        echo ""
        echo -e "    \033[1;37m# Monitorowanie wielu par z limitem straty\033[0m"
        echo "    ./scripts/trade.sh --symbols=BTC-USD,ETH-USD,SOL-USD --max-loss=100"
        echo ""
        echo -e "    \033[1;37m# Długa sesja z dużym kapitałem\033[0m"
        echo "    ./scripts/trade.sh --balance=100000 --time-limit=24h --max-loss=1000"
        echo ""
        echo -e "    \033[1;37m# Verbose mode dla debugowania\033[0m"
        echo "    ./scripts/trade.sh --verbose --interval=30sek --time-limit=5min"
        echo ""
        echo -e "\033[0;36m═══════════════════════════════════════════════════════════════════\033[0m"
    else
        # Wersja bez kolorów (gdy NO_COLOR jest ustawione)
        cat << EOF
═══════════════════════════════════════════════════════════════════
AI Blockchain Trading Script
═══════════════════════════════════════════════════════════════════

UŻYCIE:
    ./scripts/trade.sh [OPCJE]

OPCJE:
    --strategy=NAZWA
        Nazwa strategii tradingowej
        Domyślnie: piotrek_breakout_strategy
        Dostępne: piotrek_breakout_strategy

    --mode=MODE
        Tryb tradingu: paper (wirtualne pieniądze) lub real (prawdziwe)
        Domyślnie: paper
        UWAGA: Tryb 'real' wymaga konfiguracji API keys!

    --time-limit=CZAS
        Maksymalny czas trwania sesji
        Format: 10h, 30min, 45sek, lub kombinacja: 2h 30min 15sek
        Przykład: --time-limit=10h
        Domyślnie: brak limitu

    --interval=CZAS
        Interwał sprawdzania rynku
        Format: jak wyżej
        Przykład: --interval=5min
        Domyślnie: 5min (300 sekund)

    --max-loss=KWOTA
        Maksymalna strata w USD (po osiągnięciu bot się zatrzyma)
        Format: liczba z opcjonalną jednostką (USDC/USD)
        Przykład: --max-loss=100, --max-loss=50.50USDC
        Domyślnie: brak limitu

    --symbols=LISTA
        Lista symboli do monitorowania (oddzielone przecinkami)
        Przykład: --symbols=BTC-USD,ETH-USD,SOL-USD
        Domyślnie: BTC-USD,ETH-USD

    --balance=KWOTA
        Początkowy kapitał (tylko dla paper trading)
        Przykład: --balance=50000
        Domyślnie: 10000

    --leverage=LICZBA
        Domyślna dźwignia (1-20x)
        Przykład: --leverage=2
        Domyślnie: 2

    --account=NAZWA
        Nazwa konta tradingowego
        Przykład: --account=my_bot
        Domyślnie: piotrek_bot

    --verbose, -v
        Szczegółowe logi (DEBUG level)

    --help, -h
        Pokaż tę pomoc

PRZYKŁADY:
    # Podstawowe uruchomienie (paper trading, 10min)
    ./scripts/trade.sh --time-limit=10min

    # Agresywny trading z małym interwałem
    ./scripts/trade.sh --interval=1min --leverage=5 --time-limit=1h

    # Monitorowanie wielu par z limitem straty
    ./scripts/trade.sh --symbols=BTC-USD,ETH-USD,SOL-USD --max-loss=100

    # Długa sesja z dużym kapitałem
    ./scripts/trade.sh --balance=100000 --time-limit=24h --max-loss=1000

    # Verbose mode dla debugowania
    ./scripts/trade.sh --verbose --interval=30sek --time-limit=5min

═══════════════════════════════════════════════════════════════════
EOF
    fi
}

# === Domyślne wartości ===
STRATEGY="piotrek_breakout_strategy"
MODE="paper"
TIME_LIMIT=""
INTERVAL="5min"
MAX_LOSS=""
SYMBOLS="BTC-USD,ETH-USD"
BALANCE="10000"
LEVERAGE="2"
ACCOUNT="piotrek_bot"
VERBOSE=""

# === Parsowanie argumentów ===
for arg in "$@"; do
    case $arg in
        --strategy=*)
            STRATEGY="${arg#*=}"
            shift
            ;;
        --mode=*)
            MODE="${arg#*=}"
            shift
            ;;
        --time-limit=*)
            TIME_LIMIT="${arg#*=}"
            shift
            ;;
        --interval=*)
            INTERVAL="${arg#*=}"
            shift
            ;;
        --max-loss=*)
            MAX_LOSS="${arg#*=}"
            # Usuń USDC/USD z końca jeśli jest
            MAX_LOSS=$(echo "$MAX_LOSS" | sed 's/USDC$//' | sed 's/USD$//')
            shift
            ;;
        --symbols=*)
            SYMBOLS="${arg#*=}"
            shift
            ;;
        --balance=*)
            BALANCE="${arg#*=}"
            shift
            ;;
        --leverage=*)
            LEVERAGE="${arg#*=}"
            shift
            ;;
        --account=*)
            ACCOUNT="${arg#*=}"
            shift
            ;;
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Nieznany argument: $arg"
            echo ""
            show_help
            exit 1
            ;;
    esac
done

# === Walidacja ===
if [[ "$MODE" != "paper" && "$MODE" != "real" ]]; then
    log_error "Nieprawidłowy tryb: $MODE (dozwolone: paper, real)"
    exit 1
fi

if [[ "$MODE" == "real" ]]; then
    log_error "Tryb REAL nie jest jeszcze zaimplementowany!"
    log_warning "Użyj --mode=paper do testowania"
    exit 1
fi

# === Informacje o sesji ===
clear
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${WHITE}           🤖 AI BLOCKCHAIN TRADING BOT 🤖${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
echo ""
log_info "Strategia: ${GREEN}$STRATEGY${NC}"
log_info "Tryb: ${YELLOW}$MODE${NC}"
log_info "Symbole: ${BLUE}$SYMBOLS${NC}"
log_info "Interwał: ${MAGENTA}$INTERVAL${NC}"
[[ -n "$TIME_LIMIT" ]] && log_info "Limit czasu: ${YELLOW}$TIME_LIMIT${NC}"
[[ -n "$MAX_LOSS" ]] && log_info "Max strata: ${RED}\$$MAX_LOSS${NC}"
log_info "Kapitał początkowy: ${GREEN}\$$BALANCE${NC}"
log_info "Dźwignia: ${CYAN}${LEVERAGE}x${NC}"
log_info "Konto: ${WHITE}$ACCOUNT${NC}"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
echo ""

# === Inicjalizacja bazy danych ===
log_info "Sprawdzam bazę danych..."

# Sprawdź czy .env istnieje i ma DATABASE_URL
if [ -f "$PROJECT_DIR/.env" ] && grep -q "DATABASE_URL" "$PROJECT_DIR/.env"; then
    DB_TYPE="PostgreSQL"
    log_info "Znaleziono DATABASE_URL w .env - używam PostgreSQL"
else
    DB_TYPE="SQLite"
    log_info "Brak DATABASE_URL w .env - używam SQLite"
fi

# Sprawdź czy tabele istnieją (dla SQLite sprawdź plik, dla PostgreSQL sprawdź połączenie)
if [ "$DB_TYPE" = "SQLite" ]; then
    if [ ! -f "data/paper_trading.db" ] || [ -z "$(sqlite3 data/paper_trading.db "SELECT name FROM sqlite_master WHERE type='table' AND name='strategies';" 2>/dev/null)" ]; then
        log_warning "Baza SQLite nie istnieje lub jest niekompletna - inicjalizuję..."
        python scripts/init_trading_db.py 2>&1 | grep -v "NotOpenSSLWarning\|could not parse" || true
        log_success "Baza danych zainicjalizowana"
    else
        log_success "Baza SQLite gotowa"
    fi
else
    # Dla PostgreSQL - zawsze sprawdź czy tabele istnieją
    log_info "Sprawdzam tabele w PostgreSQL..."
    python -c "
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

env_path = Path('.env')
if env_path.exists():
    load_dotenv(env_path)

db_url = os.getenv('DATABASE_URL')
if db_url:
    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if 'strategies' in tables:
        print('OK')
    else:
        exit(1)
else:
    exit(1)
" 2>/dev/null
    if [ $? -eq 0 ]; then
        log_success "Baza PostgreSQL gotowa"
    else
        log_warning "Baza PostgreSQL nie jest zainicjalizowana - inicjalizuję..."
        python scripts/init_trading_db.py 2>&1 | grep -v "NotOpenSSLWarning\|could not parse" || true
        log_success "Baza danych zainicjalizowana"
    fi
fi
echo ""

# === Uruchomienie bota ===
log_info "Uruchamiam bota tradingowego..."
echo ""

# Przygotuj parametry dla Pythona
PYTHON_ARGS="--account=$ACCOUNT --balance=$BALANCE --symbols=$SYMBOLS --leverage=$LEVERAGE"

[[ -n "$TIME_LIMIT" ]] && PYTHON_ARGS="$PYTHON_ARGS --time-limit=$TIME_LIMIT"
[[ -n "$MAX_LOSS" ]] && PYTHON_ARGS="$PYTHON_ARGS --max-loss=$MAX_LOSS"
[[ -n "$INTERVAL" ]] && PYTHON_ARGS="$PYTHON_ARGS --interval=$INTERVAL"
[[ -n "$VERBOSE" ]] && PYTHON_ARGS="$PYTHON_ARGS $VERBOSE"

# Ścieżka do projektu
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Aktywuj venv jeśli istnieje
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Uruchom Pythonowego bota
python scripts/run_paper_trading_enhanced.py $PYTHON_ARGS

# === Podsumowanie ===
EXIT_CODE=$?

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
if [ $EXIT_CODE -eq 0 ]; then
    log_success "Sesja tradingowa zakończona pomyślnie"
else
    log_error "Sesja zakończona z błędem (kod: $EXIT_CODE)"
fi
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
echo ""

exit $EXIT_CODE

