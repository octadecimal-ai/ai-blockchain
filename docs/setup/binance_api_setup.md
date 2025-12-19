# Konfiguracja API Binance

## 📋 Wymagania

Binance API **NIE WYMAGA API keys** dla podstawowych operacji (pobieranie danych rynkowych, tickerów, świec OHLCV).

## 🔑 Kiedy potrzebujesz API Keys?

API keys są wymagane **TYLKO** dla:
- **Trading** (otwieranie/zamykanie pozycji)
- **Zarządzanie portfelem** (sprawdzanie salda)
- **Private endpoints** (historia zamówień, depozyty, wypłaty)

## ✅ Operacje BEZ API Keys (Publiczne Endpointy)

Możesz używać BinanceCollector bez API keys do:
- ✅ Pobierania danych historycznych (OHLCV)
- ✅ Pobierania aktualnych cen (ticker)
- ✅ Pobierania listy dostępnych par handlowych
- ✅ Pobierania danych z wielu lat wstecz

## 🧪 Testy integracyjne

Dla testów integracyjnych w tym projekcie **nie potrzebujesz API keys** - wszystkie testy używają publicznych endpointów.

## 🔧 Konfiguracja

### Tryb Publiczny (bez API keys) - Domyślny

```python
from src.collectors.exchange.binance_collector import BinanceCollector

# Działa bez API keys!
collector = BinanceCollector(sandbox=False)

# Pobierz dane historyczne
df = collector.fetch_historical(
    symbol="BTC/USDT",
    timeframe="1h",
    start_date=datetime(2022, 1, 1),
    end_date=datetime(2022, 12, 31)
)
```

### Tryb z API Keys (tylko dla tradingu)

Jeśli chcesz używać Binance do tradingu, potrzebujesz API keys:

1. Przejdź na [Binance API Management](https://www.binance.com/en/my/settings/api-management)
2. Utwórz API Key z odpowiednimi uprawnieniami
3. Dodaj do `.env`:
```env
BINANCE_API_KEY=twoj_api_key
BINANCE_SECRET=twoj_secret
```

4. Użyj w kodzie:
```python
from src.collectors.exchange.binance_collector import BinanceCollector

collector = BinanceCollector(
    sandbox=False,
    api_key=os.getenv('BINANCE_API_KEY'),
    secret=os.getenv('BINANCE_SECRET')
)
```

## ⚠️ Limity API

Binance API:
- **Rate limiting**: 1200 requests/minute dla publicznych endpointów
- **Weight limits**: Różne endpointy mają różne wagi
- Kolektor automatycznie używa rate limiting (`enableRateLimit: True`)

## 📚 Publiczne Endpointy (bez API keys)

- `GET /api/v3/klines` - świece OHLCV ✅
- `GET /api/v3/ticker/24hr` - ticker 24h ✅
- `GET /api/v3/exchangeInfo` - informacje o rynku ✅
- `GET /api/v3/ticker/price` - aktualna cena ✅

## 🔒 Prywatne Endpointy (wymagają API keys)

- `POST /api/v3/order` - złożenie zamówienia ❌
- `GET /api/v3/account` - informacje o koncie ❌
- `GET /api/v3/myTrades` - historia transakcji ❌
- `GET /api/v3/openOrders` - otwarte zamówienia ❌

## 🐛 Rozwiązywanie problemów

### Błąd: 429 Too Many Requests
- API ma rate limiting
- Kolektor automatycznie używa rate limiting
- Jeśli problem się powtarza, zwiększ opóźnienia między requestami

### Błąd: 403 Forbidden
- Sprawdź, czy nie próbujesz użyć prywatnych endpointów bez API keys
- Publiczne endpointy (OHLCV, ticker) nie wymagają autoryzacji

## 📚 Dokumentacja

- [Binance API Docs](https://binance-docs.github.io/apidocs/spot/en/)
- [ccxt Binance Documentation](https://docs.ccxt.com/#/README?id=binance)

## 💡 Przykład użycia bez API keys

```python
from src.collectors.exchange.binance_collector import BinanceCollector
from datetime import datetime

# Inicjalizacja bez API keys - działa!
collector = BinanceCollector()

# Pobierz dane z 2022, 2023, 2024
for year in [2022, 2023, 2024]:
    df = collector.fetch_historical(
        symbol="BTC/USDT",
        timeframe="1h",
        start_date=datetime(year, 1, 1),
        end_date=datetime(year, 12, 31)
    )
    print(f"{year}: {len(df)} świec")
```
