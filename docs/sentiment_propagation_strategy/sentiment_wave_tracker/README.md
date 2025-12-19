# 🌊 Sentiment Wave Tracker

System do śledzenia propagacji sentymentu kryptowalutowego między regionami świata.

## Koncepcja

Informacje o kryptowalutach rozprzestrzeniają się z opóźnieniem między regionami:
- **US/GB** zazwyczaj reagują pierwsze (główne źródła newsów EN)
- **Europa (DE)** opóźniona o ~2h
- **Azja (JP, KR)** opóźniona o ~3-4h
- **Chiny (CN)** opóźnione o ~6h (inna strefa czasowa + filtrowanie)

**Wykrycie tego opóźnienia może dać przewagę tradingową** - reagując na zmianę sentymentu w US przed propagacją do Azji.

## Moduły

### 1. `gdelt_collector.py`
Kolektor danych z GDELT (Global Database of Events, Language, and Tone):
- Monitoruje media z całego świata w 65+ językach
- Darmowy, bez klucza API
- Dostarcza tone/sentiment artykułów

```python
from gdelt_collector import GDELTCollector

collector = GDELTCollector()

# Pobierz artykuły o Bitcoin
df_articles = collector.fetch_articles(
    query="bitcoin OR cryptocurrency",
    days_back=7,
    max_records=250
)

# Pobierz timeline sentymentu dla wielu krajów
df_multi = collector.fetch_multi_country_timeseries(
    query="bitcoin",
    countries=["US", "CN", "JP", "KR", "DE", "GB"],
    days_back=14
)
```

### 2. `sentiment_propagation_analyzer.py`
Analizator propagacji sentymentu:
- Cross-correlation do wykrywania lag-ów między regionami
- Identyfikacja "lidera" (region który reaguje pierwszy)
- Wykrywanie "fal" sentymentu

```python
from sentiment_propagation_analyzer import SentimentPropagationAnalyzer

analyzer = SentimentPropagationAnalyzer(
    time_resolution_hours=1.0,
    max_lag_hours=24
)

# Oblicz macierz lag-ów
lag_matrix = analyzer.compute_lag_matrix(df_multi)

# Znajdź lidera
leader, avg_lead = analyzer.find_leader_region(lag_matrix)

# Wykryj fale sentymentu
waves = analyzer.detect_sentiment_waves(df_multi)
```

### 3. `sentiment_wave_tracker.py`
Główny tracker integrujący wszystko:
- Pobieranie danych z GDELT
- Analiza propagacji
- Korelacja z cenami BTC
- Zapis do bazy danych

```python
from sentiment_wave_tracker import SentimentWaveTracker

tracker = SentimentWaveTracker()

results = tracker.run_full_analysis(
    query="bitcoin",
    countries=["US", "CN", "JP", "KR", "DE", "GB"],
    days_back=7
)

tracker.print_report(results)
```

## Integracja z Twoim projektem

### Struktura katalogów

```
src/
├── collectors/
│   ├── exchange/
│   │   ├── binance_collector.py
│   │   ├── dydx_collector.py
│   │   └── cryptodatadownload_collector.py
│   └── sentiment/           # ← NOWY FOLDER
│       ├── __init__.py
│       ├── gdelt_collector.py
│       ├── sentiment_propagation_analyzer.py
│       └── sentiment_wave_tracker.py
├── database/
│   ├── manager.py
│   └── models.py
└── strategies/
    └── base_strategy.py
```

### Krok 1: Skopiuj pliki

```bash
mkdir -p src/collectors/sentiment
cp gdelt_collector.py src/collectors/sentiment/
cp sentiment_propagation_analyzer.py src/collectors/sentiment/
cp sentiment_wave_tracker.py src/collectors/sentiment/
touch src/collectors/sentiment/__init__.py
```

### Krok 2: Dodaj do `__init__.py`

```python
# src/collectors/sentiment/__init__.py
from .gdelt_collector import GDELTCollector
from .sentiment_propagation_analyzer import SentimentPropagationAnalyzer
from .sentiment_wave_tracker import SentimentWaveTracker

__all__ = [
    'GDELTCollector',
    'SentimentPropagationAnalyzer', 
    'SentimentWaveTracker'
]
```

### Krok 3: Rozszerz model SentimentScore (opcjonalnie)

W `models.py` możesz dodać nowe pola:

```python
class SentimentScore(Base):
    __tablename__ = 'sentiment_scores'
    
    # ... istniejące pola ...
    
    # Nowe pola dla propagacji
    source_country = Column(String(10), nullable=True)  # Kod kraju źródła
    propagation_lag = Column(Float, nullable=True)       # Lag względem US (w godzinach)
    wave_id = Column(String(50), nullable=True)          # ID fali (jeśli część fali)
```

### Krok 4: Użycie w strategii

```python
# W under_human_strategy.py lub nowej strategii

from src.collectors.sentiment import SentimentWaveTracker

class SentimentWaveStrategy(BaseStrategy):
    name = "SentimentWave"
    description = "Strategia oparta na propagacji sentymentu"
    
    def __init__(self, config=None):
        super().__init__(config)
        self.tracker = SentimentWaveTracker()
    
    def analyze(self, df, symbol="BTC-USD"):
        # Pobierz aktualny sentyment
        results = self.tracker.run_full_analysis(
            query="bitcoin",
            days_back=3
        )
        
        # Sprawdź czy jest aktywna fala
        signals = results.get("summary", {}).get("trading_signals", [])
        
        if signals:
            latest_signal = signals[0]
            if latest_signal["type"] == "bullish":
                return TradingSignal(
                    signal_type=SignalType.BUY,
                    symbol=symbol,
                    confidence=latest_signal["strength"] * 10,
                    price=df["close"].iloc[-1],
                    reason=latest_signal["message"],
                    strategy=self.name
                )
        
        return None
```

## Wyniki Demo

Z syntetycznych danych (realistyczna symulacja):

```
👑 LIDER: US
   Średnio wyprzedza inne regiony o: 3.8h

📊 TOP LAG-I:
   US → CN: -6.0h (r=0.936)
   US → KR: -4.0h (r=0.980)
   US → JP: -3.0h (r=0.978)
   US → DE: -2.0h (r=0.988)

🌊 WYKRYTE FALE: 29
```

## Wizualizacje

System generuje:
- `sentiment_timeseries.png` - porównanie sentymentu między krajami
- `lag_heatmap.png` - macierz opóźnień
- `wave_propagation.png` - wizualizacja propagacji fali

## Ograniczenia GDELT

- Dane dla niektórych krajów (CN, JP) mogą być ograniczone
- Timeline API czasami zwraca puste odpowiedzi
- Fallback method (agregacja artykułów) jest wolniejszy

### Alternatywne źródła danych:
- **NewsAPI** (płatny) - lepsza jakość
- **Kaggle datasets** - dane historyczne
- **Twitter/X API** - realtime ale drogi
- **Własne scrapery** - najbardziej elastyczne

## Zależności

```bash
pip install pandas numpy scipy requests loguru matplotlib pyarrow
```

## Autor

Wygenerowano przez Claude dla projektu AI Blockchain Trading.
