# AI Blockchain - Inteligentna Analiza Rynku Kryptowalut

## 🎯 Cel Projektu
Platforma do zbierania, analizy i przewidywania rynku kryptowalut z wykorzystaniem AI/LLM.

## 📁 Struktura Projektu

```
ai-blockchain/
├── 📄 install.sh                    # Skrypt instalacyjny (automatyczna instalacja)
├── 📄 requirements.txt               # Zależności Python
├── 📄 docker-compose.yml             # Konfiguracja Docker (TimescaleDB, Redis)
├── 📄 README.md                      # Dokumentacja projektu
│
├── 📁 config/                        # Konfiguracja projektu
│   ├── settings.yaml                 # Główna konfiguracja (giełdy, wskaźniki, LLM)
│   └── env.example.txt               # Przykład zmiennych środowiskowych
│
├── 📁 data/                          # Dane projektu
│   ├── raw/                          # Surowe dane pobrane z API
│   ├── processed/                    # Dane po preprocessingu
│   └── models/                       # Wytrenowane modele ML
│
├── 📁 src/                           # Kod źródłowy
│   ├── __init__.py
│   │
│   ├── 📁 collectors/                # Kolektory danych
│   │   ├── exchange/                  # API giełd
│   │   │   ├── binance_collector.py   # ✅ Kolektor Binance
│   │   │   └── dydx_collector.py      # ✅ Kolektor dYdX (perpetual)
│   │   ├── onchain/                   # Dane on-chain (przygotowane)
│   │   └── sentiment/                 # Dane sentymentu (przygotowane)
│   │
│   ├── 📁 analysis/                  # Moduły analityczne
│   │   ├── technical/                 # Analiza techniczna
│   │   │   └── indicators.py          # ✅ Wskaźniki (RSI, MACD, Bollinger, etc.)
│   │   ├── fundamental/               # Analiza fundamentalna (przygotowane)
│   │   └── llm/                       # Analiza z użyciem LLM
│   │       └── market_analyzer.py     # ✅ Generowanie raportów AI
│   │
│   ├── 📁 models/                     # Modele predykcyjne
│   │   ├── lstm/                      # Modele LSTM (przygotowane)
│   │   ├── transformer/               # Modele Transformer (przygotowane)
│   │   └── ensemble/                 # Modele ensemble (przygotowane)
│   │
│   ├── 📁 database/                   # Zarządzanie bazą danych
│   │   ├── models.py                  # ✅ Modele SQLAlchemy (OHLCV, Signals, etc.)
│   │   └── manager.py                 # ✅ Manager bazy (TimescaleDB/SQLite)
│   │
│   ├── 📁 strategies/                 # Strategie handlowe
│   │   └── arbitrage.py               # ✅ Arbitraż Binance ↔ dYdX
│   │
│   ├── 📁 backtesting/               # Testowanie strategii (przygotowane)
│   └── 📁 utils/                      # Narzędzia pomocnicze (przygotowane)
│
├── 📁 notebooks/                      # Jupyter notebooks
│   └── 01_getting_started.ipynb       # ✅ Notebook startowy
│
├── 📁 prompts/                        # Prompty systemowe dla LLM (przygotowane)
│
├── 📁 docker/                         # Konfiguracja Docker
│   └── init-db/                       # Skrypty inicjalizacyjne bazy
│       └── 01-init-timescale.sql      # ✅ Inicjalizacja TimescaleDB
│
├── 📁 api/                            # REST API (przygotowane)
├── 📁 dashboard/                      # Frontend (przygotowane)
├── 📁 tests/                          # Testy (przygotowane)
│
└── 📁 .dev/                           # Skrypty deweloperskie
    ├── scripts/
    │   └── time.sh                    # ✅ Skrypt do pobierania czasu
    └── logs/
        └── cursor/                     # Logi rozmów z AI
```

### Legenda:
- ✅ = **Zaimplementowane** - kod gotowy do użycia
- 📁 = Katalog
- 📄 = Plik
- (przygotowane) = Struktura utworzona, kod do implementacji+

### Kluczowe pliki:

| Plik | Opis |
|------|------|
| `install.sh` | Automatyczna instalacja wszystkich komponentów |
| `src/collectors/exchange/binance_collector.py` | Pobieranie danych z Binance |
| `src/collectors/exchange/dydx_collector.py` | Pobieranie danych z dYdX (perpetual) |
| `src/analysis/technical/indicators.py` | Wskaźniki analizy technicznej |
| `src/analysis/llm/market_analyzer.py` | Generowanie raportów rynkowych z LLM |
| `src/database/manager.py` | Zarządzanie bazą danych (TimescaleDB/SQLite) |
| `src/strategies/arbitrage.py` | Skaner okazji arbitrażowych |
| `docker-compose.yml` | TimescaleDB + Redis + Adminer |

## 🚀 Szybki Start

### Instalacja (Automatyczna)

Najprostszy sposób - użyj skryptu instalacyjnego:

```bash
./install.sh
```

Skrypt automatycznie:
- ✅ Sprawdzi wymagania systemowe (Python >= 3.8)
- ✅ Utworzy/zaktualizuje virtual environment
- ✅ Zainstaluje wszystkie zależności z `requirements.txt`
- ✅ Sprawdzi czy pakiety są aktualne (pominie jeśli tak)
- ✅ Skonfiguruje katalogi projektu
- ✅ (Opcjonalnie) Uruchomi kontenery Docker

**Opcje:**
```bash
./install.sh --skip-docker    # Pomiń konfigurację Docker
./install.sh --skip-ml        # Pomiń pakiety ML (PyTorch, scikit-learn)
```

### Instalacja (Ręczna)

```bash
# 1. Utwórz virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Zainstaluj zależności
pip install --upgrade pip
pip install -r requirements.txt

# 3. (Opcjonalnie) Uruchom Docker
docker-compose up -d
```

## ✅ Status Implementacji

### Zaimplementowane (Gotowe do użycia)
- ✅ **Kolektory danych**: Binance, dYdX
- ✅ **Analiza techniczna**: RSI, MACD, Bollinger Bands, SMA/EMA, ATR, OBV, VWAP
- ✅ **Baza danych**: TimescaleDB/SQLite z modelami SQLAlchemy
- ✅ **Strategie**: Arbitraż Binance ↔ dYdX
- ✅ **LLM Integration**: Generowanie raportów rynkowych (Claude/GPT-4)
- ✅ **Docker**: TimescaleDB + Redis + Adminer
- ✅ **Instalacja**: Automatyczny skrypt `install.sh`

### W trakcie / Planowane
- 🔄 Modele predykcyjne (LSTM, Transformer)
- 🔄 Backtesting framework
- 🔄 Analiza sentymentu (Twitter, Reddit)
- 🔄 On-chain data collectors
- 🔄 REST API (FastAPI)
- 🔄 Dashboard (Plotly/Dash)

## 🚀 Fazy Rozwoju

### Faza 1: Fundament Danych (Tydzień 1-2)
- [ ] Konfiguracja środowiska Python
- [ ] Integracja z API Binance
- [ ] Pobieranie danych historycznych OHLCV
- [ ] Podstawowy preprocessing

### Faza 2: Analiza Techniczna (Tydzień 3-4)
- [ ] Implementacja wskaźników technicznych
- [ ] Wizualizacja danych
- [ ] Wykrywanie wzorców

### Faza 3: Modele Predykcyjne (Tydzień 5-8)
- [ ] Model LSTM do predykcji cen
- [ ] Backtesting
- [ ] Optymalizacja hiperparametrów

### Faza 4: Integracja LLM (Tydzień 9-12)
- [ ] Analiza sentymentu newsów
- [ ] Generowanie raportów rynkowych
- [ ] Multi-agent system do analizy

### Faza 5: Dashboard & Automatyzacja (Tydzień 13+)
- [ ] REST API
- [ ] Dashboard z wizualizacjami
- [ ] Alerty i notyfikacje

## 🛠️ Technologie

### Backend & Przetwarzanie Danych
- **Python 3.9+** - główny język (kompatybilne z 3.8-3.11)
- **pandas, numpy** - przetwarzanie danych
- **ccxt** - ujednolicone API giełd (100+ giełd)
- **ta** - wskaźniki analizy technicznej
- **SQLAlchemy** - ORM do baz danych

### Bazy Danych
- **TimescaleDB** (PostgreSQL) - baza danych szeregów czasowych
- **SQLite** - baza deweloperska
- **Redis** - cache i kolejki

### Machine Learning & AI
- **PyTorch** - modele deep learning (opcjonalnie)
- **scikit-learn** - klasyczne ML
- **LangChain** - integracja z LLM (Claude, GPT-4)
- **transformers** - modele NLP

### API & Frontend
- **FastAPI** - REST API
- **Plotly / Dash** - wizualizacje interaktywne
- **mplfinance** - wykresy świecowe

### DevOps
- **Docker & Docker Compose** - konteneryzacja
- **Alembic** - migracje bazy danych

## 📊 Źródła Danych

| Źródło | Typ | API | Status |
|--------|-----|-----|--------|
| **Binance** | OHLCV, orderbook, ticker | ccxt | ✅ Zaimplementowane |
| **dYdX** | Perpetual contracts, funding rates | REST API v4 | ✅ Zaimplementowane |
| CoinGecko | Metadane, rankingi | REST | 🔄 Planowane |
| Glassnode | On-chain metrics | REST | 🔄 Planowane |
| CryptoQuant | On-chain data | REST | 🔄 Planowane |
| Twitter/X | Sentiment analysis | API v2 | 🔄 Planowane |
| Reddit | Sentiment analysis | PRAW | 🔄 Planowane |

**Legenda:**
- ✅ Zaimplementowane - kod gotowy do użycia
- 🔄 Planowane - do implementacji

## 🔑 Kluczowe Metryki do Śledzenia

1. **Cenowe**: OHLCV, wolumen, kapitalizacja
2. **On-chain**: Active addresses, NVT, MVRV
3. **Sentiment**: Fear & Greed, social volume
4. **Macro**: DXY, S&P500 korelacja

## ⚠️ Disclaimer

Projekt służy celom edukacyjnym. Inwestowanie w kryptowaluty wiąże się z wysokim ryzykiem. 
Nie traktuj wyników modeli jako porady inwestycyjnej.

---
*Utworzono: 2025-12-09*

