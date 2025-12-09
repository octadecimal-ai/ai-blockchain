# Konfiguracja Bazy Danych

## 📋 Opcje

Projekt wspiera następujące opcje bazy danych:

1. **SQLite** (domyślna, dla rozwoju/testów) ⭐ **Rekomendowane dla startu**
2. **PostgreSQL + TimescaleDB** (dla produkcji, time-series data) ⭐ **Rekomendowane dla produkcji**
3. **MySQL** (opcjonalnie, ale **nie rekomendowane** - zobacz [mysql_vs_postgresql.md](./mysql_vs_postgresql.md))

> 💡 **Dlaczego PostgreSQL?** Dla danych time-series (OHLCV, tickers) PostgreSQL + TimescaleDB jest **znacznie lepszy** niż MySQL dzięki hypertables, kompresji i wydajności. Zobacz szczegółowe porównanie w [mysql_vs_postgresql.md](./mysql_vs_postgresql.md).

## 🗄️ SQLite (Domyślna)

### Konfiguracja

**Brak konfiguracji wymaganej** - działa out-of-the-box!

```python
from src.database.manager import DatabaseManager

db = DatabaseManager()  # Używa SQLite domyślnie
db.create_tables()
```

### Lokalizacja

Baza jest tworzona w: `data/ai_blockchain.db`

## 🐘 PostgreSQL + TimescaleDB (Produkcja)

### Wymagania

- Docker (dla łatwej instalacji)
- Lub lokalna instalacja PostgreSQL + TimescaleDB

### Opcja 1: Docker (Rekomendowane)

1. Uruchom TimescaleDB:
```bash
docker-compose up -d timescaledb
```

2. Skonfiguruj `.env`:
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/ai_blockchain
USE_TIMESCALE=true
```

3. Użyj w kodzie:
```python
from src.database.manager import DatabaseManager

db = DatabaseManager(
    database_url=os.getenv('DATABASE_URL'),
    use_timescale=True
)
db.create_tables()
```

### Opcja 2: Lokalna instalacja

1. Zainstaluj PostgreSQL:
```bash
# macOS (PostgreSQL 17 - rekomendowane dla TimescaleDB)
brew install postgresql@17
brew services start postgresql@17

# Ubuntu
sudo apt install postgresql postgresql-contrib
```

2. Zainstaluj TimescaleDB:
```bash
# macOS
brew install timescaledb

# Ubuntu
sudo apt install timescaledb-2-postgresql-14
```

3. Utwórz bazę:
```bash
createdb ai_blockchain
psql ai_blockchain -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

4. Skonfiguruj `.env`:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/ai_blockchain
USE_TIMESCALE=true
```

## 🧪 Testy

### SQLite (Domyślne)

Testy używają tymczasowej bazy SQLite - **brak konfiguracji wymaganej**.

### PostgreSQL (Opcjonalne)

Aby uruchomić testy z PostgreSQL:

1. Ustaw zmienne środowiskowe:
```bash
export DATABASE_URL=postgresql://user:pass@localhost:5432/test_db
export USE_TIMESCALE=true
```

2. Uruchom testy:
```bash
pytest tests/integration/test_database_integration.py
```

## 📊 Struktura Bazy

### Tabele

- `ohlcv` - dane OHLCV (hypertable w TimescaleDB)
- `tickers` - aktualne tickery
- `funding_rates` - funding rates z dYdX
- `trades` - transakcje
- `technical_indicators` - wskaźniki techniczne
- `sentiment_scores` - wyniki analizy sentymentu
- `signals` - sygnały tradingowe
- `portfolio` - portfel
- `positions` - pozycje

### Indeksy

Wszystkie tabele mają odpowiednie indeksy dla szybkich zapytań.

## 🔧 Migracje

Obecnie projekt nie używa Alembic - tabele są tworzone automatycznie przez `create_tables()`.

W przyszłości można dodać migracje:

```bash
# Przykład (do zaimplementowania)
alembic init alembic
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

## 🐛 Rozwiązywanie problemów

### Błąd: "relation does not exist"
- Uruchom `db.create_tables()` przed użyciem

### Błąd: "extension timescaledb does not exist"
- Zainstaluj TimescaleDB
- Uruchom `CREATE EXTENSION timescaledb;` w PostgreSQL

### Błąd: "connection refused"
- Sprawdź czy PostgreSQL działa: `pg_isready`
- Sprawdź `DATABASE_URL` w `.env`

## 🔄 MySQL (Opcjonalnie, Nie Rekomendowane)

Jeśli musisz użyć MySQL (np. masz już infrastrukturę MySQL):

1. Zainstaluj MySQL 8.0.23+ (dla HeatWave time-series features)
2. Skonfiguruj `.env`:
```env
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/ai_blockchain
```

3. Zainstaluj driver:
```bash
pip install pymysql
```

**⚠️ Uwaga:** MySQL nie ma tak dobrych funkcji time-series jak TimescaleDB. Będziesz musiał ręcznie partycjonować tabele i optymalizować zapytania. Zobacz szczegóły w [mysql_vs_postgresql.md](./mysql_vs_postgresql.md).

## 📚 Dokumentacja

- [TimescaleDB Docs](https://docs.timescale.com/)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [MySQL vs PostgreSQL dla tego projektu](./mysql_vs_postgresql.md)

