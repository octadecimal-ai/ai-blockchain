-- Migracja: Dodanie kolumn Tavily do tabeli llm_sentiment_analysis
-- =================================================================
-- Dodaje kolumny do przechowywania zapytań i odpowiedzi z Tavily (web search)

-- Dodaj kolumny Tavily
ALTER TABLE llm_sentiment_analysis 
ADD COLUMN IF NOT EXISTS tavily_query TEXT,
ADD COLUMN IF NOT EXISTS tavily_response TEXT,
ADD COLUMN IF NOT EXISTS tavily_answer TEXT,
ADD COLUMN IF NOT EXISTS tavily_results_count INTEGER;

-- Komentarze do nowych kolumn
COMMENT ON COLUMN llm_sentiment_analysis.tavily_query IS 'Zapytanie wysłane do Tavily (web search)';
COMMENT ON COLUMN llm_sentiment_analysis.tavily_response IS 'Pełna odpowiedź z Tavily w formacie JSON';
COMMENT ON COLUMN llm_sentiment_analysis.tavily_answer IS 'Podsumowanie AI z Tavily (jeśli dostępne)';
COMMENT ON COLUMN llm_sentiment_analysis.tavily_results_count IS 'Liczba wyników zwróconych przez Tavily';

