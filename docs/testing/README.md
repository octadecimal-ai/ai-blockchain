# Dokumentacja Testów

## 📋 Przegląd

Projekt używa **pytest** jako framework testowy.

## 📁 Struktura

```
tests/
├── unit/              # Testy jednostkowe
│   ├── test_binance_collector.py
│   ├── test_dydx_collector.py
│   ├── test_technical_indicators.py
│   ├── test_database_manager.py
│   ├── test_arbitrage.py
│   └── test_market_analyzer.py
│
├── integration/       # Testy integracyjne
│   ├── test_binance_integration.py
│   ├── test_dydx_integration.py
│   ├── test_arbitrage_integration.py
│   └── test_database_integration.py
│
└── conftest.py        # Shared fixtures
```

## 🚀 Uruchamianie Testów

### Wszystkie testy

```bash
pytest
```

### Tylko testy jednostkowe

```bash
pytest tests/unit/
```

### Tylko testy integracyjne

```bash
pytest tests/integration/
```

### Konkretny plik

```bash
pytest tests/unit/test_binance_collector.py
```

### Konkretny test

```bash
pytest tests/unit/test_binance_collector.py::TestBinanceCollector::test_fetch_ohlcv_success
```

### Z markerami

```bash
# Tylko testy jednostkowe
pytest -m unit

# Tylko testy integracyjne
pytest -m integration

# Pomiń wolne testy
pytest -m "not slow"
```

## 🔧 Konfiguracja

### Wymagane zmienne środowiskowe

Dla testów integracyjnych mogą być wymagane:

```bash
# Binance (opcjonalnie)
export BINANCE_API_KEY=your_key
export BINANCE_SECRET=your_secret

# LLM (opcjonalnie)
export ANTHROPIC_API_KEY=your_key
export OPENAI_API_KEY=your_key

# Database (opcjonalnie, domyślnie SQLite)
export DATABASE_URL=postgresql://user:pass@localhost:5432/test
export USE_TIMESCALE=true
```

**Uwaga**: Testy jednostkowe **nie wymagają** żadnych kluczy - używają mocków.

### Plik .env

Możesz też użyć pliku `.env`:

```bash
cp config/env.example.txt .env
# Edytuj .env i dodaj klucze
```

## 📊 Pokrycie Kodu

### Uruchom z pokryciem

```bash
pytest --cov=src --cov-report=html --cov-report=term-missing
```

### Zobacz raport

```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## 🧪 Typy Testów

### Testy Jednostkowe

- **Szybkie** (< 1s każdy)
- **Izolowane** (mocki zamiast realnych API)
- **Deterministyczne** (te same dane wejściowe = te same wyniki)

**Przykład:**
```python
def test_fetch_ohlcv_success(self):
    with patch('ccxt.binance') as mock_binance:
        mock_binance.fetch_ohlcv.return_value = [...]
        result = collector.fetch_ohlcv("BTC/USDT")
        assert len(result) > 0
```

### Testy Integracyjne

- **Wolniejsze** (realne requesty do API)
- **Wymagają** konfiguracji (API keys, baza danych)
- **Oznaczone** markerem `@pytest.mark.integration`

**Przykład:**
```python
@pytest.mark.integration
def test_fetch_ohlcv_real(self, collector):
    df = collector.fetch_ohlcv("BTC/USDT", "1h", limit=10)
    assert len(df) > 0
```

## 🔍 Debugowanie

### Verbose output

```bash
pytest -v
```

### Z printami

```bash
pytest -s
```

### Zatrzymaj przy pierwszym błędzie

```bash
pytest -x
```

### Zatrzymaj po N błędach

```bash
pytest --maxfail=3
```

### Uruchom ostatni test

```bash
pytest --lf  # last failed
pytest --ff  # failed first
```

## 📝 Pisanie Testów

### Struktura

```python
class TestClassName:
    """Testy dla klasy ClassName."""
    
    def test_method_name(self):
        """Test metody method_name."""
        # Arrange
        obj = ClassName()
        
        # Act
        result = obj.method()
        
        # Assert
        assert result == expected
```

### Fixtures

Użyj fixtures z `conftest.py`:

```python
def test_example(sample_ohlcv_dataframe):
    analyzer = TechnicalAnalyzer(sample_ohlcv_dataframe)
    # ...
```

### Mocki

```python
from unittest.mock import patch, MagicMock

def test_with_mock(self):
    with patch('module.function') as mock_func:
        mock_func.return_value = "mocked"
        result = code_under_test()
        assert result == "mocked"
```

## ⚠️ Best Practices

1. **Nazwy testów**: Opisowe, mówiące co testują
2. **AAA Pattern**: Arrange, Act, Assert
3. **Jeden test = jedna rzecz**: Nie testuj wielu rzeczy w jednym teście
4. **Mocki dla zewnętrznych zależności**: Nie testuj API w testach jednostkowych
5. **Testy integracyjne**: Tylko tam gdzie ma sens (realne połączenia)

## 🐛 Rozwiązywanie problemów

### Import errors

```bash
# Upewnij się że jesteś w katalogu projektu
cd /path/to/ai-blockchain

# Sprawdź PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Błąd: "No module named 'src'"

```bash
# Zainstaluj projekt w trybie development
pip install -e .
```

### Testy integracyjne failują

- Sprawdź czy masz poprawne API keys w `.env`
- Sprawdź czy masz połączenie z internetem
- Sprawdź czy API nie ma rate limiting

## 📚 Zasoby

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)

