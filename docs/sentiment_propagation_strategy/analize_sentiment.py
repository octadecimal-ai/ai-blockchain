import anthropic

def analyze_sentiment(texts: list, region: str, language: str = "en") -> dict:
    """
    Analizuje sentyment używając Claude API.
    
    Args:
        texts: Lista tekstów do analizy
        region: Kod regionu (US, CN, JP, KR, DE, etc.)
        language: Kod języka (en, zh, ja, ko, etc.)
    """
    
    # Słownik slangu dla różnych języków
    slang_context = {
        "zh": """Chinese crypto slang:
- 韭菜 (leeks) = retail being harvested
- 梭哈 = all-in, FOMO
- 割肉 = selling at loss
- 暴涨/暴跌 = pump/dump""",
        "ko": """Korean crypto slang:
- 존버 = HODL
- 떡락/떡상 = dump/pump  
- 김치프리미엄 = Korea premium""",
        "ja": """Japanese crypto slang:
- 億り人 = made 100M+ yen
- ガチホ = diamond hands
- 養分 = retail being harvested""",
    }
    
    # Formatuj teksty
    texts_formatted = "\n".join([f"- {t[:500]}" for t in texts[:20]])
    
    # Dodaj kontekst językowy jeśli dostępny
    lang_context = slang_context.get(language, "")
    
    prompt = f"""Analyze aggregate crypto sentiment from {region} ({language}):

{lang_context}

<texts>
{texts_formatted}
</texts>

Consider: sarcasm, irony, cultural context, and crypto-specific terminology.

Respond ONLY with valid JSON:
{{
    "sentiment": "very_bearish|bearish|neutral|bullish|very_bullish",
    "score": <float -1.0 to 1.0>,
    "confidence": <float 0.0 to 1.0>,
    "key_topics": ["topic1", "topic2"],
    "fud_level": <float 0.0 to 1.0>,
    "fomo_level": <float 0.0 to 1.0>,
    "market_impact": "high|medium|low",
    "reasoning": "<brief explanation>"
}}"""

    client = anthropic.Anthropic()
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )
    
    import json
    return json.loads(response.content[0].text)


# Użycie:
result = analyze_sentiment(
    texts=[
        "Bitcoin ETF approved! Institutions are coming!",
        "This is the top, selling everything",
        "Sideways action, waiting for breakout"
    ],
    region="US",
    language="en"
)

print(f"Sentiment: {result['sentiment']} ({result['score']:+.2f})")
print(f"Reasoning: {result['reasoning']}")