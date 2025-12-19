# Tavily Search Queries by Region/Language
# =========================================

## Problem z obecnymi zapytaniami

Stare zapytania:
```
"BTC/USDC cryptocurrency news sentiment Germany"
"BTC/USDC cryptocurrency news sentiment China"
```

**Problemy:**
1. ❌ Wszystkie po angielsku → zwracają anglojęzyczne źródła
2. ❌ Generyczne → brak lokalnych giełd, regulatorów, influencerów
3. ❌ Identyczne struktury → brak różnorodności wyników

## Nowe zapytania

Każdy plik zawiera **20-30 zapytań** w lokalnym języku, podzielone na kategorie:
- Breaking News
- Local Exchanges (Upbit, Zonda, Bitvavo, etc.)
- Regulatory (FSA, BaFin, KNF, MAS, etc.)
- Community Sentiment
- Market Analysis
- Region-specific (Kimchi Premium, Halal/Haram, LATAM inflation, etc.)

## Pliki

| Plik | Region | Język | Specyfika |
|------|--------|-------|-----------|
| `en.txt` | US/UK | English | SEC, ETF, Coinbase |
| `zh.txt` | China/HK/TW | 中文 | 韭菜, 矿业, 币安 |
| `ko.txt` | South Korea | 한국어 | 김치프리미엄, 업비트 |
| `ja.txt` | Japan | 日本語 | 金融庁, bitFlyer |
| `ru.txt` | Russia/CIS | Русский | санкции, Telegram, P2P |
| `de.txt` | Germany/DACH | Deutsch | BaFin, Steuer 1 Jahr |
| `es.txt` | LATAM + Spain | Español | inflación, El Salvador |
| `pt.txt` | Brazil + Portugal | Português | PIX, Nubank, day trade |
| `fr.txt` | France + Africa | Français | AMF, Ledger, mobile money |
| `ar.txt` | Gulf + MENA | العربية | حلال/حرام, دبي, VARA |
| `pl.txt` | Poland | Polski | KNF, Zonda, 19% podatek |
| `nl.txt` | Netherlands | Nederlands | DNB, box 3, Bitvavo |
| `it.txt` | Italy | Italiano | Consob, 26% tasse |
| `sg.txt` | Singapore | EN + 中文 | MAS, DBS, Web3 hub |

## Użycie

```python
import random
from pathlib import Path

class TavilyQueryManager:
    def __init__(self, queries_dir: str = "tavily_queries"):
        self.queries_dir = Path(queries_dir)
        self.cache = {}
    
    def load_queries(self, language: str) -> list:
        """Ładuje zapytania dla danego języka."""
        if language in self.cache:
            return self.cache[language]
        
        path = self.queries_dir / f"{language}.txt"
        if not path.exists():
            path = self.queries_dir / "en.txt"  # fallback
        
        queries = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Pomiń komentarze i puste linie
                if line and not line.startswith('#'):
                    queries.append(line)
        
        self.cache[language] = queries
        return queries
    
    def get_random_queries(self, language: str, count: int = 3) -> list:
        """Zwraca losowe zapytania dla danego języka."""
        queries = self.load_queries(language)
        return random.sample(queries, min(count, len(queries)))
    
    def get_categorized_queries(self, language: str) -> dict:
        """Zwraca zapytania pogrupowane według kategorii."""
        queries = self.load_queries(language)
        # Można rozszerzyć o parsowanie kategorii z komentarzy
        return {"all": queries}


# Przykład użycia z Tavily
def search_sentiment_multi_region(regions: list, queries_per_region: int = 2):
    """
    Wyszukuje sentyment dla wielu regionów.
    
    Args:
        regions: Lista kodów regionów np. ["en", "zh", "ko", "ja"]
        queries_per_region: Ile zapytań na region
    """
    from tavily import TavilyClient
    
    manager = TavilyQueryManager()
    client = TavilyClient(api_key="your-api-key")
    
    results = {}
    
    for region in regions:
        queries = manager.get_random_queries(region, queries_per_region)
        region_results = []
        
        for query in queries:
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=5
            )
            region_results.extend(response.get("results", []))
        
        results[region] = region_results
    
    return results


# Mapowanie region -> language code
REGION_TO_LANGUAGE = {
    "United States": "en",
    "United Kingdom": "en", 
    "China": "zh",
    "Hong Kong": "zh",
    "Taiwan": "zh",
    "South Korea": "ko",
    "Japan": "ja",
    "Russia": "ru",
    "Germany": "de",
    "Austria": "de",
    "Switzerland": "de",  # lub "fr" dla Romandie
    "Spain": "es",
    "Mexico": "es",
    "Argentina": "es",
    "Brazil": "pt",
    "Portugal": "pt",
    "France": "fr",
    "Senegal": "fr",
    "UAE": "ar",
    "Saudi Arabia": "ar",
    "Egypt": "ar",
    "Poland": "pl",
    "Netherlands": "nl",
    "Belgium": "nl",  # lub "fr"
    "Italy": "it",
    "Singapore": "sg",
}
```

## Strategia rotacji zapytań

```python
class QueryRotator:
    """Rotuje zapytania żeby nie powtarzać tych samych."""
    
    def __init__(self, queries_dir: str):
        self.manager = TavilyQueryManager(queries_dir)
        self.used = {}  # {language: set of used queries}
    
    def get_fresh_queries(self, language: str, count: int = 3) -> list:
        """Zwraca zapytania które nie były ostatnio używane."""
        all_queries = self.manager.load_queries(language)
        used = self.used.get(language, set())
        
        # Znajdź nieużywane
        fresh = [q for q in all_queries if q not in used]
        
        # Jeśli wszystkie użyte, zresetuj
        if len(fresh) < count:
            self.used[language] = set()
            fresh = all_queries
        
        # Wybierz losowo
        selected = random.sample(fresh, min(count, len(fresh)))
        
        # Oznacz jako użyte
        if language not in self.used:
            self.used[language] = set()
        self.used[language].update(selected)
        
        return selected
```

## Porównanie wyników

| Aspekt | Stare zapytanie | Nowe zapytanie |
|--------|-----------------|----------------|
| Zapytanie | "cryptocurrency news China" | "比特币最新消息今天" |
| Wyniki | Reuters, Bloomberg (EN) | 金色财经, 币安公告 (ZH) |
| Relevance | Zewnętrzna perspektywa | Lokalna perspektywa |
| Sentiment | Zachodni filtr | Autentyczny lokalny |

## Tips

1. **Używaj 2-3 zapytań na region** - więcej = więcej kosztów API
2. **Rotuj zapytania** - te same zapytania dają te same wyniki
3. **Mieszaj kategorie** - News + Exchange + Social dla pełnego obrazu
4. **Cache wyniki** - Tavily jest płatne, cache na 1h wystarczy
5. **Fallback do EN** - jeśli brak pliku dla języka
