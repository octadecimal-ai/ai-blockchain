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
# 5. DOCKER (OPCJONALNIE)
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
# 6. WERYFIKACJA INSTALACJI
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
# 7. PODSUMOWANIE
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

