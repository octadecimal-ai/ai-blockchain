#!/bin/bash

# ============================================================================
# Start GDELT Sentiment Daemon
# ============================================================================
# Uruchamia daemon do zbierania danych sentymentu z GDELT API w tle.
# Daemon działa nawet po wylogowaniu z systemu.
#
# Użycie:
#   ./scripts/start_gdelt_sentiment_daemon.sh
#   ./scripts/start_gdelt_sentiment_daemon.sh --interval=3600 --countries=US,CN,JP
#   ./scripts/start_gdelt_sentiment_daemon.sh --stop  # Zatrzymaj daemon
#   ./scripts/start_gdelt_sentiment_daemon.sh --status  # Sprawdź status
#
# Autor: AI Assistant
# Data: 2025-12-18
# ============================================================================

set -eo pipefail

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
PID_FILE="$PROJECT_ROOT/data/gdelt_sentiment_daemon.pid"
LOG_FILE="$PROJECT_ROOT/logs/gdelt_sentiment_daemon.log"
DAEMON_SCRIPT="$SCRIPT_DIR/gdelt_sentiment_daemon.py"

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
    
    log_info "Uruchamiam GDELT Sentiment Daemon..."
    
    # Sprawdź czy venv jest aktywne
    if [ -z "$VIRTUAL_ENV" ]; then
        if [ -f "venv/bin/activate" ]; then
            source venv/bin/activate
        else
            log_error "Venv nie jest dostępne!"
            return 1
        fi
    fi
    
    # Utwórz katalogi jeśli nie istnieją
    mkdir -p "$PROJECT_ROOT/data"
    mkdir -p "$PROJECT_ROOT/logs"
    
    # Zbierz dodatkowe argumenty
    EXTRA_ARGS=()
    while [[ $# -gt 0 ]]; do
        EXTRA_ARGS+=("$1")
        shift
    done
    
    # Uruchom daemon w tle z nohup
    if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
        nohup python "$DAEMON_SCRIPT" "${EXTRA_ARGS[@]}" > "$LOG_FILE" 2>&1 &
    else
        nohup python "$DAEMON_SCRIPT" > "$LOG_FILE" 2>&1 &
    fi
    DAEMON_PID=$!
    
    # Zapisz PID
    echo "$DAEMON_PID" > "$PID_FILE"
    
    # Poczekaj chwilę i sprawdź czy proces nadal działa
    sleep 2
    if ps -p "$DAEMON_PID" > /dev/null 2>&1; then
        log_success "Daemon uruchomiony (PID: $DAEMON_PID)"
        log_info "Logi: $LOG_FILE"
        return 0
    else
        log_error "Daemon nie uruchomił się poprawnie!"
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
    log_info "Zatrzymuję daemon (PID: $PID)..."
    
    kill "$PID" 2>/dev/null || true
    
    # Poczekaj na zakończenie
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    
    # Jeśli nadal działa, użyj kill -9
    if ps -p "$PID" > /dev/null 2>&1; then
        log_warning "Proces nie zakończył się, używam kill -9..."
        kill -9 "$PID" 2>/dev/null || true
        sleep 1
    fi
    
    rm -f "$PID_FILE"
    log_success "Daemon zatrzymany"
}

status_daemon() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        log_success "Daemon działa (PID: $PID)"
        
        # Pokaż ostatnie linie logów
        if [ -f "$LOG_FILE" ]; then
            log_info "Ostatnie logi:"
            tail -n 5 "$LOG_FILE" | sed 's/^/  /'
        fi
        return 0
    else
        log_warning "Daemon nie działa"
        return 1
    fi
}

# === Główna logika ===
ACTION="${1:-start}"
shift || true

# Zbierz dodatkowe argumenty
EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
    EXTRA_ARGS+=("$1")
    shift
done

case $ACTION in
    start)
        if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
            start_daemon "${EXTRA_ARGS[@]}"
        else
            start_daemon
        fi
        ;;
    stop)
        stop_daemon
        ;;
    restart)
        if is_running; then
            stop_daemon
            sleep 2
        fi
        if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
            start_daemon "${EXTRA_ARGS[@]}"
        else
            start_daemon
        fi
        ;;
    status)
        status_daemon
        ;;
    *)
        log_error "Nieznana akcja: $ACTION"
        echo "Użycie: $0 {start|stop|restart|status} [dodatkowe argumenty]"
        echo ""
        echo "Przykłady:"
        echo "  $0 start"
        echo "  $0 start --interval=3600 --countries=US,CN,JP"
        echo "  $0 stop"
        echo "  $0 restart"
        echo "  $0 status"
        exit 1
        ;;
esac

