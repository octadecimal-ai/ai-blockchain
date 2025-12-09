#!/bin/bash
# Skrypt instalacyjny PostgreSQL + TimescaleDB dla macOS
# Wersja: 1.0.0
# Data: 2025-12-09

set -e  # Zatrzymaj przy błędzie

# Kolory dla outputu
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funkcje pomocnicze
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
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

# Sprawdź czy jesteśmy na macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    log_error "Ten skrypt jest przeznaczony tylko dla macOS!"
    exit 1
fi

log_info "Rozpoczynam instalację PostgreSQL + TimescaleDB dla macOS..."

# Sprawdź czy Homebrew jest zainstalowany
if ! command -v brew &> /dev/null; then
    log_error "Homebrew nie jest zainstalowany!"
    log_info "Instalowanie Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Dodaj Homebrew do PATH (dla Apple Silicon)
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    log_success "Homebrew jest już zainstalowany"
fi

# Aktualizuj Homebrew
log_info "Aktualizowanie Homebrew..."
brew update

# Sprawdź czy PostgreSQL jest już zainstalowany
if command -v psql &> /dev/null; then
    PSQL_VERSION=$(psql --version | awk '{print $3}')
    log_warning "PostgreSQL jest już zainstalowany (wersja: $PSQL_VERSION)"
    
    # Sprawdź czy to wersja 14, 15 lub 16 (wspierane)
    if [[ "$PSQL_VERSION" =~ ^1[4-6]\. ]]; then
        log_info "Używam istniejącej instalacji PostgreSQL $PSQL_VERSION"
        PSQL_MAJOR_VERSION=$(echo "$PSQL_VERSION" | cut -d. -f1)
        
        # Sprawdź czy to postgresql@14, @15 czy @16
        if brew list postgresql@$PSQL_MAJOR_VERSION &> /dev/null; then
            log_success "PostgreSQL@$PSQL_MAJOR_VERSION jest zainstalowany przez Homebrew"
        fi
    else
        log_warning "Wykryto starą wersję PostgreSQL. Rozważ aktualizację do wersji 14+"
    fi
else
    log_info "Instalowanie PostgreSQL 16..."
    brew install postgresql@16
    
    # Dodaj do PATH
    log_info "Konfigurowanie PATH..."
    if [[ -f "$HOME/.zshrc" ]]; then
        if ! grep -q "postgresql@16" "$HOME/.zshrc"; then
            echo 'export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"' >> "$HOME/.zshrc"
            log_success "Dodano PostgreSQL do ~/.zshrc"
        fi
    fi
    
    # Dodaj do obecnej sesji
    export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
fi

# Sprawdź czy PostgreSQL działa
log_info "Sprawdzanie statusu PostgreSQL..."

# Znajdź zainstalowaną wersję PostgreSQL
PSQL_SERVICE=""
if brew services list | grep -q "postgresql@16.*started"; then
    PSQL_SERVICE="postgresql@16"
elif brew services list | grep -q "postgresql@15.*started"; then
    PSQL_SERVICE="postgresql@15"
elif brew services list | grep -q "postgresql@14.*started"; then
    PSQL_SERVICE="postgresql@14"
elif brew list postgresql@16 &> /dev/null; then
    PSQL_SERVICE="postgresql@16"
elif brew list postgresql@15 &> /dev/null; then
    PSQL_SERVICE="postgresql@15"
elif brew list postgresql@14 &> /dev/null; then
    PSQL_SERVICE="postgresql@14"
fi

if [[ -n "$PSQL_SERVICE" ]]; then
    if brew services list | grep -q "$PSQL_SERVICE.*started"; then
        log_success "PostgreSQL ($PSQL_SERVICE) jest już uruchomiony"
    else
        log_info "Uruchamianie PostgreSQL ($PSQL_SERVICE)..."
        brew services start "$PSQL_SERVICE"
        sleep 3  # Poczekaj na start
    fi
else
    log_error "Nie znaleziono zainstalowanego PostgreSQL przez Homebrew"
    log_info "Próbuję użyć systemowego PostgreSQL..."
fi

# Sprawdź połączenie
if psql -U "$USER" -d postgres -c "SELECT version();" &> /dev/null; then
    log_success "Połączenie z PostgreSQL działa"
else
    log_warning "Nie można połączyć się z PostgreSQL jako $USER"
    log_info "Tworzenie użytkownika bazy danych..."
    
    # Utwórz użytkownika jeśli nie istnieje
    createuser -s "$USER" 2>/dev/null || true
fi

# Instalacja TimescaleDB
log_info "Sprawdzanie TimescaleDB..."
if psql -U "$USER" -d postgres -c "SELECT * FROM pg_extension WHERE extname = 'timescaledb';" 2>/dev/null | grep -q "timescaledb"; then
    log_success "TimescaleDB jest już zainstalowany"
else
    log_info "Instalowanie TimescaleDB..."
    
    # Sprawdź wersję PostgreSQL
    PSQL_MAJOR_VERSION=$(psql --version | awk '{print $3}' | cut -d. -f1)
    
    log_info "Wykryto PostgreSQL $PSQL_MAJOR_VERSION"
    log_info "Instalowanie TimescaleDB dla PostgreSQL $PSQL_MAJOR_VERSION..."
    
    # Dodaj TimescaleDB tap (jeśli nie istnieje)
    if ! brew tap | grep -q "timescale/tap"; then
        log_info "Dodawanie TimescaleDB tap..."
        brew tap timescale/tap
    fi
    
    # Instalacja TimescaleDB
    if brew list timescaledb &> /dev/null; then
        log_success "TimescaleDB jest już zainstalowany przez Homebrew"
    else
        log_info "Instalowanie TimescaleDB..."
        brew install timescaledb
        
        # Konfiguracja TimescaleDB dla właściwej wersji PostgreSQL
        log_info "Konfigurowanie TimescaleDB dla PostgreSQL $PSQL_MAJOR_VERSION..."
        
        # Uruchom timescaledb_move.sh aby przenieść rozszerzenie do właściwej wersji
        if command -v timescaledb_move.sh &> /dev/null; then
            log_info "Przenoszenie TimescaleDB do PostgreSQL $PSQL_MAJOR_VERSION..."
            sudo timescaledb_move.sh || {
                log_warning "timescaledb_move.sh wymaga sudo - uruchom ręcznie:"
                log_info "  sudo timescaledb_move.sh"
            }
        fi
        
        # Konfiguruj postgresql.conf
        log_info "Konfigurowanie postgresql.conf..."
        PG_CONFIG_PATH="/opt/homebrew/var/postgresql@$PSQL_MAJOR_VERSION/postgresql.conf"
        if [[ -f "$PG_CONFIG_PATH" ]]; then
            if ! grep -q "shared_preload_libraries = 'timescaledb'" "$PG_CONFIG_PATH"; then
                log_info "Dodawanie TimescaleDB do shared_preload_libraries..."
                # Backup
                cp "$PG_CONFIG_PATH" "$PG_CONFIG_PATH.backup"
                # Dodaj konfigurację
                if grep -q "^shared_preload_libraries" "$PG_CONFIG_PATH"; then
                    sed -i '' "s/^shared_preload_libraries = .*/shared_preload_libraries = 'timescaledb'/" "$PG_CONFIG_PATH"
                else
                    echo "shared_preload_libraries = 'timescaledb'" >> "$PG_CONFIG_PATH"
                fi
                log_success "Zaktualizowano postgresql.conf"
            else
                log_success "TimescaleDB jest już w postgresql.conf"
            fi
        else
            log_warning "Nie znaleziono postgresql.conf w $PG_CONFIG_PATH"
            log_info "Musisz ręcznie dodać do postgresql.conf:"
            log_info "  shared_preload_libraries = 'timescaledb'"
        fi
        
        # Uruchom timescaledb-tune (opcjonalnie)
        if command -v timescaledb-tune &> /dev/null; then
            log_info "Optymalizowanie konfiguracji TimescaleDB..."
            timescaledb-tune --quiet --yes || log_warning "timescaledb-tune nie powiódł się (opcjonalne)"
        fi
        
        # Restart PostgreSQL po instalacji TimescaleDB
        log_info "Restartowanie PostgreSQL..."
        if [[ -n "$PSQL_SERVICE" ]]; then
            brew services restart "$PSQL_SERVICE"
        else
            log_warning "Nie można automatycznie zrestartować PostgreSQL"
            log_info "Uruchom ręcznie: brew services restart postgresql@$PSQL_MAJOR_VERSION"
        fi
        sleep 5  # Daj więcej czasu na restart
    fi
    
    # Włącz rozszerzenie TimescaleDB
    log_info "Włączanie rozszerzenia TimescaleDB..."
    if psql -U "$USER" -d postgres -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" 2>/dev/null; then
        log_success "TimescaleDB został zainstalowany i włączony"
    else
        log_warning "Nie można włączyć TimescaleDB automatycznie"
        log_info "Możliwe przyczyny:"
        log_info "  1. TimescaleDB wymaga restartu PostgreSQL"
        log_info "  2. TimescaleDB może wymagać ręcznej konfiguracji"
        log_info ""
        log_info "Spróbuj ręcznie:"
        log_info "  1. brew services restart $PSQL_SERVICE"
        log_info "  2. psql -U $USER -d postgres -c 'CREATE EXTENSION IF NOT EXISTS timescaledb;'"
    fi
fi

# Utwórz bazę danych dla projektu
DB_NAME="ai_blockchain"
log_info "Sprawdzanie bazy danych '$DB_NAME'..."

if psql -U "$USER" -d postgres -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    log_warning "Baza danych '$DB_NAME' już istnieje"
    read -p "Czy chcesz ją usunąć i utworzyć na nowo? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Usuwanie istniejącej bazy danych..."
        psql -U "$USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
        log_info "Tworzenie nowej bazy danych..."
        psql -U "$USER" -d postgres -c "CREATE DATABASE $DB_NAME;"
        log_success "Baza danych '$DB_NAME' została utworzona"
    fi
else
    log_info "Tworzenie bazy danych '$DB_NAME'..."
    psql -U "$USER" -d postgres -c "CREATE DATABASE $DB_NAME;"
    log_success "Baza danych '$DB_NAME' została utworzona"
fi

# Włącz TimescaleDB w bazie projektu
log_info "Włączanie TimescaleDB w bazie '$DB_NAME'..."
psql -U "$USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" || {
    log_warning "Nie można włączyć TimescaleDB w bazie projektu (może być już włączone)"
}

# Wyświetl informacje o instalacji
log_success "=========================================="
log_success "Instalacja zakończona pomyślnie!"
log_success "=========================================="
echo
log_info "Informacje o instalacji:"
PSQL_VERSION=$(psql --version | awk '{print $3}')
echo "  PostgreSQL: $PSQL_VERSION"
echo "  Baza danych: $DB_NAME"
echo "  Użytkownik: $USER"
echo "  Port: 5432 (domyślny)"
echo
log_info "Connection string:"
echo "  postgresql://$USER@localhost:5432/$DB_NAME"
echo
log_info "Aby użyć w projekcie, dodaj do .env:"
echo "  DATABASE_URL=postgresql://$USER@localhost:5432/$DB_NAME"
echo "  USE_TIMESCALE=true"
echo
log_info "Przydatne komendy:"
if [[ -n "$PSQL_SERVICE" ]]; then
    echo "  Start PostgreSQL:  brew services start $PSQL_SERVICE"
    echo "  Stop PostgreSQL:   brew services stop $PSQL_SERVICE"
else
    echo "  Start PostgreSQL:  brew services start postgresql@14 (lub @15/@16)"
    echo "  Stop PostgreSQL:   brew services stop postgresql@14"
fi
echo "  Status:            brew services list | grep postgresql"
echo "  Połączenie:        psql -U $USER -d $DB_NAME"
echo
log_warning "UWAGA: Jeśli TimescaleDB nie działa, wykonaj dodatkowe kroki:"
echo "  1. sudo timescaledb_move.sh"
echo "  2. Sprawdź postgresql.conf (shared_preload_libraries = 'timescaledb')"
echo "  3. brew services restart $PSQL_SERVICE"
echo "  4. psql -U $USER -d $DB_NAME -c 'CREATE EXTENSION IF NOT EXISTS timescaledb;'"
echo
log_info "Szczegółowe instrukcje: docs/setup/postgresql_macos_manual_steps.md"
echo

