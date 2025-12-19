#!/bin/bash
# Skrypt do generowania kluczy kryptograficznych dla projektu AI Blockchain
# Wersja: 1.0.0
# Data: 2025-12-09

set -e  # Zatrzymaj przy błędzie

# Kolory dla outputu
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Sprawdź czy jesteśmy w katalogu projektu
if [[ ! -f "README.md" ]]; then
    log_error "Uruchom skrypt z katalogu głównego projektu!"
    exit 1
fi

# Katalog na klucze
KEYS_DIR=".keys"
mkdir -p "$KEYS_DIR"
chmod 700 "$KEYS_DIR"  # Tylko właściciel może czytać

log_info "=========================================="
log_info "Generator Kluczy - AI Blockchain"
log_info "=========================================="
echo ""

# Menu wyboru
echo "Wybierz typ kluczy do wygenerowania:"
echo ""
echo "1) Klucze SSH (Ed25519) - rekomendowane"
echo "2) Klucze SSH (RSA 4096-bit)"
echo "3) Klucze do szyfrowania danych (AES)"
echo "4) Wszystkie powyższe"
echo "5) Tylko szablon .env (bez generowania kluczy)"
echo ""
read -p "Twój wybór (1-5): " choice

case $choice in
    1)
        GENERATE_SSH_ED25519=true
        GENERATE_SSH_RSA=false
        GENERATE_AES=false
        ;;
    2)
        GENERATE_SSH_ED25519=false
        GENERATE_SSH_RSA=true
        GENERATE_AES=false
        ;;
    3)
        GENERATE_SSH_ED25519=false
        GENERATE_SSH_RSA=false
        GENERATE_AES=true
        ;;
    4)
        GENERATE_SSH_ED25519=true
        GENERATE_SSH_RSA=true
        GENERATE_AES=true
        ;;
    5)
        GENERATE_SSH_ED25519=false
        GENERATE_SSH_RSA=false
        GENERATE_AES=false
        GENERATE_ENV_TEMPLATE=true
        ;;
    *)
        log_error "Nieprawidłowy wybór!"
        exit 1
        ;;
esac

# Generowanie kluczy SSH Ed25519
if [[ "$GENERATE_SSH_ED25519" == "true" ]]; then
    log_step "Generowanie kluczy SSH Ed25519..."
    
    read -p "Nazwa klucza (domyślnie: ai_blockchain_ed25519): " key_name
    key_name=${key_name:-ai_blockchain_ed25519}
    
    read -p "Email dla klucza (opcjonalnie): " key_email
    
    key_path="$KEYS_DIR/$key_name"
    
    if [[ -f "$key_path" ]]; then
        log_warning "Klucz $key_path już istnieje!"
        read -p "Nadpisać? (y/n): " overwrite
        if [[ "$overwrite" != "y" ]]; then
            log_info "Pomijam generowanie klucza Ed25519"
        else
            rm -f "$key_path" "$key_path.pub"
        fi
    fi
    
    if [[ ! -f "$key_path" ]]; then
        comment="${key_email:+${key_email}}"
        comment="${comment:-ai-blockchain-project}"
        
        ssh-keygen -t ed25519 -C "$comment" -f "$key_path" -N "" <<< y
        
        chmod 600 "$key_path"
        chmod 644 "$key_path.pub"
        
        log_success "Klucz Ed25519 wygenerowany: $key_path"
        log_info "Klucz publiczny:"
        cat "$key_path.pub"
        echo ""
    fi
fi

# Generowanie kluczy SSH RSA
if [[ "$GENERATE_SSH_RSA" == "true" ]]; then
    log_step "Generowanie kluczy SSH RSA 4096-bit..."
    
    read -p "Nazwa klucza (domyślnie: ai_blockchain_rsa): " key_name
    key_name=${key_name:-ai_blockchain_rsa}
    
    read -p "Email dla klucza (opcjonalnie): " key_email
    
    key_path="$KEYS_DIR/$key_name"
    
    if [[ -f "$key_path" ]]; then
        log_warning "Klucz $key_path już istnieje!"
        read -p "Nadpisać? (y/n): " overwrite
        if [[ "$overwrite" != "y" ]]; then
            log_info "Pomijam generowanie klucza RSA"
        else
            rm -f "$key_path" "$key_path.pub"
        fi
    fi
    
    if [[ ! -f "$key_path" ]]; then
        comment="${key_email:+${key_email}}"
        comment="${comment:-ai-blockchain-project}"
        
        ssh-keygen -t rsa -b 4096 -C "$comment" -f "$key_path" -N "" <<< y
        
        chmod 600 "$key_path"
        chmod 644 "$key_path.pub"
        
        log_success "Klucz RSA wygenerowany: $key_path"
        log_info "Klucz publiczny (PEM format):"
        
        # Konwertuj do formatu PEM jeśli potrzeba
        if command -v ssh-keygen &> /dev/null; then
            ssh-keygen -f "$key_path.pub" -e -m PEM > "$key_path.pub.pem" 2>/dev/null || {
                # Alternatywnie użyj openssl
                if command -v openssl &> /dev/null; then
                    openssl rsa -in "$key_path" -pubout -out "$key_path.pub.pem" 2>/dev/null || true
                fi
            }
        fi
        
        cat "$key_path.pub"
        echo ""
    fi
fi

# Generowanie klucza AES do szyfrowania danych
if [[ "$GENERATE_AES" == "true" ]]; then
    log_step "Generowanie klucza AES-256 do szyfrowania danych..."
    
    aes_key_path="$KEYS_DIR/aes_key.enc"
    
    if [[ -f "$aes_key_path" ]]; then
        log_warning "Klucz AES już istnieje!"
        read -p "Nadpisać? (y/n): " overwrite
        if [[ "$overwrite" != "y" ]]; then
            log_info "Pomijam generowanie klucza AES"
        else
            rm -f "$aes_key_path"
        fi
    fi
    
    if [[ ! -f "$aes_key_path" ]]; then
        # Generuj losowy klucz AES-256 (32 bajty = 256 bitów)
        if command -v openssl &> /dev/null; then
            openssl rand -base64 32 > "$aes_key_path"
            chmod 600 "$aes_key_path"
            log_success "Klucz AES-256 wygenerowany: $aes_key_path"
            log_warning "⚠️  ZAPISZ TEN KLUCZ W BEZPIECZNYM MIEJSCU!"
            log_warning "⚠️  Bez tego klucza nie odzyskasz zaszyfrowanych danych!"
        else
            log_error "OpenSSL nie jest zainstalowany. Nie można wygenerować klucza AES."
        fi
    fi
fi

# Generowanie szablonu .env
if [[ "$GENERATE_ENV_TEMPLATE" == "true" ]] || [[ "$GENERATE_SSH_ED25519" == "true" ]] || [[ "$GENERATE_SSH_RSA" == "true" ]] || [[ "$GENERATE_AES" == "true" ]]; then
    log_step "Tworzenie szablonu .env..."
    
    if [[ -f ".env" ]]; then
        log_warning "Plik .env już istnieje!"
        read -p "Nadpisać? (y/n): " overwrite
        if [[ "$overwrite" != "y" ]]; then
            log_info "Pomijam tworzenie .env"
        else
            cp .env ".env.backup.$(date +%Y%m%d_%H%M%S)"
            log_info "Utworzono backup: .env.backup.*"
        fi
    fi
    
    if [[ ! -f ".env" ]] || [[ "$overwrite" == "y" ]]; then
        cat > .env << 'EOF'
# AI Blockchain - Konfiguracja
# Skopiowano z config/env.example.txt
# Data utworzenia: $(date)

# === API Keys dla LLM ===
# Anthropic Claude (zalecany)
ANTHROPIC_API_KEY=your-anthropic-key-here

# OpenAI (alternatywnie)
OPENAI_API_KEY=your-openai-key-here

# === API Giełd ===
# Binance (opcjonalnie - dla prywatnych endpointów)
BINANCE_API_KEY=your-binance-key-here
BINANCE_SECRET_KEY=your-binance-secret-here

# === Database ===
# PostgreSQL 17 + TimescaleDB (produkcja) - REKOMENDOWANE
DATABASE_URL=postgresql://piotradamczyk@localhost:5432/ai_blockchain
USE_TIMESCALE=true

# SQLite (development - bez konfiguracji, domyślne)
# DATABASE_URL=sqlite:///data/ai_blockchain.db

# === Sentiment APIs ===
# Twitter/X API v2
TWITTER_BEARER_TOKEN=your-twitter-token-here

# Reddit API (dla PRAW)
REDDIT_CLIENT_ID=your-reddit-client-id
REDDIT_CLIENT_SECRET=your-reddit-secret
REDDIT_USER_AGENT=ai-blockchain-bot/1.0

# === Alerty ===
# Telegram Bot
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# === Klucze Kryptograficzne (opcjonalnie) ===
# Ścieżki do kluczy SSH (jeśli wygenerowane)
# SSH_PRIVATE_KEY_PATH=.keys/ai_blockchain_ed25519
# SSH_PUBLIC_KEY_PATH=.keys/ai_blockchain_ed25519.pub

# Klucz AES do szyfrowania danych (jeśli wygenerowany)
# AES_KEY_PATH=.keys/aes_key.enc
EOF
        
        # Zastąp datę
        sed -i '' "s/\$(date)/$(date '+%Y-%m-%d %H:%M:%S')/" .env 2>/dev/null || \
        sed -i "s/\$(date)/$(date '+%Y-%m-%d %H:%M:%S')/" .env
        
        log_success "Szablon .env utworzony"
    fi
fi

# Podsumowanie
echo ""
log_success "=========================================="
log_success "Generowanie zakończone!"
log_success "=========================================="
echo ""

if [[ "$GENERATE_SSH_ED25519" == "true" ]] || [[ "$GENERATE_SSH_RSA" == "true" ]]; then
    log_info "📋 Klucze SSH zostały zapisane w: $KEYS_DIR/"
    echo ""
    log_info "Aby dodać klucz SSH do agenta:"
    echo "  eval \$(ssh-agent -s)"
    echo "  ssh-add $KEYS_DIR/ai_blockchain_ed25519"
    echo ""
    log_info "Aby skopiować klucz publiczny do schowka:"
    echo "  pbcopy < $KEYS_DIR/ai_blockchain_ed25519.pub  # macOS"
    echo "  xclip -sel clip < $KEYS_DIR/ai_blockchain_ed25519.pub  # Linux"
    echo ""
fi

if [[ "$GENERATE_AES" == "true" ]]; then
    log_warning "⚠️  WAŻNE: Klucz AES jest w $KEYS_DIR/aes_key.enc"
    log_warning "⚠️  ZAPISZ GO W BEZPIECZNYM MIEJSCU (password manager, etc.)"
    echo ""
fi

log_info "📝 Następne kroki:"
echo "  1. Skonfiguruj API keys w pliku .env"
echo "  2. Dodaj klucze SSH do GitHub/GitLab (Settings → SSH Keys)"
echo "  3. Upewnij się, że .keys/ jest w .gitignore (już jest)"
echo ""

