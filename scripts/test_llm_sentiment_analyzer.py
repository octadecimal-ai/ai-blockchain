#!/usr/bin/env python3
"""
Test LLM Sentiment Analyzer
============================
Prosty skrypt testowy do analizy sentymentu używając LLM.
"""

import os
import sys
from pathlib import Path

# Dodaj ścieżkę projektu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from loguru import logger
from src.collectors.sentiment import LLMSentimentAnalyzer, analyze_sentiment_llm

# Załaduj .env
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)

def main():
    """Test analizy sentymentu."""
    
    # Przykładowe teksty
    texts = [
        "Bitcoin ETF approved! Institutions are coming!",
        "This is the top, selling everything",
        "Sideways action, waiting for breakout",
        "Huge whale accumulation detected",
        "Market looks bearish, expect correction"
    ]
    
    logger.info("🧪 Test analizy sentymentu LLM")
    logger.info(f"   Teksty: {len(texts)}")
    logger.info(f"   Region: US")
    logger.info(f"   Język: en")
    
    try:
        # Użyj funkcji pomocniczej
        result = analyze_sentiment_llm(
            texts=texts,
            region="US",
            language="en",
            symbol="BTC/USDC",
            model="claude-sonnet-4-20250514",
            save_to_db=True
        )
        
        print("\n" + "="*70)
        print("📊 WYNIKI ANALIZY SENTYMENTU")
        print("="*70)
        print(f"Sentiment: {result['sentiment']}")
        print(f"Score: {result['score']:+.2f}")
        print(f"Confidence: {result['confidence']:.2%}")
        print(f"FUD Level: {result.get('fud_level', 0):.2%}")
        print(f"FOMO Level: {result.get('fomo_level', 0):.2%}")
        print(f"Market Impact: {result.get('market_impact', 'N/A')}")
        print(f"\nKey Topics: {', '.join(result.get('key_topics', []))}")
        print(f"\nReasoning: {result.get('reasoning', 'N/A')}")
        print("\n" + "-"*70)
        print("💰 KOSZTY")
        print("-"*70)
        print(f"Model: {result['llm_model']}")
        print(f"Input Tokens: {result['input_tokens']:,}")
        print(f"Output Tokens: {result['output_tokens']:,}")
        print(f"Total Tokens: {result['total_tokens']:,}")
        print(f"Cost: {result['cost_pln']:.4f} PLN")
        print("="*70)
        
        logger.success("✅ Analiza zakończona pomyślnie")
        
    except Exception as e:
        logger.error(f"❌ Błąd: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

