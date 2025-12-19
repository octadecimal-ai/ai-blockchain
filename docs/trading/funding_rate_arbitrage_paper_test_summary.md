# Podsumowanie: Skrypt Testowy Funding Rate Arbitrage

## Data: 2025-12-11

## ✅ Gotowe do Użycia

Przygotowano kompletny skrypt shell do testowania strategii **Funding Rate Arbitrage** na rzeczywistym serwisie dYdX w trybie **paper trading**.

---

## 📁 Utworzone Pliki

### 1. Skrypt Testowy
**Plik:** `scripts/test_funding_arbitrage_paper.sh`

**Funkcje:**
- ✅ Automatyczne sprawdzanie środowiska (venv, baza danych)
- ✅ Ustawianie optymalnych parametrów dla pierwszego testu
- ✅ Uruchamianie strategii w trybie paper trading
- ✅ Wyświetlanie wyników i instrukcji

### 2. Aktualizacje Kodu

**Strategia (`src/trading/strategies/funding_rate_arbitrage_strategy.py`):**
- ✅ Dodano obsługę rzeczywistych funding rates z dYdX API
- ✅ Fallback do symulacji (dla backtestingu)
- ✅ Konfiguracja `use_real_funding_rate` i `dydx_collector`

**Run Paper Trading (`scripts/run_paper_trading_enhanced.py`):**
- ✅ Dodano obsługę strategii `funding_rate_arbitrage`
- ✅ Automatyczne przekazywanie DydxCollector do strategii
- ✅ Konserwatywne parametry dla pierwszego testu

**Trading Bot (`src/trading/trading_bot.py`):**
- ✅ Automatyczne przekazywanie DydxCollector do strategii (jeśli potrzebny)

### 3. Dokumentacja
**Plik:** `docs/trading/funding_rate_arbitrage_paper_test_guide.md`

---

## 🚀 Uruchomienie

```bash
./scripts/test_funding_arbitrage_paper.sh
```

Skrypt automatycznie:
1. Sprawdzi środowisko
2. Wyświetli parametry testu
3. Poprosi o potwierdzenie
4. Uruchomi strategię w trybie paper trading

---

## ⚙️ Parametry Testu

### Podstawowe
- **Strategia:** `funding_rate_arbitrage`
- **Tryb:** `paper` (wirtualne pieniądze)
- **Symbol:** `BTC-USD`
- **Kapitał:** $10,000
- **Interwał:** 1h (sprawdzanie co godzinę)
- **Limit czasu:** 24h
- **Max strata:** $500 (5% kapitału)

### Parametry Strategii (Konserwatywne)

```python
{
    'min_funding_rate': 0.02,      # 0.02% na 8h (wyższy próg)
    'target_funding_rate': 0.06,   # 0.06% na 8h
    'max_position_size': 30.0,     # 30% kapitału
    'min_holding_hours': 48,       # Minimum 48h (2-3 płatności)
    'use_real_funding_rate': True  # Rzeczywiste funding rates z dYdX
}
```

**Dlaczego konserwatywne?**
- Wyższy próg = mniej transakcji, ale bezpieczniejsze
- Mniejszy rozmiar pozycji = mniejsze ryzyko
- Dłuższe trzymanie = więcej płatności funding

---

## 🔌 Integracja z dYdX API

### Rzeczywiste Funding Rates

Strategia **automatycznie** pobiera rzeczywiste funding rates z dYdX:

```python
# W strategii:
ticker_data = self.dydx_collector.get_ticker(symbol)
next_funding_rate = ticker_data.get('next_funding_rate', None)
funding_rate_percent = float(next_funding_rate) * 100
```

**Endpoint dYdX:**
- `GET /v4/perpetualMarkets`
- Zwraca `nextFundingRate` dla każdego rynku
- **Publiczne API** - nie wymaga kluczy

### Test Połączenia

```bash
python -c "
from src.collectors.exchange.dydx_collector import DydxCollector
collector = DydxCollector(testnet=False)
ticker = collector.get_ticker('BTC-USD')
print(f'Funding rate: {ticker[\"next_funding_rate\"]*100:.4f}%')
"
```

**Wynik:** `Funding rate: 0.0010%` (aktualny funding rate dla BTC-USD)

---

## 📊 Oczekiwane Zachowanie

### Gdy Funding Rate > 0.02%

1. **Otwarcie Pozycji:**
   - Strategia generuje sygnał BUY
   - Bot otwiera pozycję SHORT na kontrakcie wieczystym
   - Pozycja jest hedged (w paper trading symulowane)

2. **Otrzymywanie Płatności:**
   - Co 8h otrzymujesz płatność z funding rate
   - Płatności są śledzone w bazie danych

3. **Zamknięcie Pozycji:**
   - Gdy funding rate spadnie < 0.01% (50% minimum)
   - Gdy funding rate stanie się ujemny
   - Po min. 48h jeśli funding rate się pogorszył
   - Przy dużym odchyleniu ceny (>10%)

### Gdy Funding Rate < 0.02%

- Strategia **nie generuje sygnałów**
- Bot czeka na lepsze warunki
- Monitoruje funding rate co godzinę

---

## 📈 Monitorowanie

### Podczas Testu

Bot wyświetla w czasie rzeczywistym:
```
📊 PODSUMOWANIE SESJI
─────────────────────────────────────────
Konto: funding_arbitrage_test
Kapitał: $10,000.00 → $10,125.00 (+1.25%)
Transakcje: 1
Win Rate: 100%

Otwarte pozycje: 1
  BTC-USD SHORT: 0.1 BTC @ $50,000
  Funding rate: 0.03% na 8h
  Otrzymane płatności: $125.00
```

### Po Zakończeniu

```bash
# Ostatnie transakcje
sqlite3 data/paper_trading.db \
  "SELECT * FROM paper_trades ORDER BY created_at DESC LIMIT 10;"

# Status konta
sqlite3 data/paper_trading.db \
  "SELECT name, current_balance, total_trades, win_rate, roi FROM paper_accounts;"
```

---

## ⚠️ Ważne Uwagi

### 1. Aktualny Funding Rate

**Aktualny funding rate dla BTC-USD:** ~0.0010% (0.01%)

**To oznacza:**
- Strategia z `min_funding_rate=0.02%` **nie wygeneruje sygnałów** przy obecnym funding rate
- Musisz poczekać na wyższy funding rate (np. podczas bull market)
- Lub obniżyć `min_funding_rate` do 0.005% (0.5% rocznie)

### 2. Rekomendacja

Dla pierwszego testu z obecnym funding rate (0.0010%):

```bash
# Zmień parametry w run_paper_trading_enhanced.py:
'min_funding_rate': 0.005,  # 0.005% na 8h (niższy próg)
```

Lub poczekaj na wyższy funding rate (zwykle podczas bull market).

### 3. Paper Trading

- ✅ **Bezpieczne** - nie używa prawdziwych pieniędzy
- ✅ **Realistyczne** - używa rzeczywistych cen i funding rates
- ✅ **Idealne do testowania** - możesz eksperymentować bez ryzyka

---

## 🔧 Dostosowanie Parametrów

### Dla Niższego Funding Rate

Jeśli aktualny funding rate jest niski (< 0.02%), możesz:

1. **Obniżyć próg:**
   ```python
   'min_funding_rate': 0.005,  # 0.005% na 8h
   ```

2. **Zwiększyć rozmiar pozycji:**
   ```python
   'max_position_size': 50.0,  # 50% kapitału
   ```

3. **Skrócić czas trzymania:**
   ```python
   'min_holding_hours': 24,  # 24h zamiast 48h
   ```

### Dla Wyższego Funding Rate

Jeśli funding rate jest wysoki (> 0.05%), możesz:

1. **Zwiększyć próg:**
   ```python
   'min_funding_rate': 0.03,  # 0.03% na 8h
   ```

2. **Zwiększyć rozmiar pozycji:**
   ```python
   'max_position_size': 50.0,  # 50% kapitału
   ```

---

## 📝 Następne Kroki

### Po Pierwszym Teście

1. **Analiza Wyników**
   - Sprawdź czy strategia generowała transakcje
   - Oceń jakość sygnałów
   - Sprawdź czy funding rates były pobierane poprawnie

2. **Optymalizacja**
   - Dostosuj parametry na podstawie wyników
   - Testuj różne wartości `min_funding_rate`
   - Testuj różne `max_position_size`

3. **Rozszerzenie**
   - Dodaj więcej symboli (ETH-USD, SOL-USD)
   - Zwiększ limit czasu
   - Testuj dłuższe okresy

4. **Produkcja** (po wielu testach)
   - Gdy strategia działa stabilnie w paper trading
   - Rozważ użycie w trybie real (wymaga API keys)

---

## ✅ Podsumowanie

**Gotowe do użycia:**
- ✅ Skrypt testowy przygotowany
- ✅ Strategia zintegrowana z dYdX API
- ✅ Rzeczywiste funding rates działają
- ✅ Tryb paper trading (bezpieczny)
- ✅ Konserwatywne parametry dla pierwszego testu

**Uruchomienie:**
```bash
./scripts/test_funding_arbitrage_paper.sh
```

**Uwaga:** Przy obecnym funding rate (0.0010%) strategia może nie generować sygnałów. Rozważ obniżenie `min_funding_rate` do 0.005% lub poczekaj na wyższy funding rate.

