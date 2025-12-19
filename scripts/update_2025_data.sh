#!/bin/bash

# ============================================================================
# Update 2025 Data - Uzupełnienie danych BTC/USDT do aktualnej daty
# ============================================================================
# Pobiera brakujące dane z Binance i aktualizuje plik CSV dla 2025 roku.
#
# Użycie:
#   ./scripts/update_2025_data.sh
#
# Autor: AI Assistant
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

# === Sprawdzenie środowiska ===
log_info "Sprawdzam środowisko..."

# Sprawdź czy jesteśmy w katalogu projektu
if [ ! -f "scripts/update_2025_data.py" ]; then
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

# Sprawdź czy plik CSV istnieje
CSV_FILE="data/backtest_periods/binance/BTCUSDT_2025_1h.csv"
if [ ! -f "$CSV_FILE" ]; then
    log_error "Plik CSV nie istnieje: $CSV_FILE"
    log_info "Najpierw musisz pobrać dane z 2025 roku"
    exit 1
fi

# Wyświetl informacje o aktualnym stanie
if command -v python3 &> /dev/null; then
    log_info "📂 Aktualny stan danych:"
    python3 << 'EOF'
import pandas as pd
from pathlib import Path

csv_file = Path("data/backtest_periods/binance/BTCUSDT_2025_1h.csv")
if csv_file.exists():
    df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
    print(f"  Ostatnia świeca: {df.index[-1]}")
    print(f"  Liczba świec: {len(df)}")
else:
    print("  Plik nie istnieje")
EOF
fi

# === Wyświetl banner ===
echo ""
echo -e "${MAGENTA}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║${NC}  ${WHITE}🔄 UZUPEŁNIANIE DANYCH 2025 - BTC/USDT${NC}                        ${MAGENTA}║${NC}"
echo -e "${MAGENTA}╠══════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${MAGENTA}║${NC}  Pobieranie brakujących danych z Binance do aktualnej daty      ${MAGENTA}║${NC}"
echo -e "${MAGENTA}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# === Potwierdzenie ===
read -p "$(echo -e ${YELLOW}Czy chcesz zaktualizować dane? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Anulowano"
    exit 0
fi

# === Uruchomienie ===
echo ""
log_info "Uruchamiam aktualizację danych..."
echo ""

python scripts/update_2025_data.py

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    log_success "Aktualizacja zakończona pomyślnie!"
    echo ""
    log_info "📊 Sprawdź zaktualizowane dane:"
    echo "  cat data/backtest_periods/binance/BTCUSDT_2025_1h_metadata.json"
    echo ""
    log_info "💡 Możesz teraz uruchomić backtest:"
    echo "  ./scripts/test_piotr_swiec_2025.sh"
else
    log_error "Aktualizacja zakończona z błędem (kod: $EXIT_CODE)"
    exit $EXIT_CODE
fi

