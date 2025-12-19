-- Migracja: Dodanie kolumn prompt i response do tabeli llm_sentiment_analysis
-- ============================================================================
-- Dodaje kolumny do przechowywania pełnego promptu i odpowiedzi LLM

-- Dodaj kolumny prompt i response
ALTER TABLE llm_sentiment_analysis 
ADD COLUMN IF NOT EXISTS prompt TEXT,
ADD COLUMN IF NOT EXISTS response TEXT;

-- Komentarze do nowych kolumn
COMMENT ON COLUMN llm_sentiment_analysis.prompt IS 'Pełny prompt wysłany do LLM';
COMMENT ON COLUMN llm_sentiment_analysis.response IS 'Pełna odpowiedź z LLM (przed parsowaniem JSON)';

