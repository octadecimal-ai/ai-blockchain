#!/usr/bin/env python3
"""
Test połączenia z GDELT API
==========================
Prosty skrypt do sprawdzenia czy połączenie z GDELT API działa poprawnie.
"""

import sys
from pathlib import Path

# Dodaj ścieżkę projektu
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.sentiment import GDELTCollector
from loguru import logger
import time
import json

# Konfiguracja loggera
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

def test_gdelt_connection():
    """Test podstawowego połączenia z GDELT API."""
    print("\n" + "="*70)
    print("🌍 TEST POŁĄCZENIA Z GDELT API")
    print("="*70)
    
    collector = GDELTCollector()
    
    # Test 1: Podstawowe połączenie - pobierz artykuły
    print("\n📰 Test 1: Pobieranie artykułów o Bitcoin (ostatnie 3 dni)")
    print("-" * 70)
    
    try:
        # Test bezpośredniego requestu do API
        import requests
        from datetime import datetime, timedelta, timezone
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=3)
        start_str = start_date.strftime("%Y%m%d%H%M%S")
        end_str = end_date.strftime("%Y%m%d%H%M%S")
        
        # GDELT wymaga nawiasów dla OR
        params = {
            "query": "(bitcoin OR BTC)",
            "mode": "ArtList",
            "format": "json",
            "maxrecords": 10,
            "startdatetime": start_str,
            "enddatetime": end_str,
            "sort": "DateDesc",
        }
        
        print(f"   Wysyłam request do: {collector.DOC_API_URL}")
        print(f"   Parametry: {params}")
        
        response = requests.get(collector.DOC_API_URL, params=params, timeout=60)
        print(f"   Status code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   Response text (pierwsze 500 znaków): {response.text[:500]}")
            return False
        
        # Sprawdź czy to JSON
        try:
            data = response.json()
            print(f"   ✅ Otrzymano poprawny JSON")
            print(f"   Klucze w odpowiedzi: {list(data.keys()) if isinstance(data, dict) else 'nie jest dict'}")
            
            if isinstance(data, dict) and "articles" in data:
                articles = data.get("articles", [])
                print(f"   Liczba artykułów: {len(articles)}")
                if articles:
                    print(f"   Przykładowy artykuł (pierwsze klucze): {list(articles[0].keys())[:5]}")
        except json.JSONDecodeError as e:
            print(f"   ❌ Błąd parsowania JSON: {e}")
            print(f"   Response text (pierwsze 500 znaków): {response.text[:500]}")
            return False
        
        # Teraz użyj metody kolektora
        df = collector.fetch_articles(
            query="bitcoin OR BTC",
            days_back=3,
            max_records=10
        )
        
        if not df.empty:
            print(f"✅ SUKCES: Pobrano {len(df)} artykułów")
            print(f"   Średni tone: {df['tone'].mean():.2f}")
            print(f"   Zakres tone: {df['tone'].min():.2f} do {df['tone'].max():.2f}")
            if 'source_country' in df.columns:
                print(f"   Kraje źródłowe: {df['source_country'].value_counts().head(3).to_dict()}")
            return True
        else:
            print("⚠️  OSTRZEŻENIE: API zwróciło pusty wynik")
            print("   To może oznaczać:")
            print("   - Brak artykułów dla zapytania w ostatnich 3 dniach")
            print("   - Problem z API (sprawdź połączenie internetowe)")
            return False
            
    except Exception as e:
        print(f"❌ BŁĄD: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Timeline API
    print("\n📈 Test 2: Timeline sentymentu (7 dni)")
    print("-" * 70)
    
    try:
        time.sleep(1)  # Rate limiting
        df_timeline = collector.fetch_tone_timeseries(
            query="bitcoin",
            days_back=7
        )
        
        if not df_timeline.empty:
            print(f"✅ SUKCES: Pobrano {len(df_timeline)} punktów timeline")
            print(f"   Zakres tone: {df_timeline['tone'].min():.2f} do {df_timeline['tone'].max():.2f}")
            print(f"   Okres: {df_timeline.index[0]} → {df_timeline.index[-1]}")
            return True
        else:
            print("⚠️  OSTRZEŻENIE: Timeline API zwróciło pusty wynik")
            return False
            
    except Exception as e:
        print(f"❌ BŁĄD: {type(e).__name__}: {e}")
        return False
    
    # Test 3: Multi-country (jeden kraj)
    print("\n🌐 Test 3: Multi-country timeseries (US)")
    print("-" * 70)
    
    try:
        time.sleep(1)  # Rate limiting
        df_multi = collector.fetch_multi_country_timeseries(
            query="bitcoin",
            countries=["US"],
            days_back=3,
            metric="tone"
        )
        
        if not df_multi.empty:
            print(f"✅ SUKCES: Pobrano dane dla {len(df_multi.columns)} krajów")
            print(f"   Punkty danych: {len(df_multi)}")
            for country in df_multi.columns:
                mean_tone = df_multi[country].mean()
                print(f"   {country}: średni tone = {mean_tone:.2f}")
            return True
        else:
            print("⚠️  OSTRZEŻENIE: Multi-country API zwróciło pusty wynik")
            return False
            
    except Exception as e:
        print(f"❌ BŁĄD: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    print("\n🔍 Sprawdzam połączenie z GDELT API...")
    print("   URL: https://api.gdeltproject.org/api/v2/doc/doc")
    print("   (To może chwilę potrwać - GDELT ma rate limiting)\n")
    
    results = []
    
    # Test 1
    result1 = test_gdelt_connection()
    results.append(("Pobieranie artykułów", result1))
    
    # Podsumowanie
    print("\n" + "="*70)
    print("📊 PODSUMOWANIE")
    print("="*70)
    
    for test_name, result in results:
        status = "✅ DZIAŁA" if result else "❌ BŁĄD"
        print(f"   {test_name}: {status}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\n✅ WSZYSTKIE TESTY PRZESZŁY - Połączenie z GDELT API działa poprawnie!")
    else:
        print("\n⚠️  NIEKTÓRE TESTY NIE PRZESZŁY - Sprawdź połączenie internetowe i status GDELT API")
    
    print("="*70)
    
    sys.exit(0 if all_passed else 1)

