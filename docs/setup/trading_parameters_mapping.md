# Mapowanie Parametrów Tradingowych z Rozmowy na Skrypt

## 📋 Parametry z Rozmowy vs. Parametry Skryptu

### 1. **Wartość pozycji = 1 BTC**

**Z rozmowy:**
> "wartość pozycji = 1 BTC, dźwignia wynika z tego, ile masz hajsu, w sumie jest nieistotna"

**Jak to ustawić w skrypcie:**

Obecnie skrypt używa procentu kapitału (`position_size_percent`), ale możemy obliczyć wymaganą dźwignię dla 1 BTC:

```bash
# Przykład: Jeśli chcesz pozycję o wartości 1 BTC przy cenie ~$93,000
# Wartość pozycji = 1 BTC × $93,000 = $93,000
# Jeśli masz $10,000 kapitału:
# Wymagana dźwignia = $93,000 / $10,000 = 9.3x

# Uruchomienie:
./scripts/trade.sh \
  --balance=10000 \
  --leverage=10 \
  --symbols=BTC-USD
```

**Uwaga:** Obecna implementacja oblicza rozmiar pozycji jako procent kapitału. Aby mieć dokładnie 1 BTC, trzeba:
- Ustawić odpowiedni `balance` i `leverage`
- Lub zmodyfikować strategię aby używała stałego rozmiaru pozycji (1 BTC)

**Rekomendacja:** Dodać parametr `--position-size=BTC:1` do skryptu.

---

### 2. **Dopuszczalna strata: 300-1000 USD, zazwyczaj 500 USD**

**Z rozmowy:**
> "dopuszczalna strata: 300 - 1000 USD, zazwyczaj 500, zależnie od tego, jak wygląda zachowanie ceny"

**Jak to ustawić w skrypcie:**

```bash
# Standardowa strata (500 USD)
./scripts/trade.sh --max-loss=500

# Konserwatywna (300 USD)
./scripts/trade.sh --max-loss=300

# Agresywna (1000 USD)
./scripts/trade.sh --max-loss=1000
```

**Dodatkowo w strategii:**
- Stop Loss powinien być ustawiony tak, aby maksymalna strata na pozycji nie przekraczała 500 USD
- Jeśli pozycja = 1 BTC @ $93,000, to stop loss powinien być około $500 poniżej ceny wejścia

---

### 3. **Oczekiwany zysk: 500-2000 USD**

**Z rozmowy:**
> "oczekiwany zysk: 500-2000 USD, w zależności od tego, jak obiecująco się to zachowuje"

**Jak to ustawić w strategii:**

Obecnie strategia używa `risk_reward_ratio` (domyślnie 2.0). Dla pozycji 1 BTC:

```python
# W konfiguracji strategii (w bazie danych):
{
  "risk_reward_ratio": 2.0,  # Dla 500 USD ryzyka = 1000 USD zysku
  "min_profit_target": 500,  # Minimalny zysk w USD
  "max_profit_target": 2000  # Maksymalny zysk w USD
}
```

**Obliczenie Take Profit:**
- Jeśli stop loss = $500 poniżej ceny wejścia
- Take profit = $500 × 2.0 = $1000 powyżej ceny wejścia
- To daje zysk około $1000 USD (w zakresie 500-2000)

---

### 4. **RSI >70 (spadki) lub <30 (wzrosty)**

**Z rozmowy:**
> "generalnie staram się wykonywać ruchy, gdy wskaźnik RSI jest >70 (będzie spadać) lub < 30 (będzie rosnąć)"
> "więc idealnie jest gdy jest gwałtowny ruch w jakąś stronę, RSI przebija ten pułap i wtedy wchodzę w przeciwnym kierunku"

**Status:** RSI jest obliczany w `indicators.py`, ale **nie jest jeszcze używany** w `PiotrekBreakoutStrategy`.

**Wymagane zmiany:**
1. Dodać obliczanie RSI w strategii
2. Dodać warunek: RSI >70 dla SHORT, RSI <30 dla LONG
3. Dodać warunek: gwałtowny ruch + RSI przebija pułap

**Przykładowa konfiguracja:**
```python
{
  "use_rsi": True,
  "rsi_period": 14,
  "rsi_oversold": 30,  # Wejście LONG gdy RSI < 30
  "rsi_overbought": 70,  # Wejście SHORT gdy RSI > 70
  "rsi_momentum_threshold": 5.0  # Gwałtowny ruch = zmiana RSI > 5 punktów
}
```

---

### 5. **Częstotliwość sprawdzania: 1 minuta lub 30 sekund**

**Z rozmowy:**
> "jak często próby? pewnie im częściej tym lepiej; raz na minutę będzie chyba wystarczająco; no, może na 30 s? wchodzenie poniżej 10-15 sekund zaczyna być i tak zbędne"

**Jak to ustawić w skrypcie:**

```bash
# Raz na minutę (zalecane)
./scripts/trade.sh --interval=1min

# Co 30 sekund (agresywne)
./scripts/trade.sh --interval=30sek

# NIE używaj poniżej 15 sekund (nieefektywne)
# ./scripts/trade.sh --interval=10sek  # ❌ NIE ZALECANE
```

**Domyślna wartość:** `5min` (300 sekund) - można zmienić na `1min` lub `30sek`.

---

### 6. **Slippage (poślizg)**

**Z rozmowy:**
> "do operacji zamknięcia pozycji należy doliczyć tzw. "slippage", czyli stratę wynikającą z tego, że jak chcesz w danej chwili sprzedać po jakiejś cenie, to nie znaczy, że ktoś to dokładnie wtedy i za tyle kupi"
> "więc zazwyczaj parę procent z potencjalnego zysku odpada na taki "poślizg""

**Status:** Slippage **nie jest jeszcze uwzględniony** w implementacji.

**Wymagane zmiany:**
1. Dodać parametr `slippage_percent` (domyślnie 0.5-1.0%)
2. Odejmować slippage od zysku przy zamykaniu pozycji
3. Uwzględniać slippage w obliczeniach take profit

**Przykładowa konfiguracja:**
```python
{
  "slippage_percent": 0.75,  # 0.75% slippage
  "account_for_slippage": True
}
```

**Obliczenie:**
- Potencjalny zysk: $1000
- Slippage: $1000 × 0.75% = $7.50
- Rzeczywisty zysk: $1000 - $7.50 = $992.50

---

## 🎯 Kompletny Przykład Uruchomienia

### Scenariusz: Trading zgodny z rozmową

```bash
./scripts/trade.sh \
  --strategy=piotrek_breakout_strategy \
  --mode=paper \
  --balance=10000 \
  --leverage=10 \
  --symbols=BTC-USD \
  --interval=1min \
  --max-loss=500 \
  --time-limit=4h \
  --account=piotrek_rsi_strategy
```

**Wyjaśnienie parametrów:**
- `--balance=10000`: Kapitał początkowy $10,000
- `--leverage=10`: Dźwignia 10x (pozwala na pozycję ~$100,000 = ~1 BTC @ $100k)
- `--interval=1min`: Sprawdzanie co minutę
- `--max-loss=500`: Maksymalna strata $500
- `--time-limit=4h`: Sesja 4 godziny

---

## 📊 Konfiguracja Strategii w Bazie Danych

Aby strategia działała zgodnie z rozmową, należy zaktualizować konfigurację w bazie:

```sql
UPDATE strategies 
SET configuration = '{
  "breakout_threshold": 1.0,
  "consolidation_threshold": 0.5,
  "consolidation_candles": 3,
  "lookback_period": 20,
  "min_confidence": 6,
  "risk_reward_ratio": 2.0,
  "use_rsi": true,
  "rsi_period": 14,
  "rsi_oversold": 30,
  "rsi_overbought": 70,
  "rsi_momentum_threshold": 5.0,
  "position_size_btc": 1.0,
  "max_loss_usd": 500,
  "min_profit_target_usd": 500,
  "max_profit_target_usd": 2000,
  "slippage_percent": 0.75,
  "account_for_slippage": true
}'
WHERE name = 'piotrek_breakout_strategy';
```

---

## ⚠️ Brakujące Funkcjonalności

### 1. **RSI w Strategii**
- ✅ RSI jest obliczany w `indicators.py`
- ❌ Nie jest używany w `PiotrekBreakoutStrategy`
- **Wymagane:** Dodać logikę RSI do strategii

### 2. **Stały Rozmiar Pozycji (1 BTC)**
- ✅ Obecnie: rozmiar = procent kapitału
- ❌ Brak: opcja "wartość pozycji = 1 BTC"
- **Wymagane:** Dodać parametr `--position-size=BTC:1`

### 3. **Slippage**
- ❌ Nie uwzględniony w obliczeniach
- **Wymagane:** Dodać slippage do zamykania pozycji

### 4. **SHORT Pozycje (RSI >70)**
- ✅ Strategia obsługuje tylko LONG
- ❌ Brak: logika SHORT dla RSI >70
- **Wymagane:** Dodać obsługę SHORT

---

## 🔧 Rekomendowane Następne Kroki

1. **Dodać RSI do strategii:**
   - Obliczać RSI w `analyze()`
   - Dodawać warunek: RSI <30 dla LONG, RSI >70 dla SHORT
   - Wykrywać gwałtowne ruchy RSI

2. **Dodać parametr pozycji:**
   - `--position-size=BTC:1` lub `--position-value=93000`
   - Automatyczne obliczanie wymaganej dźwigni

3. **Dodać slippage:**
   - Parametr `slippage_percent` w konfiguracji
   - Odejmowanie od zysku przy zamykaniu

4. **Dodać SHORT:**
   - Logika SHORT dla RSI >70
   - Obsługa w `_handle_sell_signal()`

---

## 📝 Podsumowanie Mapowania

| Parametr z Rozmowy | Parametr Skryptu | Status |
|-------------------|------------------|--------|
| Wartość pozycji = 1 BTC | `--leverage` + `--balance` | ⚠️ Wymaga obliczeń |
| Dopuszczalna strata: 500 USD | `--max-loss=500` | ✅ Gotowe |
| Oczekiwany zysk: 500-2000 USD | `risk_reward_ratio` w strategii | ✅ Gotowe |
| RSI >70 / <30 | Brak w strategii | ❌ Do dodania |
| Częstotliwość: 1min/30sek | `--interval=1min` | ✅ Gotowe |
| Slippage 0.5-1% | Brak | ❌ Do dodania |

---

*Dokument utworzony: 2024-12-10*
*Na podstawie rozmowy o strategii tradingowej*

