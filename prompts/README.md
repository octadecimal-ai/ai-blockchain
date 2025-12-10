# Prompty Tradingowe

Ten katalog zawiera prompty i strategie tradingowe do wykorzystania z AI/LLM.

## 📁 Struktura

```
prompts/
├── README.md                              # Ten plik
└── trading/                               # Strategie tradingowe
    └── piotrek_breakout_strategy.md       # Strategia breakout Piotrka
```

## 🎯 Dostępne strategie

### 1. Piotrek Breakout Strategy
**Plik:** `trading/piotrek_breakout_strategy.md`

Strategia oparta na:
- Identyfikacji breakoutów powyżej poziomów oporu
- Wyjściu z pozycji gdy cena się "wypłaszcza" (konsolidacja)
- Krótkim timeframe (daytrading/swing)
- Zarządzaniu ryzykiem - "lepiej pewny zysk niż loteria"

**Kluczowe zasady:**
1. Wejście po przebicie oporu z wolumenem
2. Exit gdy momentum słabnie
3. Akceptacja przedwczesnych wyjść
4. "Dalej to loteria" - nie zgaduj, zamykaj

## 🔧 Użycie z LLM

Prompty można wykorzystać z:
- Claude (Anthropic)
- GPT-4 (OpenAI)
- Lokalnie z LLaMA/Mistral

Przykład użycia w kodzie:

```python
from src.analysis.llm.market_analyzer import MarketAnalyzerLLM

# Załaduj prompt
with open('prompts/trading/piotrek_breakout_strategy.md', 'r') as f:
    strategy_prompt = f.read()

# Użyj z analizatorem
analyzer = MarketAnalyzerLLM(provider="anthropic")
result = analyzer.analyze_with_prompt(
    market_data=df,
    system_prompt=strategy_prompt
)
```

## 📝 Dodawanie nowych strategii

1. Utwórz nowy plik `.md` w odpowiednim podkatalogu
2. Użyj formatu z istniejących strategii
3. Dołącz:
   - Opis metody
   - Zasady wejścia/wyjścia
   - Przykładowy kod implementacji
   - Checklistę przed transakcją

---

*Katalog utworzony: 2024-12-09*

