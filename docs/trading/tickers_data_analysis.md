# Analiza Danych dla Tabeli Tickers (2020-now)

## 📊 Kolumny w tabeli `tickers`

| Kolumna | Typ | Wymagane | Źródło |
|---------|-----|----------|--------|
| `price` | Float | ✅ | OHLCV.close |
| `bid` | Float | ❌ | Orderbook API |
| `ask` | Float | ❌ | Orderbook API |
| `spread` | Float | ❌ | Obliczone z bid/ask |
| `volume_24h` | Float | ❌ | Obliczone z OHLCV |
| `change_24h` | Float | ❌ | Obliczone z OHLCV |
| `high_24h` | Float | ❌ | Obliczone z OHLCV |
| `low_24h` | Float | ❌ | Obliczone z OHLCV |
| `funding_rate` | Float | ❌ | Funding rates (Binance Futures) |
| `open_interest` | Float | ❌ | Open interest (Binance Futures) |

## ✅ Dane które możemy POBRAĆ (2020-now)

### 1. **OHLCV** (Open, High, Low, Close, Volume)
- **Źródło:** Binance API / baza danych
- **Dostępność:** ✅ Od 2020 do teraz
- **Częstotliwość:** 1m, 5m, 15m, 1h, 4h, 1d
- **Status:** ✅ Mamy w bazie danych
- **Użycie:**
  - `price` = `close`
  - Możemy obliczyć: `high_24h`, `low_24h`, `volume_24h`, `change_24h`

### 2. **Funding Rates**
- **Źródło:** Binance Futures API
- **Dostępność:** ✅ Od 2019-09-10 do teraz (Binance perpetual futures)
- **Częstotliwość:** Co 8 godzin
- **Status:** ✅ Mamy w bazie (6873 rekordów)
- **Użycie:**
  - `funding_rate` = wartość z bazy danych
  - Forward fill do timestamp świec

### 3. **Open Interest**
- **Źródło:** Binance Futures API
- **Dostępność:** ⚠️ Tylko ostatnie ~2 dni (500 rekordów)
- **Częstotliwość:** Co 5-15 minut
- **Status:** ⚠️ Ograniczona historia w bazie
- **Użycie:**
  - `open_interest` = wartość z bazy (jeśli dostępna)
  - Dla starszych danych: NULL

## 📐 Dane które możemy OBLICZYĆ (2020-now)

### 1. **high_24h** (Najwyższa cena w ostatnich 24h)
- **Źródło:** Obliczone z OHLCV
- **Metoda:** `max(high)` z okna 24h
- **Dostępność:** ✅ Dla wszystkich danych OHLCV (2020-now)
- **Implementacja:**
  ```python
  window_24h = ohlcv_df[(ohlcv_df.index >= timestamp - timedelta(hours=24)) & 
                        (ohlcv_df.index <= timestamp)]
  high_24h = window_24h['high'].max()
  ```

### 2. **low_24h** (Najniższa cena w ostatnich 24h)
- **Źródło:** Obliczone z OHLCV
- **Metoda:** `min(low)` z okna 24h
- **Dostępność:** ✅ Dla wszystkich danych OHLCV (2020-now)
- **Implementacja:**
  ```python
  low_24h = window_24h['low'].min()
  ```

### 3. **volume_24h** (Wolumen w ostatnich 24h)
- **Źródło:** Obliczone z OHLCV
- **Metoda:** `sum(volume)` z okna 24h
- **Dostępność:** ✅ Dla wszystkich danych OHLCV (2020-now)
- **Implementacja:**
  ```python
  volume_24h = window_24h['volume'].sum()
  ```

### 4. **change_24h** (Zmiana ceny w ostatnich 24h)
- **Źródło:** Obliczone z OHLCV
- **Metoda:** `(close_now - close_24h_ago) / close_24h_ago * 100`
- **Dostępność:** ✅ Dla wszystkich danych OHLCV (2020-now)
- **Implementacja:**
  ```python
  close_24h_ago = window_24h['close'].iloc[0]
  close_now = window_24h['close'].iloc[-1]
  change_24h = ((close_now - close_24h_ago) / close_24h_ago) * 100
  ```

### 5. **spread** (Spread bid-ask)
- **Źródło:** Obliczone z bid/ask
- **Metoda:** `ask - bid`
- **Dostępność:** ⚠️ Tylko jeśli mamy bid/ask

## ❌ Dane których NAM ZABRAKNIE (2020-now)

### 1. **bid** (Cena kupna)
- **Źródło:** Orderbook API
- **Problem:** ❌ Binance API nie udostępnia historii orderbook
- **Dostępność:** 
  - ❌ Historia: Brak
  - ✅ Real-time: Dostępne (tylko aktualny orderbook)
- **Rozwiązanie:**
  - Regularne zbieranie orderbook (co 1-5 minut) i zapisywanie do bazy
  - Utworzenie tabeli `orderbook_snapshots` do przechowywania historii

### 2. **ask** (Cena sprzedaży)
- **Źródło:** Orderbook API
- **Problem:** ❌ Binance API nie udostępnia historii orderbook
- **Dostępność:**
  - ❌ Historia: Brak
  - ✅ Real-time: Dostępne (tylko aktualny orderbook)
- **Rozwiązanie:** Jak wyżej

### 3. **spread** (Różnica bid-ask)
- **Źródło:** Obliczone z bid/ask
- **Problem:** ❌ Nie możemy obliczyć bez bid/ask
- **Dostępność:**
  - ❌ Historia: Brak (bo brak bid/ask)
  - ✅ Real-time: Możemy obliczyć z aktualnego orderbook

### 4. **open_interest** (dla starszych danych)
- **Źródło:** Binance Futures API
- **Problem:** ⚠️ Binance zwraca tylko ostatnie ~2 dni historii
- **Dostępność:**
  - ❌ 2020-2025-12-16: Brak
  - ✅ 2025-12-16-now: Dostępne (500 rekordów)
- **Rozwiązanie:**
  - Regularne zbieranie open interest (co 15 min) i zapisywanie do bazy
  - Budowanie własnej historii od momentu rozpoczęcia zbierania

## 🎯 Plan Uzupełnienia Tabeli Tickers

### Faza 1: Dane z OHLCV (2020-now) ✅
- [x] `price` = `close` z OHLCV
- [x] `high_24h` = obliczone z OHLCV
- [x] `low_24h` = obliczone z OHLCV
- [x] `volume_24h` = obliczone z OHLCV
- [x] `change_24h` = obliczone z OHLCV

### Faza 2: Funding Rates (2019-09-10-now) ✅
- [x] `funding_rate` = z bazy danych (6873 rekordów)
- [x] Forward fill do timestamp świec

### Faza 3: Open Interest (tylko ostatnie ~2 dni) ⚠️
- [x] `open_interest` = z bazy danych (500 rekordów)
- [ ] Regularne zbieranie open interest (cron job) - do implementacji
- [ ] Budowanie historii od teraz w przyszłość

### Faza 4: Bid/Ask/Spread (tylko real-time) ❌
- [ ] Regularne zbieranie orderbook (cron job) - do implementacji
- [ ] Utworzenie tabeli `orderbook_snapshots` - do implementacji
- [ ] Zapisywanie bid/ask/spread do tickers - do implementacji

## 📋 Podsumowanie

### ✅ Możemy uzupełnić (2020-now):
1. **price** - z OHLCV ✅
2. **high_24h** - obliczone z OHLCV ✅
3. **low_24h** - obliczone z OHLCV ✅
4. **volume_24h** - obliczone z OHLCV ✅
5. **change_24h** - obliczone z OHLCV ✅
6. **funding_rate** - z bazy (2019-09-10-now) ✅
7. **open_interest** - z bazy (tylko ostatnie ~2 dni) ⚠️

### ❌ Nie możemy uzupełnić (2020-now):
1. **bid** - brak historii orderbook ❌
2. **ask** - brak historii orderbook ❌
3. **spread** - brak historii orderbook ❌
4. **open_interest** - brak historii dla 2020-2025-12-16 ❌

## 🛠️ Następne Kroki

1. ✅ Uruchomić `generate_historical_tickers.py` dla danych 2020-now
2. ⏳ Utworzyć skrypt do regularnego zbierania orderbook (bid/ask/spread)
3. ⏳ Utworzyć skrypt do regularnego zbierania open interest
4. ⏳ Utworzyć tabelę `orderbook_snapshots` dla historii orderbook

