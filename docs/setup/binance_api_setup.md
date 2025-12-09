# Konfiguracja API Binance

## 📋 Wymagania

Aby uruchomić testy integracyjne z Binance API, potrzebujesz:

1. **Konto Binance** (możesz użyć testnet/sandbox)
2. **API Key** i **Secret Key**

## 🔑 Jak uzyskać API Keys

### Krok 1: Utwórz konto Binance

1. Przejdź na [binance.com](https://www.binance.com)
2. Zarejestruj się i zweryfikuj konto (jeśli wymagane)

### Krok 2: Utwórz API Key

1. Zaloguj się do Binance
2. Przejdź do **API Management**: 
   - Menu użytkownika (ikonka profilu) → **API Management**
3. Kliknij **Create API**
4. Wybierz typ:
   - **Read-only** - dla testów (bezpieczniejsze)
   - **Enable Spot & Margin Trading** - jeśli potrzebujesz tradingu
5. Zweryfikuj tożsamość (SMS/Email)
6. **Zapisz klucze** - Secret Key jest widoczny tylko raz!

### Krok 3: Skonfiguruj w projekcie

1. Skopiuj `config/env.example.txt` do `.env`:
```bash
cp config/env.example.txt .env
```

2. Dodaj klucze do `.env`:
```env
BINANCE_API_KEY=twoj_api_key_tutaj
BINANCE_SECRET=twoj_secret_key_tutaj
```

3. **WAŻNE**: Dodaj `.env` do `.gitignore` (już jest dodany)

## 🧪 Tryb Sandbox (Testnet)

Dla testów możesz użyć trybu sandbox:

```python
from src.collectors.exchange.binance_collector import BinanceCollector

collector = BinanceCollector(sandbox=True)
```

**Uwaga**: Sandbox używa testowych danych i nie wymaga prawdziwych środków.

## 🔒 Bezpieczeństwo

- **Nigdy** nie commituj API keys do git
- Używaj **Read-only** keys dla testów
- Włącz **IP Whitelist** w ustawieniach API (opcjonalnie)
- Regularnie rotuj klucze

## ⚠️ Limity API

Binance ma limity requestów:
- **1200 requests per minute** (weighted)
- Testy integracyjne mogą przekroczyć limity - używaj z umiarem

## 🐛 Rozwiązywanie problemów

### Błąd: "Invalid API-key"
- Sprawdź czy klucze są poprawne
- Sprawdź czy nie ma dodatkowych spacji w `.env`

### Błąd: "IP address not whitelisted"
- Wyłącz IP Whitelist w ustawieniach API
- Lub dodaj swój IP do whitelist

### Błąd: "API-key format invalid"
- Sprawdź format kluczy (powinny być długie stringi)
- Upewnij się że nie używasz kluczy z innych giełd

## 📚 Dokumentacja

- [Binance API Docs](https://binance-docs.github.io/apidocs/spot/en/)
- [API Management](https://www.binance.com/en/my/settings/api-management)

