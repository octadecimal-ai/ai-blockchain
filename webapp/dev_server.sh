#!/bin/bash
# Skrypt do zarządzania serwerami deweloperskimi (backend + frontend)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Pliki PID
BACKEND_PID_FILE="$SCRIPT_DIR/.backend.pid"
FRONTEND_PID_FILE="$SCRIPT_DIR/.frontend.pid"

# Porty
BACKEND_PORT=5001
FRONTEND_PORT=3000

# Funkcje pomocnicze
log_info() {
    echo "ℹ️  $1"
}

log_success() {
    echo "✅ $1"
}

log_error() {
    echo "❌ $1" >&2
}

log_warning() {
    echo "⚠️  $1"
}

# Sprawdź czy proces działa
is_process_running() {
    local pid=$1
    if [ -z "$pid" ] || [ "$pid" = "" ]; then
        return 1
    fi
    kill -0 "$pid" 2>/dev/null
}

# Pobierz PID z pliku
get_pid_from_file() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        cat "$pid_file" 2>/dev/null || echo ""
    else
        echo ""
    fi
}

# Zapisz PID do pliku
save_pid_to_file() {
    local pid_file=$1
    local pid=$2
    echo "$pid" > "$pid_file"
}

# Usuń plik PID
remove_pid_file() {
    local pid_file=$1
    rm -f "$pid_file"
}

# Znajdź PID procesu na podstawie portu
find_pid_by_port() {
    local port=$1
    lsof -ti:$port 2>/dev/null || echo ""
}

# Sprawdź status serwerów
check_status() {
    local backend_pid=""
    local frontend_pid=""
    local backend_running=false
    local frontend_running=false
    
    # Sprawdź backend
    backend_pid=$(get_pid_from_file "$BACKEND_PID_FILE")
    if [ -n "$backend_pid" ] && is_process_running "$backend_pid"; then
        backend_running=true
    else
        # Spróbuj znaleźć przez port
        backend_pid=$(find_pid_by_port $BACKEND_PORT)
        if [ -n "$backend_pid" ] && is_process_running "$backend_pid"; then
            backend_running=true
            save_pid_to_file "$BACKEND_PID_FILE" "$backend_pid"
        fi
    fi
    
    # Sprawdź frontend
    frontend_pid=$(get_pid_from_file "$FRONTEND_PID_FILE")
    if [ -n "$frontend_pid" ] && is_process_running "$frontend_pid"; then
        frontend_running=true
    else
        # Spróbuj znaleźć przez port
        frontend_pid=$(find_pid_by_port $FRONTEND_PORT)
        if [ -n "$frontend_pid" ] && is_process_running "$frontend_pid"; then
            frontend_running=true
            save_pid_to_file "$FRONTEND_PID_FILE" "$frontend_pid"
        fi
    fi
    
    # Wyświetl status
    echo ""
    echo "📊 Status serwerów deweloperskich:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ "$backend_running" = true ]; then
        echo "🔧 Backend:  ✅ DZIAŁA (PID: $backend_pid, Port: $BACKEND_PORT)"
        echo "   URL: http://localhost:$BACKEND_PORT"
    else
        echo "🔧 Backend:  ❌ ZATRZYMANY"
    fi
    
    if [ "$frontend_running" = true ]; then
        echo "🎨 Frontend: ✅ DZIAŁA (PID: $frontend_pid, Port: $FRONTEND_PORT)"
        echo "   URL: http://localhost:$FRONTEND_PORT"
    else
        echo "🎨 Frontend: ❌ ZATRZYMANY"
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Zwróć status
    if [ "$backend_running" = true ] && [ "$frontend_running" = true ]; then
        return 0  # Oba działają
    elif [ "$backend_running" = true ] || [ "$frontend_running" = true ]; then
        return 1  # Jeden działa
    else
        return 2  # Oba zatrzymane
    fi
}

# Zatrzymaj serwer
stop_server() {
    local server_name=$1
    local pid_file=$2
    local port=$3
    
    log_info "Zatrzymuję $server_name..."
    
    # Pobierz PID z pliku
    local pid=$(get_pid_from_file "$pid_file")
    
    # Jeśli nie ma PID w pliku, spróbuj znaleźć przez port
    if [ -z "$pid" ] || ! is_process_running "$pid"; then
        pid=$(find_pid_by_port "$port")
    fi
    
    # Zatrzymaj proces
    if [ -n "$pid" ] && is_process_running "$pid"; then
        kill "$pid" 2>/dev/null || true
        sleep 1
        # Jeśli nadal działa, użyj kill -9
        if is_process_running "$pid"; then
            kill -9 "$pid" 2>/dev/null || true
        fi
        log_success "$server_name zatrzymany (PID: $pid)"
    else
        log_warning "$server_name nie był uruchomiony"
    fi
    
    # Usuń plik PID
    remove_pid_file "$pid_file"
}

# Uruchom backend
start_backend() {
    log_info "Uruchamiam backend API..."
    
    # Sprawdź czy już działa
    local existing_pid=$(find_pid_by_port $BACKEND_PORT)
    if [ -n "$existing_pid" ] && is_process_running "$existing_pid"; then
        log_warning "Backend już działa (PID: $existing_pid)"
        save_pid_to_file "$BACKEND_PID_FILE" "$existing_pid"
        return 0
    fi
    
    # Sprawdź czy .env istnieje
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        log_error "Brak pliku .env w katalogu głównym projektu!"
        log_error "Utwórz plik .env z DATABASE_URL"
        return 1
    fi
    
    # Sprawdź czy venv istnieje
    if [ ! -d "$BACKEND_DIR/venv" ]; then
        log_info "Tworzę virtual environment dla backendu..."
        cd "$BACKEND_DIR"
        python3 -m venv venv
        source venv/bin/activate
        pip install -q -r requirements.txt
    fi
    
    # Uruchom backend
    cd "$BACKEND_DIR"
    source venv/bin/activate
    python app.py > /tmp/flask_backend.log 2>&1 &
    local backend_pid=$!
    
    # Zapisz PID
    save_pid_to_file "$BACKEND_PID_FILE" "$backend_pid"
    
    # Poczekaj chwilę na uruchomienie
    sleep 2
    
    # Sprawdź czy działa
    if is_process_running "$backend_pid"; then
        log_success "Backend uruchomiony (PID: $backend_pid, Port: $BACKEND_PORT)"
        log_info "Logi: tail -f /tmp/flask_backend.log"
        return 0
    else
        log_error "Backend nie uruchomił się poprawnie"
        remove_pid_file "$BACKEND_PID_FILE"
        return 1
    fi
}

# Uruchom frontend
start_frontend() {
    log_info "Uruchamiam frontend..."
    
    # Sprawdź czy już działa
    local existing_pid=$(find_pid_by_port $FRONTEND_PORT)
    if [ -n "$existing_pid" ] && is_process_running "$existing_pid"; then
        log_warning "Frontend już działa (PID: $existing_pid)"
        save_pid_to_file "$FRONTEND_PID_FILE" "$existing_pid"
        return 0
    fi
    
    # Sprawdź czy node_modules istnieje
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        log_info "Instaluję zależności frontendu..."
        cd "$FRONTEND_DIR"
        npm install
    fi
    
    # Uruchom frontend
    cd "$FRONTEND_DIR"
    npm run dev > /tmp/vite_dev.log 2>&1 &
    local frontend_pid=$!
    
    # Zapisz PID
    save_pid_to_file "$FRONTEND_PID_FILE" "$frontend_pid"
    
    # Poczekaj chwilę na uruchomienie
    sleep 3
    
    # Sprawdź czy działa
    if is_process_running "$frontend_pid"; then
        log_success "Frontend uruchomiony (PID: $frontend_pid, Port: $FRONTEND_PORT)"
        log_info "Logi: tail -f /tmp/vite_dev.log"
        return 0
    else
        log_error "Frontend nie uruchomił się poprawnie"
        remove_pid_file "$FRONTEND_PID_FILE"
        return 1
    fi
}

# Zatrzymaj wszystkie serwery
stop_all() {
    log_info "Zatrzymuję wszystkie serwery..."
    stop_server "Backend" "$BACKEND_PID_FILE" $BACKEND_PORT
    stop_server "Frontend" "$FRONTEND_PID_FILE" $FRONTEND_PORT
    log_success "Wszystkie serwery zatrzymane"
}

# Uruchom wszystkie serwery
start_all() {
    log_info "Uruchamiam wszystkie serwery..."
    start_backend
    sleep 1
    start_frontend
    echo ""
    log_success "Aplikacja uruchomiona!"
    echo "   Backend:  http://localhost:$BACKEND_PORT"
    echo "   Frontend: http://localhost:$FRONTEND_PORT"
    echo ""
}

# Restart wszystkich serwerów
restart_all() {
    log_info "Restartuję wszystkie serwery..."
    stop_all
    sleep 2
    start_all
}

# Pokaż pomoc
show_help() {
    cat << EOF
🚀 Dev Server Manager - Zarządzanie serwerami deweloperskimi

Użycie:
    $0 [OPCJA]

Opcje:
    --help, -h          Pokaż tę pomoc
    --status, -s        Sprawdź status serwerów
    --start             Uruchom wszystkie serwery (backend + frontend)
    --stop              Zatrzymaj wszystkie serwery
    --restart           Zrestartuj wszystkie serwery
    --start-backend     Uruchom tylko backend
    --stop-backend      Zatrzymaj tylko backend
    --start-frontend    Uruchom tylko frontend
    --stop-frontend     Zatrzymaj tylko frontend

Przykłady:
    $0 --start          # Uruchom backend i frontend
    $0 --status         # Sprawdź status
    $0 --stop           # Zatrzymaj wszystko
    $0 --restart        # Zrestartuj wszystko

Logi:
    Backend:  tail -f /tmp/flask_backend.log
    Frontend: tail -f /tmp/vite_dev.log

EOF
}

# Główna logika
main() {
    case "${1:-}" in
        --help|-h)
            show_help
            ;;
        --status|-s)
            check_status
            ;;
        --start)
            start_all
            ;;
        --stop)
            stop_all
            ;;
        --restart)
            restart_all
            ;;
        --start-backend)
            start_backend
            ;;
        --stop-backend)
            stop_server "Backend" "$BACKEND_PID_FILE" $BACKEND_PORT
            ;;
        --start-frontend)
            start_frontend
            ;;
        --stop-frontend)
            stop_server "Frontend" "$FRONTEND_PID_FILE" $FRONTEND_PORT
            ;;
        "")
            # Domyślnie pokaż status
            check_status
            ;;
        *)
            log_error "Nieznana opcja: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Uruchom
main "$@"

