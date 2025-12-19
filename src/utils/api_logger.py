"""
API Logger
==========
Moduł do logowania wszystkich requestów i odpowiedzi z API LLM.
Logi są zapisywane TYLKO do pliku, bez wyświetlania w konsoli.
"""

import os
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List
from loguru import logger


class APILogger:
    """
    Logger dla requestów i odpowiedzi API LLM.
    
    Zapisuje wszystkie requesty i odpowiedzi do osobnego pliku logu.
    Logi NIE są wyświetlane w konsoli - tylko zapisywane do pliku.
    """
    
    def __init__(self, log_dir: str = "logs"):
        """
        Inicjalizacja loggera.
        
        Args:
            log_dir: Katalog do zapisu logów
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Utwórz całkowicie nowy logger tylko do pliku (bez wyświetlania w konsoli)
        # Używamy unikalnej nazwy, aby odróżnić nasze logi od innych
        self.logger_name = "api_llm_file_only"
        
        # Usuń domyślny handler konsoli (jeśli istnieje)
        # Następnie dodamy go z powrotem z filtrem, który odrzuca nasze logi
        logger.remove()  # Usuń wszystkie domyślne handlery
        
        # Dodaj handler konsoli z filtrem, który odrzuca logi z naszą nazwą
        def console_filter(record):
            """Filtr odrzucający logi z api_llm_file_only"""
            extra = record.get("extra", {})
            # Odrzuć logi z naszą nazwą - nie wyświetlaj ich w konsoli
            return extra.get("name") != self.logger_name
        
        logger.add(
            sys.stderr,  # Domyślny handler konsoli
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
            filter=console_filter,
            colorize=True
        )
        
        # Dodaj handler do pliku z filtrem
        # Ten handler będzie akceptował tylko logi z naszą nazwą
        # i nie będzie propagował ich do innych handlerów (konsola)
        log_file = self.log_dir / f"api_llm_requests_{datetime.now().strftime('%Y-%m-%d')}.log"
        
        # Funkcja filtrująca - akceptuje tylko logi z naszą nazwą
        def api_log_filter(record):
            """Filtr akceptujący tylko logi z api_llm_file_only"""
            # Sprawdź czy record ma naszą nazwę w extra
            extra = record.get("extra", {})
            # Tylko logi z naszą nazwą przejdą przez filtr
            # Wszystkie inne logi zostaną odrzucone przez ten handler
            return extra.get("name") == self.logger_name
        
        handler_id = logger.add(
            str(log_file),
            rotation="1 day",
            retention="90 days",  # Przechowuj logi przez 90 dni
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
            encoding="utf-8",
            filter=api_log_filter,
            enqueue=False,  # Nie używaj kolejki, aby uniknąć propagacji
            colorize=False  # Wyłącz kolory (niepotrzebne w pliku)
        )
        
        # Zapisz ID handlera
        self._handler_id = handler_id
        
        # Utwórz bindowany logger z naszą nazwą
        self.api_logger = logger.bind(name=self.logger_name)
        
        # Statystyki tokenów i kosztów w sesji
        self.session_stats = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_requests": 0,
            "total_errors": 0,
            "model_usage": {}  # {model: {"input": int, "output": int}}
        }
        
        # Cenniki modeli (USD za 1M tokenów) - input/output
        self.model_pricing = {
            # Anthropic
            "claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},
            "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
            "claude-3-opus-20240229": {"input": 10.0, "output": 30.0},
            "claude-3-sonnet-20240229": {"input": 3.0, "output": 15.0},
            "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
            # OpenAI
            "gpt-4-turbo-preview": {"input": 10.0, "output": 30.0},
            "gpt-4": {"input": 30.0, "output": 60.0},
            "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        }
        
        # Kurs USD/PLN (można później pobierać z API)
        self.usd_to_pln = 4.0
    
    def log_request(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Loguje request do API LLM.
        
        Args:
            provider: Provider (anthropic, openai)
            model: Nazwa modelu
            messages: Lista wiadomości (system, user, etc.)
            temperature: Temperatura (opcjonalnie)
            max_tokens: Maksymalna liczba tokenów (opcjonalnie)
            metadata: Dodatkowe metadane (symbol, strategy, etc.)
        """
        request_data = {
            "type": "REQUEST",
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "messages": messages,
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            "metadata": metadata or {}
        }
        
        # Formatuj jako JSON dla czytelności
        log_message = json.dumps(request_data, ensure_ascii=False, indent=2)
        
        # Loguj tylko do pliku (bez wyświetlania w konsoli)
        # Używamy opt(depth=2, colors=False) aby całkowicie pominąć propagację do konsoli
        # Dodatkowo używamy opt() z parametrem depth=2 aby całkowicie pominąć propagację
        # Używamy opt() z parametrem depth=2 aby całkowicie pominąć propagację do konsoli
        self.api_logger.opt(depth=2, colors=False).info(f"=== API REQUEST ===\n{log_message}")
    
    def log_response(
        self,
        provider: str,
        model: str,
        response_text: str,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        response_time_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """
        Loguje odpowiedź z API LLM.
        
        Args:
            provider: Provider (anthropic, openai)
            model: Nazwa modelu
            response_text: Tekst odpowiedzi
            input_tokens: Liczba tokenów wejściowych (opcjonalnie)
            output_tokens: Liczba tokenów wyjściowych (opcjonalnie)
            response_time_ms: Czas odpowiedzi w ms (opcjonalnie)
            metadata: Dodatkowe metadane (symbol, strategy, etc.)
            error: Błąd (jeśli wystąpił)
        """
        response_data = {
            "type": "RESPONSE",
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "response_text": response_text,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": (input_tokens or 0) + (output_tokens or 0) if input_tokens or output_tokens else None
            },
            "performance": {
                "response_time_ms": response_time_ms
            },
            "metadata": metadata or {},
            "error": error
        }
        
        # Formatuj jako JSON dla czytelności
        log_message = json.dumps(response_data, ensure_ascii=False, indent=2)
        
        # Loguj tylko do pliku (bez wyświetlania w konsoli)
        # Używamy opt(depth=2) aby całkowicie pominąć propagację do konsoli
        if error:
            self.api_logger.opt(depth=2, colors=False).error(f"=== API RESPONSE (ERROR) ===\n{log_message}")
            self.session_stats["total_errors"] += 1
        else:
            self.api_logger.opt(depth=2, colors=False).info(f"=== API RESPONSE ===\n{log_message}")
            
            # Aktualizuj statystyki sesji (tylko jeśli są tokeny)
            if input_tokens or output_tokens:
                self.session_stats["total_input_tokens"] += (input_tokens or 0)
                self.session_stats["total_output_tokens"] += (output_tokens or 0)
                self.session_stats["total_requests"] += 1
                
                # Aktualizuj statystyki per model
                if model not in self.session_stats["model_usage"]:
                    self.session_stats["model_usage"][model] = {"input": 0, "output": 0}
                self.session_stats["model_usage"][model]["input"] += (input_tokens or 0)
                self.session_stats["model_usage"][model]["output"] += (output_tokens or 0)
    
    def log_request_response_pair(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, Any]],
        response_text: str,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        response_time_ms: Optional[float] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """
        Loguje parę request-response w jednym wywołaniu.
        
        Args:
            provider: Provider (anthropic, openai)
            model: Nazwa modelu
            messages: Lista wiadomości (system, user, etc.)
            response_text: Tekst odpowiedzi
            input_tokens: Liczba tokenów wejściowych (opcjonalnie)
            output_tokens: Liczba tokenów wyjściowych (opcjonalnie)
            response_time_ms: Czas odpowiedzi w ms (opcjonalnie)
            temperature: Temperatura (opcjonalnie)
            max_tokens: Maksymalna liczba tokenów (opcjonalnie)
            metadata: Dodatkowe metadane (symbol, strategy, etc.)
            error: Błąd (jeśli wystąpił)
        """
        self.log_request(
            provider=provider,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata
        )
        
        self.log_response(
            provider=provider,
            model=model,
            response_text=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_time_ms=response_time_ms,
            metadata=metadata,
            error=error
        )
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Zwraca statystyki sesji (tokeny i koszty).
        
        Returns:
            Słownik ze statystykami
        """
        total_tokens = self.session_stats["total_input_tokens"] + self.session_stats["total_output_tokens"]
        
        # Oblicz koszt w USD
        total_cost_usd = 0.0
        cost_by_model = {}
        
        for model, usage in self.session_stats["model_usage"].items():
            pricing = self.model_pricing.get(model, {"input": 0.0, "output": 0.0})
            
            # Koszt w USD (cena za 1M tokenów)
            input_cost = (usage["input"] / 1_000_000) * pricing["input"]
            output_cost = (usage["output"] / 1_000_000) * pricing["output"]
            model_cost = input_cost + output_cost
            
            total_cost_usd += model_cost
            cost_by_model[model] = {
                "input_tokens": usage["input"],
                "output_tokens": usage["output"],
                "cost_usd": model_cost,
                "cost_pln": model_cost * self.usd_to_pln
            }
        
        # Koszt w PLN
        total_cost_pln = total_cost_usd * self.usd_to_pln
        
        return {
            "total_input_tokens": self.session_stats["total_input_tokens"],
            "total_output_tokens": self.session_stats["total_output_tokens"],
            "total_tokens": total_tokens,
            "total_requests": self.session_stats["total_requests"],
            "total_errors": self.session_stats["total_errors"],
            "total_cost_usd": total_cost_usd,
            "total_cost_pln": total_cost_pln,
            "cost_by_model": cost_by_model,
            "usd_to_pln_rate": self.usd_to_pln
        }
    
    def print_session_stats(self):
        """
        Wyświetla statystyki sesji w konsoli (krótka wersja).
        """
        stats = self.get_session_stats()
        
        if stats["total_requests"] == 0:
            return
        
        # Formatuj liczby tokenów
        total_tokens = stats["total_tokens"]
        input_tokens = stats["total_input_tokens"]
        output_tokens = stats["total_output_tokens"]
        
        # Formatuj koszty
        cost_pln = stats["total_cost_pln"]
        
        # Wyświetl krótkie statystyki
        logger.info(
            f"🤖 API LLM: {total_tokens:,} tokenów "
            f"({input_tokens:,} in + {output_tokens:,} out) | "
            f"Koszt: {cost_pln:.4f} PLN"
        )


# Singleton instance
_api_logger_instance: Optional[APILogger] = None


def get_api_logger() -> APILogger:
    """
    Zwraca singleton instance APILogger.
    
    Returns:
        APILogger instance
    """
    global _api_logger_instance
    if _api_logger_instance is None:
        _api_logger_instance = APILogger()
    return _api_logger_instance
