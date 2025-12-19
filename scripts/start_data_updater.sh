#!/bin/bash

# ============================================================================
# Start Data Updater Daemon
# ============================================================================
# Uruchamia daemon do aktualizacji danych OHLCV i tickers w tle.
# Daemon działa nawet po wylogowaniu z systemu.
#
# Użycie:
#   ./scripts/start_data_updater.sh
#   ./scripts/start_data_updater.sh --symbols=BTC/USDC,ETH/USDC --interval=30
#   ./scripts/start_data_updater.sh --stop  # Zatrzymaj daemon
#   ./scripts/start_data_updater.sh --status  # Sprawdź status
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

# === Pliki ===
PID_FILE="$PROJECT_ROOT/data/data_updater.pid"
LOG_FILE="$PROJECT_ROOT/logs/data_updater.log"
DAEMON_SCRIPT="$SCRIPT_DIR/data_updater_daemon.py"

# === Funkcje daemona ===
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            # PID file istnieje ale proces nie działa - usuń plik
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

start_daemon() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        log_warning "Daemon już działa (PID: $PID)"
        return 1
    fi
    
    log_info "Uruchamiam Data Updater Daemon..."
    
    # Sprawdź czy venv jest aktywne
    if [ -z "$VIRTUAL_ENV" ]; then
        if [ -f "venv/bin/activate" ]; then
            source venv/bin/activate
        else
            log_error "Venv nie jest dostępne!"
            return 1
        fi
    fi
    
    # Uruchom daemon w tle z nohup
    nohup python "$DAEMON_SCRIPT" "$@" > "$LOG_FILE" 2>&1 &
    DAEMON_PID=$!
    
    # Zapisz PID
    echo "$DAEMON_PID" > "$PID_FILE"
    
    # Poczekaj chwilę i sprawdź czy proces nadal działa
    sleep 2
    if ps -p "$DAEMON_PID" > /dev/null 2>&1; then
        log_success "✅ Daemon uruchomiony (PID: $DAEMON_PID)"
        log_info "   Logi: $LOG_FILE"
        log_info "   PID file: $PID_FILE"
        log_info "   Aby zatrzymać: $0 --stop"
        return 0
    else
        log_error "❌ Daemon nie uruchomił się poprawnie"
        rm -f "$PID_FILE"
        log_info "Sprawdź logi: $LOG_FILE"
        return 1
    fi
}

stop_daemon() {
    if ! is_running; then
        log_warning "Daemon nie działa"
        return 1
    fi
    
    PID=$(cat "$PID_FILE")
    log_info "Zatrzymywanie daemona (PID: $PID)..."
    
    # Wyślij SIGTERM
    kill "$PID" 2>/dev/null || true
    
    # Poczekaj na zakończenie
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            log_success "✅ Daemon zatrzymany"
            rm -f "$PID_FILE"
            return 0
        fi
        sleep 1
    done
    
    # Jeśli nadal działa, użyj SIGKILL
    if ps -p "$PID" > /dev/null 2>&1; then
        log_warning "Daemon nie odpowiedział na SIGTERM, używam SIGKILL..."
        kill -9 "$PID" 2>/dev/null || true
        sleep 1
        if ! ps -p "$PID" > /dev/null 2>&1; then
            log_success "✅ Daemon zatrzymany (SIGKILL)"
            rm -f "$PID_FILE"
            return 0
        fi
    fi
    
    log_error "❌ Nie można zatrzymać daemona"
    return 1
}

status_daemon() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        log_success "✅ Daemon działa (PID: $PID)"
        
        # Pokaż statystyki procesu
        if command -v ps > /dev/null; then
            echo ""
            ps -p "$PID" -o pid,ppid,etime,cmd --no-headers | awk '{print "   Uptime: " $3 "\n   Command: " $4 " " $5 " " $6 " ..."}'
        fi
        
        # Pokaż ostatnie linie logów
        if [ -f "$LOG_FILE" ]; then
            echo ""
            log_info "Ostatnie 5 linii z logów:"
            tail -n 5 "$LOG_FILE" | sed 's/^/   /'
        fi
        
        return 0
    else
        log_warning "❌ Daemon nie działa"
        return 1
    fi
}

# === Parsowanie argumentów ===
ACTION="start"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --stop)
            ACTION="stop"
            shift
            ;;
        --status)
            ACTION="status"
            shift
            ;;
        --restart)
            ACTION="restart"
            shift
            ;;
        --symbols=*)
            EXTRA_ARGS+=("--symbols=${1#*=}")
            shift
            ;;
        --exchanges=*)
            EXTRA_ARGS+=("--exchanges=${1#*=}")
            shift
            ;;
        --interval=*)
            EXTRA_ARGS+=("--interval=${1#*=}")
            shift
            ;;
        --verbose|-v)
            EXTRA_ARGS+=("--verbose")
            shift
            ;;
        --help|-h)
            echo "Użycie: $0 [OPCJE]"
            echo ""
            echo "Akcje:"
            echo "  (brak)        Uruchom daemon (domyślnie)"
            echo "  --stop        Zatrzymaj daemon"
            echo "  --status      Sprawdź status daemona"
            echo "  --restart     Zatrzymaj i uruchom ponownie"
            echo ""
            echo "Opcje (tylko przy starcie):"
            echo "  --symbols=SYMBOL1,SYMBOL2   Symbole do aktualizacji (domyślnie: BTC/USDC)"
            echo "  --exchanges=EXCHANGE1,EXCHANGE2   Giełdy (domyślnie: binance,dydx)"
            echo "  --interval=SEKUNDY   Interwał aktualizacji (domyślnie: 60)"
            echo "  --verbose, -v        Szczegółowe logowanie"
            echo ""
            echo "Przykłady:"
            echo "  $0"
            echo "  $0 --symbols=BTC/USDC,ETH/USDC --interval=30"
            echo "  $0 --stop"
            echo "  $0 --status"
            exit 0
            ;;
        *)
            log_error "Nieznany parametr: $1"
            echo "Użyj --help aby zobaczyć dostępne opcje"
            exit 1
            ;;
    esac
done

# === Wykonaj akcję ===
case $ACTION in
    start)
        start_daemon "${EXTRA_ARGS[@]}"
        ;;
    stop)
        stop_daemon
        ;;
    status)
        status_daemon
        ;;
    restart)
        if is_running; then
            stop_daemon
            sleep 2
        fi
        start_daemon "${EXTRA_ARGS[@]}"
        ;;
esac

