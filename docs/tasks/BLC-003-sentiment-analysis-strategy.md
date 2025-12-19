## 📋 Opis

Ten PR wprowadza kompleksowy system analizy sentimentu z wykorzystaniem LLM i GDELT - platformę do zbierania, analizy i wykorzystywania sentimentu rynkowego z mediów z całego świata w strategiach tradingowych.

## ✨ Główne Funkcjonalności

### 🤖 LLM Sentiment Analyzer
- ✅ **LLMSentimentAnalyzer** - analiza sentimentu używająca Large Language Models:
  - Obsługa modeli Claude (Haiku, Sonnet, Opus)
  - Analiza w 15+ językach (EN, PL, ZH, JA, KO, DE, FR, ES, IT, RU, AR, PT, NL, SG)
  - Kontekst kulturowy i slang dla różnych języków
  - Obliczanie kosztów zapytań (tracking tokenów i kosztów)
  - Zapis wyników do bazy danych
  - Prompty dostosowane do języka
  - Analiza FUD i FOMO levels
  - Market impact assessment
  - Key topics extraction

### 📰 GDELT Collector
- ✅ **GDELTCollector** - kolektor danych z GDELT (Global Database of Events, Language, and Tone):
  - Pobieranie artykułów z mediów z całego świata (65+ języków)
  - Filtrowanie po kraju/języku źródła
  - Agregacja tone/sentiment w oknach czasowych
  - Geolokalizacja źródeł
  - Cache'owanie wyników
  - Obsługa wielu zapytań równolegle
  - Bez klucza API (w pełni darmowy)

### 🌊 Sentiment Propagation Analyzer
- ✅ **SentimentPropagationAnalyzer** - analiza propagacji sentimentu między regionami:
  - Wykrywanie lag-ów między regionami (cross-correlation)
  - Identyfikacja kierunku propagacji (US → EU → Asia)
  - Wykrywanie "fal" sentimentu propagujących się globalnie
  - Analiza korelacji z cenami BTC
  - Timezone-aware analysis
  - Region-specific configurations

### 📊 Sentiment Wave Tracker
- ✅ **SentimentWaveTracker** - śledzenie fal sentimentu:
  - Pełna analiza propagacji między regionami
  - Wykrywanie aktywnych fal sentimentu
  - Korelacja z cenami kryptowalut
  - Cache'owanie wyników analizy
  - Integracja z bazą danych (LLM i GDELT)
  - Wizualizacja propagacji (heatmaps, time series)

### 🌍 Timezone Aware Analyzer
- ✅ **TimezoneAwareAnalyzer** - analiza z uwzględnieniem stref czasowych:
  - Konfiguracja regionów (US, EU, Asia, etc.)
  - Analiza aktywności w różnych strefach czasowych
  - Wykrywanie lag-ów z uwzględnieniem timezone
  - Region-specific activity patterns
  - Multi-region correlation analysis

### 📈 Sentiment Propagation Strategy
- ✅ **SentimentPropagationStrategy** - strategia tradingowa oparta na propagacji sentimentu:
  - Monitorowanie sentimentu z regionu lidera (zazwyczaj US)
  - Wykrywanie "fal" sentimentu propagujących się między regionami
  - Generowanie sygnałów BUY/SELL na podstawie wykrytych fal
  - Korelacja sentimentu z cenami BTC
  - Konfigurowalne parametry (min_wave_strength, min_confidence)
  - Integracja z paper trading engine
  - Stop Loss / Take Profit
  - Backtesting support

### 🔄 Daemony do Zbierania Danych
- ✅ **LLM Sentiment Daemon** - automatyczne zbieranie danych sentimentu z LLM:
  - Okresowe pobieranie danych z różnych regionów
  - Automatyczna analiza używając LLM
  - Zapis do bazy danych
  - Obsługa błędów i retry logic
  - Logowanie wszystkich operacji
  
- ✅ **GDELT Sentiment Daemon** - automatyczne zbieranie danych z GDELT:
  - Okresowe pobieranie artykułów z mediów
  - Agregacja sentimentu po regionach
  - Zapis do bazy danych
  - Cache'owanie dla wydajności

### 💾 Baza Danych
- ✅ **Modele SQLAlchemy** - kompletne modele dla sentimentu:
  - `llm_sentiment_analysis` - wyniki analizy LLM:
    - Symbol, region, language
    - Model LLM, tokeny, koszty
    - Score, confidence, FUD, FOMO
    - Market impact, key topics
    - Reasoning
  - `gdelt_sentiment` - dane z GDELT:
    - Artykuły z mediów
    - Tone/sentiment scores
    - Geolokalizacja
    - Timestamps
  - `web_search` - wyniki wyszukiwania (Tavily)
  - `prompt_response` - odpowiedzi LLM (dla debugowania)

- ✅ **Migracje bazy danych:**
  - `03-create-llm-sentiment-analysis.sql` - tabela LLM sentiment
  - `04-add-prompt-response-to-llm-sentiment.sql` - prompt/response tracking
  - `05-add-tavily-to-llm-sentiment.sql` - integracja Tavily
  - `06-create-gdelt-sentiment.sql` - tabela GDELT sentiment
  - `07-rename-tavily-to-web-search.sql` - refaktoryzacja nazewnictwa

### 📚 Prompty i Konfiguracja
- ✅ **Prompty sentimentu** - szablony w 15+ językach:
  - `prompts/sentiment/en.txt` - angielski (bazowy)
  - `prompts/sentiment/pl.txt` - polski
  - `prompts/sentiment/zh.txt` - chiński
  - `prompts/sentiment/ja.txt` - japoński
  - `prompts/sentiment/ko.txt` - koreański
  - I wiele innych...
  
- ✅ **Tavily Queries** - zapytania wyszukiwania w różnych językach:
  - `docs/tavily_queries/` - zapytania dla różnych regionów
  - `prompts/tavily_queries/` - prompty dla Tavily API

## 🧪 Testy

### Testy Jednostkowe
- ✅ Testy LLM Sentiment Analyzer
- ✅ Testy GDELT Collector
- ✅ Testy Sentiment Propagation Analyzer
- ✅ Testy Sentiment Wave Tracker

### Testy Integracyjne
- ✅ Integracja z bazą danych
- ✅ Integracja z TradingBot
- ✅ Testy z rzeczywistymi danymi z API
- ✅ Testy propagacji między regionami

## 📚 Dokumentacja

### Setup Guides
- ✅ **LLM Sentiment Values** - dokumentacja wartości zwracanych przez LLM
- ✅ **Google CSE Setup** - konfiguracja Google Custom Search Engine
- ✅ **Tavily Queries** - dokumentacja zapytań Tavily

### Dokumentacja Strategii
- ✅ **Sentiment Propagation Strategy** - przewodnik strategii propagacji
- ✅ **Sentiment Wave Tracker** - dokumentacja tracker'a fal
- ✅ **Data Updater Daemon Management** - zarządzanie daemonami

### Skrypty
- ✅ `scripts/llm_sentiment_daemon.py` - daemon LLM sentiment
- ✅ `scripts/gdelt_sentiment_daemon.py` - daemon GDELT sentiment
- ✅ `scripts/start_llm_sentiment_daemon.sh` - uruchomienie LLM daemon
- ✅ `scripts/start_gdelt_sentiment_daemon.sh` - uruchomienie GDELT daemon
- ✅ `scripts/check_llm_sentiment_data.py` - sprawdzanie danych LLM
- ✅ `scripts/check_gdelt_sentiment_data.py` - sprawdzanie danych GDELT
- ✅ `scripts/run_sentiment_propagation_strategy.sh` - uruchomienie strategii

## 🔧 Konfiguracja

### Nowe Pliki Konfiguracyjne
- `src/collectors/sentiment/llm_sentiment_analyzer.py` - analizator LLM
- `src/collectors/sentiment/gdelt_collector.py` - kolektor GDELT
- `src/collectors/sentiment/sentiment_propagation_analyzer.py` - analizator propagacji
- `src/collectors/sentiment/sentiment_wave_tracker.py` - tracker fal
- `src/collectors/sentiment/timezone_aware_analyzer.py` - analizator timezone-aware
- `src/trading/strategies/sentiment_propagation_strategy.py` - strategia tradingowa
- `prompts/sentiment/` - prompty w różnych językach
- `docs/tavily_queries/` - zapytania Tavily

### Struktura Projektu
```
ai-blockchain/
├── src/collectors/sentiment/
│   ├── llm_sentiment_analyzer.py      # ✅ LLM Sentiment Analyzer
│   ├── gdelt_collector.py             # ✅ GDELT Collector
│   ├── sentiment_propagation_analyzer.py  # ✅ Propagation Analyzer
│   ├── sentiment_wave_tracker.py      # ✅ Wave Tracker
│   ├── timezone_aware_analyzer.py     # ✅ Timezone Aware Analyzer
│   └── __init__.py                    # ✅ Eksport modułów
├── src/trading/strategies/
│   └── sentiment_propagation_strategy.py  # ✅ Strategia tradingowa
├── src/database/migrations/
│   ├── 03-create-llm-sentiment-analysis.sql
│   ├── 04-add-prompt-response-to-llm-sentiment.sql
│   ├── 05-add-tavily-to-llm-sentiment.sql
│   ├── 06-create-gdelt-sentiment.sql
│   └── 07-rename-tavily-to-web-search.sql
├── scripts/
│   ├── llm_sentiment_daemon.py        # ✅ Daemon LLM
│   ├── gdelt_sentiment_daemon.py     # ✅ Daemon GDELT
│   └── run_sentiment_propagation_strategy.sh
├── prompts/sentiment/                 # ✅ Prompty w 15+ językach
├── docs/tavily_queries/               # ✅ Zapytania Tavily
└── data/sentiment_waves/              # ✅ Cache fal sentimentu
```

## 🐛 Naprawy i Ulepszenia

### Code Review Fixes
- ✅ Obsługa wielu języków z kontekstem kulturowym
- ✅ Tracking kosztów LLM (tokeny, koszty w PLN)
- ✅ Cache'owanie wyników dla wydajności
- ✅ Retry logic dla API calls
- ✅ Obsługa błędów i edge cases
- ✅ Timezone-aware operations
- ✅ Bulk operations dla bazy danych

### Kompatybilność
- ✅ SQLite compatibility (development)
- ✅ PostgreSQL compatibility (production)
- ✅ TimescaleDB support (hypertables)
- ✅ Session management
- ✅ Multi-region support

## 📊 Statystyki

- **20+ plików zmienionych/dodanych**
- **4,000+ wierszy dodanych**
- **15+ języków obsługiwanych**
- **65+ języków GDELT**
- **7 migracji bazy danych**
- **2 daemony do zbierania danych**

## 🚀 Jak Przetestować

### 1. Konfiguracja API
```bash
# Ustaw klucze API w .env
ANTHROPIC_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here  # opcjonalnie
```

### 2. Uruchomienie daemonów
```bash
# LLM Sentiment Daemon
./scripts/start_llm_sentiment_daemon.sh

# GDELT Sentiment Daemon
./scripts/start_gdelt_sentiment_daemon.sh
```

### 3. Sprawdzenie danych
```bash
# Sprawdź dane LLM
python scripts/check_llm_sentiment_data.py

# Sprawdź dane GDELT
python scripts/check_gdelt_sentiment_data.py
```

### 4. Uruchomienie strategii
```bash
# Strategia propagacji sentimentu
./scripts/run_sentiment_propagation_strategy.sh
```

### 5. Przykładowe użycie
```python
from src.collectors.sentiment import LLMSentimentAnalyzer, GDELTCollector
from src.collectors.sentiment import SentimentWaveTracker
from src.trading.strategies.sentiment_propagation_strategy import SentimentPropagationStrategy

# LLM Sentiment Analyzer
llm_analyzer = LLMSentimentAnalyzer(
    model="claude-3-5-haiku-20241022",
    save_to_db=True
)

# Analiza sentimentu
result = llm_analyzer.analyze_sentiment(
    texts=["Bitcoin price surges to new all-time high"],
    region="US",
    language="en"
)
print(f"Score: {result['score']}, Confidence: {result['confidence']}")

# GDELT Collector
gdelt = GDELTCollector()
articles = gdelt.fetch_articles(
    query="bitcoin OR cryptocurrency",
    days_back=7
)

# Sentiment Wave Tracker
tracker = SentimentWaveTracker(use_database=True)
results = tracker.run_full_analysis(
    query="bitcoin OR cryptocurrency",
    countries=["US", "CN", "JP", "KR", "DE", "GB"],
    days_back=7,
    symbol="BTC/USDC"
)

# Strategia tradingowa
strategy = SentimentPropagationStrategy(
    config={
        "query": "bitcoin OR cryptocurrency",
        "countries": ["US", "CN", "JP", "KR", "DE", "GB"],
        "min_wave_strength": 0.5,
        "min_confidence": 6.0
    }
)
```

## ✅ Checklist

- [x] LLM Sentiment Analyzer z obsługą wielu języków
- [x] GDELT Collector z geolokalizacją
- [x] Sentiment Propagation Analyzer
- [x] Sentiment Wave Tracker
- [x] Timezone Aware Analyzer
- [x] Sentiment Propagation Strategy
- [x] Daemony do zbierania danych
- [x] Migracje bazy danych
- [x] Prompty w 15+ językach
- [x] Dokumentacja kompletna
- [x] Testy jednostkowe i integracyjne
- [x] Integracja z TradingBot
- [x] Integracja z paper trading

## 🔗 Powiązane

- Issue: #BLC-003
- Branch: `feature/BLC-003-sentiment-analysis-strategy`
- Base: `feature/BLC-002-paper-trading-dydx`

## 📝 Uwagi

- LLM Sentiment Analyzer wymaga `ANTHROPIC_API_KEY`
- GDELT jest w pełni darmowy (bez klucza API)
- Tavily API opcjonalne (dla wyszukiwania newsów)
- Wszystkie dane zapisywane do bazy danych
- Daemony uruchamiane jako background services
- Strategia wymaga danych z co najmniej 2 regionów
- Propagacja sentimentu działa najlepiej z danymi z 6+ regionów
- Koszty LLM są trackowane i zapisywane w PLN

---

**Autor:** @piotradamczyk  
**Data:** 2025-12-19

