#!/usr/bin/env python3
"""Sprawdź dane w tabeli llm_sentiment_analysis"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.manager import DatabaseManager

env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

db = DatabaseManager(database_url=os.getenv('DATABASE_URL'))

with db.get_session() as session:
    result = session.execute(text('SELECT COUNT(*) as count FROM llm_sentiment_analysis'))
    count = result.scalar()
    print(f'Liczba rekordów w bazie: {count}')
    
    if count > 0:
        result = session.execute(text('''
            SELECT 
                timestamp, symbol, region, sentiment, score, cost_pln, llm_model
            FROM llm_sentiment_analysis 
            ORDER BY timestamp DESC 
            LIMIT 10
        '''))
        print("\nOstatnie 10 rekordów:")
        for row in result:
            print(f"  {row.timestamp} | {row.symbol} | {row.region} | {row.sentiment} | score: {row.score:+.2f} | cost: {row.cost_pln:.4f} PLN | {row.llm_model}")

