"""
LLM Sentiment Analyzer
======================
Analizator sentymentu używający LLM (Claude/OpenAI) do analizy tekstów kryptowalutowych.

Obsługuje:
- Analizę sentymentu z różnych regionów i języków
- Kontekst kulturowy i slang kryptowalutowy
- Obliczanie kosztów zapytań
- Zapis wyników do bazy danych
"""

import os
import json
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic SDK niedostępny - zainstaluj: pip install anthropic")

from src.database.manager import DatabaseManager
from src.database.models import LLMSentimentAnalysis

# Spróbuj zaimportować API logger
try:
    from src.utils.api_logger import APILogger
    API_LOGGER_AVAILABLE = True
except ImportError:
    API_LOGGER_AVAILABLE = False
    APILogger = None


class LLMSentimentAnalyzer:
    """
    Analizator sentymentu używający LLM.
    
    Obsługuje:
    - Claude (Anthropic)
    - Kontekst kulturowy i slang dla różnych języków
    - Obliczanie kosztów zapytań
    - Zapis wyników do bazy danych
    """
    
    # Słownik slangu dla różnych języków
    SLANG_CONTEXT = {
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
    
    # Cenniki modeli (USD za 1M tokenów) - input/output
    MODEL_PRICING = {
        # Anthropic Claude
        "claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
        "claude-3-opus-20240229": {"input": 10.0, "output": 30.0},
        "claude-3-sonnet-20240229": {"input": 3.0, "output": 15.0},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},  # Najnowszy model
    }
    
    # Kurs USD/PLN (można później pobierać z API)
    USD_TO_PLN = 4.0
    
    # Ścieżka do katalogu z szablonami promptów
    PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts" / "sentiment"
    
    # Mapowanie języków na dostępne pliki promptów
    # Jeśli język nie ma pliku, mapujemy na najbliższy dostępny
    LANGUAGE_TO_PROMPT_FILE = {
        # Języki z plikami promptów
        "ar": "ar",  # Arabic
        "de": "de",  # German
        "en": "en",  # English
        "es": "es",  # Spanish
        "fr": "fr",  # French
        "it": "it",  # Italian
        "ja": "ja",  # Japanese
        "ko": "ko",  # Korean
        "nl": "nl",  # Dutch
        "pl": "pl",  # Polish
        "pt": "pt",  # Portuguese
        "ru": "ru",  # Russian
        "zh": "zh",  # Chinese
        
        # Mapowanie języków bez plików na dostępne
        "sg": "en",  # Singapore - używa angielskiego (nie ma sg.txt)
        "cn": "zh",  # China - alternatywny kod
        "hk": "zh",  # Hong Kong - używa chińskiego
        "tw": "zh",  # Taiwan - używa chińskiego
        
        # Fallback dla nieznanych języków
        "default": "en",  # Domyślnie angielski
    }
    
    def __init__(
        self,
        model: str = "claude-3-5-haiku-20241022",  # Claude Haiku - tańszy model
        api_key: Optional[str] = None,
        database_url: Optional[str] = None,
        save_to_db: bool = True,
        log_prompts: bool = True
    ):
        """
        Inicjalizacja analizatora.
        
        Args:
            model: Nazwa modelu LLM
            api_key: Klucz API (lub z zmiennej środowiskowej)
            database_url: URL bazy danych (opcjonalnie)
            save_to_db: Czy zapisywać wyniki do bazy danych
            log_prompts: Czy logować prompty i odpowiedzi (domyślnie: True)
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic SDK niedostępny - zainstaluj: pip install anthropic")
        
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Brak ANTHROPIC_API_KEY - ustaw w .env lub przekaż jako parametr")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.save_to_db = save_to_db
        self.log_prompts = log_prompts
        
        # Inicjalizuj API logger jeśli dostępny i włączony
        self.api_logger = None
        if self.log_prompts and API_LOGGER_AVAILABLE:
            try:
                self.api_logger = APILogger(log_dir="logs")
                logger.debug("API Logger zainicjalizowany dla LLMSentimentAnalyzer")
            except Exception as e:
                logger.warning(f"Nie można zainicjalizować API Logger: {e}")
        
        if save_to_db:
            self.db = DatabaseManager(database_url=database_url)
            self.db.create_tables()
        
        logger.info(f"LLMSentimentAnalyzer zainicjalizowany: model={model}")
    
    def _load_prompt_template(self, language: str) -> str:
        """
        Ładuje szablon promptu dla danego języka.
        Za każdym razem ładuje z pliku (hot reload).
        
        Args:
            language: Kod języka (en, zh, ja, ko, etc.)
            
        Returns:
            Szablon promptu jako string
        """
        # Normalizuj język (lowercase)
        language = language.lower()
        
        # Mapuj język na dostępny plik promptu
        prompt_file_name = self.LANGUAGE_TO_PROMPT_FILE.get(language)
        if not prompt_file_name:
            # Jeśli język nie jest w mapowaniu, spróbuj użyć go bezpośrednio
            prompt_file_name = language
            logger.debug(f"Język {language} nie jest w mapowaniu, próbuję użyć bezpośrednio")
        
        # Spróbuj załadować plik dla zmapowanego języka
        prompt_file = self.PROMPTS_DIR / f"{prompt_file_name}.txt"
        
        # Jeśli plik nie istnieje, użyj angielskiego jako fallback
        if not prompt_file.exists():
            logger.debug(f"Brak promptu dla języka {language} (mapowany na {prompt_file_name}), używam en.txt")
            prompt_file_name = self.LANGUAGE_TO_PROMPT_FILE.get("default", "en")
            prompt_file = self.PROMPTS_DIR / f"{prompt_file_name}.txt"
        
        # Jeśli angielski też nie istnieje, użyj domyślnego promptu
        if not prompt_file.exists():
            logger.warning(f"Brak pliku promptu {prompt_file}, używam domyślnego promptu")
            return self._get_default_prompt_template()
        
        try:
            # Załaduj prompt z pliku (za każdym razem - hot reload)
            prompt_template = prompt_file.read_text(encoding='utf-8')
            logger.debug(f"Załadowano prompt z {prompt_file.name} dla języka {language}")
            return prompt_template
        except Exception as e:
            logger.error(f"Błąd ładowania promptu z {prompt_file}: {e}")
            return self._get_default_prompt_template()
    
    def _get_default_prompt_template(self) -> str:
        """
        Zwraca domyślny szablon promptu (fallback).
        
        Returns:
            Domyślny szablon promptu
        """
        return """Analyze aggregate crypto sentiment from {region} ({language}):

{slang_context}

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
    
    def _calculate_cost_pln(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Oblicza koszt zapytania w PLN.
        
        Args:
            input_tokens: Liczba tokenów wejściowych
            output_tokens: Liczba tokenów wyjściowych
            
        Returns:
            Koszt w PLN
        """
        pricing = self.MODEL_PRICING.get(self.model)
        if not pricing:
            logger.warning(f"Brak cennika dla modelu {self.model}, używam domyślnego")
            pricing = {"input": 3.0, "output": 15.0}
        
        # Oblicz koszt w USD
        cost_usd = (
            (input_tokens / 1_000_000) * pricing["input"] +
            (output_tokens / 1_000_000) * pricing["output"]
        )
        
        # Konwertuj na PLN
        cost_pln = cost_usd * self.USD_TO_PLN
        
        return cost_pln
    
    def analyze_sentiment(
        self,
        texts: List[str],
        region: str,
        language: str = "en",
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analizuje sentyment używając LLM.
        
        Args:
            texts: Lista tekstów do analizy
            region: Kod regionu (US, CN, JP, KR, DE, etc.)
            language: Kod języka (en, zh, ja, ko, etc.)
            symbol: Symbol kryptowaluty (opcjonalnie, dla zapisu do bazy)
            
        Returns:
            Dict z wynikami analizy + metadanymi (tokens, cost_pln)
        """
        if not texts:
            raise ValueError("Lista tekstów nie może być pusta")
        
        # Formatuj teksty (maksymalnie 20, każdy do 500 znaków)
        texts_formatted = "\n".join([f"- {t[:500]}" for t in texts[:20]])
        
        # Dodaj kontekst językowy jeśli dostępny
        lang_context = self.SLANG_CONTEXT.get(language, "")
        
        # Załaduj szablon promptu dla danego języka (hot reload)
        prompt_template = self._load_prompt_template(language)
        
        # Wypełnij szablon promptu
        prompt = prompt_template.format(
            region=region,
            language=language,
            slang_context=lang_context,
            texts_formatted=texts_formatted
        )

        try:
            # Przygotuj messages do logowania
            messages_for_log = [{"role": "user", "content": prompt}]
            
            # Loguj request jeśli włączone
            if self.api_logger:
                try:
                    self.api_logger.log_request(
                        provider="anthropic",
                        model=self.model,
                        messages=messages_for_log,
                        temperature=None,  # Anthropic nie używa temperature w messages.create
                        max_tokens=512,
                        metadata={
                            "method": "analyze_sentiment",
                            "region": region,
                            "language": language,
                            "symbol": symbol,
                            "texts_count": len(texts)
                        }
                    )
                except Exception as e:
                    logger.debug(f"Błąd logowania requestu: {e}")
            
            # Wywołaj API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Pobierz odpowiedź (zapisz surową odpowiedź przed parsowaniem)
            raw_response_text = response.content[0].text
            response_text = raw_response_text  # Kopia do parsowania
            
            # Loguj response jeśli włączone
            if self.api_logger:
                try:
                    # Pobierz usage z response
                    input_tokens = response.usage.input_tokens if hasattr(response, 'usage') else None
                    output_tokens = response.usage.output_tokens if hasattr(response, 'usage') else None
                    
                    self.api_logger.log_response(
                        provider="anthropic",
                        model=self.model,
                        response_text=raw_response_text,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        response_time_ms=None,  # Nie mierzymy czasu w tym miejscu
                        metadata={
                            "method": "analyze_sentiment",
                            "region": region,
                            "language": language,
                            "symbol": symbol
                        }
                    )
                except Exception as e:
                    logger.debug(f"Błąd logowania odpowiedzi: {e}")
            
            # LLM może zwrócić JSON w markdown code block - usuń go jeśli istnieje
            if "```json" in response_text:
                # Wyciągnij JSON z markdown code block
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end != -1:
                    response_text = response_text[start:end].strip()
            elif "```" in response_text:
                # Wyciągnij JSON z code block bez języka
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                if end != -1:
                    response_text = response_text[start:end].strip()
            
            # Usuń ewentualne białe znaki na początku/końcu
            response_text = response_text.strip()
            
            # Spróbuj parsować JSON
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # Jeśli nie jest to czysty JSON, spróbuj znaleźć JSON w tekście
                import re
                json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise ValueError(f"Nie można znaleźć JSON w odpowiedzi: {response_text[:200]}")
            
            # Pobierz metadane z odpowiedzi
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            
            # Oblicz koszt
            cost_pln = self._calculate_cost_pln(input_tokens, output_tokens)
            
            # Dodaj metadane do wyniku (włączając prompt i surową odpowiedź)
            result.update({
                "llm_model": self.model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "cost_pln": cost_pln,
                "region": region,
                "language": language,
                "texts_count": len(texts),
                "timestamp": datetime.now(timezone.utc),
                "prompt": prompt,  # Zapisz pełny prompt
                "response": raw_response_text  # Zapisz surową odpowiedź (przed parsowaniem)
            })
            
            # Zapisz do bazy danych jeśli włączone
            if self.save_to_db and symbol:
                self._save_to_database(result, symbol)
            
            logger.info(
                f"Analiza sentymentu: {result['sentiment']} "
                f"(score: {result['score']:+.2f}, confidence: {result['confidence']:.2f}, "
                f"cost: {cost_pln:.4f} PLN)"
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Błąd parsowania JSON z LLM: {e}")
            logger.error(f"Odpowiedź: {response_text[:500]}")
            raise
        except Exception as e:
            logger.error(f"Błąd podczas analizy sentymentu: {e}")
            raise
    
    def _save_to_database(
        self,
        result: Dict[str, Any],
        symbol: str
    ):
        """
        Zapisuje wynik analizy do bazy danych.
        
        Args:
            result: Wynik analizy z metadanymi
            symbol: Symbol kryptowaluty
        """
        try:
            # Przygotuj dane do zapisu
            llm_sentiment = LLMSentimentAnalysis(
                timestamp=result["timestamp"],
                symbol=symbol,
                region=result["region"],
                language=result["language"],
                llm_model=result["llm_model"],
                sentiment=result["sentiment"],
                score=result["score"],
                confidence=result["confidence"],
                fud_level=result.get("fud_level"),
                fomo_level=result.get("fomo_level"),
                market_impact=result.get("market_impact"),
                key_topics=json.dumps(result.get("key_topics", [])),
                reasoning=result.get("reasoning"),
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
                total_tokens=result["total_tokens"],
                cost_pln=result["cost_pln"],
                texts_count=result["texts_count"],
                prompt=result.get("prompt"),  # Zapisz prompt
                response=result.get("response"),  # Zapisz surową odpowiedź
                web_search_query=result.get("web_search_query"),  # Zapisz zapytanie Web Search
                web_search_response=result.get("web_search_response"),  # Zapisz odpowiedź Web Search
                web_search_answer=result.get("web_search_answer"),  # Zapisz podsumowanie AI z Web Search
                web_search_results_count=result.get("web_search_results_count")  # Zapisz liczbę wyników
            )
            
            # Zapisz do bazy
            with self.db.get_session() as session:
                session.add(llm_sentiment)
                session.commit()
            
            logger.debug(f"Zapisano analizę sentymentu LLM do bazy: {symbol} @ {result['timestamp']}")
            
        except Exception as e:
            logger.error(f"Błąd podczas zapisu do bazy danych: {e}")
            # Nie przerywamy - analiza się powiodła, tylko zapis nie


# Funkcja pomocnicza dla łatwego użycia
def analyze_sentiment(
    texts: List[str],
    region: str,
    language: str = "en",
    symbol: Optional[str] = None,
    model: str = "claude-3-5-haiku-20241022",  # Claude Haiku - tańszy model
    save_to_db: bool = True
) -> Dict[str, Any]:
    """
    Funkcja pomocnicza do analizy sentymentu.
    
    Args:
        texts: Lista tekstów do analizy
        region: Kod regionu (US, CN, JP, KR, DE, etc.)
        language: Kod języka (en, zh, ja, ko, etc.)
        symbol: Symbol kryptowaluty (opcjonalnie, dla zapisu do bazy)
        model: Nazwa modelu LLM
        save_to_db: Czy zapisywać wyniki do bazy danych
        
    Returns:
        Dict z wynikami analizy
    """
    analyzer = LLMSentimentAnalyzer(model=model, save_to_db=save_to_db)
    return analyzer.analyze_sentiment(texts, region, language, symbol)

