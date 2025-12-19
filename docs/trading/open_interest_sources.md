# Źródła Danych Open Interest - Przewodnik

## 📊 Problem

Binance API dla open interest history ma ograniczenia:
- Zwraca tylko ~100 rekordów (ostatnie ~8 godzin)
- Problemy z parametrem `startTime` dla starszych danych
- Brak długiej historii przez standardowe API

## 🔍 Dostępne Źródła

### 1. **Binance - Regularne Zbieranie (Zalecane)**

**Rozwiązanie:** Zbierać aktualny open interest regularnie i budować historię.

**Zalety:**
- ✅ Darmowe
- ✅ Aktualne dane
- ✅ Można zbudować długą historię (od momentu rozpoczęcia zbierania)

**Implementacja:**
```python
# Uruchom cron job co 15 minut lub 1 godzinę
# Zbieraj aktualny open interest i zapisuj do bazy
```

**Skrypt:** `scripts/collect_open_interest_regularly.py` (do utworzenia)

### 2. **Binance - Bezpośrednie API Endpoint**

**Endpoint:** `/fapi/v1/openInterestHist` (Futures Data API)

**Zalety:**
- ✅ Może mieć więcej danych niż przez ccxt
- ✅ Kontrola nad parametrami

**Ograniczenia:**
- ⚠️ Nadal może być limitowany do ostatnich dni

**Implementacja:**
```python
import requests

def get_open_interest_history_direct(symbol="BTCUSDT", period="5m", limit=500):
    url = "https://fapi.binance.com/fapi/v1/openInterestHist"
    params = {
        "symbol": symbol,
        "period": period,  # 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d
        "limit": limit
    }
    response = requests.get(url, params=params)
    return response.json()
```

### 3. **Inne Giełdy**

#### Bybit
- ✅ Ma historię open interest
- ✅ API: `/v5/market/open-interest`
- ⚠️ Różne symbole (BTCUSDT vs BTC/USDT:USDT)

#### OKX
- ✅ Ma historię open interest
- ✅ API: `/api/v5/public/open-interest`
- ⚠️ Różne symbole

#### dYdX
- ❌ Tylko aktualny open interest (brak historii)
- ✅ Dostępny przez `get_ticker()`

### 4. **Płatne API**

#### CoinAPI
- ✅ Długie serie historyczne
- ✅ REST API + WebSocket
- ❌ Płatne (od $79/miesiąc)

#### CryptoCompare
- ✅ Dane historyczne open interest
- ✅ REST API
- ❌ Płatne (od $99/miesiąc)

#### Glassnode
- ✅ Zaawansowane metryki on-chain
- ✅ Open interest dla różnych giełd
- ❌ Płatne (od $29/miesiąc)

### 5. **Agregatory Danych**

#### CryptoQuant
- ✅ Dane open interest z wielu giełd
- ✅ API dostępne
- ❌ Płatne (od $19/miesiąc)

#### TradingView
- ✅ Długie serie historyczne
- ✅ Eksport do CSV
- ⚠️ Ograniczenia API (wymaga subskrypcji)

## 💡 Rekomendowane Rozwiązanie

### Opcja 1: Regularne Zbieranie (Najlepsze dla długoterminowej historii)

**Utwórz skrypt cron job:**
```python
# scripts/collect_open_interest_regularly.py
# Uruchamiaj co 15 minut lub 1 godzinę
# Zbiera aktualny open interest i zapisuje do bazy
```

**Zalety:**
- ✅ Budujesz własną historię od zera
- ✅ Pełna kontrola nad danymi
- ✅ Darmowe
- ✅ Możesz zbierać z wielu giełd jednocześnie

### Opcja 2: Użyj Innych Giełd

**Dodaj kolektory dla:**
- Bybit
- OKX
- Inne giełdy z historią open interest

**Zalety:**
- ✅ Możesz mieć dłuższą historię z innych giełd
- ✅ Różne perspektywy rynku

### Opcja 3: Płatne API (Dla natychmiastowej długiej historii)

**Jeśli potrzebujesz natychmiast długiej historii:**
- CoinAPI
- CryptoCompare
- Glassnode

## 🛠️ Implementacja

### Krok 1: Utwórz skrypt do regularnego zbierania

```python
# scripts/collect_open_interest_regularly.py
from src.collectors.exchange.binance_collector import BinanceCollector
from src.database.manager import DatabaseManager
import schedule
import time

def collect_open_interest():
    collector = BinanceCollector()
    db = DatabaseManager()
    
    # Pobierz aktualny open interest
    oi = collector.futures_exchange.fetch_open_interest('BTC/USDT:USDT')
    
    # Zapisz do bazy
    # ...
```

### Krok 2: Uruchom jako cron job

```bash
# Co 15 minut
*/15 * * * * python scripts/collect_open_interest_regularly.py

# Lub co 1 godzinę
0 * * * * python scripts/collect_open_interest_regularly.py
```

### Krok 3: Alternatywnie - użyj bezpośredniego Binance API

Zmień `get_open_interest()` w `BinanceCollector` aby używać bezpośredniego endpointu zamiast ccxt.

## 📈 Obecny Stan

- **Binance przez ccxt:** ~100 rekordów (ostatnie 8h)
- **Binance bezpośrednie API:** Może mieć więcej (do sprawdzenia)
- **dYdX:** Tylko aktualny (brak historii)
- **Inne giełdy:** Do zaimplementowania

## 🎯 Następne Kroki

1. ✅ Sprawdź bezpośredni Binance API endpoint
2. ✅ Utwórz skrypt do regularnego zbierania
3. ⏳ Dodaj kolektory dla innych giełd (Bybit, OKX)
4. ⏳ Rozważ płatne API jeśli potrzebna natychmiastowa długa historia

