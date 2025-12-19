# Przewodnik po Backtestingu

## 📊 Wprowadzenie

Backtesting pozwala przetestować strategię tradingową na danych historycznych **bez ryzyka** i **szybko** (rok danych w ~10 sekund). To idealne narzędzie do:

- Optymalizacji parametrów strategii
- Porównywania różnych strategii
- Testowania przed użyciem prawdziwych pieniędzy
- Analizy wydajności na różnych okresach

## 🚀 Szybki Start

### Podstawowe użycie:

```bash
# Test strategii scalping na ostatnich 30 dniach
python scripts/backtest.py --strategy=scalping_strategy --symbol=BTC-USD --days=30

# Test strategii breakout na konkretnym okresie
python scripts/backtest.py --strategy=piotrek_breakout_strategy --symbol=BTC-USD \
  --start=2024-01-01 --end=2024-12-01

# Przez skrypt trade.sh
./scripts/trade.sh --mode=backtest --strategy=scalping_strategy --days=90
```

## 📋 Parametry

### Podstawowe:

- `--strategy=NAZWA` - Strategia do testowania (`piotrek_breakout_strategy`, `scalping_strategy`)
- `--symbol=SYMBOL` - Symbol pary (np. `BTC-USD`, `ETH-USD`)
- `--timeframe=TIMEFRAME` - Timeframe (1m, 5m, 1h, 1d). Domyślnie z strategii

### Okres testowania:

- `--days=N` - Liczba dni wstecz (np. `--days=30` dla ostatniego miesiąca)
- `--start=DATA` - Data początkowa (YYYY-MM-DD lub `30d` dla 30 dni temu)
- `--end=DATA` - Data końcowa (YYYY-MM-DD, domyślnie: teraz)

### Parametry backtestingu:

- `--balance=KWOTA` - Początkowy kapitał (domyślnie: 10000)
- `--position-size=PROCENT` - % kapitału na pozycję (domyślnie: 10%)
- `--slippage=PROCENT` - Slippage w % (domyślnie: 0.1%)
- `--leverage=LICZBA` - Dźwignia (domyślnie: 1.0 = brak)

### Parametry strategii:

- `--param KEY=VALUE` - Parametr strategii (można użyć wielokrotnie)
  - Przykład: `--param min_confidence=5.0 --param rsi_oversold=30`

### Inne:

- `--verbose, -v` - Szczegółowe logi

## 📊 Wyniki Backtestingu

Backtesting zwraca szczegółowe statystyki:

### 💰 Finanse:
- Początkowy i końcowy kapitał
- Całkowity PnL i zwrot (%)
- Opłaty transakcyjne

### 📈 Transakcje:
- Liczba wszystkich transakcji
- Win rate (% zyskownych)
- Liczba zyskownych/stratnych transakcji

### 💵 Zyski/Straty:
- Całkowity zysk i strata
- Średni zysk/strata per transakcja
- Najlepsza i najgorsza transakcja
- Profit Factor (zysk / strata)

### 📉 Ryzyko:
- Max Drawdown (%)
- Sharpe Ratio
- Max kolejne zyski/straty

### ⏱️ Czas:
- Średni czas trzymania pozycji

## 💡 Przykłady Użycia

### 1. Szybki test scalping (30 dni):
```bash
python scripts/backtest.py \
  --strategy=scalping_strategy \
  --symbol=BTC-USD \
  --days=30
```

### 2. Test z własnymi parametrami:
```bash
python scripts/backtest.py \
  --strategy=scalping_strategy \
  --symbol=BTC-USD \
  --days=90 \
  --param min_confidence=3.0 \
  --param rsi_oversold=30 \
  --param rsi_overbought=70
```

### 3. Test na konkretnym okresie:
```bash
python scripts/backtest.py \
  --strategy=piotrek_breakout_strategy \
  --symbol=BTC-USD \
  --start=2024-06-01 \
  --end=2024-09-01
```

### 4. Test z większym kapitałem i dźwignią:
```bash
python scripts/backtest.py \
  --strategy=scalping_strategy \
  --symbol=BTC-USD \
  --days=60 \
  --balance=50000 \
  --leverage=2.0 \
  --position-size=15
```

### 5. Przez trade.sh:
```bash
./scripts/trade.sh \
  --mode=backtest \
  --strategy=scalping_strategy \
  --days=90 \
  --verbose
```

## 🎯 Optymalizacja Parametrów

Backtesting jest idealny do optymalizacji parametrów. Przykład:

```bash
# Test 1: Domyślne parametry
python scripts/backtest.py --strategy=scalping_strategy --symbol=BTC-USD --days=90

# Test 2: Niższy próg confidence
python scripts/backtest.py --strategy=scalping_strategy --symbol=BTC-USD --days=90 \
  --param min_confidence=3.0

# Test 3: Wyższy próg confidence
python scripts/backtest.py --strategy=scalping_strategy --symbol=BTC-USD --days=90 \
  --param min_confidence=6.0

# Porównaj wyniki i wybierz najlepsze parametry
```

## ⚡ Wydajność

Backtesting jest zoptymalizowany pod kątem szybkości:
- **Rok danych (1h timeframe)**: ~10 sekund
- **Miesiąc danych (1min timeframe)**: ~5-10 sekund
- **Rok danych (1min timeframe)**: ~30-60 sekund

Czas zależy od:
- Liczby świec (timeframe)
- Złożoności strategii
- Liczby transakcji

## ⚠️ Ograniczenia

1. **Look-ahead bias**: Backtesting używa danych historycznych, więc nie ma "przyszłości"
2. **Slippage**: Symulowany slippage może różnić się od rzeczywistego
3. **Liquidity**: Nie uwzględnia problemów z płynnością
4. **Emocje**: Brak emocji i paniki (co może być zaletą)

## 📝 Wskazówki

1. **Testuj na różnych okresach** - strategia może działać dobrze w trendzie, ale źle w konsolidacji
2. **Używaj realistycznych parametrów** - slippage, opłaty, dźwignia
3. **Porównuj strategie** - testuj różne strategie na tych samych danych
4. **Optymalizuj stopniowo** - zmieniaj jeden parametr na raz
5. **Sprawdzaj max drawdown** - nawet zyskowna strategia może mieć duże drawdowny

## 🔗 Zobacz też

- [Przewodnik po strategiach](../trading/dydx_strategies_research.md)
- [Przewodnik po trade.sh](../setup/trade_script_guide.md)
- [Przewodnik po logach](../trading/logs_summary_guide.md)

