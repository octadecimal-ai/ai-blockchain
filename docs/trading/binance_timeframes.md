# Binance Timeframes - Dostępne Interwały

## 📊 Dostępne Timeframes OHLCV

Binance oferuje następujące interwały dla danych OHLCV:

### Krótkie interwały (scalping, day trading):
- **1m** - 1 minuta ⚡
- **3m** - 3 minuty
- **5m** - 5 minut
- **15m** - 15 minut
- **30m** - 30 minut

### Średnie interwały (swing trading):
- **1h** - 1 godzina (domyślny)
- **2h** - 2 godziny
- **4h** - 4 godziny
- **6h** - 6 godzin
- **8h** - 8 godzin
- **12h** - 12 godzin

### Długie interwały (position trading):
- **1d** - 1 dzień
- **3d** - 3 dni
- **1w** - 1 tydzień
- **1M** - 1 miesiąc

## ⚠️ Ograniczenia

### ❌ Brak danych OHLCV co sekundę
Binance **NIE oferuje** danych OHLCV z interwałem 1 sekundy. Najmniejszy dostępny interwał to **1 minuta**.

### 💡 Dla danych co sekundę potrzebne są:
1. **Tick Data (transakcje)** - dostępne przez:
   - WebSocket API (real-time)
   - REST API `/api/v3/trades` (ostatnie transakcje)
   - REST API `/api/v3/aggTrades` (agregowane transakcje)

2. **Agregacja Tick Data do OHLCV**:
   ```python
   # Przykład agregacji tick data do 1s OHLCV
   ticks = fetch_trades(symbol="BTC/USDC", limit=1000)
   ohlcv_1s = ticks.resample('1s').agg({
       'price': ['first', 'max', 'min', 'last'],
       'amount': 'sum'
   })
   ```

## 🔧 Użycie w Projekcie

### Zmiana timeframe w BTCUSDCDataLoader:

```python
from src.database.btcusdc_loader import BTCUSDCDataLoader
from datetime import datetime, timezone

# Dla 1 minuty
loader_1m = BTCUSDCDataLoader(timeframe="1m")
loader_1m.load_historical_data(start_date=datetime(2024, 1, 1, tzinfo=timezone.utc))

# Dla 5 minut
loader_5m = BTCUSDCDataLoader(timeframe="5m")
loader_5m.load_historical_data(start_date=datetime(2024, 1, 1, tzinfo=timezone.utc))

# Dla 15 minut
loader_15m = BTCUSDCDataLoader(timeframe="15m")
loader_15m.load_historical_data(start_date=datetime(2024, 1, 1, tzinfo=timezone.utc))
```

### Pobieranie danych z różnych timeframes:

```python
from src.collectors.exchange.binance_collector import BinanceCollector
from datetime import datetime, timezone

collector = BinanceCollector()

# 1 minuta
df_1m = collector.fetch_historical(
    symbol="BTC/USDC",
    timeframe="1m",
    start_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 12, 17, tzinfo=timezone.utc)
)

# 5 minut
df_5m = collector.fetch_historical(
    symbol="BTC/USDC",
    timeframe="5m",
    start_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 12, 17, tzinfo=timezone.utc)
)
```

## 📈 Zalecenia

### Dla Scalping (bardzo krótkie pozycje):
- **1m** - maksymalna szczegółowość
- **3m** - kompromis między szczegółowością a szumem

### Dla Day Trading:
- **5m** - dobre dla intraday
- **15m** - mniej szumu, nadal szczegółowe

### Dla Swing Trading:
- **1h** - domyślny, dobry balans
- **4h** - mniej sygnałów, wyższa jakość

### Dla Position Trading:
- **1d** - długoterminowe trendy
- **1w** - bardzo długoterminowe

## 🗄️ Przechowywanie w Bazie

Wszystkie timeframes są przechowywane w tej samej tabeli `ohlcv` z kolumną `timeframe`:

```sql
SELECT * FROM ohlcv 
WHERE exchange = 'binance' 
  AND symbol = 'BTC/USDC' 
  AND timeframe = '1m'
ORDER BY timestamp DESC;
```

## 📚 Dokumentacja

- [Binance API - Kline/Candlestick Data](https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data)
- [ccxt Binance Documentation](https://docs.ccxt.com/#/README?id=binance)

