# Automatyczna Optymalizacja Strategii Tradingowej

## Wprowadzenie

System automatycznej optymalizacji strategii (`strategy_auto_optimizer.py`) został stworzony do iteracyjnego testowania, poprawiania i optymalizacji strategii tradingowych aż do osiągnięcia założonych wyników.

## Jak to działa?

### 1. Testy Jednostkowe

Utworzono testy jednostkowe dla strategii breakout (`tests/unit/test_piotrek_strategy.py`):
- Test inicjalizacji strategii
- Test wykrywania konsolidacji
- Test wykrywania breakoutów (LONG/SHORT)
- Test generowania sygnałów
- Test zamykania pozycji

### 2. Znajdowanie Okresu Testowego

Optymalizator automatycznie znajduje najlepszy okres do testowania strategii:
- Szuka okresów z wyraźnymi breakoutami
- Preferuje trendy wzrostowe (dla strategii breakout)
- Używa zapisanych danych CSV (np. z Binance)
- Minimalne okno: 500-1000 świec dla lepszych testów

### 3. Iteracyjna Optymalizacja

Proces składa się z następujących kroków:

```
ITERACJA:
1. Test strategii z obecnymi parametrami
2. Ocena wyników (Win Rate, Profit Factor, Zwrot)
3. Sprawdzenie kryteriów sukcesu
4. Jeśli NIE spełnia → Poprawa parametrów
5. Powtórz aż do sukcesu lub max iteracji
```

### 4. Automatyczna Poprawa Strategii

Optymalizator automatycznie poprawia parametry na podstawie wyników:

**Jeśli Win Rate niski:**
- ⬆️ Zwiększa `min_confidence`
- ⬆️ Zwiększa `breakout_threshold`

**Jeśli Profit Factor niski:**
- ⬆️ Zwiększa `risk_reward_ratio`
- ⬆️ Zwiększa `min_confidence`

**Jeśli brak transakcji:**
- ⬇️ Zmniejsza `min_confidence`
- ⬇️ Zmniejsza `breakout_threshold`

**Jeśli duża strata:**
- ⚠️ Drastyczne zmiany wszystkich parametrów
- ⬆️ Zwiększa `risk_reward_ratio`

### 5. Kryteria Sukcesu

Strategia jest uznana za sukces, gdy spełnia **wszystkie** kryteria:
- ✅ Win Rate >= docelowy (domyślnie 35%)
- ✅ Profit Factor >= docelowy (domyślnie 1.1)
- ✅ Zwrot >= docelowy (domyślnie 1.0%)
- ✅ Ma transakcje (total_trades > 0)
- ✅ Nie jest bankrutem (zwrot > -100%)

## Użycie

### Podstawowe użycie:

```bash
python scripts/strategy_auto_optimizer.py \
  --symbol=BTC/USDT \
  --target-win-rate=35.0 \
  --target-profit-factor=1.1 \
  --target-return=1.0 \
  --max-iterations=20 \
  --slippage=0.1 \
  --save
```

### Parametry:

- `--symbol`: Symbol pary (np. BTC/USDT)
- `--target-win-rate`: Docelowy Win Rate (%)
- `--target-profit-factor`: Docelowy Profit Factor
- `--target-return`: Docelowy zwrot (%)
- `--max-iterations`: Maksymalna liczba iteracji
- `--slippage`: Slippage w %
- `--save`: Zapisz wyniki do pliku JSON

## Poprawki Strategii

### 1. Lepszy Stop Loss

**Problem:** Stop loss był zbyt ciaski (2%), powodując przedwczesne zamykanie pozycji.

**Rozwiązanie:**
- Użycie ATR (Average True Range) do obliczania stop loss
- Minimalny margines zwiększony z 2% do 5%
- Stop loss = entry - (ATR * 1.5) lub min 5% margines

### 2. Filtr Trendu

**Problem:** Strategia generowała sygnały SHORT w trendzie wzrostowym (przeciwne do trendu).

**Rozwiązanie:**
- Dodano metodę `_detect_trend()` używającą SMA(50)
- LONG tylko w trendzie wzrostowym lub sideways
- SHORT tylko w trendzie spadkowym lub sideways

### 3. Większe Okno Testowe

**Problem:** Okno testowe było zbyt małe (150-200 świec), co dawało nieprecyzyjne wyniki.

**Rozwiązanie:**
- Zwiększono okno do 500-1000 świec
- Lepsze znalezienie okresów z breakoutami

## Wyniki Optymalizacji

### Obecny Status:

Strategia nadal wymaga dalszych poprawek. Obecne wyniki:
- Win Rate: ~11-20% (cel: 35%+)
- Profit Factor: ~0.04-0.17 (cel: 1.1+)
- Zwrot: -85% do -98% (cel: 1%+)

### Zidentyfikowane Problemy:

1. **Zbyt wiele fałszywych sygnałów** - strategia wchodzi w transakcje, które kończą się stratą
2. **Stop loss zbyt ciaski** - nawet po poprawkach (5%) może być za ciaski dla volatile rynku
3. **Brak filtrowania w trendzie** - strategia nie uwzględniała trendu (poprawione)
4. **Slippage** - 0.75% może być zbyt wysoki (zmniejszony do 0.1% w testach)

## Następne Kroki

### Krótkoterminowe:

1. ✅ Testy jednostkowe - **ZROBIONE**
2. ✅ System optymalizacji - **ZROBIONE**
3. ✅ Poprawa stop loss - **ZROBIONE**
4. ✅ Filtr trendu - **ZROBIONE**
5. ⏳ Dalsze testy i poprawki

### Długoterminowe:

1. **Dodanie więcej filtrów:**
   - Filtr wolumenu (tylko transakcje z wysokim wolumenem)
   - Filtr zmienności (tylko w okresach wysokiej zmienności)
   - Filtr czasu (unikanie okresów niskiej płynności)

2. **Poprawa logiki zamykania:**
   - Trailing stop loss
   - Częściowe zamykanie pozycji
   - Dynamiczne dostosowanie TP/SL

3. **Optymalizacja parametrów:**
   - Grid search zamiast prostych zmian
   - Machine learning do wyboru parametrów
   - Walidacja na out-of-sample danych

4. **Dodatkowe strategie:**
   - Mean reversion
   - Momentum trading
   - Arbitrage

## Pliki

- `scripts/strategy_auto_optimizer.py` - Główny skrypt optymalizacji
- `tests/unit/test_piotrek_strategy.py` - Testy jednostkowe strategii
- `data/optimization/strategy_optimization_results.json` - Zapisane wyniki

## Przykład Wyników

```json
{
  "timestamp": "2025-12-10T23:55:53.876307",
  "targets": {
    "win_rate": 35.0,
    "profit_factor": 1.1,
    "return": 1.0
  },
  "iterations": [
    {
      "iteration": 1,
      "params": {...},
      "result": {
        "total_return": -98.21,
        "win_rate": 13.16,
        "profit_factor": 0.10,
        "total_trades": 38
      },
      "is_successful": false
    }
  ]
}
```

## Uwagi

- Optymalizator działa iteracyjnie i może zająć dużo czasu (kilka minut do kilku godzin)
- Wyniki są zapisywane do `data/optimization/strategy_optimization_results.json`
- Strategia może wymagać wielu iteracji, aby osiągnąć sukces
- Niektóre strategie mogą nigdy nie osiągnąć założonych celów bez fundamentalnych zmian

