# Dostępność Danych Historycznych

## 📊 dYdX v4

**Najstarsza dostępna data:** Listopad 2023 (~2023-11-01)

**Dostępność:**
- ✅ Dane od listopada 2023 do teraz
- ❌ Brak danych z lat 2022 i wcześniejszych
- ❌ Brak danych z początku 2023

**Powód:** dYdX v4 został uruchomiony w 2023 roku, więc dane historyczne są dostępne tylko od momentu uruchomienia platformy.

## 📊 Binance

**Najstarsza dostępna data:** Wiele lat wstecz (co najmniej 2021)

**Dostępność:**
- ✅ Dane od wielu lat wstecz (2021, 2022, 2023, 2024+)
- ✅ Bardzo długa historia danych
- ✅ Idealne do backtestingu na długich okresach
- ✅ Dostępne przez API (BinanceCollector)

**API Key:**
- ❌ **NIE WYMAGANE** do pobierania danych historycznych (OHLCV, ticker)
- ✅ Wymagane tylko dla operacji prywatnych (trading, saldo, historia zamówień)
- ✅ BinanceCollector działa w trybie publicznym bez API keys

## 📊 CryptoDataDownload.com

**Najstarsza dostępna data:** Wiele lat wstecz (od 2017)

**Dostępność:**
- ✅ Darmowe dane historyczne w formacie CSV
- ✅ Dane z wielu giełd (Binance, Coinbase, Kraken, Bitstamp, Gemini, itp.)
- ✅ Dane OHLCV dla różnych timeframe'ów
- ✅ Bez rejestracji (dla większości danych)
- ✅ Standardowy format CSV
- ✅ Licencja: Creative Commons Attribution-NonCommercial-ShareAlike 4.0

**Źródło:** [CryptoDataDownload.com](https://www.cryptodatadownload.com/data/)

**Uwaga:** CryptoDataDownload.com jest dobrym źródłem danych historycznych, ale wymaga ręcznego pobierania plików CSV lub użycia web scraping. Binance API jest bardziej niezawodne dla programowego pobierania danych.

## 💡 Rekomendacje

### Dla backtestingu na dYdX:

1. **Użyj danych z dYdX** jeśli testujesz strategię specyficzną dla dYdX:
   - Dostępne: ~13 miesięcy danych (od listopada 2023)
   - Wystarczające dla większości testów

2. **Użyj Binance jako alternatywy** jeśli potrzebujesz:
   - Dłuższych okresów testowych (2+ lata)
   - Większej ilości danych historycznych
   - Testowania na różnych warunkach rynkowych

### Przykłady użycia:

```python
# dYdX - najstarsze dostępne dane
from src.collectors.exchange.dydx_collector import DydxCollector
from datetime import datetime, timedelta

collector = DydxCollector(testnet=False)
start = datetime(2023, 11, 1)  # Najstarsza dostępna data
end = datetime.now()

df = collector.fetch_historical_candles('BTC-USD', '1h', start, end)
```

```python
# Binance - dane z wielu lat wstecz
from src.collectors.exchange.binance_collector import BinanceCollector
from datetime import datetime

collector = BinanceCollector()
start = datetime(2021, 1, 1)  # Dane z 2021
end = datetime.now()

df = collector.fetch_historical('BTC/USDT', '1h', start, end)
```

## 🔄 Integracja z Backtestingiem

Backtesting engine obecnie używa tylko dYdX. Można go rozszerzyć o Binance:

```python
# W backtesting.py można dodać:
def fetch_historical_data(self, symbol, timeframe, start_date, end_date, source='dydx'):
    if source == 'binance':
        # Konwertuj symbol (BTC-USD -> BTC/USDT)
        binance_symbol = symbol.replace('-', '/').replace('USD', 'USDT')
        collector = BinanceCollector()
        df = collector.fetch_historical(binance_symbol, timeframe, start_date, end_date)
    else:
        # dYdX (domyślnie)
        df = self.dydx.fetch_historical_candles(...)
    return df
```

## 📝 Uwagi

1. **Różnice w symbolach:**
   - dYdX: `BTC-USD`
   - Binance: `BTC/USDT`

2. **Różnice w cenach:**
   - dYdX: kontrakty perpetual (może być różnica w cenie vs spot)
   - Binance: ceny spot

3. **Różnice w timeframe:**
   - Oba wspierają podobne timeframe'y, ale nazwy mogą się różnić

## 📁 Zapisane dane

Dane historyczne z Binance zostały zapisane w katalogu `data/backtest_periods/binance/`:

### Dane roczne (2020-2025):

- `BTCUSDT_2020_1h.csv` - dane z 2020 roku (8744 świec, +304.72%)
- `BTCUSDT_2021_1h.csv` - dane z 2021 roku (8725 świec, +62.75%)
- `BTCUSDT_2022_1h.csv` - dane z 2022 roku (8738 świec, -64.13%)
- `BTCUSDT_2023_1h.csv` - dane z 2023 roku (8737 świec, +156.12%)
- `BTCUSDT_2024_1h.csv` - dane z 2024 roku (8762 świec, +118.64%)
- `BTCUSDT_2025_1h.csv` - dane z 2025 roku (8256 świec, -0.97%, do 2025-12-10)

**Łącznie:** ~51,962 świec (6 lat danych)

Każdy plik ma odpowiadający plik metadanych w formacie JSON zawierający:
- Statystyki cenowe (początkowa, końcowa, max, min)
- Zmiana procentowa w roku
- Volatility
- Liczba świec
- Okres danych

## 🔗 Zobacz też

- [Przewodnik po backtestingu](./backtesting_guide.md)
- [Przewodnik po optymalizacji](./strategy_optimization_guide.md)

