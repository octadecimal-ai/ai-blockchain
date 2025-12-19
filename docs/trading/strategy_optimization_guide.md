# Przewodnik po Optymalizacji Strategii

## 📊 Wprowadzenie

Skrypt `optimize_strategy.py` pozwala automatycznie testować różne kombinacje parametrów strategii tradingowych, aby znaleźć optymalne ustawienia dla maksymalnego zysku.

## 🚀 Szybki Start

### Podstawowe użycie:

```bash
# Optymalizacja jednej strategii
python scripts/optimize_strategy.py --strategy=scalping_strategy --symbol=BTC-USD --days=30

# Optymalizacja obu strategii
python scripts/optimize_strategy.py --strategy=all --symbol=BTC-USD --days=30

# Z ograniczoną liczbą kombinacji (szybciej)
python scripts/optimize_strategy.py --strategy=scalping_strategy --symbol=BTC-USD --days=30 --max-combinations=50
```

## 📋 Parametry

### Podstawowe:

- `--strategy=NAZWA` - Strategia do optymalizacji:
  - `scalping_strategy` - Strategia scalping
  - `piotrek_breakout_strategy` - Strategia breakout
  - `all` - Obie strategie
- `--symbol=SYMBOL` - Symbol pary (np. `BTC-USD`, `ETH-USD`)
- `--days=N` - Liczba dni danych historycznych (domyślnie: 30)

### Optymalizacja:

- `--max-combinations=N` - Maksymalna liczba kombinacji do testowania (domyślnie: wszystkie)
  - **Uwaga**: Pełna optymalizacja może zająć dużo czasu!
  - Scalping: ~2000 kombinacji
  - Breakout: ~2000 kombinacji
- `--top-n=N` - Liczba najlepszych wyników do wyświetlenia (domyślnie: 10)
- `--position-size=PROCENT` - % kapitału na pozycję (domyślnie: 10%)

### Inne:

- `--save` - Zapisz wyniki do pliku JSON (`data/optimization/`)
- `--verbose, -v` - Szczegółowe logi

## 🔍 Testowane Parametry

### Scalping Strategy:

- `min_confidence`: [2.0, 3.0, 4.0, 5.0, 6.0]
- `rsi_oversold`: [20, 25, 30, 35, 40]
- `rsi_overbought`: [60, 65, 70, 75, 80]
- `atr_multiplier`: [1.0, 1.5, 2.0, 2.5]
- `min_volume_ratio`: [1.0, 1.2, 1.5, 2.0]

**Łącznie**: 5 × 5 × 5 × 4 × 4 = **2000 kombinacji**

### Piotrek Breakout Strategy:

- `min_confidence`: [3.0, 4.0, 5.0, 6.0, 7.0]
- `breakout_threshold`: [0.3, 0.5, 0.8, 1.0, 1.5]
- `consolidation_threshold`: [0.2, 0.3, 0.4, 0.5]
- `rsi_oversold`: [25, 30, 35, 40]
- `rsi_overbought`: [60, 65, 70, 75]

**Łącznie**: 5 × 5 × 4 × 4 × 4 = **1600 kombinacji**

## 💡 Przykłady Użycia

### 1. Szybki test (50 kombinacji):
```bash
python scripts/optimize_strategy.py \
  --strategy=scalping_strategy \
  --symbol=BTC-USD \
  --days=30 \
  --max-combinations=50 \
  --top-n=5
```

### 2. Pełna optymalizacja z zapisem:
```bash
python scripts/optimize_strategy.py \
  --strategy=all \
  --symbol=BTC-USD \
  --days=60 \
  --save \
  --top-n=20
```

### 3. Optymalizacja dla konkretnego symbolu:
```bash
python scripts/optimize_strategy.py \
  --strategy=piotrek_breakout_strategy \
  --symbol=ETH-USD \
  --days=90 \
  --max-combinations=100
```

## 📊 Interpretacja Wyników

### Top N Konfiguracji:

Dla każdej strategii wyświetlane są najlepsze konfiguracje posortowane po:
1. **Zwrot (%)** - główne kryterium
2. **Profit Factor** - zysk / strata
3. **Win Rate** - % zyskownych transakcji
4. **Max Drawdown** - maksymalna strata
5. **Sharpe Ratio** - stosunek zwrotu do ryzyka

### Statystyki:

- **Średni zwrot** - średnia ze wszystkich testów
- **Najlepszy/Najgorszy zwrot** - ekstremalne wartości
- **Średnia liczba transakcji** - ile transakcji generuje strategia
- **Średni Win Rate** - średni % zyskownych transakcji
- **Zyskownych konfiguracji** - ile % konfiguracji było zyskownych

## ⚠️ Ważne Uwagi

1. **Overfitting**: Najlepsze parametry na danych historycznych mogą nie działać w przyszłości
2. **Okres testowania**: Różne okresy mogą dawać różne wyniki
3. **Czas wykonania**: Pełna optymalizacja może zająć wiele godzin
4. **Walidacja**: Zawsze przetestuj najlepsze parametry na out-of-sample danych

## 📁 Zapisane Wyniki

Z flagą `--save`, wyniki są zapisywane do:
```
data/optimization/optimization_{strategy}_{timestamp}.json
```

Format JSON zawiera:
- Parametry każdej konfiguracji
- Wszystkie statystyki (zwrot, PnL, win rate, etc.)
- Timestamp testu

## 🎯 Najlepsze Praktyki

1. **Zacznij od małej liczby kombinacji** (`--max-combinations=50-100`)
2. **Testuj na różnych okresach** (30, 60, 90 dni)
3. **Sprawdź różne symbole** (BTC-USD, ETH-USD)
4. **Użyj `--save`** aby zachować wyniki
5. **Porównaj wyniki** między strategiami
6. **Waliduj na out-of-sample** danych przed użyciem w produkcji

## 🔗 Zobacz też

- [Przewodnik po backtestingu](./backtesting_guide.md)
- [Przewodnik po strategiach](./dydx_strategies_research.md)
- [Przewodnik po trade.sh](../setup/trade_script_guide.md)

