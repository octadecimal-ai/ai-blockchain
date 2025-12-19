# Interpretacja Wyników Backtestingu

## ⚠️ Ważne: Dlaczego strategie mogą być stratne?

### 1. **Okres testowania może być niekorzystny**

Strategie tradingowe **nie działają na wszystkich okresach**. Jeśli testujesz strategię na okresie spadkowym, nawet najlepsza strategia może być stratna.

**Przykład:**
- Strategia breakout działa dobrze w trendzie wzrostowym
- Jeśli testujesz na okresie spadkowym, strategia będzie stratna
- To **NIE oznacza**, że strategia jest zła - tylko że okres był niekorzystny

### 2. **Parametry mogą być nieoptymalne**

Domyślne parametry strategii mogą nie być optymalne dla danego okresu:
- Zbyt restrykcyjne progi (np. `min_confidence=5.0`) → za mało transakcji
- Zbyt luźne progi (np. `min_confidence=2.0`) → za dużo transakcji, większe ryzyko
- Nieodpowiednie wartości RSI (np. `rsi_oversold=25` może być za niskie)

### 3. **Slippage i opłaty**

Backtesting uwzględnia:
- **Slippage**: 0.1% (realistyczny dla dYdX)
- **Opłaty**: 0.05% taker fee
- **Łącznie**: ~0.15% kosztów per transakcja

Dla strategii z wieloma transakcjami, koszty mogą znacząco wpłynąć na wyniki.

### 4. **Win Rate vs Profit Factor**

Nawet strategia z niskim Win Rate może być zyskowna, jeśli:
- Średni zysk jest dużo większy niż średnia strata
- Profit Factor > 1.0

**Przykład:**
- Win Rate: 30% (tylko 30% transakcji zyskownych)
- Ale średni zysk: $100, średnia strata: $20
- Profit Factor: 3.0 → strategia jest zyskowna!

### 5. **Overfitting**

Jeśli optymalizujesz parametry na jednym okresie, mogą one nie działać na innych:
- Parametry zoptymalizowane na 30 dniach mogą nie działać na 90 dniach
- Zawsze testuj na **out-of-sample** danych

## 📊 Jak interpretować wyniki?

### ✅ Pozytywne sygnały:

1. **Profit Factor > 1.0** - zysk > strata
2. **Win Rate > 50%** - więcej zyskownych niż stratnych transakcji
3. **Sharpe Ratio > 1.0** - dobry stosunek zwrotu do ryzyka
4. **Max Drawdown < 20%** - akceptowalne ryzyko
5. **Stabilne wyniki** na różnych okresach

### ❌ Negatywne sygnały:

1. **Profit Factor < 1.0** - strata > zysk
2. **Win Rate < 30%** - za mało zyskownych transakcji
3. **Sharpe Ratio < 0** - negatywny stosunek zwrotu do ryzyka
4. **Max Drawdown > 50%** - zbyt wysokie ryzyko
5. **Brak transakcji** - parametry zbyt restrykcyjne

## 🔍 Co zrobić gdy wszystkie strategie są stratne?

### 1. **Sprawdź trend rynkowy**

```bash
# Sprawdź czy okres był wzrostowy czy spadkowy
python -c "
from datetime import datetime, timedelta
from src.collectors.exchange.dydx_collector import DydxCollector

collector = DydxCollector()
end_date = datetime.now()
start_date = end_date - timedelta(days=30)
df = collector.fetch_historical_candles('BTC-USD', '1h', start_date, end_date)
if not df.empty:
    first = float(df.iloc[0]['close'])
    last = float(df.iloc[-1]['close'])
    change = ((last - first) / first) * 100
    print(f'Zmiana ceny: {change:+.2f}%')
"
```

### 2. **Testuj na dłuższym okresie**

```bash
# Testuj na 90 lub 180 dniach
python scripts/backtest.py --strategy=piotrek_breakout_strategy --days=90
```

### 3. **Zmniejsz restrykcyjność parametrów**

```bash
# Niższy próg confidence = więcej transakcji
python scripts/backtest.py --strategy=scalping_strategy \
  --param min_confidence=2.0 \
  --param rsi_oversold=40 \
  --param rsi_overbought=60
```

### 4. **Użyj optymalizacji**

```bash
# Znajdź najlepsze parametry
python scripts/optimize_strategy.py \
  --strategy=scalping_strategy \
  --symbol=BTC-USD \
  --days=90 \
  --max-combinations=100
```

### 5. **Testuj różne symbole**

```bash
# Może strategia działa lepiej na ETH?
python scripts/backtest.py --strategy=scalping_strategy --symbol=ETH-USD --days=30
```

## 💡 Przykładowe interpretacje

### Scenariusz 1: Strategia z niskim Win Rate ale wysokim Profit Factor

```
Win Rate: 25%
Profit Factor: 2.5
Zwrot: +15%
```

**Interpretacja:** Strategia działa! Mimo niskiego Win Rate, średni zysk jest 2.5x większy niż średnia strata. To jest **dobra strategia**.

### Scenariusz 2: Strategia z wysokim Win Rate ale niskim Profit Factor

```
Win Rate: 70%
Profit Factor: 0.8
Zwrot: -10%
```

**Interpretacja:** Strategia jest stratna. Mimo wysokiego Win Rate, średnia strata jest większa niż średni zysk. To jest **zła strategia**.

### Scenariusz 3: Strategia bez transakcji

```
Transakcje: 0
Zwrot: 0%
```

**Interpretacja:** Parametry są zbyt restrykcyjne. Strategia nie generuje sygnałów. **Zmniejsz progi** (np. `min_confidence`, `rsi_oversold/overbought`).

## 🎯 Rekomendacje

1. **Zawsze testuj na różnych okresach** (30, 60, 90, 180 dni)
2. **Sprawdź trend rynkowy** przed interpretacją wyników
3. **Użyj optymalizacji** aby znaleźć najlepsze parametry
4. **Waliduj na out-of-sample** danych przed użyciem w produkcji
5. **Nie oczekuj zysków na każdym okresie** - to normalne, że strategie są stratne na niektórych okresach

## 🔗 Zobacz też

- [Przewodnik po backtestingu](./backtesting_guide.md)
- [Przewodnik po optymalizacji](./strategy_optimization_guide.md)
- [Przewodnik po strategiach](./dydx_strategies_research.md)

