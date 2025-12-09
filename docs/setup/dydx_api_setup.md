# Konfiguracja API dYdX

## 📋 Wymagania

dYdX v4 API jest **publiczne** i **nie wymaga API keys** dla podstawowych operacji (pobieranie danych rynkowych, tickerów, świec).

## 🔑 Kiedy potrzebujesz API Keys?

API keys są wymagane tylko dla:
- **Trading** (otwieranie/zamykanie pozycji)
- **Zarządzanie portfelem**
- **Private endpoints** (historia zamówień, saldo)

## 🧪 Testy integracyjne

Dla testów integracyjnych w tym projekcie **nie potrzebujesz API keys** - wszystkie testy używają publicznych endpointów.

## 🔧 Konfiguracja

### Tryb Mainnet (produkcyjny)

```python
from src.collectors.exchange.dydx_collector import DydxCollector

collector = DydxCollector(testnet=False)
```

### Tryb Testnet (dla testów)

```python
collector = DydxCollector(testnet=True)
```

## 📚 Dostępne Endpointy (bez API keys)

- `GET /markets` - lista rynków
- `GET /markets/{market}` - szczegóły rynku
- `GET /candles/{market}` - świece OHLCV
- `GET /trades/{market}` - ostatnie transakcje
- `GET /historical-funding/{market}` - funding rates

## 🔒 Jeśli potrzebujesz Trading API

1. Przejdź na [dydx.exchange](https://dydx.exchange)
2. Zaloguj się i przejdź do **API Settings**
3. Utwórz API Key z odpowiednimi uprawnieniami
4. Dodaj do `.env`:
```env
DYDX_API_KEY=twoj_api_key
DYDX_API_SECRET=twoj_secret
DYDX_API_PASSPHRASE=twoj_passphrase
```

## ⚠️ Limity API

dYdX v4 API:
- **Rate limiting**: ~100 requests/second
- Testy integracyjne używają retry logic z exponential backoff

## 🐛 Rozwiązywanie problemów

### Błąd: 429 Too Many Requests
- API ma rate limiting
- Kolektor automatycznie retry z exponential backoff
- Jeśli problem się powtarza, zwiększ opóźnienia

### Błąd: 503 Service Unavailable
- Tymczasowy problem z API
- Retry logic powinien to obsłużyć automatycznie

## 📚 Dokumentacja

- [dYdX v4 API Docs](https://docs.dydx.exchange/)
- [API Reference](https://docs.dydx.exchange/#/)

