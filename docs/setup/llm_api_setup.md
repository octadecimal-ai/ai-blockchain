# Konfiguracja API LLM (Anthropic/OpenAI)

## 📋 Wymagania

Aby używać analizy rynkowej z LLM, potrzebujesz API key od jednego z dostawców:

- **Anthropic Claude** (domyślny)
- **OpenAI GPT-4**

## 🔑 Anthropic Claude (Rekomendowane)

### Krok 1: Utwórz konto

1. Przejdź na [console.anthropic.com](https://console.anthropic.com)
2. Zarejestruj się i zweryfikuj email

### Krok 2: Utwórz API Key

1. Przejdź do **API Keys**: [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)
2. Kliknij **Create Key**
3. Nadaj nazwę (np. "ai-blockchain-project")
4. **Zapisz klucz** - jest widoczny tylko raz!

### Krok 3: Skonfiguruj w projekcie

1. Dodaj do `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-api03-twoj_klucz_tutaj
```

2. Użyj w kodzie:
```python
from src.analysis.llm.market_analyzer import MarketAnalyzer

analyzer = MarketAnalyzer(model_name="claude-3-opus-20240229")
```

## 🔑 OpenAI GPT-4 (Alternatywa)

### Krok 1: Utwórz konto

1. Przejdź na [platform.openai.com](https://platform.openai.com)
2. Zarejestruj się i zweryfikuj

### Krok 2: Utwórz API Key

1. Przejdź do **API Keys**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Kliknij **Create new secret key**
3. **Zapisz klucz** - jest widoczny tylko raz!

### Krok 3: Skonfiguruj w projekcie

1. Dodaj do `.env`:
```env
OPENAI_API_KEY=sk-twoj_klucz_tutaj
```

2. Zmień model w kodzie (wymaga modyfikacji `MarketAnalyzer`):
```python
# Wymaga implementacji obsługi OpenAI w MarketAnalyzer
analyzer = MarketAnalyzer(provider="openai", model_name="gpt-4")
```

## 💰 Koszty

### Anthropic Claude
- **Claude 3 Opus**: ~$15/1M input tokens, ~$75/1M output tokens
- **Claude 3 Sonnet**: ~$3/1M input tokens, ~$15/1M output tokens
- **Claude 3 Haiku**: ~$0.25/1M input tokens, ~$1.25/1M output tokens

### OpenAI GPT-4
- **GPT-4 Turbo**: ~$10/1M input tokens, ~$30/1M output tokens
- **GPT-3.5 Turbo**: ~$0.50/1M input tokens, ~$1.50/1M output tokens

**Rekomendacja**: Dla testów użyj **Claude 3 Haiku** (najtańszy).

## 🧪 Testy

Testy jednostkowe używają mocków i **nie wymagają** API keys.

Testy integracyjne (jeśli dodane) będą wymagały kluczy.

## 🔒 Bezpieczeństwo

- **Nigdy** nie commituj API keys do git
- Używaj zmiennych środowiskowych
- Ustaw limity wydatków w panelu dostawcy

## 🐛 Rozwiązywanie problemów

### Błąd: "Invalid API key"
- Sprawdź czy klucz jest poprawny
- Sprawdź czy nie ma dodatkowych spacji w `.env`
- Upewnij się że używasz właściwego formatu (sk-ant-... dla Anthropic)

### Błąd: 429 Rate Limit
- Przekroczono limit requestów
- Poczekaj lub zwiększ limit w panelu dostawcy

### Błąd: Insufficient credits
- Brak środków na koncie
- Doładuj konto w panelu dostawcy

## 📚 Dokumentacja

- [Anthropic API Docs](https://docs.anthropic.com/)
- [OpenAI API Docs](https://platform.openai.com/docs)

