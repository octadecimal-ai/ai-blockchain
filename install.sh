#!/bin/bash
# =============================================================================
# AI Blockchain - Skrypt Instalacyjny
# =============================================================================
# Automatyczna instalacja wszystkich komponentów projektu.
# Sprawdza czy komponenty istnieją i aktualizuje je jeśli potrzeba.
#
# Użycie: ./install.sh [--skip-docker] [--skip-ml]
# =============================================================================

set -e  # Zatrzymaj przy błędzie

# Kolory dla outputu
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Flagi
SKIP_DOCKER=false
SKIP_ML=false

# Parsowanie argumentów
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-docker)
            SKIP_DOCKER=true
            shift
            ;;
        --skip-ml)
            SKIP_ML=true
            shift
            ;;
        *)
            echo -e "${RED}Nieznany argument: $1${NC}"
            exit 1
            ;;
    esac
done

# Funkcje pomocnicze
print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

get_python_version() {
    python3 --version 2>/dev/null | cut -d' ' -f2 | cut -d'.' -f1,2
}

# =============================================================================
# 1. SPRAWDZENIE WYMAGAŃ
# =============================================================================
print_header "🔍 SPRAWDZANIE WYMAGAŃ SYSTEMOWYCH"

# Python
if ! check_command python3; then
    print_error "Python 3 nie jest zainstalowany!"
    exit 1
fi

PYTHON_VERSION=$(get_python_version)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    print_error "Wymagany Python >= 3.8, znaleziono: $PYTHON_VERSION"
    exit 1
fi

print_success "Python $PYTHON_VERSION znaleziony"

# pip
if ! check_command pip3; then
    print_warning "pip3 nie znaleziony, instaluję..."
    python3 -m ensurepip --upgrade
fi

PIP_VERSION=$(pip3 --version | cut -d' ' -f2)
print_success "pip $PIP_VERSION znaleziony"

# Docker (opcjonalnie)
if [ "$SKIP_DOCKER" = false ]; then
    if check_command docker; then
        DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
        print_success "Docker $DOCKER_VERSION znaleziony"
    else
        print_warning "Docker nie jest zainstalowany (opcjonalne dla TimescaleDB)"
        print_info "Zainstaluj Docker Desktop: https://www.docker.com/products/docker-desktop"
    fi
    
    if check_command docker-compose; then
        print_success "docker-compose znaleziony"
    else
        print_warning "docker-compose nie znaleziony (opcjonalne)"
    fi
fi

# =============================================================================
# 2. VIRTUAL ENVIRONMENT
# =============================================================================
print_header "🐍 KONFIGURACJA VIRTUAL ENVIRONMENT"

VENV_DIR="venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -d "$VENV_DIR" ]; then
    print_info "Virtual environment już istnieje w $VENV_DIR"
    
    # Sprawdź czy venv jest aktualny
    if [ -f "$VENV_DIR/pyvenv.cfg" ]; then
        VENV_PYTHON=$(grep "version" "$VENV_DIR/pyvenv.cfg" | cut -d'=' -f2 | tr -d ' ')
        if [ "$VENV_PYTHON" != "$PYTHON_VERSION" ]; then
            print_warning "Wersja Pythona w venv ($VENV_PYTHON) różni się od systemowej ($PYTHON_VERSION)"
            print_info "Usuwam stary venv i tworzę nowy..."
            rm -rf "$VENV_DIR"
            python3 -m venv "$VENV_DIR"
            print_success "Nowy virtual environment utworzony"
        else
            print_success "Virtual environment jest aktualny"
        fi
    fi
else
    print_info "Tworzenie virtual environment..."
    python3 -m venv "$VENV_DIR"
    print_success "Virtual environment utworzony"
fi

# Aktywacja venv
source "$VENV_DIR/bin/activate"

# Aktualizacja pip w venv
print_info "Aktualizacja pip..."
pip install --upgrade pip setuptools wheel --quiet
PIP_VERSION=$(pip --version | cut -d' ' -f2)
print_success "pip zaktualizowany do wersji $PIP_VERSION"

# =============================================================================
# 3. INSTALACJA ZALEŻNOŚCI PYTHON
# =============================================================================
print_header "📦 INSTALACJA ZALEŻNOŚCI PYTHON"

if [ ! -f "requirements.txt" ]; then
    print_error "Plik requirements.txt nie znaleziony!"
    exit 1
fi

# Sprawdź czy requirements.txt się zmienił
REQUIREMENTS_HASH=$(md5sum requirements.txt 2>/dev/null | cut -d' ' -f1 || md5 -q requirements.txt 2>/dev/null || echo "unknown")
CACHED_HASH_FILE="$VENV_DIR/.requirements_hash"

if [ -f "$CACHED_HASH_FILE" ]; then
    CACHED_HASH=$(cat "$CACHED_HASH_FILE")
    if [ "$REQUIREMENTS_HASH" = "$CACHED_HASH" ]; then
        print_info "requirements.txt nie zmienił się od ostatniej instalacji"
        print_info "Sprawdzam czy wszystkie pakiety są zainstalowane..."
        
        # Szybkie sprawdzenie czy główne pakiety są zainstalowane
        MISSING_PACKAGES=$(pip list --format=freeze 2>/dev/null | grep -E "^(pandas|numpy|ccxt|ta)=" || echo "")
        if [ -z "$MISSING_PACKAGES" ]; then
            print_success "Wszystkie pakiety są zainstalowane i aktualne"
            SKIP_INSTALL=true
        else
            SKIP_INSTALL=false
        fi
    else
        SKIP_INSTALL=false
    fi
else
    SKIP_INSTALL=false
fi

if [ "$SKIP_INSTALL" = false ]; then
    print_info "Instalowanie/aktualizowanie pakietów z requirements.txt..."
    
    # Podziel requirements na kategorie dla lepszego feedbacku
    print_info "  → Instalowanie podstawowych pakietów..."
    pip install -q python-dotenv pyyaml loguru
    
    print_info "  → Instalowanie pakietów do przetwarzania danych..."
    pip install -q "pandas>=1.5.0,<2.1.0" "numpy>=1.24.0,<1.26.0" "pyarrow>=10.0.0,<14.0.0"
    
    print_info "  → Instalowanie pakietów API giełd..."
    pip install -q ccxt python-binance requests aiohttp websockets
    
    print_info "  → Instalowanie pakietów analizy technicznej..."
    pip install -q "ta>=0.11.0" "mplfinance>=0.12.9b7"
    
    if [ "$SKIP_ML" = false ]; then
        print_info "  → Instalowanie pakietów Machine Learning..."
        pip install -q "scikit-learn>=1.0.0,<1.3.0" || print_warning "Nie udało się zainstalować scikit-learn"
        
        # PyTorch - opcjonalnie, może być duży
        print_info "  → Instalowanie PyTorch (może chwilę potrwać)..."
        pip install -q "torch>=1.13.0,<2.1.0" || print_warning "Nie udało się zainstalować PyTorch"
    else
        print_info "  → Pomijanie pakietów ML (--skip-ml)"
    fi
    
    print_info "  → Instalowanie pakietów LLM..."
    pip install -q langchain langchain-openai langchain-anthropic openai anthropic tiktoken || print_warning "Niektóre pakiety LLM nie zostały zainstalowane"
    
    print_info "  → Instalowanie pakietów wizualizacji..."
    pip install -q matplotlib plotly dash seaborn
    
    print_info "  → Instalowanie pakietów API..."
    pip install -q fastapi uvicorn pydantic
    
    print_info "  → Instalowanie pakietów baz danych..."
    pip install -q sqlalchemy psycopg2-binary redis alembic
    
    print_info "  → Instalowanie pakietów deweloperskich..."
    pip install -q black ruff mypy ipykernel jupyter
    
    print_info "  → Instalowanie pozostałych pakietów..."
    pip install -q -r requirements.txt 2>&1 | grep -v "already satisfied" || true
    
    # Zapisz hash requirements.txt
    echo "$REQUIREMENTS_HASH" > "$CACHED_HASH_FILE"
    print_success "Wszystkie pakiety zainstalowane/zaktualizowane"
else
    print_success "Pakiety są aktualne, pomijam instalację"
fi

# =============================================================================
# 4. KONFIGURACJA PROJEKTU
# =============================================================================
print_header "⚙️  KONFIGURACJA PROJEKTU"

# Utworzenie katalogów jeśli nie istnieją
DIRS=("data/raw" "data/processed" "data/models" "logs" ".dev/logs/cursor")
for dir in "${DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        print_success "Utworzono katalog: $dir"
    fi
done

# Plik .env
if [ ! -f ".env" ]; then
    if [ -f "config/env.example.txt" ]; then
        cp config/env.example.txt .env
        print_success "Utworzono plik .env z przykładu"
        print_warning "Uzupełnij klucze API w pliku .env"
    else
        print_warning "Plik .env nie istnieje, utwórz go ręcznie"
    fi
else
    print_success "Plik .env już istnieje"
fi

# =============================================================================
# 5. INICJALIZACJA BAZY DANYCH
# =============================================================================
print_header "🗄️  INICJALIZACJA BAZY DANYCH"

# Sprawdź czy użytkownik chce zainicjalizować bazę
INIT_DB=false
if [ -f ".env" ]; then
    # Sprawdź czy DATABASE_URL jest ustawiony
    if grep -q "DATABASE_URL" .env && ! grep -q "^#.*DATABASE_URL" .env; then
        read -p "Czy chcesz zainicjalizować bazę danych i załadować dane BTC/USDC? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            INIT_DB=true
        fi
    else
        print_info "DATABASE_URL nie jest ustawiony w .env - pomijam inicjalizację bazy"
    fi
else
    print_info "Plik .env nie istnieje - pomijam inicjalizację bazy"
fi

if [ "$INIT_DB" = true ]; then
    print_info "Inicjalizacja bazy danych..."
    
    # Wykonaj migracje i utwórz tabele
    python3 << PYTHON_EOF
import sys
import os
from pathlib import Path

# Dodaj ścieżkę projektu
project_root = Path('$PROJECT_DIR')
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from loguru import logger

# Konfiguracja loggera
logger.remove()
logger.add(sys.stderr, level="INFO", format="{message}")

# Załaduj .env
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)

try:
    from src.database.manager import DatabaseManager
    from src.database.run_migrations import run_migrations
    
    database_url = os.getenv('DATABASE_URL')
    use_timescale = os.getenv('USE_TIMESCALE', 'false').lower() == 'true'
    
    # Utwórz tabele
    logger.info("Tworzenie tabel w bazie danych...")
    db = DatabaseManager(database_url=database_url, use_timescale=use_timescale)
    db.create_tables()
    logger.info("✓ Tabele utworzone")
    
    # Wykonaj migracje SQL
    logger.info("Wykonuję migracje SQL...")
    if run_migrations(database_url=database_url, use_timescale=use_timescale):
        logger.info("✓ Migracje wykonane")
    else:
        logger.warning("⚠ Niektóre migracje mogły się nie powieść (to może być normalne)")
    
    # Zapytaj o załadowanie danych BTC/USDC
    print("\n📊 Dane BTC/USDC")
    print("Czy chcesz pobrać dane historyczne BTC/USDC od 2020 roku?")
    print("(Może to zająć kilka minut)")
    response = input("Pobierz dane? (y/N): ").strip().lower()
    
    if response == 'y':
        logger.info("Pobieranie danych BTC/USDC z Binance...")
        from src.database.btcusdc_loader import BTCUSDCDataLoader
        from datetime import datetime, timezone
        
        loader = BTCUSDCDataLoader(database_url=database_url, use_timescale=use_timescale)
        start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        count = loader.load_historical_data(start_date=start_date)
        logger.info(f"✓ Zapisano {count} świec do bazy danych")
    else:
        logger.info("Pominięto pobieranie danych (możesz to zrobić później: ./scripts/init_btcusdc_data.sh)")
        
except Exception as e:
    logger.error(f"Błąd podczas inicjalizacji bazy: {e}")
    print(f"⚠ Nie udało się zainicjalizować bazy danych: {e}")
    print("Możesz to zrobić później ręcznie:")
    print("  python scripts/init_trading_db.py")
    print("  ./scripts/init_btcusdc_data.sh")
PYTHON_EOF

    if [ $? -eq 0 ]; then
        print_success "Baza danych zainicjalizowana"
    else
        print_warning "Inicjalizacja bazy danych zakończona z ostrzeżeniami"
    fi
fi

# =============================================================================
# 6. DOCKER (OPCJONALNIE)
# =============================================================================
if [ "$SKIP_DOCKER" = false ] && check_command docker && check_command docker-compose; then
    print_header "🐳 KONFIGURACJA DOCKER"
    
    if [ -f "docker-compose.yml" ]; then
        print_info "Sprawdzam status kontenerów Docker..."
        
        # Sprawdź czy kontenery są uruchomione
        if docker ps --format '{{.Names}}' | grep -q "ai_blockchain"; then
            print_success "Kontenery Docker są uruchomione"
        else
            print_info "Kontenery Docker nie są uruchomione"
            read -p "Czy chcesz uruchomić kontenery Docker? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                docker-compose up -d
                print_success "Kontenery Docker uruchomione"
                print_info "TimescaleDB: localhost:5432"
                print_info "Redis: localhost:6379"
                print_info "Adminer: http://localhost:8080"
            fi
        fi
    else
        print_warning "Plik docker-compose.yml nie znaleziony"
    fi
else
    if [ "$SKIP_DOCKER" = true ]; then
        print_info "Pomijanie konfiguracji Docker (--skip-docker)"
    else
        print_info "Docker nie jest zainstalowany, pomijam konfigurację"
    fi
fi

# =============================================================================
# 7. WERYFIKACJA INSTALACJI
# =============================================================================
print_header "✅ WERYFIKACJA INSTALACJI"

# Sprawdź kluczowe pakiety
PACKAGES=("pandas" "numpy" "ccxt" "ta" "sqlalchemy" "fastapi")
ALL_OK=true

for package in "${PACKAGES[@]}"; do
    if pip show "$package" &> /dev/null; then
        VERSION=$(pip show "$package" | grep "^Version:" | cut -d' ' -f2)
        print_success "$package $VERSION"
    else
        print_error "$package nie jest zainstalowany"
        ALL_OK=false
    fi
done

# Test importów
print_info "Testowanie importów Python..."
python3 << EOF
try:
    import pandas as pd
    import numpy as np
    import ccxt
    import ta
    import sqlalchemy
    print("✓ Wszystkie kluczowe moduły importują się poprawnie")
except ImportError as e:
    print(f"✗ Błąd importu: {e}")
    exit(1)
EOF

if [ $? -eq 0 ]; then
    print_success "Importy działają poprawnie"
else
    print_error "Niektóre importy nie działają"
    ALL_OK=false
fi

# =============================================================================
# 8. BTC/USDC AUTOMATYCZNA AKTUALIZACJA
# =============================================================================
print_header "🔄 KONFIGURACJA AUTOMATYCZNEJ AKTUALIZACJI"

# Sprawdź czy użytkownik chce skonfigurować automatyczną aktualizację
SETUP_UPDATER=false
if [ -f ".env" ] && grep -q "DATABASE_URL" .env && ! grep -q "^#.*DATABASE_URL" .env; then
    read -p "Czy chcesz skonfigurować automatyczną aktualizację danych BTC/USDC co 1 minutę? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        SETUP_UPDATER=true
    fi
fi

if [ "$SETUP_UPDATER" = true ]; then
    print_info "Konfiguracja automatycznej aktualizacji danych..."
    
    # Sprawdź czy systemd jest dostępny (Linux)
    if command -v systemctl &> /dev/null && [ "$(uname)" != "Darwin" ]; then
        print_info "Wykryto systemd - tworzę service..."
        
        # Utwórz plik service
        SERVICE_FILE="/tmp/btcusdc-updater.service"
        cat > "$SERVICE_FILE" << EOF
[Unit]
Description=BTC/USDC Data Updater - Automatyczna aktualizacja danych z Binance
After=network.target postgresql.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PROJECT_DIR/venv/bin/python3 -m src.database.btcusdc_updater --interval 60
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        print_success "Plik service utworzony: $SERVICE_FILE"
        print_info "Aby zainstalować service, uruchom jako root:"
        print_info "  sudo cp $SERVICE_FILE /etc/systemd/system/btcusdc-updater.service"
        print_info "  sudo systemctl daemon-reload"
        print_info "  sudo systemctl enable btcusdc-updater.service"
        print_info "  sudo systemctl start btcusdc-updater.service"
    else
        # macOS lub brak systemd - użyj launchd (macOS) lub po prostu skrypt
        if [ "$(uname)" = "Darwin" ]; then
            print_info "Wykryto macOS - tworzę LaunchAgent..."
            
            LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
            mkdir -p "$LAUNCH_AGENT_DIR"
            
            PLIST_FILE="$LAUNCH_AGENT_DIR/com.ai-blockchain.btcusdc-updater.plist"
            cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ai-blockchain.btcusdc-updater</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/venv/bin/python3</string>
        <string>-m</string>
        <string>src.database.btcusdc_updater</string>
        <string>--interval</string>
        <string>60</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/btcusdc_updater.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/btcusdc_updater.error.log</string>
</dict>
</plist>
EOF
            
            print_success "LaunchAgent utworzony: $PLIST_FILE"
            print_info "Aby uruchomić service, wykonaj:"
            print_info "  launchctl load $PLIST_FILE"
            print_info "  launchctl start com.ai-blockchain.btcusdc-updater"
        else
            # Inny system - po prostu pokaż jak uruchomić ręcznie
            print_info "Brak systemd/launchd - uruchom ręcznie:"
            print_info "  ./scripts/start_btcusdc_updater.sh"
            print_info "Lub w tle:"
            print_info "  nohup ./scripts/start_btcusdc_updater.sh > logs/btcusdc_updater.log 2>&1 &"
        fi
    fi
    
    print_info ""
    print_info "Możesz również uruchomić updater ręcznie:"
    print_info "  ./scripts/start_btcusdc_updater.sh"
    print_info "Lub jednorazową aktualizację:"
    print_info "  ./scripts/start_btcusdc_updater.sh --once"
else
    print_info "Pominięto konfigurację automatycznej aktualizacji"
    print_info "Możesz uruchomić updater później: ./scripts/start_btcusdc_updater.sh"
fi

# =============================================================================
# 9. PODSUMOWANIE
# =============================================================================
print_header "📋 PODSUMOWANIE INSTALACJI"

if [ "$ALL_OK" = true ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓ Instalacja zakończona pomyślnie!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BLUE}Następne kroki:${NC}"
    echo "  1. Uzupełnij klucze API w pliku .env"
    echo "  2. Aktywuj virtual environment: source venv/bin/activate"
    echo "  3. Uruchom notebook: jupyter notebook notebooks/01_getting_started.ipynb"
    echo "  4. (Opcjonalnie) Uruchom Docker: docker-compose up -d"
    echo "  5. (Opcjonalnie) Uruchom automatyczną aktualizację: ./scripts/start_btcusdc_updater.sh"
    echo ""
else
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}⚠ Instalacja zakończona z ostrzeżeniami${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Sprawdź powyższe błędy i spróbuj ponownie."
    echo ""
fi

# Informacja o wersji Pythona
echo -e "${BLUE}Środowisko:${NC}"
echo "  Python: $(python3 --version)"
echo "  pip: $(pip --version | cut -d' ' -f1,2)"
echo "  Virtual env: $VENV_DIR"
echo ""

