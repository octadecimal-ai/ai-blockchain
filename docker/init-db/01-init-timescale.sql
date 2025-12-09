-- Inicjalizacja TimescaleDB dla AI Blockchain
-- ============================================

-- Włącz rozszerzenie TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Informacja o wersji
SELECT timescaledb_pre_restore();
SELECT * FROM timescaledb_information.compressed_chunk_stats;

-- Tworzenie schematu
CREATE SCHEMA IF NOT EXISTS crypto;

-- Ustawienie domyślnego schematu
SET search_path TO crypto, public;

-- Polityka retencji - automatyczne usuwanie starych danych
-- (opcjonalnie, odkomentuj jeśli potrzebujesz)
-- SELECT add_retention_policy('ohlcv', INTERVAL '1 year');

-- Indeks do szybkiego wyszukiwania
-- CREATE INDEX IF NOT EXISTS ix_ohlcv_symbol_time ON ohlcv (symbol, timestamp DESC);

COMMENT ON DATABASE ai_blockchain IS 'Baza danych dla projektu AI Blockchain - analiza kryptowalut';

