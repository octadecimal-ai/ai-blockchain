"""
Web Search for LLM
==================
Moduł do wyszukiwania informacji w internecie dla LLM.

Domyślnie używa DuckDuckGo (całkowicie darmowe, bez API key).
Alternatywnie może używać Google Custom Search API lub Serper API.
"""

import os
import time
import requests
from requests.exceptions import HTTPError, ConnectTimeout, Timeout
from typing import List, Dict, Optional, Any
from datetime import datetime
from loguru import logger


class WebSearchEngine:
    """
    Silnik wyszukiwania w internecie dla LLM.
    
    Domyślnie używa DuckDuckGo (całkowicie darmowe, bez API key).
    Alternatywnie może używać Google Custom Search API lub Serper API.
    """
    
    def __init__(self, provider: str = "duckduckgo"):
        """
        Inicjalizacja silnika wyszukiwania.
        
        Args:
            provider: "duckduckgo" (domyślny, darmowe), "tavily", "serper", "google"
        """
        self.provider = provider
        
        # Tavily - zoptymalizowane dla LLM, zwraca podsumowanie AI
        if provider == "tavily":
            self.api_key = os.getenv('TAVILY_API_KEY')
            self.cse_id = None
            self.api_url = "https://api.tavily.com/search"
            if not self.api_key:
                logger.warning("Brak TAVILY_API_KEY - Tavily będzie niedostępne")
            else:
                logger.info("Tavily wybrane - zoptymalizowane dla LLM, zwraca podsumowanie AI")
        
        # DuckDuckGo - domyślny, całkowicie darmowe
        elif provider == "duckduckgo":
            self.api_key = None
            self.cse_id = None
            self.api_url = None  # Używamy biblioteki duckduckgo-search lub HTML scraping
            logger.info("DuckDuckGo wybrane - całkowicie darmowe, bez API key")
        elif provider == "google":
            self.api_key = os.getenv('GOOGLE_API_KEY')
            self.cse_id = os.getenv('GOOGLE_CSE_ID')  # Custom Search Engine ID
            self.api_url = "https://www.googleapis.com/customsearch/v1"
            if not self.api_key or not self.cse_id:
                logger.warning("Brak GOOGLE_API_KEY lub GOOGLE_CSE_ID - Google Custom Search będzie niedostępne")
        elif provider == "serper":
            self.api_key = os.getenv('SERPER_API_KEY')
            self.api_url = "https://google.serper.dev/search"
            self.cse_id = None
            if not self.api_key:
                logger.warning("Brak SERPER_API_KEY - web search będzie niedostępne")
        else:
            raise ValueError(f"Nieznany provider: {provider}. Dostępne: duckduckgo (darmowe), google, serper")
    
    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",  # "basic" lub "advanced" dla Tavily
        include_answer: bool = True,
        include_raw_content: bool = False,
        region: Optional[str] = None,  # Region DuckDuckGo (np. 'us-en', 'de-de', 'jp-jp')
        language: Optional[str] = None  # Język (np. 'en', 'de', 'pl') - używany tylko dla HTML scraping
    ) -> Dict[str, Any]:
        """
        Wyszukuje informacje w internecie.
        
        Args:
            query: Zapytanie wyszukiwania
            max_results: Maksymalna liczba wyników
            search_depth: Głębokość wyszukiwania (dla Tavily)
            include_answer: Czy dołączyć odpowiedź AI (dla Tavily)
            include_raw_content: Czy dołączyć surową treść (dla Tavily)
            region: Region DuckDuckGo (np. 'us-en', 'de-de', 'jp-jp') - dla biblioteki DDGS
            language: Język dla HTML scraping (np. 'en-US', 'de-DE', 'pl-PL') - używany tylko dla HTML scraping
            
        Returns:
            Słownik z wynikami wyszukiwania
        """
        # Sprawdź dostępność API key (DuckDuckGo nie wymaga)
        if self.provider != "duckduckgo" and not self.api_key:
            # Google wymaga też CSE ID
            if self.provider == "google" and not self.cse_id:
                return {
                    "success": False,
                    "error": f"Brak GOOGLE_API_KEY lub GOOGLE_CSE_ID",
                    "results": []
                }
            elif self.provider == "tavily":
                return {
                    "success": False,
                    "error": f"Brak TAVILY_API_KEY",
                    "results": []
                }
            elif self.provider != "google" and self.provider != "tavily":
                return {
                    "success": False,
                    "error": f"Brak API key dla {self.provider}",
                    "results": []
                }
        
        try:
            if self.provider == "duckduckgo":
                # Dla języków azjatyckich (ja, ko, zh) DuckDuckGo często ma timeouty
                # Użyj od razu Tavily/Google zamiast DuckDuckGo
                asian_languages = ['ja', 'ko', 'zh', 'ja-JP', 'ko-KR', 'zh-CN', 'zh-HK', 'zh-TW']
                is_asian_language = language and any(lang in language for lang in asian_languages)
                
                # Jeśli język azjatycki i mamy Tavily/Google, użyj ich od razu
                if is_asian_language:
                    if os.getenv('TAVILY_API_KEY'):
                        logger.info(f"Język azjatycki ({language}) - używam Tavily zamiast DuckDuckGo dla: {query[:50]}...")
                        try:
                            tavily_engine = WebSearchEngine(provider="tavily")
                            tavily_result = tavily_engine.search(query, max_results, search_depth, include_answer, include_raw_content)
                            if tavily_result.get("success"):
                                logger.success(f"✅ Tavily zakończone sukcesem dla języka azjatyckiego: {query[:50]}...")
                                return tavily_result
                        except Exception as e:
                            logger.warning(f"Tavily nie powiodło się dla języka azjatyckiego: {e}")
                    
                    if os.getenv('GOOGLE_API_KEY') and os.getenv('GOOGLE_CSE_ID'):
                        logger.info(f"Język azjatycki ({language}) - używam Google zamiast DuckDuckGo dla: {query[:50]}...")
                        try:
                            google_engine = WebSearchEngine(provider="google")
                            google_result = google_engine.search(query, max_results)
                            if google_result.get("success"):
                                logger.success(f"✅ Google zakończone sukcesem dla języka azjatyckiego: {query[:50]}...")
                                return google_result
                        except Exception as e:
                            logger.warning(f"Google nie powiodło się dla języka azjatyckiego: {e}")
                
                # Dla innych języków lub jeśli Tavily/Google nie są dostępne, użyj DuckDuckGo
                result = self._search_duckduckgo(query, max_results, region=region, language=language)
                # Jeśli DuckDuckGo nie powiódł się, spróbuj fallback: najpierw Tavily, potem Google
                if not result.get("success"):
                    # Fallback 1: Tavily (jeśli dostępne)
                    tavily_success = False
                    if os.getenv('TAVILY_API_KEY'):
                        logger.info(f"DuckDuckGo nie powiódł się ({result.get('error', 'nieznany błąd')[:50]}), próbuję Tavily jako fallback dla: {query[:50]}...")
                        try:
                            tavily_engine = WebSearchEngine(provider="tavily")
                            tavily_result = tavily_engine.search(query, max_results, search_depth, include_answer, include_raw_content)
                            if tavily_result.get("success"):
                                logger.success(f"✅ Tavily fallback zakończony sukcesem dla: {query[:50]}...")
                                return tavily_result
                            else:
                                logger.warning(f"Tavily fallback również nie powiódł się: {tavily_result.get('error', 'nieznany błąd')[:100]}")
                                tavily_success = False
                        except Exception as e:
                            logger.warning(f"Tavily fallback wywołał wyjątek: {e}")
                            tavily_success = False
                    
                    # Fallback 2: Google (tylko jeśli Tavily nie powiodło się lub nie jest dostępne)
                    if not tavily_success and os.getenv('GOOGLE_API_KEY') and os.getenv('GOOGLE_CSE_ID'):
                        logger.info(f"DuckDuckGo nie powiódł się ({result.get('error', 'nieznany błąd')[:50]}), próbuję Google jako fallback dla: {query[:50]}...")
                        try:
                            google_engine = WebSearchEngine(provider="google")
                            google_result = google_engine.search(query, max_results)
                            if google_result.get("success"):
                                logger.success(f"✅ Google fallback zakończony sukcesem dla: {query[:50]}...")
                                return google_result
                            else:
                                logger.warning(f"Google fallback również nie powiódł się: {google_result.get('error', 'nieznany błąd')[:100]}")
                        except Exception as e:
                            logger.warning(f"Google fallback wywołał wyjątek: {e}")
                return result
            elif self.provider == "tavily":
                return self._search_tavily(query, max_results, search_depth, include_answer, include_raw_content)
            elif self.provider == "google":
                return self._search_google(query, max_results)
            elif self.provider == "serper":
                return self._search_serper(query, max_results)
            else:
                return {
                    "success": False,
                    "error": f"Nieobsługiwany provider: {self.provider}",
                    "results": []
                }
        except requests.exceptions.HTTPError as e:
            # Loguj szczegóły błędu HTTP
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json() if e.response.text else {}
                    error_msg = f"{e.response.status_code}: {error_detail.get('error', e.response.text[:200])}"
                except:
                    error_msg = f"{e.response.status_code}: {e.response.text[:200] if e.response.text else 'Brak szczegółów'}"
            logger.error(f"Błąd wyszukiwania w internecie: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "results": []
            }
        except Exception as e:
            logger.error(f"Błąd wyszukiwania w internecie: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }
    
    def _search_tavily(
        self,
        query: str,
        max_results: int,
        search_depth: str,
        include_answer: bool,
        include_raw_content: bool
    ) -> Dict[str, Any]:
        """Wyszukiwanie przez Tavily API."""
        import time
        
        # Rate limiting - czekaj 1 sekundę między requestami aby uniknąć przekroczenia limitu
        time.sleep(1.0)
        
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content
        }
        
        try:
            response = requests.post(self.api_url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.HTTPError as e:
            # Jeśli to błąd 432 (limit), zwróć szczegółowy komunikat
            if e.response.status_code == 432:
                try:
                    error_detail = e.response.json()
                    error_msg = error_detail.get("detail", {}).get("error", "Limit planu przekroczony")
                    raise requests.exceptions.HTTPError(f"432: {error_msg}", response=e.response)
                except:
                    raise
            raise
        
        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0.0)
            })
        
        return {
            "success": True,
            "query": query,
            "answer": data.get("answer", ""),  # AI-generated answer
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    
    def _search_serper(self, query: str, max_results: int) -> Dict[str, Any]:
        """Wyszukiwanie przez Serper API."""
        payload = {
            "q": query,
            "num": max_results
        }
        
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("organic", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "position": item.get("position", 0)
            })
        
        return {
            "success": True,
            "query": query,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    
    def _search_google(self, query: str, max_results: int) -> Dict[str, Any]:
        """
        Wyszukiwanie przez Google Custom Search API.
        
        Wymaga:
        - GOOGLE_API_KEY: Klucz API z Google Cloud Console
        - GOOGLE_CSE_ID: ID Custom Search Engine (utworzone w https://programmablesearchengine.google.com/)
        
        Koszty:
        - Darmowy tier: 100 zapytań dziennie (bezpłatnie)
        - Po przekroczeniu: ~$5 za 1000 zapytań
        - Wymaga karty kredytowej (ale darmowy tier nie pobiera opłat)
        
        Zalety:
        - Bardzo niezawodne (rzadko timeouty)
        - Szybkie odpowiedzi
        - Wysoka jakość wyników
        """
        if not self.api_key or not self.cse_id:
            return {
                "success": False,
                "error": "Brak GOOGLE_API_KEY lub GOOGLE_CSE_ID",
                "results": []
            }
        
        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": min(max_results, 10)  # Google API max 10 wyników na zapytanie
        }
        
        try:
            response = requests.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "content": item.get("snippet", ""),  # Google zwraca tylko snippet
                })
            
            return {
                "success": True,
                "query": query,
                "results": results,
                "timestamp": datetime.now().isoformat()
            }
        except requests.exceptions.HTTPError as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", {}).get("message", str(e))
                except:
                    error_msg = f"{e.response.status_code}: {e.response.text[:200] if e.response.text else 'Brak szczegółów'}"
            raise requests.exceptions.HTTPError(error_msg, response=e.response if hasattr(e, 'response') else None)
    
    def _search_duckduckgo(self, query: str, max_results: int, region: Optional[str] = None, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Wyszukiwanie przez DuckDuckGo (całkowicie darmowe, bez API key).
        
        Używa bezpośredniego HTML scraping przez requests (jak curl/wget).
        Nie wymaga żadnych dodatkowych bibliotek - tylko requests (już w projekcie).
        
        Args:
            query: Zapytanie wyszukiwania
            max_results: Maksymalna liczba wyników
            region: Region DuckDuckGo (np. 'us-en', 'de-de', 'jp-jp') - dla biblioteki DDGS
            language: Język dla HTML scraping (np. 'en-US', 'de-DE', 'pl-PL')
        """
        try:
            # Metoda 1: Spróbuj użyć biblioteki ddgs (nowa nazwa) lub duckduckgo_search (stara nazwa)
            try:
                # Najpierw spróbuj nowej nazwy pakietu (ddgs)
                try:
                    from ddgs import DDGS
                except ImportError:
                    # Fallback do starej nazwy (duckduckgo_search)
                    from duckduckgo_search import DDGS
                
                results = []
                # DDGS.text() przyjmuje parametr 'region' (np. 'us-en', 'de-de', 'jp-jp')
                with DDGS() as ddgs:
                    for r in ddgs.text(query, region=region, max_results=max_results):
                        results.append({
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", ""),
                            "content": r.get("body", ""),
                        })
                
                if results:
                    return {
                        "success": True,
                        "query": query,
                        "results": results,
                        "timestamp": datetime.now().isoformat()
                    }
            except ImportError:
                pass  # Przejdź do HTML scraping
            except Exception as e:
                # Jeśli DDGS nie działa (np. błąd SSL/TLS), użyj HTML scraping
                error_msg = str(e)
                if "protocol version" in error_msg.lower() or "ssl" in error_msg.lower() or "tls" in error_msg.lower():
                    logger.debug(f"DDGS nie działa z powodu błędu SSL/TLS ({error_msg}), używam HTML scraping")
                else:
                    logger.debug(f"DDGS nie działa ({error_msg}), używam HTML scraping")
                # Przejdź do HTML scraping
            
            # Metoda 2: HTML scraping przez requests (jak curl/wget) - nie wymaga bibliotek
            return self._search_duckduckgo_html(query, max_results, language=language)
                
        except Exception as e:
            logger.error(f"Błąd wyszukiwania DuckDuckGo: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }
    
    def _search_duckduckgo_html(self, query: str, max_results: int, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Wyszukiwanie przez DuckDuckGo używając HTML scraping (jak curl/wget).
        
        Bezpośrednio pobiera HTML z DuckDuckGo i parsuje wyniki używając regex.
        Całkowicie darmowe, bez API key, bez dodatkowych bibliotek (tylko requests).
        
        Args:
            query: Zapytanie wyszukiwania
            max_results: Maksymalna liczba wyników
            language: Język (np. 'en-US', 'de-DE', 'pl-PL') - dodawany jako parametr 'kl' do URL
        """
        import re
        
        # DuckDuckGo HTML search URL
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        
        # Dodaj język jeśli podany (parametr 'kl' w DuckDuckGo)
        if language:
            params["kl"] = language  # np. 'en-US', 'de-DE', 'pl-PL'
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": language or "en-US,en;q=0.9"  # Dodaj Accept-Language header
        }
        
        # Retry logic z exponential backoff (3 próby)
        max_retries = 3
        base_delay = 2  # sekundy
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(f"DuckDuckGo HTML scraping - próba {attempt}/{max_retries} dla zapytania: {query[:50]}...")
                response = requests.get(url, params=params, headers=headers, timeout=30)  # Zwiększony timeout z 15s do 30s
                response.raise_for_status()
                break  # Sukces - wyjdź z pętli retry
            except (ConnectTimeout, Timeout) as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))  # Exponential backoff: 2s, 4s, 8s
                    logger.warning(f"Timeout DuckDuckGo HTML scraping (próba {attempt}/{max_retries}): {e}. Czekam {delay}s przed ponowną próbą...")
                    time.sleep(delay)
                else:
                    logger.error(f"Timeout DuckDuckGo HTML scraping po {max_retries} próbach: {e}")
                    # Fallback do Instant Answer API
                    return self._search_duckduckgo_instant(query, max_results)
            except Exception as e:
                # Inne błędy - nie retry, od razu fallback
                logger.error(f"Błąd HTML scraping DuckDuckGo: {e}")
                logger.debug(f"Szczegóły błędu: {str(e)}")
                # Fallback do Instant Answer API
                return self._search_duckduckgo_instant(query, max_results)
        
        try:
            
            html = response.text
            results = []
            
            # Parsuj HTML - DuckDuckGo używa różnych formatów HTML
            # Szukamy wyników w strukturze HTML używając regex
            
            # Pattern 1: Nowy format DuckDuckGo (klasy result, result__a, result__title, result__snippet)
            # Format: <a class="result__a" href="URL">...</a> <h2 class="result__title">TITLE</h2> <a class="result__snippet">SNIPPET</a>
            pattern1 = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>.*?<h2[^>]*class="result__title"[^>]*>([^<]*)</h2>.*?<a[^>]*class="result__snippet"[^>]*>([^<]*)</a>'
            
            # Pattern 2: Alternatywny format (web-result)
            pattern2 = r'<a[^>]*class="[^"]*web-result[^"]*"[^>]*href="([^"]*)"[^>]*>.*?<h2[^>]*>([^<]*)</h2>.*?<span[^>]*>([^<]*)</span>'
            
            # Pattern 3: Prostszy - szukaj linków z tytułami w blokach wyników
            pattern3 = r'<div[^>]*class="[^"]*result[^"]*"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>.*?<h2[^>]*>([^<]*)</h2>.*?</a>.*?<span[^>]*>([^<]{20,200})</span>'
            
            # Spróbuj każdy pattern
            for pattern in [pattern1, pattern2, pattern3]:
                matches = re.finditer(pattern, html, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    if len(results) >= max_results:
                        break
                    
                    url_result = match.group(1)
                    title = match.group(2).strip()
                    snippet = match.group(3).strip() if len(match.groups()) > 2 else ""
                    
                    # Oczyszcz HTML entities i białe znaki
                    title = re.sub(r'\s+', ' ', title).strip()
                    snippet = re.sub(r'\s+', ' ', snippet).strip()
                    
                    # Pomiń jeśli URL nie wygląda na prawidłowy
                    if not url_result.startswith('http'):
                        continue
                    
                    # Oczyszcz HTML entities
                    for entity, char in [('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"'), ('&#39;', "'")]:
                        title = title.replace(entity, char)
                        snippet = snippet.replace(entity, char)
                    
                    results.append({
                        "title": title,
                        "url": url_result,
                        "snippet": snippet,
                        "content": snippet,
                    })
                
                if results:
                    break  # Jeśli znaleziono wyniki, przerwij
            
            # Jeśli nie znaleziono wyników, spróbuj prostszego parsowania
            if not results:
                # Prostsze parsowanie - szukaj wszystkich linków z tytułami w różnych formatach
                # Pattern 1: Link z tytułem w h2
                link_pattern1 = r'<a[^>]*href="(https?://[^"]+)"[^>]*>.*?<h2[^>]*>([^<]{10,150})</h2>'
                # Pattern 2: Link z tytułem w span lub div
                link_pattern2 = r'<a[^>]*href="(https?://[^"]+)"[^>]*>.*?<[^>]*class="[^"]*title[^"]*"[^>]*>([^<]{10,150})</[^>]*>'
                # Pattern 3: Prosty link z tekstem
                link_pattern3 = r'<a[^>]*href="(https?://[^"]+)"[^>]*>([^<]{10,150})</a>'
                
                for link_pattern in [link_pattern1, link_pattern2, link_pattern3]:
                    matches = re.finditer(link_pattern, html, re.DOTALL | re.IGNORECASE)
                    for match in matches:
                        if len(results) >= max_results:
                            break
                        url_result = match.group(1)
                        title = match.group(2).strip()
                        
                        # Pomiń jeśli URL nie wygląda na prawidłowy lub to duplikat
                        if not url_result.startswith('http') or any(r.get("url") == url_result for r in results):
                            continue
                        
                        # Oczyszcz HTML entities i białe znaki
                        title = re.sub(r'\s+', ' ', title).strip()
                        for entity, char in [('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"'), ('&#39;', "'"), ('&nbsp;', ' ')]:
                            title = title.replace(entity, char)
                        
                        # Pomiń jeśli tytuł za krótki lub wygląda na nieprawidłowy
                        if len(title) < 10 or title.lower() in ['skip', 'next', 'more', 'click here']:
                            continue
                        
                        results.append({
                            "title": title,
                            "url": url_result,
                            "snippet": "",
                            "content": "",
                        })
                    
                    if results:
                        break  # Jeśli znaleziono wyniki, przerwij
            
            # Jeśli nadal brak wyników, użyj Instant Answer API jako fallback
            if not results:
                logger.debug("HTML scraping nie zwrócił wyników, używam Instant Answer API")
                return self._search_duckduckgo_instant(query, max_results)
            
            return {
                "success": True,
                "query": query,
                "results": results[:max_results],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Błąd parsowania HTML DuckDuckGo: {e}")
            logger.debug(f"Szczegóły błędu: {str(e)}")
            # Fallback do Instant Answer API
            return self._search_duckduckgo_instant(query, max_results)
    
    def _search_duckduckgo_instant(self, query: str, max_results: int) -> Dict[str, Any]:
        """
        Fallback: DuckDuckGo Instant Answer API (ograniczone wyniki).
        """
        # DuckDuckGo Instant Answer API (darmowe, bez API key)
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1"
        }
        
        # Retry logic z exponential backoff (3 próby)
        max_retries = 3
        base_delay = 1.5  # sekundy
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(f"DuckDuckGo Instant Answer API - próba {attempt}/{max_retries} dla zapytania: {query[:50]}...")
                response = requests.get(url, params=params, timeout=20)  # Zwiększony timeout z 10s do 20s
                response.raise_for_status()
                data = response.json()
                break  # Sukces - wyjdź z pętli retry
            except (ConnectTimeout, Timeout) as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))  # Exponential backoff: 1.5s, 3s, 6s
                    logger.warning(f"Timeout DuckDuckGo Instant Answer API (próba {attempt}/{max_retries}): {e}. Czekam {delay}s przed ponowną próbą...")
                    time.sleep(delay)
                else:
                    logger.error(f"Timeout DuckDuckGo Instant Answer API po {max_retries} próbach: {e}")
                    return {
                        "success": False,
                        "error": f"Timeout po {max_retries} próbach: {str(e)}",
                        "results": []
                    }
            except Exception as e:
                # Inne błędy - nie retry, zwróć błąd
                logger.error(f"Błąd DuckDuckGo Instant Answer API: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "results": []
                }
        
        # Przetwarzanie wyników (jeśli dotarliśmy tutaj, mamy dane)
        results = []
        
        # Abstract (podsumowanie)
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", query),
                "url": data.get("AbstractURL", ""),
                "snippet": data.get("AbstractText", ""),
                "content": data.get("AbstractText", ""),
            })
        
        # Related Topics
        for topic in data.get("RelatedTopics", [])[:max_results-1]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append({
                    "title": topic.get("FirstURL", "").split("/")[-1] if topic.get("FirstURL") else "",
                    "url": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", ""),
                    "content": topic.get("Text", ""),
                })
        
        return {
            "success": True,
            "query": query,
            "results": results[:max_results],
            "timestamp": datetime.now().isoformat()
        }
    
    def search_crypto_news(
        self,
        symbol: str = "BTC",
        topics: Optional[List[str]] = None,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        Wyszukuje wiadomości o kryptowalutach.
        
        Args:
            symbol: Symbol kryptowaluty (BTC, ETH, etc.)
            topics: Lista tematów (np. ["regulacje", "adopcja", "technologia"])
            max_results: Maksymalna liczba wyników
            
        Returns:
            Słownik z wynikami wyszukiwania
        """
        topics = topics or ["news", "regulations", "adoption", "technology"]
        
        queries = []
        for topic in topics:
            queries.append(f"{symbol} {topic} cryptocurrency news")
        
        all_results = []
        for query in queries:
            search_result = self.search(query, max_results=max_results)
            if search_result.get("success"):
                all_results.extend(search_result.get("results", []))
        
        # Usuń duplikaty (po URL)
        seen_urls = set()
        unique_results = []
        for result in all_results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
        
        return {
            "success": True,
            "symbol": symbol,
            "results": unique_results[:max_results],
            "timestamp": datetime.now().isoformat()
        }
    
    def search_political_news(
        self,
        symbol: str = "BTC",
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        Wyszukuje wiadomości polityczne dotyczące kryptowalut.
        
        Args:
            symbol: Symbol kryptowaluty
            max_results: Maksymalna liczba wyników
            
        Returns:
            Słownik z wynikami wyszukiwania
        """
        queries = [
            f"{symbol} cryptocurrency regulations government",
            f"{symbol} crypto policy news",
            f"cryptocurrency regulations {symbol} 2024"
        ]
        
        all_results = []
        for query in queries:
            search_result = self.search(query, max_results=max_results)
            if search_result.get("success"):
                all_results.extend(search_result.get("results", []))
        
        # Usuń duplikaty
        seen_urls = set()
        unique_results = []
        for result in all_results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
        
        return {
            "success": True,
            "symbol": symbol,
            "category": "political",
            "results": unique_results[:max_results],
            "timestamp": datetime.now().isoformat()
        }
    
    def search_tech_news(
        self,
        symbol: str = "BTC",
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        Wyszukuje wiadomości technologiczne dotyczące kryptowalut.
        
        Args:
            symbol: Symbol kryptowaluty
            max_results: Maksymalna liczba wyników
            
        Returns:
            Słownik z wynikami wyszukiwania
        """
        queries = [
            f"{symbol} blockchain technology updates",
            f"{symbol} cryptocurrency development news",
            f"{symbol} crypto adoption institutional"
        ]
        
        all_results = []
        for query in queries:
            search_result = self.search(query, max_results=max_results)
            if search_result.get("success"):
                all_results.extend(search_result.get("results", []))
        
        # Usuń duplikaty
        seen_urls = set()
        unique_results = []
        for result in all_results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
        
        return {
            "success": True,
            "symbol": symbol,
            "category": "technology",
            "results": unique_results[:max_results],
            "timestamp": datetime.now().isoformat()
        }
    
    def format_search_results_for_prompt(self, search_results: Dict[str, Any]) -> str:
        """
        Formatuje wyniki wyszukiwania do prompta dla LLM.
        
        Args:
            search_results: Wyniki z search() lub search_crypto_news()
            
        Returns:
            Sformatowany tekst do prompta
        """
        if not search_results.get("success"):
            return f"\n⚠️ Wyszukiwanie w internecie niedostępne: {search_results.get('error', 'Nieznany błąd')}"
        
        lines = ["\n=== WYNIKI WYSZUKIWANIA W INTERNECIE ==="]
        
        # Odpowiedź AI (jeśli dostępna z Tavily)
        if "answer" in search_results and search_results["answer"]:
            lines.append(f"\n🤖 Podsumowanie AI:")
            lines.append(f"   {search_results['answer']}")
        
        # Wyniki wyszukiwania
        results = search_results.get("results", [])
        if results:
            lines.append(f"\n📰 Znalezione informacje ({len(results)} wyników):")
            for i, result in enumerate(results[:5], 1):  # Max 5 wyników
                title = result.get("title", "Brak tytułu")
                url = result.get("url", "")
                content = result.get("content") or result.get("snippet", "")
                
                lines.append(f"\n{i}. {title}")
                if url:
                    lines.append(f"   Źródło: {url}")
                if content:
                    # Ogranicz długość treści
                    content_preview = content[:300] + "..." if len(content) > 300 else content
                    lines.append(f"   {content_preview}")
        else:
            lines.append("\n   Brak wyników wyszukiwania")
        
        lines.append("\n" + "="*50)
        
        return "\n".join(lines)


# Singleton instance
_web_search_instance: Optional[WebSearchEngine] = None


def get_web_search_engine() -> WebSearchEngine:
    """
    Zwraca singleton instance WebSearchEngine.
    
    Returns:
        WebSearchEngine instance
    """
    global _web_search_instance
    if _web_search_instance is None:
        _web_search_instance = WebSearchEngine()
    return _web_search_instance

