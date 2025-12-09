#!/bin/bash
# Skrypt pomocniczy do przeniesienia TimescaleDB z PostgreSQL 17 do PostgreSQL 14
# Wersja: 1.0.0

set -e

# Kolory
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

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

log_info "Przenoszenie TimescaleDB z PostgreSQL 17 do PostgreSQL 14..."

# Sprawdź czy katalog źródłowy istnieje
SOURCE_DIR="/opt/homebrew/share/postgresql@17/extension"
TARGET_DIR="/opt/homebrew/share/postgresql@14/extension"

if [[ ! -d "$SOURCE_DIR" ]]; then
    log_error "Nie znaleziono katalogu źródłowego: $SOURCE_DIR"
    exit 1
fi

# Utwórz katalog docelowy jeśli nie istnieje
if [[ ! -d "$TARGET_DIR" ]]; then
    log_info "Tworzenie katalogu docelowego: $TARGET_DIR"
    sudo mkdir -p "$TARGET_DIR"
    sudo chown $(whoami):staff "$TARGET_DIR"
fi

# Skopiuj pliki TimescaleDB
log_info "Kopiowanie plików TimescaleDB..."
sudo cp "$SOURCE_DIR"/timescaledb* "$TARGET_DIR/" 2>/dev/null || {
    log_error "Nie można skopiować plików. Sprawdź uprawnienia."
    exit 1
}

# Skopiuj bibliotekę
LIB_SOURCE="/opt/homebrew/lib/postgresql@17/timescaledb-2.24.so"
LIB_TARGET_DIR="/opt/homebrew/lib/postgresql@14"

if [[ -f "$LIB_SOURCE" ]]; then
    log_info "Kopiowanie biblioteki TimescaleDB..."
    if [[ ! -d "$LIB_TARGET_DIR" ]]; then
        sudo mkdir -p "$LIB_TARGET_DIR"
        sudo chown $(whoami):staff "$LIB_TARGET_DIR"
    fi
    sudo cp "$LIB_SOURCE" "$LIB_TARGET_DIR/" || {
        log_warning "Nie można skopiować biblioteki (może być już skopiowana)"
    }
else
    log_warning "Nie znaleziono biblioteki: $LIB_SOURCE"
    log_info "Sprawdzam alternatywne lokalizacje..."
    find /opt/homebrew/lib -name "timescaledb*.so" 2>/dev/null | head -3
fi

log_success "Pliki TimescaleDB zostały skopiowane!"
log_info ""
log_info "Następne kroki:"
log_info "1. Sprawdź konfigurację postgresql.conf:"
log_info "   shared_preload_libraries = 'timescaledb'"
log_info ""
log_info "2. Restart PostgreSQL:"
log_info "   brew services restart postgresql@14"
log_info ""
log_info "3. Włącz rozszerzenie:"
log_info "   psql -U $(whoami) -d ai_blockchain -c 'CREATE EXTENSION IF NOT EXISTS timescaledb;'"

