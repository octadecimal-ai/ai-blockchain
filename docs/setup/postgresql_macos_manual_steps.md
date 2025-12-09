# Ręczne kroki konfiguracji TimescaleDB dla PostgreSQL 14

## ⚠️ Ważne

Po automatycznej instalacji przez `install_postgresql.sh`, możesz potrzebować wykonać dodatkowe kroki, jeśli TimescaleDB nie działa od razu.

## 🔧 Kroki konfiguracji

### 1. Przenieś TimescaleDB do właściwej wersji PostgreSQL

TimescaleDB może być zainstalowany dla innej wersji PostgreSQL. Uruchom:

```bash
sudo timescaledb_move.sh
```

Ten skrypt automatycznie przeniesie rozszerzenie TimescaleDB do aktywnej wersji PostgreSQL.

### 2. Sprawdź konfigurację postgresql.conf

Upewnij się, że `shared_preload_libraries` zawiera `timescaledb`:

```bash
# Znajdź plik konfiguracyjny
psql -U $USER -d postgres -c "SHOW config_file;"

# Edytuj plik (zastąp ścieżką z powyższego)
nano /opt/homebrew/var/postgresql@14/postgresql.conf
```

Dodaj lub zaktualizuj:
```
shared_preload_libraries = 'timescaledb'
```

### 3. Restart PostgreSQL

```bash
brew services restart postgresql@14
```

### 4. Włącz rozszerzenie

```bash
psql -U $USER -d postgres -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
psql -U $USER -d ai_blockchain -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

### 5. Sprawdź instalację

```bash
psql -U $USER -d ai_blockchain -c "SELECT * FROM pg_extension WHERE extname = 'timescaledb';"
```

Powinieneś zobaczyć wiersz z `timescaledb`.

## 🐛 Rozwiązywanie problemów

### Błąd: "could not open extension control file"

**Przyczyna:** TimescaleDB nie jest w katalogu rozszerzeń PostgreSQL.

**Rozwiązanie:**
1. Uruchom `sudo timescaledb_move.sh`
2. Sprawdź czy plik istnieje:
   ```bash
   ls -la /opt/homebrew/share/postgresql@14/extension/timescaledb.control
   ```

### Błąd: "library "timescaledb" does not exist"

**Przyczyna:** Biblioteka nie jest załadowana.

**Rozwiązanie:**
1. Sprawdź `shared_preload_libraries` w `postgresql.conf`
2. Restart PostgreSQL
3. Sprawdź logi: `tail -f /opt/homebrew/var/log/postgresql@14.log`

### Błąd: "permission denied"

**Przyczyna:** Brak uprawnień do plików.

**Rozwiązanie:**
```bash
sudo chown -R $USER:staff /opt/homebrew/var/postgresql@14
```

## 📚 Alternatywa: Docker

Jeśli masz problemy z lokalną instalacją, użyj Docker:

```bash
docker-compose up -d timescaledb
```

To automatycznie skonfiguruje TimescaleDB bez dodatkowych kroków.

## ✅ Weryfikacja końcowa

Po wykonaniu wszystkich kroków, sprawdź:

```bash
# 1. Połączenie z bazą
psql -U $USER -d ai_blockchain

# 2. Włącz rozszerzenie
CREATE EXTENSION IF NOT EXISTS timescaledb;

# 3. Sprawdź wersję
SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';

# 4. Utwórz testową hypertable
CREATE TABLE test_hypertable (time TIMESTAMPTZ NOT NULL, value DOUBLE PRECISION);
SELECT create_hypertable('test_hypertable', 'time');
DROP TABLE test_hypertable;
```

Jeśli wszystkie komendy działają, TimescaleDB jest poprawnie skonfigurowany! 🎉

