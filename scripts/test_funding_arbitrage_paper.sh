#!/bin/bash

# ============================================================================
# Funding Rate Arbitrage - Paper Trading Test Script
# ============================================================================
# Skrypt do testowania strategii Funding Rate Arbitrage na dYdX
# w trybie paper trading (wirtualne pieniądze) z optymalnymi parametrami.
#
# Użycie:
#   ./scripts/test_funding_arbitrage_paper.sh
#
# Autor: AI Assistant
# Data: 2025-12-11
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

# === Parametry optymalne dla pierwszego testu ===
# Na podstawie analizy strategii i testów backtestingu

STRATEGY="funding_rate_arbitrage"
MODE="paper"
SYMBOLS="BTC-USD"  # Zacznij od jednego symbolu
BALANCE=10000000      # $10,000 początkowego kapitału
INTERVAL="30sek"   # Sprawdzanie co godzinę (funding rate zmienia się co 8h)
TIME_LIMIT="24h"   # Test przez 24 godziny
MAX_LOSS="1000000"     # Maksymalna strata $500 (5% kapitału)

# Parametry strategii (dostosowane do obecnego funding rate ~0.0010%)
MIN_FUNDING_RATE="0.0001"      # 0.005% na 8h (niższy próg dla pierwszego testu)
TARGET_FUNDING_RATE="0.006"   # 0.06% na 8h (docelowa stopa)
MAX_POSITION_SIZE="50.0"     # 30% kapitału (konserwatywne)
MIN_HOLDING_HOURS="1"       # Trzymaj minimum 48h (2-3 płatności funding)

log_info "Parametry testu:"
echo "  Strategia: $STRATEGY"
echo "  Tryb: $MODE (paper trading)"
echo "  Symbol: $SYMBOLS"
echo "  Kapitał: \$$BALANCE"
echo "  Interwał: $INTERVAL"
echo "  Limit czasu: $TIME_LIMIT"
echo "  Max strata: \$$MAX_LOSS"
echo ""
echo "  Parametry strategii:"
echo "    Min funding rate: ${MIN_FUNDING_RATE}% na 8h"
echo "    Target funding rate: ${TARGET_FUNDING_RATE}% na 8h"
echo "    Max rozmiar pozycji: ${MAX_POSITION_SIZE}%"
echo "    Min czas trzymania: ${MIN_HOLDING_HOURS}h"
echo ""

# === Potwierdzenie ===
read -p "$(echo -e ${YELLOW}Czy chcesz uruchomić test? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Anulowano"
    exit 0
fi

# === Uruchomienie ===
log_info "Uruchamiam test Funding Rate Arbitrage..."
echo ""

# Uruchom run_paper_trading_enhanced.py bezpośrednio z parametrami
python scripts/run_paper_trading_enhanced.py \
    --account="funding_arbitrage_test" \
    --balance="$BALANCE" \
    --symbols="$SYMBOLS" \
    --strategy="funding_rate_arbitrage" \
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
    echo "  sqlite3 data/paper_trading.db \"SELECT name, current_balance, total_trades, win_rate, roi FROM paper_accounts;\""
else
    log_error "Test zakończony z błędem (kod: $EXIT_CODE)"
    exit $EXIT_CODE
fi

