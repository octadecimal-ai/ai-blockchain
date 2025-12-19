#!/bin/bash
# Skrypt do uruchomienia BTC/USDC Updater
# ========================================
# Uruchamia mechanizm automatycznej aktualizacji danych BTC/USDC

set -e

# Katalog projektu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Przejdź do katalogu projektu
cd "$PROJECT_DIR"

# Aktywuj venv jeśli istnieje
if [ -d venv ]; then
    source venv/bin/activate
fi

# Uruchom updater
python3 -m src.database.btcusdc_updater "$@"

