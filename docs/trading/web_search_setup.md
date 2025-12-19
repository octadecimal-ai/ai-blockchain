# Konfiguracja Web Search API

## 🔍 Wyszukiwanie w internecie dla LLM

LLM może samodzielnie wyszukiwać informacje w internecie przed podjęciem decyzji tradingowej.

## Dostępne API

### 1. Tavily AI (Rekomendowane)

**Dlaczego Tavily:**
- ✅ Zoptymalizowane dla LLM
- ✅ Zwraca podsumowanie AI (answer) + wyniki wyszukiwania
- ✅ Darmowy tier: 1000 requestów/miesiąc
- ✅ Łatwa integracja

**Konfiguracja:**
1. Zarejestruj się na [Tavily.com](https://tavily.com)
2. Utwórz API key
3. Dodaj do `.env`:
```env
TAVILY_API_KEY=twoj_api_key_tutaj
```

### 2. Serper API (Alternatywa)

**Konfiguracja:**
1. Zarejestruj się na [Serper.dev](https://serper.dev)
2. Utwórz API key
3. Dodaj do `.env`:
```env
SERPER_API_KEY=twoj_api_key_tutaj
```

## Jak to działa

1. **LLM analizuje dane** - otrzymuje historię cen, sentyment, wiadomości
2. **LLM decyduje czy potrzebuje więcej informacji** - jeśli tak, zwraca `"action": "SEARCH"` z listą zapytań
3. **System wyszukuje informacje** - wykonuje wyszukiwania w internecie
4. **Wyniki są dodawane do prompta** - LLM otrzymuje aktualne informacje
5. **LLM podejmuje decyzję** - na podstawie pełnych informacji (techniczne + fundamentalne + wyszukane)

## Przykład użycia przez LLM

**LLM może zwrócić:**
```json
{
    "action": "SEARCH",
    "search_queries": [
        "Bitcoin ETF approval December 2024",
        "BTC regulations latest news",
        "cryptocurrency market sentiment today"
    ],
    "reason": "Potrzebuję aktualnych informacji o regulacjach i sentymencie przed podjęciem decyzji"
}
```

**System wyszuka informacje i doda do prompta:**
```
=== WYNIKI WYSZUKIWANIA W INTERNECIE ===

🤖 Podsumowanie AI:
   Bitcoin ETF approval news from December 2024...

📰 Znalezione informacje (3 wyniki):
1. Bitcoin ETF Approved - Latest News
   Źródło: https://example.com/news
   Bitcoin ETF has been approved by SEC...
```

**Następnie LLM podejmie decyzję:**
```json
{
    "action": "BUY",
    "confidence": 8.5,
    "price": 50500.0,
    "stop_loss": 48000.0,
    "take_profit": 55000.0,
    "size_percent": 15.0,
    "observations": "Pozytywne wiadomości o ETF approval + bullish sentiment z wyszukiwania wspierają trend wzrostowy...",
    "reason": "ETF approval + bullish sentiment = silny sygnał wzrostowy"
}
```

## Koszty

- **Tavily**: Darmowy tier 1000 requestów/miesiąc, potem $0.001/request
- **Serper**: Darmowy tier 2500 requestów/miesiąc, potem $0.001/request

## Bez API Key

Jeśli nie masz API key, system będzie używał:
- Symulowanych wiadomości politycznych i technologicznych
- LLM nadal może prosić o wyszukanie, ale wyszukiwanie nie będzie działać (zwróci błąd)
- System kontynuuje normalnie bez wyników wyszukiwania

## Testowanie

Aby przetestować wyszukiwanie:
1. Dodaj API key do `.env`
2. Uruchom strategię: `./scripts/run_prompt_strategy.sh`
3. LLM może poprosić o wyszukanie informacji
4. Sprawdź logi: `logs/trading_*.log` - zobaczysz `🔍 LLM prosi o wyszukanie`

