"""
Tavily Query Manager
====================
Zarządzanie zapytaniami wyszukiwania dla różnych regionów/języków.

Użycie:
    manager = TavilyQueryManager("tavily_queries")
    
    # Pobierz losowe zapytania dla Chin
    queries = manager.get_queries("zh", count=3)
    # ['比特币最新消息今天', '币安最新公告', 'BTC多空分析']
    
    # Pobierz zapytania z rotacją (bez powtórzeń)
    rotator = QueryRotator(manager)
    queries = rotator.get_fresh("ko", count=2)
"""

import random
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from loguru import logger


# Mapowanie kraj/region -> kod języka
REGION_TO_LANGUAGE = {
    # English
    "United States": "en",
    "United Kingdom": "en",
    "US": "en",
    "UK": "en",
    "GB": "en",
    "Australia": "en",
    "AU": "en",
    "Canada": "en",
    "CA": "en",
    
    # Chinese
    "China": "zh",
    "CN": "zh",
    "Hong Kong": "zh",
    "HK": "zh",
    "Taiwan": "zh",
    "TW": "zh",
    
    # Korean
    "South Korea": "ko",
    "Korea": "ko",
    "KR": "ko",
    
    # Japanese
    "Japan": "ja",
    "JP": "ja",
    
    # Russian
    "Russia": "ru",
    "RU": "ru",
    
    # German
    "Germany": "de",
    "DE": "de",
    "Austria": "de",
    "AT": "de",
    "Switzerland": "de",  # Default to German, could be FR
    "CH": "de",
    
    # Spanish
    "Spain": "es",
    "ES": "es",
    "Mexico": "es",
    "MX": "es",
    "Argentina": "es",
    "AR": "es",
    "Colombia": "es",
    "CO": "es",
    "Venezuela": "es",
    "VE": "es",
    "Chile": "es",
    "CL": "es",
    
    # Portuguese
    "Brazil": "pt",
    "BR": "pt",
    "Portugal": "pt",
    "PT": "pt",
    
    # French
    "France": "fr",
    "FR": "fr",
    "Belgium": "fr",  # Could also be NL
    "BE": "fr",
    "Senegal": "fr",
    "SN": "fr",
    
    # Arabic
    "UAE": "ar",
    "AE": "ar",
    "Saudi Arabia": "ar",
    "SA": "ar",
    "Egypt": "ar",
    "EG": "ar",
    "Morocco": "ar",
    "MA": "ar",
    
    # Polish
    "Poland": "pl",
    "PL": "pl",
    
    # Dutch
    "Netherlands": "nl",
    "NL": "nl",
    
    # Italian
    "Italy": "it",
    "IT": "it",
    
    # Singapore (special - mixed)
    "Singapore": "sg",
    "SG": "sg",
}


@dataclass
class QueryCategory:
    """Kategoria zapytań."""
    name: str
    queries: List[str] = field(default_factory=list)


class TavilyQueryManager:
    """
    Zarządza zapytaniami wyszukiwania dla różnych regionów.
    
    Features:
    - Ładowanie zapytań z plików .txt
    - Mapowanie region -> język
    - Losowy wybór zapytań
    - Parsowanie kategorii z komentarzy
    """
    
    def __init__(self, queries_dir: str = "tavily_queries"):
        """
        Inicjalizuje manager.
        
        Args:
            queries_dir: Ścieżka do katalogu z plikami zapytań
        """
        self.queries_dir = Path(queries_dir)
        self._cache: Dict[str, List[str]] = {}
        self._categories_cache: Dict[str, Dict[str, List[str]]] = {}
        
        logger.info(f"TavilyQueryManager: dir={queries_dir}")
    
    def _load_file(self, language: str) -> List[str]:
        """Ładuje zapytania z pliku."""
        path = self.queries_dir / f"{language}.txt"
        
        if not path.exists():
            logger.warning(f"Brak pliku {path}, fallback do en.txt")
            path = self.queries_dir / "en.txt"
        
        if not path.exists():
            logger.error(f"Brak pliku en.txt!")
            return []
        
        queries = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Pomiń komentarze i puste linie
                if line and not line.startswith('#'):
                    queries.append(line)
        
        return queries
    
    def _load_with_categories(self, language: str) -> Dict[str, List[str]]:
        """Ładuje zapytania z parsowaniem kategorii z komentarzy."""
        path = self.queries_dir / f"{language}.txt"
        
        if not path.exists():
            path = self.queries_dir / "en.txt"
        
        if not path.exists():
            return {"general": []}
        
        categories: Dict[str, List[str]] = {}
        current_category = "general"
        
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # Nowa kategoria (komentarz z ---)
                if line.startswith('# ---') and '---' in line[5:]:
                    # Extract category name
                    name = line.replace('#', '').replace('-', '').strip()
                    if name:
                        current_category = name.lower().replace(' ', '_')
                        if current_category not in categories:
                            categories[current_category] = []
                
                # Pomijamy inne komentarze
                elif line.startswith('#'):
                    continue
                
                # Zapytanie
                elif line:
                    if current_category not in categories:
                        categories[current_category] = []
                    categories[current_category].append(line)
        
        return categories
    
    def get_language(self, region: str) -> str:
        """Mapuje region na kod języka."""
        return REGION_TO_LANGUAGE.get(region, "en")
    
    def get_queries(
        self,
        language_or_region: str,
        count: int = 3,
        category: Optional[str] = None
    ) -> List[str]:
        """
        Zwraca losowe zapytania dla danego języka/regionu.
        
        Args:
            language_or_region: Kod języka (en, zh) lub nazwa regionu (China, US)
            count: Liczba zapytań do zwrócenia
            category: Opcjonalna kategoria (breaking_news, exchanges, etc.)
            
        Returns:
            Lista zapytań
        """
        # Normalizuj do kodu języka
        if len(language_or_region) > 2:
            language = self.get_language(language_or_region)
        else:
            language = language_or_region.lower()
        
        # Ładuj z cache lub pliku
        if language not in self._cache:
            self._cache[language] = self._load_file(language)
        
        queries = self._cache[language]
        
        # Filtruj po kategorii jeśli podana
        if category:
            if language not in self._categories_cache:
                self._categories_cache[language] = self._load_with_categories(language)
            
            cat_queries = self._categories_cache[language].get(category, [])
            if cat_queries:
                queries = cat_queries
        
        if not queries:
            logger.warning(f"Brak zapytań dla {language}")
            return []
        
        return random.sample(queries, min(count, len(queries)))
    
    def get_all_queries(self, language: str) -> List[str]:
        """Zwraca wszystkie zapytania dla języka."""
        if language not in self._cache:
            self._cache[language] = self._load_file(language)
        return self._cache[language].copy()
    
    def get_categories(self, language: str) -> Dict[str, List[str]]:
        """Zwraca zapytania pogrupowane według kategorii."""
        if language not in self._categories_cache:
            self._categories_cache[language] = self._load_with_categories(language)
        return self._categories_cache[language]


class QueryRotator:
    """
    Rotator zapytań - unika powtarzania tych samych zapytań.
    
    Użycie:
        rotator = QueryRotator(manager)
        
        # Pierwsze wywołanie
        queries = rotator.get_fresh("zh", 3)  # ["q1", "q2", "q3"]
        
        # Drugie wywołanie - inne zapytania
        queries = rotator.get_fresh("zh", 3)  # ["q4", "q5", "q6"]
        
        # Reset po wyczerpaniu lub po czasie
        rotator.reset("zh")
    """
    
    def __init__(
        self,
        manager: TavilyQueryManager,
        reset_after_hours: int = 24
    ):
        """
        Inicjalizuje rotator.
        
        Args:
            manager: TavilyQueryManager
            reset_after_hours: Po ilu godzinach resetować użyte zapytania
        """
        self.manager = manager
        self.reset_after = timedelta(hours=reset_after_hours)
        
        self._used: Dict[str, Set[str]] = {}
        self._last_reset: Dict[str, datetime] = {}
    
    def _should_reset(self, language: str) -> bool:
        """Sprawdza czy trzeba zresetować użyte zapytania."""
        if language not in self._last_reset:
            return True
        
        elapsed = datetime.now() - self._last_reset[language]
        return elapsed > self.reset_after
    
    def reset(self, language: str):
        """Resetuje użyte zapytania dla języka."""
        self._used[language] = set()
        self._last_reset[language] = datetime.now()
        logger.debug(f"Reset użytych zapytań dla {language}")
    
    def get_fresh(
        self,
        language_or_region: str,
        count: int = 3
    ) -> List[str]:
        """
        Zwraca zapytania które nie były ostatnio używane.
        
        Args:
            language_or_region: Kod języka lub nazwa regionu
            count: Liczba zapytań
            
        Returns:
            Lista niepowtarzających się zapytań
        """
        # Normalizuj
        if len(language_or_region) > 2:
            language = self.manager.get_language(language_or_region)
        else:
            language = language_or_region.lower()
        
        # Reset jeśli minął czas
        if self._should_reset(language):
            self.reset(language)
        
        # Pobierz wszystkie zapytania
        all_queries = self.manager.get_all_queries(language)
        
        if not all_queries:
            return []
        
        # Filtruj użyte
        used = self._used.get(language, set())
        fresh = [q for q in all_queries if q not in used]
        
        # Jeśli za mało świeżych, resetuj
        if len(fresh) < count:
            self.reset(language)
            fresh = all_queries
        
        # Wybierz losowo
        selected = random.sample(fresh, min(count, len(fresh)))
        
        # Oznacz jako użyte
        if language not in self._used:
            self._used[language] = set()
        self._used[language].update(selected)
        
        return selected
    
    def get_stats(self) -> Dict[str, Dict]:
        """Zwraca statystyki użycia."""
        stats = {}
        for lang, used in self._used.items():
            all_queries = self.manager.get_all_queries(lang)
            stats[lang] = {
                "used": len(used),
                "total": len(all_queries),
                "remaining": len(all_queries) - len(used),
                "last_reset": self._last_reset.get(lang, "never").isoformat() 
                    if isinstance(self._last_reset.get(lang), datetime) else "never"
            }
        return stats


class MultiRegionSearcher:
    """
    Wyszukiwarka dla wielu regionów jednocześnie.
    
    Użycie:
        searcher = MultiRegionSearcher(tavily_client, "tavily_queries")
        
        results = searcher.search_regions(
            regions=["US", "China", "Korea", "Japan"],
            queries_per_region=2
        )
    """
    
    def __init__(
        self,
        tavily_client,  # TavilyClient
        queries_dir: str = "tavily_queries"
    ):
        """
        Inicjalizuje searcher.
        
        Args:
            tavily_client: Instancja TavilyClient
            queries_dir: Ścieżka do katalogu z zapytaniami
        """
        self.client = tavily_client
        self.manager = TavilyQueryManager(queries_dir)
        self.rotator = QueryRotator(self.manager)
    
    def search_regions(
        self,
        regions: List[str],
        queries_per_region: int = 2,
        max_results_per_query: int = 5,
        search_depth: str = "advanced"
    ) -> Dict[str, List[Dict]]:
        """
        Wyszukuje dla wielu regionów.
        
        Args:
            regions: Lista regionów (np. ["US", "China", "Korea"])
            queries_per_region: Ile zapytań na region
            max_results_per_query: Max wyników na zapytanie
            search_depth: "basic" lub "advanced"
            
        Returns:
            Dict[region -> list of results]
        """
        results = {}
        
        for region in regions:
            queries = self.rotator.get_fresh(region, queries_per_region)
            region_results = []
            
            for query in queries:
                try:
                    response = self.client.search(
                        query=query,
                        search_depth=search_depth,
                        max_results=max_results_per_query
                    )
                    
                    for result in response.get("results", []):
                        result["_query"] = query
                        result["_region"] = region
                        result["_language"] = self.manager.get_language(region)
                        region_results.append(result)
                        
                except Exception as e:
                    logger.error(f"Błąd wyszukiwania '{query}': {e}")
            
            results[region] = region_results
            logger.info(f"{region}: {len(region_results)} wyników z {len(queries)} zapytań")
        
        return results


# === Demo ===
if __name__ == "__main__":
    import sys
    logger.remove()
    logger.add(sys.stderr, level='INFO')
    
    print("="*60)
    print("🔍 TAVILY QUERY MANAGER - DEMO")
    print("="*60)
    
    manager = TavilyQueryManager("tavily_queries")
    
    # Test dla różnych regionów
    test_regions = ["US", "China", "Korea", "Japan", "Germany", "Poland"]
    
    for region in test_regions:
        lang = manager.get_language(region)
        queries = manager.get_queries(region, count=3)
        
        print(f"\n📍 {region} ({lang}):")
        for q in queries:
            print(f"   • {q}")
    
    # Test rotatora
    print("\n" + "="*60)
    print("🔄 TEST ROTATORA")
    print("="*60)
    
    rotator = QueryRotator(manager)
    
    print("\nPierwsza partia (zh):")
    for q in rotator.get_fresh("zh", 3):
        print(f"   • {q}")
    
    print("\nDruga partia (zh) - inne zapytania:")
    for q in rotator.get_fresh("zh", 3):
        print(f"   • {q}")
    
    print("\nStatystyki:")
    print(json.dumps(rotator.get_stats(), indent=2, default=str))
