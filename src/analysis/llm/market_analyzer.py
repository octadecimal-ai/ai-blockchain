"""
LLM Market Analyzer
===================
Moduł do analizy rynku kryptowalut z wykorzystaniem LLM.
Generuje raporty, analizuje newsy i tworzy podsumowania trendów.
"""

import os
from typing import Optional, List
from datetime import datetime
import pandas as pd
from loguru import logger

# Obsługa różnych providerów LLM
try:
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate
    from langchain.schema import HumanMessage, SystemMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain nie jest zainstalowany. Użyj: pip install langchain langchain-anthropic langchain-openai")


class MarketAnalyzerLLM:
    """
    Klasa do analizy rynku z wykorzystaniem LLM.
    
    Obsługuje:
    - Generowanie raportów rynkowych
    - Analiza sentymentu newsów
    - Wyjaśnianie anomalii rynkowych
    - Podsumowania trendów
    """
    
    # Prompt systemowy dla analizy rynku
    SYSTEM_PROMPT = """Jesteś ekspertem od analizy rynku kryptowalut. 
Twoje zadanie to analiza danych rynkowych i generowanie wnikliwych raportów.

Zasady:
1. Bądź obiektywny - przedstawiaj zarówno argumenty za jak i przeciw
2. Bazuj na danych - nie spekuluj bez podstaw
3. Ostrzegaj przed ryzykiem - kryptowaluty to ryzykowny rynek
4. Używaj profesjonalnego, ale przystępnego języka
5. Formatuj odpowiedzi z nagłówkami i punktami dla czytelności

WAŻNE: NIE dawaj konkretnych porad inwestycyjnych typu "kup" lub "sprzedaj".
Zawsze podkreślaj, że to analiza edukacyjna, nie porada finansowa."""

    def __init__(
        self,
        provider: str = "anthropic",
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Inicjalizacja analizatora LLM.
        
        Args:
            provider: "anthropic" lub "openai"
            model: Nazwa modelu (domyślnie claude-3-sonnet lub gpt-4-turbo)
            api_key: Klucz API (lub z zmiennej środowiskowej)
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("Zainstaluj: pip install langchain langchain-anthropic langchain-openai")
        
        self.provider = provider
        
        if provider == "anthropic":
            self.model = model or "claude-3-sonnet-20240229"
            self.llm = ChatAnthropic(
                model=self.model,
                anthropic_api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
                temperature=0.3,
                max_tokens=4096
            )
        elif provider == "openai":
            self.model = model or "gpt-4-turbo-preview"
            self.llm = ChatOpenAI(
                model=self.model,
                openai_api_key=api_key or os.getenv("OPENAI_API_KEY"),
                temperature=0.3,
                max_tokens=4096
            )
        else:
            raise ValueError(f"Nieznany provider: {provider}")
        
        logger.info(f"Zainicjalizowano LLM: {self.provider}/{self.model}")
    
    def generate_market_report(
        self,
        df: pd.DataFrame,
        symbol: str = "BTC/USDT",
        signals: Optional[dict] = None,
        additional_context: str = ""
    ) -> str:
        """
        Generuje raport rynkowy na podstawie danych.
        
        Args:
            df: DataFrame z danymi OHLCV i wskaźnikami
            symbol: Para handlowa
            signals: Sygnały z analizy technicznej
            additional_context: Dodatkowy kontekst (np. newsy)
            
        Returns:
            Raport rynkowy w formie tekstu
        """
        # Przygotuj dane do analizy
        latest = df.iloc[-1]
        
        # Statystyki
        price_now = latest['close']
        price_24h_ago = df.iloc[-24]['close'] if len(df) >= 24 else df.iloc[0]['close']
        price_7d_ago = df.iloc[-168]['close'] if len(df) >= 168 else df.iloc[0]['close']
        
        change_24h = ((price_now / price_24h_ago) - 1) * 100
        change_7d = ((price_now / price_7d_ago) - 1) * 100
        
        high_24h = df.tail(24)['high'].max()
        low_24h = df.tail(24)['low'].min()
        avg_volume = df['volume'].mean()
        current_volume = latest['volume']
        
        # Formatuj dane dla LLM
        market_data = f"""
## Dane rynkowe {symbol}
- **Data**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- **Aktualna cena**: ${price_now:,.2f}
- **Zmiana 24h**: {change_24h:+.2f}%
- **Zmiana 7d**: {change_7d:+.2f}%
- **High 24h**: ${high_24h:,.2f}
- **Low 24h**: ${low_24h:,.2f}
- **Wolumen**: {current_volume:,.0f} ({'powyżej' if current_volume > avg_volume else 'poniżej'} średniej)
"""
        
        # Dodaj wskaźniki jeśli dostępne
        indicators_info = ""
        if 'rsi' in df.columns:
            indicators_info += f"\n- **RSI**: {latest.get('rsi', 'N/A'):.1f}"
        if 'MACD_12_26_9' in df.columns:
            indicators_info += f"\n- **MACD**: {latest.get('MACD_12_26_9', 0):.2f}"
        if 'sma_50' in df.columns:
            sma50 = latest.get('sma_50', price_now)
            pos = "powyżej" if price_now > sma50 else "poniżej"
            indicators_info += f"\n- **SMA 50**: ${sma50:,.2f} (cena {pos})"
        
        if indicators_info:
            market_data += f"\n## Wskaźniki techniczne{indicators_info}"
        
        # Dodaj sygnały
        if signals:
            signals_text = "\n".join([f"- **{k.upper()}**: {v}" for k, v in signals.items()])
            market_data += f"\n\n## Sygnały\n{signals_text}"
        
        # Dodaj kontekst
        if additional_context:
            market_data += f"\n\n## Dodatkowy kontekst\n{additional_context}"
        
        # Prompt dla LLM
        prompt = f"""Na podstawie poniższych danych, wygeneruj profesjonalny raport rynkowy.

{market_data}

Raport powinien zawierać:
1. **Podsumowanie** - krótkie streszczenie sytuacji
2. **Analiza trendu** - obecny trend i jego siła
3. **Kluczowe poziomy** - wsparcia i opory do obserwacji
4. **Scenariusze** - możliwe kierunki rozwoju
5. **Ryzyka** - na co zwrócić uwagę

Pamiętaj: to analiza edukacyjna, NIE porada inwestycyjna."""

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]
        
        logger.info(f"Generuję raport dla {symbol}...")
        response = self.llm.invoke(messages)
        
        return response.content
    
    def analyze_sentiment(self, texts: List[str], topic: str = "Bitcoin") -> dict:
        """
        Analizuje sentyment tekstów (newsów, postów).
        
        Args:
            texts: Lista tekstów do analizy
            topic: Temat analizy
            
        Returns:
            Słownik z wynikami analizy sentymentu
        """
        if not texts:
            return {"error": "Brak tekstów do analizy"}
        
        # Połącz teksty (ogranicz do rozsądnej długości)
        combined = "\n---\n".join(texts[:10])  # Max 10 tekstów
        
        prompt = f"""Przeanalizuj sentyment poniższych tekstów dotyczących {topic}.

TEKSTY:
{combined}

Odpowiedz w formacie JSON:
{{
    "overall_sentiment": "bullish/bearish/neutral",
    "sentiment_score": <liczba od -100 do 100>,
    "key_themes": ["temat1", "temat2", ...],
    "summary": "krótkie podsumowanie",
    "notable_points": ["punkt1", "punkt2", ...]
}}"""

        messages = [
            SystemMessage(content="Jesteś ekspertem od analizy sentymentu rynku kryptowalut. Analizuj obiektywnie."),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        # Próba parsowania JSON z odpowiedzi
        try:
            import json
            # Znajdź JSON w odpowiedzi
            content = response.content
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
        except Exception as e:
            logger.warning(f"Nie udało się sparsować JSON: {e}")
        
        return {"raw_response": response.content}
    
    def explain_anomaly(
        self,
        df: pd.DataFrame,
        anomaly_type: str,
        context: str = ""
    ) -> str:
        """
        Wyjaśnia anomalię rynkową (np. nagły spadek/wzrost).
        
        Args:
            df: Dane rynkowe
            anomaly_type: Typ anomalii (np. "price_spike", "volume_surge")
            context: Dodatkowy kontekst
            
        Returns:
            Wyjaśnienie anomalii
        """
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        prompt = f"""Wykryto anomalię rynkową typu: {anomaly_type}

Dane:
- Poprzednia cena: ${prev['close']:,.2f}
- Aktualna cena: ${latest['close']:,.2f}
- Zmiana: {((latest['close']/prev['close'])-1)*100:+.2f}%
- Wolumen: {latest['volume']:,.0f}

{f'Kontekst: {context}' if context else ''}

Wyjaśnij możliwe przyczyny tej anomalii i co może to oznaczać dla rynku.
Bądź konkretny i bazuj na typowych wzorcach rynkowych."""

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        return response.content


# === Przykład użycia ===
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    
    from src.collectors.exchange.binance_collector import BinanceCollector
    from src.analysis.technical.indicators import TechnicalAnalyzer
    
    # Sprawdź czy mamy klucz API
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Ustaw ANTHROPIC_API_KEY lub OPENAI_API_KEY w zmiennych środowiskowych")
        print("   export ANTHROPIC_API_KEY=your-key-here")
        exit(1)
    
    # Pobierz dane
    collector = BinanceCollector()
    df = collector.fetch_ohlcv("BTC/USDT", "1h", limit=200)
    
    # Dodaj wskaźniki
    analyzer = TechnicalAnalyzer(df)
    analyzer.add_all_indicators()
    df = analyzer.get_dataframe()
    signals = analyzer.get_signals()
    
    # Generuj raport z LLM
    llm_analyzer = MarketAnalyzerLLM(provider="anthropic")
    report = llm_analyzer.generate_market_report(
        df=df,
        symbol="BTC/USDT",
        signals=signals
    )
    
    print("\n" + "="*60)
    print("📊 RAPORT RYNKOWY WYGENEROWANY PRZEZ AI")
    print("="*60)
    print(report)

