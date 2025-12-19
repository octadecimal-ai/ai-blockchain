#!/bin/bash

# ============================================================================
# Backtest Strategii Piotra Święsa - Dane z 2022 roku
# ============================================================================
# Testuje strategię na danych historycznych BTC/USDT z 2022 roku.
# Dane: 1h timeframe, 8738 świec
#
# Użycie:
#   ./scripts/test_piotr_swiec_2022.sh
#   ./scripts/test_piotr_swiec_2022.sh --param impulse_threshold_pct=1.0
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

# === Domyślne parametry ===
CSV_FILE="data/backtest_periods/binance/BTCUSDT_2022_1h.csv"
METADATA_FILE="data/backtest_periods/binance/BTCUSDT_2022_1h_metadata.json"
BALANCE=10000
LEVERAGE=3.0
POSITION_SIZE=15.0  # 15% kapitału
SLIPPAGE=0.1

# === Parsowanie argumentów ===
PARAMS=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --param=*)
            PARAMS="$PARAMS --param ${1#*=}"
            shift
            ;;
        --balance=*)
            BALANCE="${1#*=}"
            shift
            ;;
        --leverage=*)
            LEVERAGE="${1#*=}"
            shift
            ;;
        --position-size=*)
            POSITION_SIZE="${1#*=}"
            shift
            ;;
        --slippage=*)
            SLIPPAGE="${1#*=}"
            shift
            ;;
        --help|-h)
            echo ""
            echo -e "${MAGENTA}📊 Backtest Strategii Piotra Święsa - 2022${NC}"
            echo ""
            echo "Użycie: $0 [OPCJE]"
            echo ""
            echo "Domyślne parametry:"
            echo "  CSV: $CSV_FILE"
            echo "  Balance: \$$BALANCE"
            echo "  Leverage: ${LEVERAGE}x"
            echo "  Position Size: ${POSITION_SIZE}%"
            echo "  Slippage: ${SLIPPAGE}%"
            echo ""
            echo "Przykłady:"
            echo "  $0"
            echo "  $0 --param impulse_threshold_pct=1.0"
            echo "  $0 --param target_profit_usd=1000 --param max_loss_usd=300"
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
if [ ! -f "scripts/backtest_from_csv.py" ]; then
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
if [ ! -f "$CSV_FILE" ]; then
    log_error "Plik CSV nie istnieje: $CSV_FILE"
    exit 1
fi

# Wyświetl informacje o danych
if [ -f "$METADATA_FILE" ]; then
    log_info "📂 Informacje o danych:"
    echo -e "  ${WHITE}Plik:${NC} $CSV_FILE"
    if command -v python3 &> /dev/null; then
        python3 << EOF
import json
with open('$METADATA_FILE', 'r') as f:
    meta = json.load(f)
    print(f"  Rok: {meta.get('year', 'N/A')}")
    print(f"  Symbol: {meta.get('symbol', 'N/A')}")
    print(f"  Timeframe: {meta.get('timeframe', 'N/A')}")
    print(f"  Świece: {meta.get('candles', 'N/A')}")
    print(f"  Okres: {meta.get('start_date', 'N/A')} → {meta.get('end_date', 'N/A')}")
    print(f"  Cena początkowa: \${meta.get('first_price', 0):,.2f}")
    print(f"  Cena końcowa: \${meta.get('last_price', 0):,.2f}")
    print(f"  Zmiana: {meta.get('change_percent', 0):.2f}%")
EOF
    fi
fi

# === Wyświetl banner ===
echo ""
echo -e "${MAGENTA}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║${NC}  ${WHITE}📊 BACKTEST STRATEGII PIOTRA ŚWIĘSA - 2022${NC}                      ${MAGENTA}║${NC}"
echo -e "${MAGENTA}╠══════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${MAGENTA}║${NC}  ${GREEN}Dane:${NC} BTC/USDT 1h (8738 świec)                                ${MAGENTA}║${NC}"
echo -e "${MAGENTA}║${NC}  ${GREEN}Okres:${NC} 2022-01-01 → 2022-12-31                                ${MAGENTA}║${NC}"
echo -e "${MAGENTA}║${NC}  ${GREEN}Strategia:${NC} PiotrSwiecStrategy (Impulse + RSI)                  ${MAGENTA}║${NC}"
echo -e "${MAGENTA}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

log_info "Parametry backtestu:"
echo -e "  ${WHITE}Kapitał:${NC}      \$$BALANCE"
echo -e "  ${WHITE}Dźwignia:${NC}     ${LEVERAGE}x"
echo -e "  ${WHITE}Position Size:${NC} ${POSITION_SIZE}%"
echo -e "  ${WHITE}Slippage:${NC}     ${SLIPPAGE}%"
echo ""

# === Uruchomienie backtestu ===
log_info "Uruchamiam backtest..."
echo ""

python scripts/backtest_from_csv.py \
    --csv="$CSV_FILE" \
    --strategy=piotr_swiec_strategy \
    --symbol="BTC/USDT" \
    --balance="$BALANCE" \
    --leverage="$LEVERAGE" \
    --position-size="$POSITION_SIZE" \
    --slippage="$SLIPPAGE" \
    $PARAMS

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    log_success "Backtest zakończony pomyślnie!"
    echo ""
    log_info "💡 Aby przetestować z innymi parametrami:"
    echo "  $0 --param impulse_threshold_pct=1.0"
    echo "  $0 --param target_profit_usd=1000 --param max_loss_usd=300"
else
    log_error "Backtest zakończony z błędem (kod: $EXIT_CODE)"
    exit $EXIT_CODE
fi

