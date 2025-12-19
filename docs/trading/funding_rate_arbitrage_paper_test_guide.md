# Dokumentacja: Test Funding Rate Arbitrage na dYdX (Paper Trading)

## Data: 2025-12-11

## Skrypt Testowy

**Plik:** `scripts/test_funding_arbitrage_paper.sh`

Skrypt shell do testowania strategii Funding Rate Arbitrage na rzeczywistym serwisie dYdX w trybie **paper trading** (wirtualne pieniądze).

---

## Użycie

```bash
./scripts/test_funding_arbitrage_paper.sh
```

Skrypt automatycznie:
1. Sprawdza środowisko (venv, baza danych)
2. Ustawia optymalne parametry dla pierwszego testu
3. Uruchamia strategię w trybie paper trading
4. Wyświetla wyniki

---

## Parametry Testu

### Podstawowe
- **Strategia:** `funding_rate_arbitrage`
- **Tryb:** `paper` (wirtualne pieniądze)
- **Symbol:** `BTC-USD` (jeden symbol na początek)
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
- Wyższy `min_funding_rate` (0.02% zamiast 0.01%) = mniej transakcji, ale bezpieczniejsze
- Mniejszy `max_position_size` (30% zamiast 50%) = mniejsze ryzyko
- Dłuższy `min_holding_hours` (48h zamiast 24h) = więcej płatności funding

---

## Co Robi Skrypt

### 1. Sprawdzenie Środowiska
```bash
✓ Sprawdza czy jesteśmy w katalogu projektu
✓ Sprawdza czy venv jest aktywne (aktywuje jeśli potrzeba)
✓ Sprawdza czy baza danych istnieje (tworzy jeśli potrzeba)
```

### 2. Wyświetlenie Parametrów
```bash
📊 Parametry testu:
  Strategia: funding_rate_arbitrage
  Tryb: paper (paper trading)
  Symbol: BTC-USD
  Kapitał: $10000
  Interwał: 1h
  Limit czasu: 24h
  Max strata: $500
```

### 3. Potwierdzenie
```bash
Czy chcesz uruchomić test? [y/N]:
```

### 4. Uruchomienie
```bash
./scripts/trade.sh \
    --strategy=funding_rate_arbitrage \
    --mode=paper \
    --symbols=BTC-USD \
    --balance=10000 \
    --interval=1h \
    --time-limit=24h \
    --max-loss=500 \
    --param min_funding_rate=0.02 \
    --param target_funding_rate=0.06 \
    --param max_position_size=30.0 \
    --param min_holding_hours=48 \
    --param use_real_funding_rate=true
```

---

## Integracja z dYdX API

### Rzeczywiste Funding Rates

Strategia została zaktualizowana aby używać **rzeczywistych funding rates** z dYdX API:

```python
# W strategii:
if self.use_real_funding_rate and self.dydx_collector:
    ticker_data = self.dydx_collector.get_ticker(symbol)
    next_funding_rate = ticker_data.get('next_funding_rate', None)
    # Konwertuj na procent
    funding_rate_percent = float(next_funding_rate) * 100
```

**Endpoint dYdX:**
- `GET /v4/perpetualMarkets/{market}`
- Zwraca `nextFundingRate` w formacie dziesiętnym (np. 0.0001 = 0.01%)

### Fallback do Symulacji

Jeśli nie uda się pobrać rzeczywistego funding rate, strategia używa symulacji na podstawie RSI (dla backtestingu).

---

## Monitorowanie Wyników

### Podczas Testu

Bot wyświetla w czasie rzeczywistym:
- Aktualny funding rate
- Otwarte pozycje
- PnL każdej pozycji
- Podsumowanie konta

### Po Zakończeniu

Sprawdź wyniki w bazie danych:

```bash
# Ostatnie transakcje
sqlite3 data/paper_trading.db \
  "SELECT * FROM paper_trades ORDER BY created_at DESC LIMIT 10;"

# Status konta
sqlite3 data/paper_trading.db \
  "SELECT name, current_balance, total_trades, win_rate, roi FROM paper_accounts;"

# Otwarte pozycje
sqlite3 data/paper_trading.db \
  "SELECT * FROM paper_positions WHERE status = 'open';"
```

---

## Przykładowe Wyniki

### Pozytywny Scenariusz

```
📊 PODSUMOWANIE SESJI
─────────────────────────────────────────
Konto: funding_arbitrage_test
Kapitał: $10,000.00 → $10,450.00 (+4.5%)
Transakcje: 3
Win Rate: 100%
PnL: +$450.00

Otwarte pozycje: 1
  BTC-USD SHORT: 0.1 BTC @ $50,000
  Funding rate: 0.05% na 8h
  Otrzymane płatności: $125.00
```

### Negatywny Scenariusz

```
📊 PODSUMOWANIE SESJI
─────────────────────────────────────────
Konto: funding_arbitrage_test
Kapitał: $10,000.00 → $9,850.00 (-1.5%)
Transakcje: 2
Win Rate: 50%
PnL: -$150.00

Powód straty:
- Funding rate spadł poniżej minimum
- Opłaty transakcyjne
```

---

## Optymalizacja Parametrów

### Dla Większej Liczby Transakcji

```bash
--param min_funding_rate=0.01      # Niższy próg
--param max_position_size=50.0     # Większy rozmiar
--param min_holding_hours=24       # Krótsze trzymanie
```

### Dla Większego Bezpieczeństwa

```bash
--param min_funding_rate=0.03       # Wyższy próg
--param max_position_size=20.0      # Mniejszy rozmiar
--param min_holding_hours=72       # Dłuższe trzymanie
```

---

## Uwagi

### ⚠️ Ważne

1. **Paper Trading = Wirtualne Pieniądze**
   - Nie używa prawdziwych środków
   - Idealne do testowania strategii

2. **Rzeczywiste Funding Rates**
   - Strategia pobiera rzeczywiste funding rates z dYdX API
   - Wymaga połączenia z internetem
   - API dYdX jest publiczne (nie wymaga kluczy)

3. **Konserwatywne Parametry**
   - Parametry są ustawione konserwatywnie dla pierwszego testu
   - Po pozytywnych wynikach można je zoptymalizować

4. **Limit Straty**
   - Bot zatrzyma się przy stracie $500 (5% kapitału)
   - Chroni przed dużymi stratami podczas testów

---

## Następne Kroki

Po pierwszym teście:

1. **Analiza Wyników**
   - Sprawdź czy strategia generuje transakcje
   - Oceń jakość sygnałów
   - Sprawdź czy funding rates są pobierane poprawnie

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

## Troubleshooting

### Problem: Brak transakcji

**Możliwe przyczyny:**
- Funding rate jest zbyt niski (< min_funding_rate)
- Błąd połączenia z dYdX API
- Nieprawidłowe parametry

**Rozwiązanie:**
```bash
# Sprawdź aktualny funding rate
python -c "
from src.collectors.exchange.dydx_collector import DydxCollector
collector = DydxCollector(testnet=False)
ticker = collector.get_ticker('BTC-USD')
print(f'Funding rate: {ticker[\"next_funding_rate\"]*100:.4f}%')
"
```

### Problem: Błąd połączenia z API

**Rozwiązanie:**
- Sprawdź połączenie internetowe
- Sprawdź czy dYdX API jest dostępne
- Sprawdź logi w `logs/trading_*.log`

---

## Podsumowanie

✅ **Skrypt gotowy do użycia**

- Automatyczna konfiguracja środowiska
- Optymalne parametry dla pierwszego testu
- Integracja z rzeczywistymi funding rates z dYdX
- Tryb paper trading (bezpieczny)
- Monitoring wyników w czasie rzeczywistym

**Uruchomienie:**
```bash
./scripts/test_funding_arbitrage_paper.sh
```

**Czas testu:** 24 godziny (można przerwać wcześniej Ctrl+C)

**Oczekiwane rezultaty:**
- Strategia powinna generować transakcje gdy funding rate > 0.02%
- Pozycje powinny być trzymane minimum 48h
- Płatności funding powinny być śledzone

