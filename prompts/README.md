# Prompty Tradingowe

Ten katalog zawiera prompty i strategie tradingowe do wykorzystania z AI/LLM.

## 📁 Struktura

```
prompts/
├── README.md                                  # Ten plik
└── trading/                                   # Strategie tradingowe
    ├── piotrek_breakout_strategy.md           # Strategia breakout Piotrka
    ├── prompt_strategy_example.txt            # Przykładowy prompt dla PromptStrategy v1.0
    └── aggressive_dynamic_v11.txt             # 🆕 Agresywny prompt dla v1.1
```

## 🎯 Dostępne strategie

### 1. Piotrek Breakout Strategy
**Plik:** `trading/piotrek_breakout_strategy.md`

Strategia oparta na:
- Identyfikacji breakoutów powyżej poziomów oporu
- Wyjściu z pozycji gdy cena się "wypłaszcza" (konsolidacja)
- Krótkim timeframe (daytrading/swing)
- Zarządzaniu ryzykiem - "lepiej pewny zysk niż loteria"

### 2. Prompt Strategy v1.0 (podstawowa)
**Plik:** `trading/prompt_strategy_example.txt`

Podstawowa strategia LLM z:
- Analizą sentymentu (Twitter, Reddit)
- Możliwością wyszukiwania w internecie
- Konserwatywnym podejściem

### 3. 🆕 Aggressive Dynamic Strategy v1.1
**Plik:** `trading/aggressive_dynamic_v11.txt`

Ulepszona strategia dla dynamicznego tradingu:
- **Wskaźniki techniczne:** RSI, MACD, Bollinger Bands, ATR
- **Informacja o otwartych pozycjach** - LLM wie co ma i jak zarządzać
- **Agresywne zasady:** CLOSE przy ±3%, trailing stop 2-3%
- **Szybkie decyzje:** częste transakcje dla maksymalizacji zysków

**Uruchomienie:**
```bash
./scripts/run_prompt_strategy_v11.sh
```

## 🔧 Użycie z LLM

Prompty można wykorzystać z:
- Claude (Anthropic) - zalecane: claude-3-5-haiku-20241022
- GPT-4 (OpenAI)
- Lokalnie z LLaMA/Mistral

### Przykład użycia PromptStrategy v1.1:

```bash
# Domyślne ustawienia (zoptymalizowane)
./scripts/run_prompt_strategy_v11.sh

# Z własnymi parametrami
./scripts/run_prompt_strategy_v11.sh \
    --symbols=BTC-USD,ETH-USD \
    --interval=5min \
    --time-limit=24h \
    --max-loss=500
```

### Porównanie wersji:

| Cecha | v1.0 | v1.1 |
|-------|------|------|
| Wskaźniki techniczne | ❌ | ✅ RSI, MACD, BB, ATR |
| Otwarte pozycje w promptcie | ❌ | ✅ |
| Trailing stop | ❌ | ✅ 2-3% |
| Zarządzanie pozycją | Pasywne | Aktywne |
| Interwał domyślny | 1min | 5min |
| Max loss | $100 | $500 (5%) |

## 📝 Dodawanie nowych strategii

1. Utwórz nowy plik `.txt` lub `.md` w `trading/`
2. Użyj formatu z istniejących strategii
3. Dołącz:
   - Opis metody i zasad
   - Interpretację wskaźników
   - Format odpowiedzi JSON
   - Przykłady decyzji

---

*Ostatnia aktualizacja: 2025-12-12*

