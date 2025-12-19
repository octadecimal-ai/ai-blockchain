-- Migracja: Utworzenie tabeli llm_sentiment_analysis
-- ===================================================
-- Tabela do przechowywania wyników analizy sentymentu wykonanej przez LLM
-- Zawiera szczegółowe informacje o kosztach, tokenach i wynikach analizy

-- Utworzenie tabeli
CREATE TABLE IF NOT EXISTS llm_sentiment_analysis (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    region VARCHAR(10) NOT NULL,
    language VARCHAR(10) NOT NULL,
    
    -- Informacje o LLM
    llm_model VARCHAR(100) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    cost_pln FLOAT NOT NULL,
    
    -- Wyniki analizy sentymentu
    sentiment VARCHAR(20) NOT NULL,
    score FLOAT NOT NULL,
    confidence FLOAT,
    fud_level FLOAT,
    fomo_level FLOAT,
    market_impact VARCHAR(10),
    key_topics TEXT,  -- JSON array
    reasoning TEXT,
    
    -- Metadane
    texts_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indeksy dla szybkiego wyszukiwania
CREATE INDEX IF NOT EXISTS ix_llm_sentiment_lookup ON llm_sentiment_analysis (symbol, region, timestamp);
CREATE INDEX IF NOT EXISTS ix_llm_sentiment_model ON llm_sentiment_analysis (llm_model, timestamp);
CREATE INDEX IF NOT EXISTS ix_llm_sentiment_timestamp ON llm_sentiment_analysis (timestamp DESC);

-- Komentarze do kolumn
COMMENT ON TABLE llm_sentiment_analysis IS 'Wyniki analizy sentymentu wykonanej przez LLM (Large Language Model)';
COMMENT ON COLUMN llm_sentiment_analysis.llm_model IS 'Nazwa modelu LLM użytego do analizy (np. claude-sonnet-4-20250514)';
COMMENT ON COLUMN llm_sentiment_analysis.input_tokens IS 'Liczba tokenów wejściowych użytych w zapytaniu';
COMMENT ON COLUMN llm_sentiment_analysis.output_tokens IS 'Liczba tokenów wyjściowych wygenerowanych przez model';
COMMENT ON COLUMN llm_sentiment_analysis.total_tokens IS 'Łączna liczba tokenów (input + output)';
COMMENT ON COLUMN llm_sentiment_analysis.cost_pln IS 'Koszt zapytania w PLN';
COMMENT ON COLUMN llm_sentiment_analysis.sentiment IS 'Wynik sentymentu: very_bearish, bearish, neutral, bullish, very_bullish';
COMMENT ON COLUMN llm_sentiment_analysis.score IS 'Wynik numeryczny sentymentu (-1.0 do 1.0)';
COMMENT ON COLUMN llm_sentiment_analysis.confidence IS 'Poziom pewności analizy (0.0 do 1.0)';
COMMENT ON COLUMN llm_sentiment_analysis.fud_level IS 'Poziom FUD (Fear, Uncertainty, Doubt) - 0.0 do 1.0';
COMMENT ON COLUMN llm_sentiment_analysis.fomo_level IS 'Poziom FOMO (Fear Of Missing Out) - 0.0 do 1.0';
COMMENT ON COLUMN llm_sentiment_analysis.market_impact IS 'Oczekiwany wpływ na rynek: high, medium, low';
COMMENT ON COLUMN llm_sentiment_analysis.key_topics IS 'Kluczowe tematy w formacie JSON array';
COMMENT ON COLUMN llm_sentiment_analysis.reasoning IS 'Wyjaśnienie analizy sentymentu';

-- Dla TimescaleDB: konwersja na hypertable (opcjonalnie)
-- Odkomentuj jeśli używasz TimescaleDB i chcesz partycjonować po czasie
-- SELECT create_hypertable('llm_sentiment_analysis', 'timestamp', if_not_exists => TRUE);

