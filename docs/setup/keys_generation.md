# Generowanie Kluczy Kryptograficznych

## 🔑 Przegląd

Projekt AI Blockchain może wymagać różnych typów kluczy kryptograficznych:

1. **Klucze SSH** - do autoryzacji Git (GitHub/GitLab)
2. **Klucze AES** - do szyfrowania wrażliwych danych lokalnie
3. **API Keys** - generowane przez zewnętrzne serwisy (nie lokalnie)

## 🚀 Szybki Start

Użyj skryptu automatycznego:

```bash
./scripts/generate_keys.sh
```

Skrypt interaktywnie przeprowadzi Cię przez proces generowania kluczy.

## 📋 Typy Kluczy

### 1. Klucze SSH (Ed25519) - Rekomendowane

**Zastosowanie:**
- Autoryzacja Git (GitHub, GitLab)
- Połączenia SSH z serwerami
- Najbezpieczniejsze i najszybsze

**Generowanie:**
```bash
./scripts/generate_keys.sh
# Wybierz opcję 1
```

**Lokalizacja:**
- Klucz prywatny: `.keys/ai_blockchain_ed25519`
- Klucz publiczny: `.keys/ai_blockchain_ed25519.pub`

**Dodanie do GitHub/GitLab:**
1. Skopiuj zawartość klucza publicznego:
   ```bash
   cat .keys/ai_blockchain_ed25519.pub
   ```
2. Wklej w Settings → SSH Keys na GitHub/GitLab

### 2. Klucze SSH (RSA 4096-bit)

**Zastosowanie:**
- Alternatywa dla Ed25519
- Wymagane przez niektóre systemy (starsze)
- Format PEM dla kompatybilności

**Generowanie:**
```bash
./scripts/generate_keys.sh
# Wybierz opcję 2
```

**Lokalizacja:**
- Klucz prywatny: `.keys/ai_blockchain_rsa`
- Klucz publiczny: `.keys/ai_blockchain_rsa.pub`
- Klucz publiczny PEM: `.keys/ai_blockchain_rsa.pub.pem`

### 3. Klucze AES-256 (Szyfrowanie Danych)

**Zastosowanie:**
- Szyfrowanie wrażliwych danych lokalnie
- Backup zaszyfrowanych danych
- Ochrona plików konfiguracyjnych

**Generowanie:**
```bash
./scripts/generate_keys.sh
# Wybierz opcję 3
```

**Lokalizacja:**
- Klucz: `.keys/aes_key.enc`

**⚠️ WAŻNE:**
- **ZAPISZ TEN KLUCZ W BEZPIECZNYM MIEJSCU!**
- Bez tego klucza nie odzyskasz zaszyfrowanych danych
- Użyj password managera (1Password, Bitwarden, etc.)

## 🔧 Ręczne Generowanie

### SSH Ed25519

```bash
# Utwórz katalog
mkdir -p .keys
chmod 700 .keys

# Generuj klucz
ssh-keygen -t ed25519 -C "twoj-email@example.com" -f .keys/ai_blockchain_ed25519

# Ustaw uprawnienia
chmod 600 .keys/ai_blockchain_ed25519
chmod 644 .keys/ai_blockchain_ed25519.pub
```

### SSH RSA (PEM format)

```bash
# Generuj klucz RSA 4096-bit
ssh-keygen -t rsa -b 4096 -C "twoj-email@example.com" -f .keys/ai_blockchain_rsa

# Konwertuj do PEM (jeśli potrzeba)
openssl rsa -in .keys/ai_blockchain_rsa -pubout -out .keys/ai_blockchain_rsa.pub.pem
```

### AES-256

```bash
# Generuj losowy klucz 256-bit
openssl rand -base64 32 > .keys/aes_key.enc
chmod 600 .keys/aes_key.enc
```

## 🔐 Bezpieczeństwo

### Best Practices

1. **Nigdy nie commituj kluczy prywatnych**
   - Katalog `.keys/` jest w `.gitignore`
   - Sprawdź przed commitem: `git status`

2. **Ograniczone uprawnienia**
   ```bash
   chmod 700 .keys/      # Tylko właściciel
   chmod 600 .keys/*     # Klucze prywatne
   chmod 644 .keys/*.pub # Klucze publiczne
   ```

3. **Backup kluczy**
   - Zapisz w password managerze
   - Backup w bezpiecznym miejscu (offline)
   - Nie przechowuj w chmurze bez szyfrowania

4. **Rotacja kluczy**
   - Regularnie rotuj klucze (co 6-12 miesięcy)
   - Używaj różnych kluczy dla różnych celów

## 📝 Konfiguracja SSH Agent

### macOS / Linux

```bash
# Uruchom ssh-agent
eval $(ssh-agent -s)

# Dodaj klucz
ssh-add .keys/ai_blockchain_ed25519

# Sprawdź dodane klucze
ssh-add -l
```

### Automatyczne dodanie (macOS)

Dodaj do `~/.ssh/config`:
```
Host github.com
    IdentityFile ~/Projects/Octadecimal/ai-blockchain/.keys/ai_blockchain_ed25519
    IdentitiesOnly yes
```

## 🧪 Weryfikacja

### Sprawdź klucz SSH

```bash
# Test połączenia z GitHub
ssh -T git@github.com

# Test połączenia z GitLab
ssh -T git@gitlab.com
```

### Sprawdź klucz AES

```bash
# Sprawdź czy klucz istnieje
ls -la .keys/aes_key.enc

# Sprawdź rozmiar (powinien być 44 znaki base64 = 32 bajty)
wc -c .keys/aes_key.enc
```

## 🐛 Rozwiązywanie Problemów

### Błąd: "Permission denied (publickey)"

**Przyczyna:** Klucz nie jest dodany do ssh-agent lub nie jest w GitHub/GitLab

**Rozwiązanie:**
1. Dodaj klucz do ssh-agent: `ssh-add .keys/ai_blockchain_ed25519`
2. Sprawdź czy klucz jest w GitHub/GitLab (Settings → SSH Keys)
3. Sprawdź uprawnienia: `chmod 600 .keys/ai_blockchain_ed25519`

### Błąd: "Bad permissions"

**Przyczyna:** Zbyt otwarte uprawnienia do klucza

**Rozwiązanie:**
```bash
chmod 600 .keys/ai_blockchain_ed25519
chmod 644 .keys/ai_blockchain_ed25519.pub
```

### Błąd: "OpenSSL not found"

**Przyczyna:** OpenSSL nie jest zainstalowany

**Rozwiązanie:**
```bash
# macOS
brew install openssl

# Ubuntu/Debian
sudo apt install openssl
```

## 📚 Zasoby

- [GitHub: Generating SSH keys](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent)
- [OpenSSH Documentation](https://www.openssh.com/manual.html)
- [Ed25519 vs RSA](https://blog.g3rt.nl/upgrade-your-ssh-keys.html)

---

*Ostatnia aktualizacja: 2025-12-09*

