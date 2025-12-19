-- Migracja: Zmiana nazw kolumn z tavily_* na web_search_*
-- ============================================================
-- Zmienia nazwy kolumn związanych z Tavily na bardziej ogólne web_search_*
-- ponieważ teraz używamy DuckDuckGo/Google/Serper, a nie tylko Tavily

-- Zmiana nazw kolumn
ALTER TABLE llm_sentiment_analysis
    RENAME COLUMN tavily_query TO web_search_query;

ALTER TABLE llm_sentiment_analysis
    RENAME COLUMN tavily_response TO web_search_response;

ALTER TABLE llm_sentiment_analysis
    RENAME COLUMN tavily_answer TO web_search_answer;

ALTER TABLE llm_sentiment_analysis
    RENAME COLUMN tavily_results_count TO web_search_results_count;

-- Aktualizacja komentarzy
COMMENT ON COLUMN llm_sentiment_analysis.web_search_query IS 'Zapytanie wysłane do web search (DuckDuckGo/Google/Serper)';
COMMENT ON COLUMN llm_sentiment_analysis.web_search_response IS 'Pełna odpowiedź z web search w formacie JSON';
COMMENT ON COLUMN llm_sentiment_analysis.web_search_answer IS 'Podsumowanie AI z web search (jeśli dostępne)';
COMMENT ON COLUMN llm_sentiment_analysis.web_search_results_count IS 'Liczba wyników zwróconych przez web search';

