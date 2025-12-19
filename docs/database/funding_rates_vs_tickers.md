# Analiza: funding_rates vs tickers.funding_rate

## 📊 Porównanie tabel

### Tabela `funding_rates`
- **Rekordów**: 6,873
- **Zakres dat**: 2019-09-10 → 2025-12-18
- **Kolumny**: `timestamp`, `exchange`, `symbol`, `funding_rate`, `price_at_funding`
- **Unique constraint**: `(timestamp, exchange, symbol)`
- **Użycie**: Źródło danych do wypełnienia `tickers.funding_rate`

### Tabela `tickers.funding_rate`
- **Rekordów**: 48,296 (wszystkie mają `funding_rate`)
- **Zakres dat**: 2020-01-01 → 2025-12-18
- **Kolumna**: `funding_rate` (nullable, część większego snapshotu)
- **Użycie**: Używana w strategiach do analizy

## 🔍 Różnice

### 1. **Zakres dat**
- `funding_rates`: 2019-09-10 → 2025-12-18
- `tickers`: 2020-01-01 → 2025-12-18
- **Różnica**: `funding_rates` ma 338 rekordów przed 2020-01-01 (4.9% danych)

### 2. **Kolumna `price_at_funding`**
- **Status**: Nieużywana (0% rekordów ma wartość)
- **Przeznaczenie**: Cena w momencie funding rate (może być przydatna w przyszłości)

### 3. **Struktura danych**
- `funding_rates`: Dedykowana tabela tylko dla funding rates
- `tickers.funding_rate`: Część większego snapshotu (price, volume, OI, etc.)

## 📋 Użycie w kodzie

### 1. **Pobieranie danych**
- `under_human_strategy_1.0.py`: Używa `db.get_funding_rates()` w trybie backtestingu
- `generate_historical_tickers.py`: Używa `db.get_funding_rates()` do wypełnienia `tickers.funding_rate`
- Większość strategii: Używa `dydx_collector.get_funding_rates()` dla danych real-time

### 2. **Zapytania**
- `db.get_funding_rates()`: Zwraca DataFrame z funding rates (używane w backtestingu)
- `tickers.funding_rate`: Używane bezpośrednio w strategiach (gdy dane są już w DataFrame)

## 💡 Rekomendacja

### ✅ **ZOSTAW OBYDWIE TABELE** (obecna architektura)

**Powody:**

1. **Różne zakresy dat**
   - `funding_rates` ma dane przed 2020-01-01 (338 rekordów)
   - `tickers` zaczyna od 2020-01-01
   - Usunięcie `funding_rates` spowodowałoby utratę danych historycznych

2. **Różne przypadki użycia**
   - `funding_rates`: Zapytania tylko o funding rates (bez innych danych tickera)
   - `tickers.funding_rate`: Część większego snapshotu (używane razem z price, volume, OI)

3. **Optymalizacja zapytań**
   - `funding_rates`: Mniejsza tabela (6,873 rekordów) - szybsze zapytania
   - `tickers`: Większa tabela (48,296 rekordów) - wolniejsze zapytania tylko o funding rate

4. **Normalizacja danych**
   - `funding_rates` jest źródłem prawdy (source of truth)
   - `tickers.funding_rate` jest denormalizacją dla szybkiego dostępu

### ❌ **NIE USUWAJMY `funding_rates`**

**Problemy z usunięciem:**

1. **Utrata danych historycznych**
   - 338 rekordów przed 2020-01-01
   - Możliwe, że w przyszłości będziemy potrzebować tych danych

2. **Wolniejsze zapytania**
   - Zapytania tylko o funding rates będą musiały skanować większą tabelę `tickers`
   - `funding_rates` jest zoptymalizowana dla tego typu zapytań

3. **Brak kolumny `price_at_funding`**
   - Może być przydatna w przyszłości (analiza korelacji cena vs funding rate)
   - `tickers` ma `price`, ale to może być inna cena (close z OHLCV)

## 🔄 Alternatywne podejście (opcjonalne)

Jeśli chcemy uprościć architekturę:

1. **Przenieś dane z `funding_rates` do `tickers`**
   - Uzupełnij `tickers` danymi z 2019-09-10 → 2020-01-01
   - Użyj `price_at_funding` jako `price` w tickers (jeśli dostępne)

2. **Usuń `funding_rates`**
   - Wszystkie zapytania będą używać `tickers.funding_rate`
   - Uproszczenie architektury

3. **Utwórz view/materialized view**
   - `funding_rates_view` jako widok na `tickers.funding_rate`
   - Zachowaj kompatybilność z istniejącym kodem

## 📊 Podsumowanie

| Aspekt | funding_rates | tickers.funding_rate |
|--------|--------------|---------------------|
| **Rekordów** | 6,873 | 48,296 |
| **Zakres dat** | 2019-09-10 → 2025-12-18 | 2020-01-01 → 2025-12-18 |
| **Dedykowana tabela** | ✅ Tak | ❌ Nie (część tickers) |
| **Szybkość zapytań** | ✅ Szybka (mniejsza tabela) | ⚠️ Wolniejsza (większa tabela) |
| **Dane historyczne** | ✅ 2019-09-10 | ❌ Od 2020-01-01 |
| **price_at_funding** | ✅ Tak (niewypełnione) | ❌ Nie |
| **Użycie** | Źródło danych | Używane w strategiach |

## ✅ Finalna rekomendacja

**Zostaw obydwie tabele** - obecna architektura jest poprawna:
- `funding_rates` jako źródło danych (source of truth)
- `tickers.funding_rate` jako denormalizacja dla szybkiego dostępu
- Różne zakresy dat i przypadki użycia uzasadniają obydwie tabele

