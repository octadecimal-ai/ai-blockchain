#!/bin/bash

# ============================================================================
# Sentiment Propagation Strategy - Paper Trading
# ============================================================================
# Skrypt do uruchomienia strategii Propagacji Sentymentu na dYdX
# w trybie paper trading (wirtualne pieniądze).
#
# Strategia wykorzystuje:
# - GDELT API do pobierania sentymentu z mediów z różnych krajów
# - Analizę propagacji sentymentu między regionami (timezone-aware)
# - Wykrywanie "fal" sentymentu propagujących się globalnie
# - Korelację z cenami BTC
#
# Użycie:
#   ./scripts/run_sentiment_propagation_strategy.sh
#   ./scripts/run_sentiment_propagation_strategy.sh --symbols=BTC-USD --time-limit=12h
#   ./scripts/run_sentiment_propagation_strategy.sh --balance=50000 --interval=1h
#
# Autor: AI Assistant
# Data: 2025-12-18
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

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

log_strategy() {
    echo -e "${MAGENTA}[STRATEGY]${NC} $1"
}

# === Domyślne parametry ===
INTERVAL="1h"  # Strategia używa danych godzinowych
BALANCE=10000
TIME_LIMIT="24h"
MODE="paper"
MAX_LOSS=1000
SYMBOLS="BTC-USD"
ACCOUNT="sentiment_propagation_bot"
LEVERAGE=2.0
VERBOSE=false
SENTIMENT_SOURCE="llm"  # llm lub gdelt

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
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --sentiment-source=*)
            SENTIMENT_SOURCE="${1#*=}"
            # Walidacja
            if [[ "$SENTIMENT_SOURCE" != "llm" && "$SENTIMENT_SOURCE" != "gdelt" ]]; then
                log_error "Nieprawidłowe źródło sentymentu: $SENTIMENT_SOURCE (dozwolone: llm, gdelt)"
                exit 1
            fi
            shift
            ;;
        --help|-h)
            echo "Użycie: $0 [OPCJE]"
            echo ""
            echo "SENTIMENT PROPAGATION STRATEGY"
            echo "Strategia oparta na propagacji sentymentu między regionami świata."
            echo ""
            echo "Opcje:"
            echo "  --interval=CZAS      Interwał sprawdzania (domyślnie: 1h)"
            echo "  --balance=KWOTA      Początkowy kapitał (domyślnie: 10000)"
            echo "  --time-limit=CZAS    Limit czasu (domyślnie: 24h)"
            echo "  --max-loss=KWOTA     Maksymalna strata w USD (domyślnie: 1000)"
            echo "  --symbols=SYMBOL     Symbole (domyślnie: BTC-USD)"
            echo "  --account=NAZWA      Nazwa konta (domyślnie: sentiment_propagation_bot)"
            echo "  --leverage=WSP       Dźwignia (domyślnie: 2.0)"
            echo "  --sentiment-source=ŹRÓDŁO  Źródło danych sentymentu: llm lub gdelt (domyślnie: llm)"
            echo "  --verbose, -v        Szczegółowe logowanie"
            echo "  --help, -h            Pokaż tę pomoc"
            echo ""
            echo "Przykłady:"
            echo "  $0"
            echo "  $0 --symbols=BTC-USD --time-limit=12h"
            echo "  $0 --balance=50000 --interval=1h --max-loss=2000"
            echo "  $0 --sentiment-source=llm    # Użyj danych z llm_sentiment_analysis (domyślnie)"
            echo "  $0 --sentiment-source=gdelt  # Użyj danych z GDELT API"
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
if [ ! -f "scripts/run_paper_trading_enhanced.py" ]; then
    log_error "Musisz uruchomić skrypt z katalogu głównego projektu!"
    exit 1
fi

# Załaduj zmienne z .env jeśli istnieje
# Używamy Python dotenv zamiast source .env (bezpieczniejsze dla URL-i z ://)
if [ -f ".env" ]; then
    log_info "Ładuję zmienne z .env..."
    # Eksportuj zmienne z .env używając Python dotenv (obsługuje URL-e z ://)
    eval "$(python -c "
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path('.env')
if env_path.exists():
    load_dotenv(env_path)
    # Eksportuj wszystkie zmienne z .env
    for key, value in os.environ.items():
        if key.startswith('DATABASE_') or key.startswith('ANTHROPIC_') or key.startswith('LLM_'):
            # Escape specjalne znaki dla bash
            value_escaped = value.replace('\"', '\\\"').replace('\$', '\\\$')
            print(f'export {key}=\"{value_escaped}\"')
")"
    log_success "Zmienne z .env załadowane"
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

# Sprawdź czy DATABASE_URL jest ustawiony (PostgreSQL)
if [ -z "${DATABASE_URL:-}" ]; then
    log_error "DATABASE_URL nie jest ustawiony! Ustaw zmienną środowiskową DATABASE_URL (PostgreSQL)"
    log_error "Lub dodaj DATABASE_URL do pliku .env"
    exit 1
fi
log_info "Używam PostgreSQL: ${DATABASE_URL#*@}"

# Sprawdź czy pytz jest zainstalowany (wymagane dla timezone-aware analizy)
if ! python -c "import pytz" 2>/dev/null; then
    log_warning "pytz nie jest zainstalowany, instaluję..."
    pip install pytz
    log_success "pytz zainstalowany"
fi

# === Wyświetl parametry ===
log_info "═══════════════════════════════════════════════════════════════"
log_strategy "🌊 SENTIMENT PROPAGATION STRATEGY"
log_info "═══════════════════════════════════════════════════════════════"
log_info "Parametry uruchomienia:"
echo "  Strategia:     SentimentPropagationStrategy"
echo "  Tryb:          $MODE"
echo "  Symbole:       $SYMBOLS"
echo "  Kapitał:       \$$BALANCE"
echo "  Interwał:      $INTERVAL"
echo "  Limit czasu:   $TIME_LIMIT"
echo "  Max strata:    \$$MAX_LOSS"
echo "  Konto:         $ACCOUNT"
echo "  Dźwignia:      ${LEVERAGE}x"
echo "  Źródło sentymentu: $SENTIMENT_SOURCE"
log_info "═══════════════════════════════════════════════════════════════"
echo ""

log_info "📊 Strategia wykorzystuje:"
if [ "$SENTIMENT_SOURCE" = "llm" ]; then
    echo "  • LLM Sentiment Analysis - dane z tabeli llm_sentiment_analysis (baza danych)"
    echo "  • Fallback do GDELT API - jeśli brak danych w bazie"
    log_warning "⚠️  UWAGA (LLM):"
    echo "    • Strategia wymaga danych w tabeli llm_sentiment_analysis (zbierane przez llm_sentiment_daemon)"
    echo "    • Jeśli brak danych w bazie, strategia użyje GDELT API jako fallback"
    echo "    • Upewnij się, że llm_sentiment_daemon działa i zbiera dane"
else
    echo "  • GDELT API - sentyment z mediów z całego świata"
    log_warning "⚠️  UWAGA (GDELT):"
    echo "    • Strategia wymaga połączenia internetowego (GDELT API)"
    echo "    • Pierwsze uruchomienie może zająć chwilę (pobieranie danych sentymentu)"
fi
echo "  • Timezone-aware analiza - uwzględnia strefy czasowe i aktywne okna"
echo "  • Wykrywanie fal sentymentu propagujących się między regionami"
echo "  • Korelacja z cenami BTC"
echo "  • Strategia cache'uje wyniki analizy na 1 godzinę"
echo ""

# === Potwierdzenie ===
read -p "$(echo -e ${YELLOW}Czy chcesz uruchomić strategię? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Anulowano"
    exit 0
fi

# === Uruchomienie ===
log_info "Uruchamiam Sentiment Propagation Strategy..."
echo ""

VERBOSE_FLAG=""
if [ "$VERBOSE" = true ]; then
    VERBOSE_FLAG="--verbose"
fi

# Uruchom run_paper_trading_enhanced.py z parametrami
python scripts/run_paper_trading_enhanced.py \
    --account="$ACCOUNT" \
    --balance="$BALANCE" \
    --symbols="$SYMBOLS" \
    --strategy="sentiment_propagation_strategy" \
    --interval="$INTERVAL" \
    --time-limit="$TIME_LIMIT" \
    --max-loss="$MAX_LOSS" \
    --leverage="$LEVERAGE" \
    --sentiment-source="$SENTIMENT_SOURCE" \
    $VERBOSE_FLAG

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log_success "✅ Strategia zakończona pomyślnie!"
    echo ""
    log_info "Sprawdź wyniki w bazie danych PostgreSQL:"
    echo "  psql \$DATABASE_URL -c \"SELECT * FROM paper_trades ORDER BY created_at DESC LIMIT 10;\""
    echo ""
    log_info "Sprawdź status konta:"
    echo "  psql \$DATABASE_URL -c \"SELECT name, current_balance, total_trades, win_rate, roi FROM paper_accounts WHERE name='$ACCOUNT';\""
    echo ""
    log_info "Sprawdź otwarte pozycje:"
    echo "  psql \$DATABASE_URL -c \"SELECT * FROM paper_positions WHERE status='open';\""
else
    log_error "❌ Strategia zakończona z błędem (kod: $EXIT_CODE)"
    exit $EXIT_CODE
fi

