# Ulepszone Szablony Promptów dla Analizy Sentymentu Crypto

## Co zostało poprawione?

### 1. Wbudowany slang (nie wymaga `{slang_context}`)
Każdy prompt zawiera teraz BEZPOŚREDNIO listę terminów crypto dla danego języka z wyjaśnieniem czy są bullish/bearish.

### 2. Kontekst regionalny
- **es.txt**: LATAM vs España (zupełnie różne rynki!)
- **pt.txt**: Brazylia vs Portugalia
- **fr.txt**: France vs Afrique vs Suisse
- **ar.txt**: Gulf vs North Africa + kontekst halal/haram
- **zh.txt**: Mainland vs Hong Kong
- **de.txt**: DACH region (DE/AT/CH)

### 3. Wykrywanie sarkazmu
Każdy prompt zawiera teraz:
```
⚠️ SARCASM ALERT: "To the moon" AFTER a crash is BEARISH (coping), not bullish!
```

### 4. Reasoning po angielsku
Zmiana: `"reasoning": "<brief explanation in English>"`
Powód: Łatwiejszy parsing i analiza cross-language

### 5. Nowe pola JSON specyficzne dla regionu
- `sarcasm_detected`: boolean (wszystkie języki)
- `kimchi_premium_mentioned`: boolean (ko.txt)
- `is_latam`: boolean (es.txt)
- `is_brazil`: boolean (pt.txt)
- `is_african_context`: boolean (fr.txt)
- `halal_discussion`: boolean (ar.txt)
- `is_gulf_context`: boolean (ar.txt)

## Struktura plików

```
prompts/
├── README.md
├── en.txt    # English (US/UK)
├── zh.txt    # Chinese (中文)
├── ja.txt    # Japanese (日本語)
├── ko.txt    # Korean (한국어)
├── ru.txt    # Russian (Русский)
├── de.txt    # German (Deutsch)
├── es.txt    # Spanish (Español) - LATAM + España
├── pt.txt    # Portuguese (Português) - Brasil + Portugal
├── fr.txt    # French (Français) - France + Afrique + Suisse
├── ar.txt    # Arabic (العربية) - Gulf + North Africa
├── pl.txt    # Polish (Polski)
├── nl.txt    # Dutch (Nederlands)
└── it.txt    # Italian (Italiano)
```

## Użycie

```python
def load_prompt(language: str) -> str:
    """Ładuje prompt dla danego języka."""
    path = f"prompts/{language}.txt"
    if not os.path.exists(path):
        path = "prompts/en.txt"  # fallback
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def analyze_sentiment(texts: list, region: str, language: str) -> dict:
    template = load_prompt(language)
    
    texts_formatted = "\n".join([f"- {t[:500]}" for t in texts[:20]])
    
    prompt = template.format(
        region=region,
        language=language,
        texts_formatted=texts_formatted
    )
    
    # Call Claude API...
    response = client.messages.create(...)
    return json.loads(response.content[0].text)
```

## Kluczowe zmiany vs stare prompty

| Aspekt | Stare | Nowe |
|--------|-------|------|
| Slang | `{slang_context}` placeholder (pusty!) | Wbudowany bezpośrednio |
| Kontekst regionalny | Brak | Tak (LATAM/España, etc.) |
| Sarkazm | Brak wykrywania | Explicit request + przykłady |
| Reasoning | W lokalnym języku | Po angielsku (parsing!) |
| Pola specyficzne | Brak | kimchi_premium, halal, latam, etc. |
| Encoding | Problemy z UTF-8 | Poprawione |

## Przykład wyniku

```json
{
    "sentiment": "bearish",
    "score": -0.6,
    "confidence": 0.85,
    "key_topics": ["ETF rejection", "SEC lawsuit"],
    "fud_level": 0.7,
    "fomo_level": 0.1,
    "market_impact": "high",
    "sarcasm_detected": true,
    "reasoning": "Multiple bearish signals: ETF rejection news and SEC lawsuit. Sarcastic 'to the moon' comments detected after -15% drop indicate capitulation."
}
```

## Uwagi

1. **Hot reload działa** - zmiany w plikach są natychmiast widoczne
2. **Fallback do en.txt** jeśli brak pliku dla danego języka
3. **UTF-8 encoding** - upewnij się że pliki są zapisane w UTF-8
