#!/bin/bash

# ============================================================================
# Improved Breakout Strategy - Paper Trading Test Script
# ============================================================================
# Skrypt do testowania strategii Improved Breakout na dYdX
# w trybie paper trading (wirtualne pieniądze) z agresywnymi parametrami
# zaprojektowanymi do generowania transakcji w ciągu 12 godzin.
#
# Użycie:
#   ./scripts/test_improved_breakout_paper.sh
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

# === Parametry agresywne dla szybkiego generowania transakcji ===
# Parametry ustawione tak, aby strategia mogła wygenerować transakcje w ciągu 12h

STRATEGY="improved_breakout_strategy"
MODE="paper"
SYMBOLS="BTC-USD,ETH-USD"  # Dwa symbole = więcej okazji
BALANCE=1000000              # $10,000 początkowego kapitału
INTERVAL="30sek"           # Sprawdzanie co 15 minut (szybsze niż 1h)
TIME_LIMIT="12h"           # Test przez 12 godzin
MAX_LOSS="1000000"            # Maksymalna strata $1000 (10% kapitału)

log_info "Parametry testu (AGRESYWNE dla szybkiego generowania transakcji):"
echo "  Strategia: $STRATEGY"
echo "  Tryb: $MODE (paper trading)"
echo "  Symbole: $SYMBOLS"
echo "  Kapitał: \$$BALANCE"
echo "  Interwał: $INTERVAL (sprawdzanie co 15 minut)"
echo "  Limit czasu: $TIME_LIMIT"
echo "  Max strata: \$$MAX_LOSS"
echo ""
echo "  Parametry strategii (agresywne):"
echo "    Breakout threshold: 0.2% (bardzo niski - łatwiej wykryje breakout)"
echo "    Min confidence: 2.5 (niska pewność - łatwiej wygeneruje sygnał)"
echo "    Min volume ratio: 1.2 (niższy próg wolumenu)"
echo "    Trend filter: WYŁĄCZONY (więcej sygnałów)"
echo "    Volume filter: WYŁĄCZONY (więcej sygnałów)"
echo "    RSI oversold: 40 (szerszy zakres)"
echo "    RSI overbought: 60 (szerszy zakres)"
echo ""

# === Potwierdzenie ===
read -p "$(echo -e ${YELLOW}Czy chcesz uruchomić test? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Anulowano"
    exit 0
fi

# === Uruchomienie ===
log_info "Uruchamiam test Improved Breakout Strategy..."
echo ""
log_warning "UWAGA: Parametry są agresywne - strategia może generować więcej transakcji niż normalnie!"
echo ""

# Uruchom run_paper_trading_enhanced.py bezpośrednio z parametrami
python scripts/run_paper_trading_enhanced.py \
    --account="improved_breakout_test" \
    --balance="$BALANCE" \
    --symbols="$SYMBOLS" \
    --strategy="improved_breakout_strategy" \
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
    echo "  sqlite3 data/paper_trading.db \"SELECT name, current_balance, total_trades, win_rate, roi FROM paper_accounts WHERE name='improved_breakout_test';\""
    echo ""
    log_info "Sprawdź otwarte pozycje:"
    echo "  sqlite3 data/paper_trading.db \"SELECT * FROM paper_positions WHERE status='open';\""
else
    log_error "Test zakończony z błędem (kod: $EXIT_CODE)"
    exit $EXIT_CODE
fi

