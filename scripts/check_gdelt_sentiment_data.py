#!/usr/bin/env python3
"""Sprawdź dane w tabeli gdelt_sentiment"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Załaduj .env
env_file = Path(__file__).parent.parent / '.env'
if env_file.exists():
    load_dotenv(env_file)

database_url = os.getenv('DATABASE_URL')
if not database_url:
    print("❌ DATABASE_URL nie jest ustawiony")
    sys.exit(1)

engine = create_engine(database_url)
conn = engine.connect()

# Sprawdź liczbę rekordów
result = conn.execute(text("SELECT COUNT(*) as count, MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM gdelt_sentiment"))
row = result.fetchone()
print(f"✅ Tabela gdelt_sentiment: {row[0]} rekordów")
if row[0] > 0:
    print(f"   Okres: {row[1]} → {row[2]}")

# Statystyki per region
result2 = conn.execute(text("""
    SELECT region, COUNT(*) as cnt, AVG(tone) as avg_tone, SUM(volume) as total_volume 
    FROM gdelt_sentiment 
    GROUP BY region 
    ORDER BY cnt DESC 
    LIMIT 10
"""))
print("\n📊 Statystyki per region:")
for r in result2:
    print(f"   {r[0]}: {r[1]} rekordów, avg tone: {r[2]:.2f}, volume: {r[3] or 0}")

conn.close()

