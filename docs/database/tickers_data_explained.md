# Wyjaśnienie Danych w Tabeli Tickers

## Co to jest Ticker?

**Ticker** to jak "zdjęcie" stanu rynku w konkretnym momencie. Wyobraź sobie, że co godzinę robisz zdjęcie ceny Bitcoina i zapisujesz wszystkie ważne informacje - to właśnie ticker.

Każdy ticker to jeden rekord w bazie danych, który zawiera wszystkie dostępne informacje o rynku w danym momencie czasu.

## Kolumny w Tabeli Tickers

### Podstawowe Informacje

#### `timestamp`
- **Co to:** Data i godzina, kiedy został zrobiony ten "snapshot" rynku
- **Przykład:** `2024-01-15 14:30:00`
- **Skąd:** Automatycznie zapisywane podczas zbierania danych

#### `exchange`
- **Co to:** Nazwa giełdy, z której pochodzą dane
- **Przykład:** `binance`
- **Skąd:** Ustawiane podczas zapisu danych

#### `symbol`
- **Co to:** Para handlowa (co kupujemy/sprzedajemy)
- **Przykład:** `BTC/USDC` oznacza "Bitcoin za USDC"
- **Skąd:** Ustawiane podczas zapisu danych

---

### Ceny

#### `price`
- **Co to:** Aktualna cena zamknięcia (ostatnia cena transakcji)
- **Przykład:** `42000.50` oznacza, że 1 Bitcoin kosztuje 42,000.50 USDC
- **Skąd:** Z danych OHLCV (ostatnia cena z danej świecy czasowej)
- **Użycie:** Główna cena używana w strategiach tradingowych

#### `bid`
- **Co to:** Najwyższa cena, którą ktoś jest gotowy ZAKUPIĆ
- **Przykład:** Jeśli `bid = 41999.00`, to znaczy, że ktoś chce kupić Bitcoina za 41,999 USDC
- **Skąd:** Z orderbook (księgi zleceń) - lista wszystkich chętnych do kupna
- **Status:** ❌ Brak w bazie (Binance nie udostępnia historii orderbook)
- **Użycie:** Ważne dla strategii, które analizują popyt

#### `ask`
- **Co to:** Najniższa cena, którą ktoś jest gotowy SPRZEDAĆ
- **Przykład:** Jeśli `ask = 42001.00`, to znaczy, że ktoś chce sprzedać Bitcoina za 42,001 USDC
- **Skąd:** Z orderbook (księgi zleceń) - lista wszystkich chętnych do sprzedaży
- **Status:** ❌ Brak w bazie (Binance nie udostępnia historii orderbook)
- **Użycie:** Ważne dla strategii, które analizują podaż

#### `spread`
- **Co to:** Różnica między ceną sprzedaży (`ask`) a ceną kupna (`bid`)
- **Przykład:** Jeśli `bid = 41999` i `ask = 42001`, to `spread = 2 USDC`
- **Skąd:** Obliczane jako `ask - bid`
- **Status:** ❌ Brak w bazie (bo brakuje `bid` i `ask`)
- **Użycie:** Pokazuje "koszt" transakcji - im większy spread, tym drożej handlować

**Dlaczego spread jest ważny?**
- Mały spread = rynek jest "płynny" (łatwo kupić/sprzedać)
- Duży spread = rynek jest "niepłynny" (trudniej handlować, większe koszty)

---

### Metryki 24-godzinne

Te kolumny pokazują, co się działo w ciągu ostatnich 24 godzin.

#### `high_24h`
- **Co to:** Najwyższa cena w ciągu ostatnich 24 godzin
- **Przykład:** `high_24h = 43000.00` oznacza, że w ciągu ostatnich 24h cena osiągnęła 43,000 USDC
- **Skąd:** Obliczane z danych OHLCV (szukamy najwyższej ceny z okna 24h)
- **Użycie:** Pokazuje maksymalny poziom ceny w ostatnim dniu

#### `low_24h`
- **Co to:** Najniższa cena w ciągu ostatnich 24 godzin
- **Przykład:** `low_24h = 41000.00` oznacza, że w ciągu ostatnich 24h cena spadła do 41,000 USDC
- **Skąd:** Obliczane z danych OHLCV (szukamy najniższej ceny z okna 24h)
- **Użycie:** Pokazuje minimalny poziom ceny w ostatnim dniu

#### `volume_24h`
- **Co to:** Łączna wartość wszystkich transakcji w ciągu ostatnich 24 godzin
- **Przykład:** `volume_24h = 1500000.50` oznacza, że w ciągu ostatnich 24h handlowano za 1.5 miliona USDC
- **Skąd:** Obliczane z danych OHLCV (sumujemy wolumen z okna 24h)
- **Użycie:** Pokazuje aktywność rynku - im większy wolumen, tym więcej handlu

**Dlaczego wolumen jest ważny?**
- Wysoki wolumen = dużo ludzi handluje = rynek jest aktywny
- Niski wolumen = mało handlu = rynek może być niestabilny

#### `change_24h`
- **Co to:** Zmiana ceny w ciągu ostatnich 24 godzin (w procentach)
- **Przykład:** `change_24h = 5.5` oznacza, że cena wzrosła o 5.5% w ciągu ostatnich 24h
- **Skąd:** Obliczane jako `(cena_teraz - cena_24h_temu) / cena_24h_temu * 100`
- **Użycie:** Pokazuje trend - dodatnia wartość = cena rośnie, ujemna = cena spada

**Przykład obliczenia:**
- Cena 24h temu: 40,000 USDC
- Cena teraz: 42,000 USDC
- Zmiana: `(42000 - 40000) / 40000 * 100 = 5%` (wzrost o 5%)

---

### Dane z Kontraktów Futures (Perpetual)

Te kolumny dotyczą kontraktów futures - umów na kupno/sprzedaż w przyszłości.

#### `funding_rate`
- **Co to:** Opłata, którą płacą traderzy co 8 godzin za utrzymanie pozycji
- **Przykład:** `funding_rate = 0.0001` oznacza 0.01% (czyli 0.0001 * 100)
- **Skąd:** Z Binance Futures API (pobierane co 8 godzin)
- **Status:** ✅ Mamy w bazie (od 2020-01-01)
- **Użycie:** Ważne dla strategii arbitrażowych

**Jak działa funding rate?**
- Jeśli funding rate jest **dodatni** (np. 0.01%):
  - Traderzy z pozycją LONG (kupno) płacą traderom z pozycją SHORT (sprzedaż)
  - Oznacza, że więcej ludzi chce kupować niż sprzedawać
- Jeśli funding rate jest **ujemny** (np. -0.01%):
  - Traderzy z pozycją SHORT płacą traderom z pozycją LONG
  - Oznacza, że więcej ludzi chce sprzedawać niż kupować

**Dlaczego to ważne?**
- Wysoki funding rate = rynek jest "przegrzany" (za dużo kupujących)
- Niski/ujemny funding rate = rynek jest "przeziębiony" (za dużo sprzedających)

#### `open_interest`
- **Co to:** Łączna wartość wszystkich otwartych pozycji futures
- **Przykład:** `open_interest = 5000000000` oznacza, że łącznie otwarte pozycje są warte 5 miliardów USDC
- **Skąd:** Z Binance Futures API
- **Status:** ⚠️ Tylko ostatnie ~2 dni w bazie (Binance zwraca tylko ostatnie 2 dni historii)
- **Użycie:** Pokazuje zainteresowanie rynkiem futures

**Dlaczego open interest jest ważny?**
- Wysoki open interest = dużo ludzi ma otwarte pozycje = rynek jest aktywny
- Rosnący open interest = więcej ludzi wchodzi na rynek
- Spadający open interest = ludzie zamykają pozycje = rynek może się zmieniać

---

## Skąd Pochodzą Dane?

### ✅ Dane które MAMY w bazie:

1. **OHLCV** (Open, High, Low, Close, Volume)
   - Pobierane z Binance API
   - Zapisane w tabeli `ohlcv`
   - Używane do obliczenia: `price`, `high_24h`, `low_24h`, `volume_24h`, `change_24h`

2. **Funding Rates**
   - Pobierane z Binance Futures API
   - Zapisane w tabeli `tickers` (kolumna `funding_rate`)
   - Dostępne od 2020-01-01

3. **Open Interest**
   - Pobierane z Binance Futures API
   - Zapisane w tabeli `tickers` (kolumna `open_interest`)
   - ⚠️ Tylko ostatnie ~2 dni (Binance zwraca tylko ostatnie 2 dni historii)

### ❌ Dane których NIE MAMY w bazie:

1. **Bid/Ask/Spread**
   - ❌ Brak w bazie (0% wypełnienia)
   - **Przyczyna:** Binance API nie udostępnia historii orderbook
   - **Rozwiązanie:** Musielibyśmy regularnie zbierać orderbook (np. co 1-5 minut) i zapisywać do bazy

2. **Open Interest (starsze dane)**
   - ⚠️ Tylko ostatnie ~2 dni (0.08% wypełnienia)
   - **Przyczyna:** Binance API zwraca tylko ostatnie ~2 dni historii
   - **Rozwiązanie:** Musielibyśmy regularnie zbierać open interest (np. co 15 minut) i budować historię

---

## Jak Są Używane Te Dane?

### W Strategiach Tradingowych:

1. **Cena (`price`)**
   - Główna cena używana do podejmowania decyzji
   - Porównywana z wskaźnikami technicznymi (RSI, EMA, itp.)

2. **Metryki 24h (`high_24h`, `low_24h`, `volume_24h`, `change_24h`)**
   - Pokazują kontekst rynku (czy cena rośnie/spada, jak aktywny jest rynek)
   - Używane do określenia "nastroju" rynku

3. **Funding Rate**
   - Używany w strategiach arbitrażowych
   - Pokazuje, czy rynek jest "przegrzany" czy "przeziębiony"
   - Wysoki funding rate = sygnał do sprzedaży (za dużo kupujących)

4. **Open Interest**
   - Pokazuje zainteresowanie rynkiem
   - Rosnący OI = więcej ludzi wchodzi na rynek
   - Spadający OI = ludzie zamykają pozycje

### W Backtestingu:

- Wszystkie dane z tickers są używane do symulacji strategii na danych historycznych
- Strategie sprawdzają, jak działałyby w przeszłości używając rzeczywistych danych

---

## Przykładowy Rekord

```python
{
    'timestamp': '2024-01-15 14:30:00',
    'exchange': 'binance',
    'symbol': 'BTC/USDC',
    'price': 42000.50,              # Aktualna cena
    'bid': None,                    # ❌ Brak w bazie
    'ask': None,                    # ❌ Brak w bazie
    'spread': None,                 # ❌ Brak w bazie
    'high_24h': 43000.00,          # Najwyższa cena w ostatnich 24h
    'low_24h': 41000.00,           # Najniższa cena w ostatnich 24h
    'volume_24h': 1500000.50,      # Wolumen w ostatnich 24h
    'change_24h': 5.5,             # Zmiana ceny w ostatnich 24h (+5.5%)
    'funding_rate': 0.0001,        # Funding rate (0.01%)
    'open_interest': None          # ⚠️ Tylko ostatnie ~2 dni
}
```

---

## Podsumowanie

Tabela `tickers` to jak "album ze zdjęciami" rynku - każdy rekord to jedno zdjęcie pokazujące:
- Jaka była cena (`price`)
- Jakie były najwyższe/najniższe ceny w ostatnich 24h (`high_24h`, `low_24h`)
- Ile było handlu (`volume_24h`)
- Jak zmieniła się cena (`change_24h`)
- Jaki był funding rate (`funding_rate`)
- Jaki był open interest (`open_interest`)

**Ważne:** Zgodnie z zasadami projektu, używamy tylko **rzeczywistych danych** z API giełd. Jeśli danych nie ma, zostawiamy `NULL` zamiast szacować lub symulować wartości.

---

## Status Wypełnienia Danych (2020-now)

| Kolumna | Wypełnienie | Źródło |
|---------|-------------|--------|
| `price` | ✅ 100% | Z OHLCV |
| `high_24h` | ✅ 100% | Obliczone z OHLCV |
| `low_24h` | ✅ 100% | Obliczone z OHLCV |
| `volume_24h` | ✅ 100% | Obliczone z OHLCV |
| `change_24h` | ✅ 100% | Obliczone z OHLCV |
| `funding_rate` | ✅ 100% | Z Binance Futures API |
| `open_interest` | ⚠️ 0.08% | Z Binance Futures API (tylko ostatnie ~2 dni) |
| `bid` | ❌ 0% | Brak (Binance nie udostępnia historii) |
| `ask` | ❌ 0% | Brak (Binance nie udostępnia historii) |
| `spread` | ❌ 0% | Brak (bo brakuje bid/ask) |

