#!/bin/bash

# ============================================================================
# Install Data Updater Service (macOS Launchd)
# ============================================================================
# Instaluje daemon jako LaunchAgent dla macOS.
# Daemon będzie uruchamiany automatycznie przy logowaniu.
#
# Użycie:
#   ./scripts/install_data_updater_service.sh
#   ./scripts/install_data_updater_service.sh --uninstall
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
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

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

# === Sprawdź system ===
if [[ "$OSTYPE" != "darwin"* ]]; then
    log_error "Ten skrypt jest tylko dla macOS!"
    log_info "Dla Linux użyj systemd service file"
    exit 1
fi

# === Ścieżki ===
PLIST_FILE="$SCRIPT_DIR/com.octadecimal.data_updater.plist"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
LAUNCHD_FILE="$LAUNCHD_DIR/com.octadecimal.data_updater.plist"
SERVICE_NAME="com.octadecimal.data_updater"

# === Funkcje ===
install_service() {
    log_info "Instalowanie Data Updater jako LaunchAgent..."
    
    # Sprawdź czy plist istnieje
    if [ ! -f "$PLIST_FILE" ]; then
        log_error "Plik plist nie istnieje: $PLIST_FILE"
        return 1
    fi
    
    # Utwórz katalog LaunchAgents jeśli nie istnieje
    mkdir -p "$LAUNCHD_DIR"
    
    # Skopiuj plist
    cp "$PLIST_FILE" "$LAUNCHD_FILE"
    
    # Zaktualizuj ścieżki w plist (używając aktualnej ścieżki projektu)
    # Escapuj slashe dla sed
    PROJECT_ROOT_ESCAPED=$(echo "$PROJECT_ROOT" | sed 's/[\/&]/\\&/g')
    sed -i '' "s|__PROJECT_ROOT__|$PROJECT_ROOT_ESCAPED|g" "$LAUNCHD_FILE"
    
    # Załaduj service
    if launchctl list "$SERVICE_NAME" > /dev/null 2>&1; then
        log_info "Service już załadowany, przeładowuję..."
        launchctl unload "$LAUNCHD_FILE" 2>/dev/null || true
    fi
    
    launchctl load "$LAUNCHD_FILE"
    
    if launchctl list "$SERVICE_NAME" > /dev/null 2>&1; then
        log_success "✅ Service zainstalowany i uruchomiony"
        log_info "   Plist: $LAUNCHD_FILE"
        log_info "   Status: launchctl list $SERVICE_NAME"
        log_info "   Zatrzymaj: launchctl unload $LAUNCHD_FILE"
        return 0
    else
        log_error "❌ Nie można załadować service"
        return 1
    fi
}

uninstall_service() {
    log_info "Odinstalowywanie Data Updater service..."
    
    # Zatrzymaj i usuń z launchd
    if launchctl list "$SERVICE_NAME" > /dev/null 2>&1; then
        launchctl unload "$LAUNCHD_FILE" 2>/dev/null || true
        log_info "Service zatrzymany"
    fi
    
    # Usuń plist
    if [ -f "$LAUNCHD_FILE" ]; then
        rm -f "$LAUNCHD_FILE"
        log_success "✅ Service odinstalowany"
        return 0
    else
        log_warning "Service nie był zainstalowany"
        return 1
    fi
}

# === Parsowanie argumentów ===
if [[ "${1:-}" == "--uninstall" ]]; then
    uninstall_service
else
    install_service
fi

