#!/bin/bash

# ============================================================================
# Prompt Strategy v1.1 - Aggressive Dynamic Trading
# ============================================================================
# Ulepszona strategia LLM z:
# - Wskaźnikami technicznymi (RSI, MACD, Bollinger Bands, ATR)
# - Informacją o otwartych pozycjach
# - Trailing stop loss
# - Agresywnym podejściem do tradingu
#
# Użycie:
#   ./scripts/run_prompt_strategy_v11.sh
#   ./scripts/run_prompt_strategy_v11.sh --symbols=BTC-USD,ETH-USD
#   ./scripts/run_prompt_strategy_v11.sh --timeframe=5min --interval=5min
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
RED='\033[0;31m'
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
    echo -e "${RED}[ERROR]${NC} $1"
}

# === Domyślne parametry ===
# Zoptymalizowane dla dynamicznego tradingu
INTERVAL="5min"                 # Częstsze sprawdzanie dla szybszych reakcji
BALANCE=10000
TIME_LIMIT="12h"                # Dłuższa sesja
MODE="paper"
MAX_LOSS=500                    # Realistyczny max loss (5% kapitału)
PROMPT_FILE="prompts/trading/aggressive_dynamic_v11.txt"
SYMBOLS="BTC-USD"
ACCOUNT="prompt_v11_dynamic"
LEVERAGE=3.0                    # Nieco wyższa dźwignia dla większych zysków

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
            echo ""
            echo -e "${CYAN}🚀 Prompt Strategy v1.1 - Aggressive Dynamic Trading${NC}"
            echo ""
            echo "Użycie: $0 [OPCJE]"
            echo ""
            echo "Domyślne parametry (zoptymalizowane dla dynamicznego tradingu):"
            echo "  --interval=5min       (częstsze sprawdzanie)"
            echo "  --balance=10000"
            echo "  --time-limit=12h      (dłuższa sesja)"
            echo "  --max-loss=500        (5% kapitału)"
            echo "  --prompt-file=prompts/trading/aggressive_dynamic_v11.txt"
            echo "  --symbols=BTC-USD"
            echo "  --account=prompt_v11_dynamic"
            echo "  --leverage=3.0"
            echo ""
            echo "Przykłady:"
            echo "  $0"
            echo "  $0 --symbols=BTC-USD,ETH-USD --time-limit=24h"
            echo "  $0 --interval=1min --max-loss=200"
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

# Sprawdź czy plik promptu istnieje
if [ ! -f "$PROMPT_FILE" ]; then
    log_error "Plik promptu nie istnieje: $PROMPT_FILE"
    log_info "Dostępne prompty:"
    ls -la prompts/trading/*.txt 2>/dev/null || echo "  Brak plików .txt w prompts/trading/"
    exit 1
fi

# Załaduj zmienne z .env jeśli istnieje
if [ -f .env ]; then
    if command -v python3 &> /dev/null; then
        while IFS='=' read -r key value; do
            [[ "$key" =~ ^#.*$ ]] && continue
            [[ -z "$key" ]] && continue
            value=$(echo "$value" | sed -e "s/^['\"]//" -e "s/['\"]$//")
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
    log_error "Brak API key dla LLM!"
    log_info "Ustaw ANTHROPIC_API_KEY lub OPENAI_API_KEY w zmiennych środowiskowych"
    log_info "Przykład: export ANTHROPIC_API_KEY=sk-ant-..."
    exit 1
else
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        log_success "Znaleziono ANTHROPIC_API_KEY"
    elif [ -n "$OPENAI_API_KEY" ]; then
        log_success "Znaleziono OPENAI_API_KEY"
    fi
fi

# === Wyświetl banner i parametry ===
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${WHITE}🚀 PROMPT STRATEGY v1.1 - AGGRESSIVE DYNAMIC TRADING${NC}           ${CYAN}║${NC}"
echo -e "${CYAN}╠══════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${CYAN}║${NC}  Ulepszenia względem v1.0:                                       ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  ✓ Wskaźniki techniczne (RSI, MACD, BB, ATR)                     ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  ✓ Informacja o otwartych pozycjach w promptcie                  ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  ✓ Trailing stop loss                                            ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  ✓ Agresywne zarządzanie pozycjami                               ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

log_info "Parametry uruchomienia:"
echo -e "  ${WHITE}Strategia:${NC}    prompt_strategy_v11 (LLM + Technical Indicators)"
echo -e "  ${WHITE}Tryb:${NC}         $MODE"
echo -e "  ${WHITE}Symbole:${NC}      $SYMBOLS"
echo -e "  ${WHITE}Kapitał:${NC}      \$$BALANCE"
echo -e "  ${WHITE}Interwał:${NC}     $INTERVAL"
echo -e "  ${WHITE}Limit czasu:${NC}  $TIME_LIMIT"
echo -e "  ${WHITE}Max strata:${NC}   \$$MAX_LOSS (${GREEN}$(echo "scale=1; $MAX_LOSS * 100 / $BALANCE" | bc)%${NC} kapitału)"
echo -e "  ${WHITE}Prompt:${NC}       $PROMPT_FILE"
echo -e "  ${WHITE}Konto:${NC}        $ACCOUNT"
echo -e "  ${WHITE}Dźwignia:${NC}     ${LEVERAGE}x"
echo ""

# === Potwierdzenie ===
echo -e "${YELLOW}⚠️  UWAGA: Strategia używa LLM API - mogą wystąpić opłaty!${NC}"
echo ""
read -p "$(echo -e ${YELLOW}Czy chcesz uruchomić strategię? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Anulowano"
    exit 0
fi

# === Uruchomienie ===
echo ""
log_info "Uruchamiam Prompt Strategy v1.1..."
echo ""

# Uruchom run_paper_trading_enhanced.py z parametrami
python scripts/run_paper_trading_enhanced.py \
    --account="$ACCOUNT" \
    --balance="$BALANCE" \
    --symbols="$SYMBOLS" \
    --strategy="prompt_strategy_v11" \
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
    log_info "📋 Otwarte pozycje:"
    echo "  sqlite3 data/paper_trading.db \"SELECT * FROM paper_positions WHERE status='open';\""
else
    log_error "Strategia zakończona z błędem (kod: $EXIT_CODE)"
    exit $EXIT_CODE
fi
