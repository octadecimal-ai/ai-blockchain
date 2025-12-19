-- Migracja: Utworzenie tabeli gdelt_sentiment
-- ============================================
-- Tabela do przechowywania danych sentymentu z GDELT API

-- Utworzenie tabeli
CREATE TABLE IF NOT EXISTS gdelt_sentiment (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    region VARCHAR(10) NOT NULL,
    language VARCHAR(10),
    
    -- Zapytanie GDELT
    query VARCHAR(500) NOT NULL,
    
    -- Dane sentymentu
    tone FLOAT,
    tone_std FLOAT,
    volume INTEGER,
    positive_count INTEGER,
    negative_count INTEGER,
    neutral_count INTEGER,
    
    -- Metadane
    resolution VARCHAR(10) NOT NULL DEFAULT 'hour',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indeksy dla szybkiego wyszukiwania
-- Uwaga: SQLite nie obsługuje IF NOT EXISTS dla CREATE INDEX w starszych wersjach
-- Dla PostgreSQL użyjemy IF NOT EXISTS, dla SQLite pominiemy jeśli już istnieją
CREATE INDEX IF NOT EXISTS ix_gdelt_sentiment_lookup ON gdelt_sentiment (region, timestamp);
CREATE INDEX IF NOT EXISTS ix_gdelt_sentiment_query ON gdelt_sentiment (query, timestamp);
CREATE INDEX IF NOT EXISTS ix_gdelt_sentiment_timestamp ON gdelt_sentiment (timestamp DESC);

-- Komentarze do kolumn
COMMENT ON TABLE gdelt_sentiment IS 'Dane sentymentu z GDELT (Global Database of Events, Language, and Tone)';
COMMENT ON COLUMN gdelt_sentiment.timestamp IS 'Czas agregacji danych';
COMMENT ON COLUMN gdelt_sentiment.region IS 'Kod regionu/kraju (US, CN, JP, KR, DE, GB, etc.)';
COMMENT ON COLUMN gdelt_sentiment.language IS 'Kod języka (en, zh, ja, ko, etc.)';
COMMENT ON COLUMN gdelt_sentiment.query IS 'Zapytanie użyte do wyszukiwania w GDELT';
COMMENT ON COLUMN gdelt_sentiment.tone IS 'Średni tone (-100 do +100)';
COMMENT ON COLUMN gdelt_sentiment.tone_std IS 'Odchylenie standardowe tone';
COMMENT ON COLUMN gdelt_sentiment.volume IS 'Liczba artykułów';
COMMENT ON COLUMN gdelt_sentiment.positive_count IS 'Liczba pozytywnych artykułów';
COMMENT ON COLUMN gdelt_sentiment.negative_count IS 'Liczba negatywnych artykułów';
COMMENT ON COLUMN gdelt_sentiment.neutral_count IS 'Liczba neutralnych artykułów';
COMMENT ON COLUMN gdelt_sentiment.resolution IS 'Rozdzielczość czasowa (hour, day)';

-- Dla TimescaleDB: konwersja na hypertable (opcjonalnie)
-- Odkomentuj jeśli używasz TimescaleDB i chcesz partycjonować po czasie
-- SELECT create_hypertable('gdelt_sentiment', 'timestamp', if_not_exists => TRUE);

