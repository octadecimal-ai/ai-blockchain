# Przewodnik po Strategii Funding Rate Arbitrage

## Wprowadzenie

Strategia `FundingRateArbitrageStrategy` wykorzystuje mechanizm stóp finansowania (funding rates) kontraktów wieczystych (perpetual futures) do generowania zysków przy zerowym ryzyku rynkowym.

## Zasada Działania

### 1. Czym są Stopy Finansowania?

Stopy finansowania (funding rates) to mechanizm w kontraktach wieczystych, który utrzymuje cenę kontraktu blisko ceny spot poprzez okresowe płatności między traderami:

- **Dodatni funding rate**: Cena kontraktu > cena spot → Długie pozycje płacą krótkim
- **Ujemny funding rate**: Cena kontraktu < cena spot → Krótkie pozycje płacą długim

Płatności odbywają się zazwyczaj co 8 godzin (3 razy dziennie).

### 2. Jak Działa Arbitraż?

Strategia wykorzystuje dodatnie stopy finansowania do generowania zysków:

```
Pozycja Arbitrażowa (Market Neutral):
┌─────────────────────────────────────────┐
│ 1. Kupno aktywa na rynku SPOT           │ ← Hedging (zabezpieczenie)
│    Przykład: Kup 1 BTC @ $50,000       │
├─────────────────────────────────────────┤
│ 2. Sprzedaż (SHORT) kontraktu wieczystego│ ← Generuje dochód z funding rate
│    Przykład: Short 1 BTC perpetual      │
└─────────────────────────────────────────┘

Rezultat:
- Zmiana ceny BTC nie ma znaczenia (pozycje się równoważą)
- Co 8h otrzymujesz płatność z funding rate
- Zysk: ~0.01-0.10% co 8h = ~11-109% ROI rocznie
```

### 3. Dlaczego To Działa?

- **Zero ryzyko rynkowe**: Pozycja spot i short perp wzajemnie się hedgują
- **Pasywny dochód**: Otrzymujesz regularne płatności co 8h
- **Wysoki zwrot**: Przy funding rate 0.05% co 8h → ~55% ROI rocznie

## Implementacja w Systemie

### Parametry Strategii

```python
{
    'min_funding_rate': 0.01,          # Minimalna stopa do otwarcia pozycji (% na 8h)
    'target_funding_rate': 0.05,       # Docelowa stopa (wysoka atrakcyjność)
    'max_position_size': 50.0,         # Maksymalny rozmiar pozycji (% kapitału)
    'funding_interval_hours': 8,       # Interwał płatności
    'min_holding_hours': 24,           # Minimalny czas trzymania pozycji
    'use_spot_hedge': True,            # Czy hedgować na rynku spot
    'max_leverage': 2.0                # Maksymalna dźwignia
}
```

### Przykładowe Zwroty

| Funding Rate (8h) | Dzienny Zwrot | Roczny Zwrot (APR) |
|-------------------|---------------|-------------------|
| 0.01%             | 0.03%         | ~11%              |
| 0.03%             | 0.09%         | ~33%              |
| 0.05%             | 0.15%         | ~55%              |
| 0.10%             | 0.30%         | ~109%             |

*Uwaga: Zwroty zakładają stały funding rate, w rzeczywistości jest on zmienny*

## Algorytm Strategii

### Otwarcie Pozycji

```
1. Monitor funding rate co godzinę
2. Jeśli funding_rate >= min_funding_rate:
   a. Oblicz roczny zwrot
   b. Sprawdź zmienność rynku
   c. Oblicz confidence (0-10)
   d. Jeśli confidence >= 3.0:
      - Kup aktywo na rynku spot
      - Otwórz SHORT na kontrakcie wieczystym
      - Równy rozmiar obu pozycji
```

### Zamknięcie Pozycji

```
Zamknij pozycję gdy:
1. funding_rate < min_funding_rate * 0.5
   (funding rate spadł poniżej 50% minimum)

2. funding_rate < 0
   (funding rate stał się ujemny - teraz płacimy!)

3. holding_time >= min_holding_hours AND funding_rate < min_funding_rate
   (minął minimalny czas i funding rate się pogorszył)

4. price_deviation > 10%
   (duże odchylenie ceny - ryzyko likwidacji)
```

## Obliczanie Confidence

```python
confidence = 0

# Funding rate (0-5 punktów)
if funding_rate >= target_funding_rate:
    confidence += 5.0
elif funding_rate >= min_funding_rate:
    ratio = (funding_rate - min) / (target - min)
    confidence += 2.5 + (ratio * 2.5)

# Volatility (0-2 punkty) - preferuj niską zmienność
if volatility < 1.0%:
    confidence += 2.0
elif volatility < 2.0%:
    confidence += 1.0
elif volatility < 3.0%:
    confidence += 0.5

# Liquidity (0-3 punkty)
confidence += liquidity_score * 3.0

return min(10.0, confidence)
```

## Użycie

### Podstawowe

```python
from src.trading.strategies.funding_rate_arbitrage_strategy import FundingRateArbitrageStrategy

strategy = FundingRateArbitrageStrategy()
signal = strategy.analyze(df, "BTC-USD")

if signal:
    print(f"Otwórz pozycję arbitrażową:")
    print(f"  Funding rate: {signal.metadata['funding_rate']:.4f}%")
    print(f"  Roczny zwrot: {signal.metadata['annual_return']:.1f}%")
```

### Z Własną Konfiguracją

```python
strategy = FundingRateArbitrageStrategy({
    'min_funding_rate': 0.03,  # Wyższy próg (bardziej konserwatywne)
    'target_funding_rate': 0.08,
    'max_position_size': 30.0,  # Mniejszy rozmiar (bezpieczniejsze)
    'min_holding_hours': 48  # Dłuższe trzymanie
})
```

### Backtesting

```bash
python scripts/backtest_from_csv.py \
  --csv=data/backtest_periods/binance/BTCUSDT_2023_1h.csv \
  --strategy=funding_rate_arbitrage \
  --symbol=BTC/USDT \
  --balance=10000 \
  --param min_funding_rate=0.01
```

## Ryzyka i Ograniczenia

### 1. **Ryzyko Zmiany Funding Rate**
- **Problem**: Funding rate może się szybko zmienić
- **Rozwiązanie**: Monitoruj funding rate w czasie rzeczywistym, zamykaj pozycję gdy spadnie

### 2. **Ryzyko Likwidacji**
- **Problem**: Ekstremalne ruchy cenowe mogą spowodować likwidację pozycji short
- **Rozwiązanie**: Używaj niskiej dźwigni (≤2x), utrzymuj wystarczający margin

### 3. **Koszty Transakcyjne**
- **Problem**: Opłaty za otwarcie/zamknięcie pozycji mogą zjeść zyski
- **Rozwiązanie**: Otwieraj pozycje tylko przy wysokim funding rate, trzymaj dłużej

### 4. **Ryzyko Płynności**
- **Problem**: Brak płynności może utrudnić zamknięcie pozycji
- **Rozwiązanie**: Handluj tylko na płynnych parach (BTC, ETH)

### 5. **Różnice w Cenach Spot vs Perp**
- **Problem**: Ceny spot i perp mogą się różnić (basis risk)
- **Rozwiązanie**: Używaj tej samej giełdy dla obu pozycji

## Przykład Rzeczywisty

### Scenariusz 1: Wysoki Funding Rate

```
Data: 2024-01-15
Symbol: BTC-USD
Cena: $50,000
Funding Rate: 0.05% co 8h

Akcja:
1. Kup 1 BTC na rynku spot @ $50,000
2. Short 1 BTC perpetual @ $50,000
3. Kapitał użyty: $50,000

Wynik po 30 dniach:
- Płatności funding: 90 * 0.05% * $50,000 = $2,250
- Opłaty transakcyjne: ~$50
- Zysk netto: $2,200
- ROI: 4.4% w miesiąc, ~53% rocznie
```

### Scenariusz 2: Funding Rate Spada

```
Data: 2024-01-15
Symbol: BTC-USD
Funding Rate: 0.05% → 0.01% (po 7 dniach)

Akcja:
1. Otwórz pozycję przy 0.05%
2. Otrzymuj płatności przez 7 dni
3. Funding rate spada do 0.01%
4. Zamknij pozycję (nie opłaca się dalej)

Wynik:
- Płatności funding: 21 * 0.04% * $50,000 = $420
- Opłaty: ~$50
- Zysk: $370 w 7 dni
```

## Integracja z dYdX

### Pobieranie Funding Rate

```python
# W rzeczywistej implementacji:
import requests

def get_dydx_funding_rate(market: str = "BTC-USD"):
    url = f"https://indexer.dydx.trade/v4/perpetualMarkets/{market}"
    response = requests.get(url)
    data = response.json()
    
    # Funding rate jest zwracany jako część odpowiedzi
    funding_rate = float(data['markets'][market]['nextFundingRate'])
    
    return funding_rate * 100  # Konwersja na %
```

### Otwarcie Pozycji Arbitrażowej

```python
# 1. Kup na rynku spot (lub użyj istniejących holdings)
spot_order = exchange.create_market_buy_order('BTC/USDT', amount)

# 2. Otwórz SHORT na kontrakcie wieczystym
perp_order = exchange.create_market_sell_order('BTC-USD-PERP', amount)

# 3. Monitoruj funding payments
```

## Porównanie ze Standardowym Tradingiem

| Aspekt | Standard Trading | Funding Rate Arbitrage |
|--------|------------------|------------------------|
| Ryzyko rynkowe | 🔴 Wysokie | 🟢 Zerowe (hedged) |
| Zwrot | 🟡 Zmienny | 🟢 Stabilny |
| Kapitał | 🟡 Średni | 🔴 Wysoki (2x pozycja) |
| Złożoność | 🟢 Niska | 🟡 Średnia |
| Czas | 🔴 Aktywny | 🟢 Pasywny |
| Opłaty | 🟢 Niskie | 🟡 Średnie (2x transakcje) |

## Rekomendacje

### Dla Początkujących:
```python
{
    'min_funding_rate': 0.03,  # Ostrożny próg
    'max_position_size': 20.0,  # Mały rozmiar
    'min_holding_hours': 48,  # Długie trzymanie
    'max_leverage': 1.0  # Bez dźwigni
}
```

### Dla Zaawansowanych:
```python
{
    'min_funding_rate': 0.01,  # Agresywny próg
    'max_position_size': 50.0,  # Większy rozmiar
    'min_holding_hours': 24,  # Krótsze trzymanie
    'max_leverage': 2.0  # Z dźwignią
}
```

## Następne Kroki

1. ✅ **Zakończone:** Implementacja strategii
2. ⏳ **W toku:** Integracja z API dYdX dla rzeczywistych funding rates
3. 📋 **Do zrobienia:**
   - Testowanie na danych historycznych
   - Implementacja automatycznego hedgingu
   - Monitoring funding payments w czasie rzeczywistym
   - Dashboard do śledzenia performance

## Źródła

- https://blog.biqutex.com/funding-rate-arbitrage/
- https://airdropalert.com/blogs/funding-rate-arbitrage-farming/
- https://sharpe.ai/blog/funding-rate-arbitrage
- https://medium.com/quantland/a-funding-rate-arbitrage-strategy-prototype-for-individual-investor-6a34d657ce79

