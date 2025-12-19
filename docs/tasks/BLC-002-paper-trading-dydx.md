## 📋 Opis

Ten PR wprowadza kompleksowy system paper trading dla dYdX - platformę do symulacji handlu na giełdzie perpetual futures bez ryzyka utraty prawdziwych środków.

## ✨ Główne Funkcjonalności

### 💼 Paper Trading Engine
- ✅ **PaperTradingEngine** - kompletny silnik symulacji handlu:
  - Tworzenie i zarządzanie wirtualnymi kontami
  - Otwieranie i zamykanie pozycji (LONG/SHORT)
  - Obliczanie PnL (realized i unrealized)
  - Symulacja slippage (domyślnie 0.75%)
  - Stop Loss / Take Profit
  - Tracking pełnej historii transakcji
  - Statystyki konta (win rate, ROI, max drawdown)

### 🤖 Trading Bot
- ✅ **TradingBot** - automatyczny bot tradingowy:
  - Monitorowanie rynku w czasie rzeczywistym
  - Integracja ze strategiami tradingowymi
  - Automatyczne wykonywanie sygnałów
  - Zarządzanie pozycjami (SL/TP monitoring)
  - Graceful shutdown (obsługa sygnałów)
  - Konfigurowalny interwał sprawdzania
  - Logowanie wszystkich akcji

### 💾 Modele Bazy Danych
- ✅ **PaperAccount** - wirtualne konta:
  - Początkowy i aktualny kapitał
  - Dźwignia (leverage 1-20x)
  - Opłaty (maker/taker fees)
  - Statystyki (total trades, win rate, ROI, max drawdown)
  
- ✅ **PaperPosition** - otwarte pozycje:
  - Symbol, side (LONG/SHORT), size
  - Cena wejścia i aktualna
  - Stop Loss / Take Profit
  - Unrealized PnL
  - Powiązanie ze strategią
  
- ✅ **PaperOrder** - zlecenia:
  - Typ (MARKET, LIMIT, STOP_LOSS, TAKE_PROFIT)
  - Status (PENDING, FILLED, CANCELLED)
  - Cena i rozmiar
  
- ✅ **PaperTrade** - wykonane transakcje:
  - Pełna historia otwarcia/zamknięcia
  - Realized PnL
  - Opłaty i slippage
  - Powiązanie ze strategią

### 📊 Integracja ze Strategiami
- ✅ **BaseStrategy** - rozszerzona o integrację z paper trading:
  - Metoda `set_paper_trading_engine()` dla wszystkich strategii
  - Dostęp do otwartych pozycji w strategiach
  - Pobieranie aktualnych cen z dYdX
  - Tracking wyników transakcji
  
- ✅ **Wsparcie dla wszystkich strategii:**
  - PiotrekBreakoutStrategy
  - PromptStrategy (v11, v12)
  - UnderHumanStrategy (1.0-2.0)
  - PiotrSwiecStrategy
  - FundingRateArbitrageStrategy
  - ScalpingStrategy
  - SentimentPropagationStrategy

### 🔧 Funkcje Zaawansowane
- ✅ **Slippage Simulation** - realistyczna symulacja kosztów transakcji
- ✅ **Leverage Support** - obsługa dźwigni 1-20x
- ✅ **Fee Calculation** - automatyczne obliczanie opłat maker/taker
- ✅ **Position Management** - automatyczne zamykanie przy SL/TP
- ✅ **Account Statistics** - kompleksowe statystyki wydajności
- ✅ **Trade History** - pełna historia z możliwością filtrowania

## 🧪 Testy

### Testy Jednostkowe
- ✅ `test_paper_trading.py` - testy PaperTradingEngine:
  - Tworzenie kont
  - Otwieranie/zamykanie pozycji
  - Obliczanie PnL
  - Stop Loss / Take Profit
  - Slippage simulation

### Testy Integracyjne
- ✅ Integracja z TradingBot
- ✅ Integracja ze strategiami
- ✅ Testy z rzeczywistymi danymi z dYdX API

## 📚 Dokumentacja

### Setup Guides
- ✅ **Trade Script Guide** - kompletny przewodnik uruchamiania tradingu
- ✅ **Trading Parameters Mapping** - dokumentacja parametrów strategii
- ✅ **dYdX Strategies Research** - badania strategii dla dYdX

### Dokumentacja Trading
- ✅ **Backtesting Guide** - jak testować strategie na danych historycznych
- ✅ **Funding Rate Arbitrage Guide** - przewodnik strategii arbitrażu
- ✅ **Strategy Optimization Guide** - optymalizacja parametrów

### Skrypty
- ✅ `scripts/run_paper_trading_enhanced.py` - zaawansowany skrypt uruchamiania
- ✅ `scripts/run_paper_trading.py` - podstawowy skrypt
- ✅ `scripts/trade.sh` - wrapper shell script

## 🔧 Konfiguracja

### Nowe Pliki Konfiguracyjne
- `src/trading/paper_trading.py` - główny silnik paper trading
- `src/trading/trading_bot.py` - bot automatyczny
- `src/trading/models.py` - modele bazy danych
- `src/trading/models_extended.py` - rozszerzone modele (strategie, sesje)
- `data/paper_trading.db` - baza danych SQLite (lub PostgreSQL)

### Struktura Projektu
```
ai-blockchain/
├── src/trading/
│   ├── paper_trading.py          # ✅ PaperTradingEngine
│   ├── trading_bot.py             # ✅ TradingBot
│   ├── models.py                 # ✅ Modele paper trading
│   ├── models_extended.py        # ✅ Rozszerzone modele
│   ├── backtesting.py            # ✅ Backtesting engine
│   └── strategies/               # ✅ Wszystkie strategie z integracją
├── scripts/
│   ├── run_paper_trading.py      # ✅ Podstawowy skrypt
│   ├── run_paper_trading_enhanced.py  # ✅ Zaawansowany skrypt
│   └── trade.sh                  # ✅ Wrapper script
├── docs/trading/                 # ✅ Dokumentacja tradingu
└── data/
    └── paper_trading.db          # ✅ Baza danych
```

## 🐛 Naprawy i Ulepszenia

### Code Review Fixes
- ✅ Obsługa timezone-aware datetime (UTC)
- ✅ Decimal precision dla obliczeń finansowych
- ✅ Obsługa błędów API dYdX
- ✅ Retry logic dla pobierania cen
- ✅ Thread-safe operations
- ✅ Graceful error handling

### Kompatybilność
- ✅ SQLite compatibility (development)
- ✅ PostgreSQL compatibility (production)
- ✅ Session management (expire_on_commit)
- ✅ Bulk operations dla wydajności

## 📊 Statystyki

- **15+ plików zmienionych/dodanych**
- **2,500+ wierszy dodanych**
- **Pokrycie testami:** Wszystkie główne moduły
- **Strategie zintegrowane:** 10+ strategii

## 🚀 Jak Przetestować

### 1. Konfiguracja bazy danych
```bash
# SQLite (domyślnie)
# Baza zostanie utworzona automatycznie w data/paper_trading.db

# PostgreSQL (opcjonalnie)
# Ustaw DATABASE_URL w .env
```

### 2. Uruchomienie paper trading
```bash
# Podstawowy skrypt
python scripts/run_paper_trading.py

# Zaawansowany skrypt z konfiguracją
python scripts/run_paper_trading_enhanced.py

# Z wrapper script
./scripts/trade.sh
```

### 3. Przykładowe użycie
```python
from src.trading.paper_trading import PaperTradingEngine
from src.trading.trading_bot import TradingBot
from src.trading.strategies.piotrek_strategy import PiotrekBreakoutStrategy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Utwórz sesję bazy danych
engine = create_engine("sqlite:///data/paper_trading.db")
Session = sessionmaker(bind=engine)
session = Session()

# Utwórz silnik paper trading
pt_engine = PaperTradingEngine(
    session=session,
    account_name="test_account",
    initial_balance=10000.0
)

# Utwórz strategię
strategy = PiotrekBreakoutStrategy()

# Utwórz bota
bot = TradingBot(
    database_url="sqlite:///data/paper_trading.db",
    account_name="test_account",
    symbols=["BTC-USD"],
    strategy=strategy,
    check_interval=60
)

# Uruchom bota
bot.start()
```

### 4. Sprawdzenie wyników
```python
# Pobierz podsumowanie konta
summary = pt_engine.get_account_summary()
print(f"Balance: ${summary['current_balance']:.2f}")
print(f"ROI: {summary['roi']:.2f}%")
print(f"Win Rate: {summary['win_rate']:.2f}%")

# Pobierz historię transakcji
trades = pt_engine.get_trade_history(limit=10)
for trade in trades:
    print(f"{trade.side}: {trade.realized_pnl:.2f} USD")
```

## ✅ Checklist

- [x] PaperTradingEngine z pełną funkcjonalnością
- [x] TradingBot z integracją strategii
- [x] Modele bazy danych kompletne
- [x] Integracja ze wszystkimi strategiami
- [x] Testy jednostkowe i integracyjne
- [x] Dokumentacja kompletna
- [x] Skrypty uruchomieniowe działają
- [x] Obsługa błędów i edge cases
- [x] Slippage i fees simulation
- [x] Stop Loss / Take Profit

## 🔗 Powiązane

- Issue: #BLC-002
- Branch: `feature/BLC-002-paper-trading-dydx`
- Base: `feature/BLC-001-initial-project-setup`

## 📝 Uwagi

- Paper trading używa rzeczywistych cen z dYdX API (testnet=False)
- Slippage domyślnie 0.75% (można skonfigurować)
- Opłaty zgodne z dYdX: maker 0.02%, taker 0.05%
- Wszystkie obliczenia w USD
- Baza danych SQLite dla development, PostgreSQL dla production
- TradingBot wymaga aktywnego połączenia z dYdX API

---

**Autor:** @piotradamczyk  
**Data:** 2025-12-19

