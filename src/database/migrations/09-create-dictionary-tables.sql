-- Migracja: Utworzenie tabel słownikowych dla wydarzeń rynkowych
-- ============================================
-- Tabele do przechowywania słowników wydarzeń wpływających na aktywność handlową BTC

-- ============================================================================
-- Tabela: dictionary_region_events
-- Wydarzenia specyficzne dla poszczególnych regionów
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.dictionary_region_events (
    id SERIAL PRIMARY KEY,
    phase_code VARCHAR(100) NOT NULL UNIQUE,
    region_code VARCHAR(10) NOT NULL,
    label VARCHAR(200) NOT NULL,
    description TEXT,
    utc_start TIME NOT NULL,
    utc_end TIME NOT NULL,
    wraps_midnight BOOLEAN NOT NULL DEFAULT FALSE,
    priority INTEGER NOT NULL DEFAULT 10,
    volatility_level VARCHAR(20), -- LOW, MEDIUM, HIGH, EXTREME
    volume_impact VARCHAR(20), -- LOW, MEDIUM, HIGH
    typical_duration_min INTEGER,
    trading_pattern VARCHAR(20), -- TRENDING, RANGING, VOLATILE, MIXED
    dominant_actors VARCHAR(20), -- RETAIL, INSTITUTIONAL, ALGO, MIXED
    news_sensitivity VARCHAR(20), -- LOW, MEDIUM, HIGH
    category VARCHAR(20), -- SESSION, OVERLAP, LIQUIDITY, WEEKEND
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (region_code) REFERENCES public.regions(region_code) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_region_events_region ON public.dictionary_region_events (region_code);
CREATE INDEX IF NOT EXISTS ix_region_events_time ON public.dictionary_region_events (utc_start, utc_end);
CREATE INDEX IF NOT EXISTS ix_region_events_priority ON public.dictionary_region_events (priority);
CREATE INDEX IF NOT EXISTS ix_region_events_category ON public.dictionary_region_events (category);

COMMENT ON TABLE public.dictionary_region_events IS 'Słownik wydarzeń specyficznych dla poszczególnych regionów';
COMMENT ON COLUMN public.dictionary_region_events.phase_code IS 'Unikalny kod fazy/wydarzenia';
COMMENT ON COLUMN public.dictionary_region_events.region_code IS 'Kod regionu (FK do regions)';
COMMENT ON COLUMN public.dictionary_region_events.priority IS 'Priorytet wydarzenia (niższy = ważniejsze)';

-- ============================================================================
-- Tabela: dictionary_global_events
-- Wydarzenia globalne (GLOBAL region)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.dictionary_global_events (
    id SERIAL PRIMARY KEY,
    phase_code VARCHAR(100) NOT NULL UNIQUE,
    region_code VARCHAR(10) DEFAULT 'GLOBAL',
    label VARCHAR(200) NOT NULL,
    description TEXT,
    utc_start TIME NOT NULL,
    utc_end TIME NOT NULL,
    wraps_midnight BOOLEAN NOT NULL DEFAULT FALSE,
    priority INTEGER NOT NULL DEFAULT 10,
    volatility_level VARCHAR(20),
    volume_impact VARCHAR(20),
    typical_duration_min INTEGER,
    trading_pattern VARCHAR(20),
    dominant_actors VARCHAR(20),
    news_sensitivity VARCHAR(20),
    category VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_global_events_time ON public.dictionary_global_events (utc_start, utc_end);
CREATE INDEX IF NOT EXISTS ix_global_events_priority ON public.dictionary_global_events (priority);
CREATE INDEX IF NOT EXISTS ix_global_events_category ON public.dictionary_global_events (category);

COMMENT ON TABLE public.dictionary_global_events IS 'Słownik wydarzeń globalnych wpływających na cały rynek BTC';

-- ============================================================================
-- Tabela: dictionary_macro_events
-- Wydarzenia makroekonomiczne (NFP, CPI, FOMC, etc.)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.dictionary_macro_events (
    id SERIAL PRIMARY KEY,
    phase_code VARCHAR(100) NOT NULL UNIQUE,
    region_code VARCHAR(10),
    label VARCHAR(200) NOT NULL,
    description TEXT,
    utc_start TIME NOT NULL,
    utc_end TIME NOT NULL,
    wraps_midnight BOOLEAN NOT NULL DEFAULT FALSE,
    priority INTEGER NOT NULL DEFAULT 10,
    volatility_level VARCHAR(20),
    volume_impact VARCHAR(20),
    typical_duration_min INTEGER,
    trading_pattern VARCHAR(20),
    dominant_actors VARCHAR(20),
    news_sensitivity VARCHAR(20),
    category VARCHAR(20) DEFAULT 'MACRO',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_macro_events_time ON public.dictionary_macro_events (utc_start, utc_end);
CREATE INDEX IF NOT EXISTS ix_macro_events_priority ON public.dictionary_macro_events (priority);
CREATE INDEX IF NOT EXISTS ix_macro_events_region ON public.dictionary_macro_events (region_code);

COMMENT ON TABLE public.dictionary_macro_events IS 'Słownik wydarzeń makroekonomicznych wpływających na rynek BTC';

-- ============================================================================
-- Tabela: dictionary_options_events
-- Wydarzenia związane z wygaśnięciem opcji i futures
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.dictionary_options_events (
    id SERIAL PRIMARY KEY,
    phase_code VARCHAR(100) NOT NULL UNIQUE,
    region_code VARCHAR(10),
    label VARCHAR(200) NOT NULL,
    description TEXT,
    utc_start TIME NOT NULL,
    utc_end TIME NOT NULL,
    wraps_midnight BOOLEAN NOT NULL DEFAULT FALSE,
    priority INTEGER NOT NULL DEFAULT 10,
    volatility_level VARCHAR(20),
    volume_impact VARCHAR(20),
    typical_duration_min INTEGER,
    trading_pattern VARCHAR(20),
    dominant_actors VARCHAR(20),
    news_sensitivity VARCHAR(20),
    category VARCHAR(20) DEFAULT 'EVENT',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_options_events_time ON public.dictionary_options_events (utc_start, utc_end);
CREATE INDEX IF NOT EXISTS ix_options_events_priority ON public.dictionary_options_events (priority);

COMMENT ON TABLE public.dictionary_options_events IS 'Słownik wydarzeń związanych z wygaśnięciem opcji i futures na BTC';

-- ============================================================================
-- Tabela: dictionary_algo_events
-- Wydarzenia związane z handlem algorytmicznym
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.dictionary_algo_events (
    id SERIAL PRIMARY KEY,
    phase_code VARCHAR(100) NOT NULL UNIQUE,
    region_code VARCHAR(10),
    label VARCHAR(200) NOT NULL,
    description TEXT,
    utc_start TIME NOT NULL,
    utc_end TIME NOT NULL,
    wraps_midnight BOOLEAN NOT NULL DEFAULT FALSE,
    priority INTEGER NOT NULL DEFAULT 10,
    volatility_level VARCHAR(20),
    volume_impact VARCHAR(20),
    typical_duration_min INTEGER,
    trading_pattern VARCHAR(20),
    dominant_actors VARCHAR(20) DEFAULT 'ALGO',
    news_sensitivity VARCHAR(20),
    category VARCHAR(20) DEFAULT 'ALGO',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_algo_events_time ON public.dictionary_algo_events (utc_start, utc_end);
CREATE INDEX IF NOT EXISTS ix_algo_events_priority ON public.dictionary_algo_events (priority);

COMMENT ON TABLE public.dictionary_algo_events IS 'Słownik wydarzeń związanych z handlem algorytmicznym';

-- ============================================================================
-- Tabela: dictionary_special_events
-- Specjalne wydarzenia rynkowe (Halving, CME Gap, Funding Rate, etc.)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.dictionary_special_events (
    id SERIAL PRIMARY KEY,
    phase_code VARCHAR(100) NOT NULL UNIQUE,
    region_code VARCHAR(10),
    label VARCHAR(200) NOT NULL,
    description TEXT,
    utc_start TIME NOT NULL,
    utc_end TIME NOT NULL,
    wraps_midnight BOOLEAN NOT NULL DEFAULT FALSE,
    priority INTEGER NOT NULL DEFAULT 10,
    volatility_level VARCHAR(20),
    volume_impact VARCHAR(20),
    typical_duration_min INTEGER,
    trading_pattern VARCHAR(20),
    dominant_actors VARCHAR(20),
    news_sensitivity VARCHAR(20),
    category VARCHAR(20) DEFAULT 'EVENT',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_special_events_time ON public.dictionary_special_events (utc_start, utc_end);
CREATE INDEX IF NOT EXISTS ix_special_events_priority ON public.dictionary_special_events (priority);

COMMENT ON TABLE public.dictionary_special_events IS 'Słownik specjalnych wydarzeń rynkowych (Halving, CME Gap, Funding Rate, etc.)';

-- ============================================================================
-- Tabela: dictionary_social_events
-- Wydarzenia związane z aktywnością w mediach społecznościowych
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.dictionary_social_events (
    id SERIAL PRIMARY KEY,
    phase_code VARCHAR(100) NOT NULL UNIQUE,
    region_code VARCHAR(10),
    label VARCHAR(200) NOT NULL,
    description TEXT,
    utc_start TIME NOT NULL,
    utc_end TIME NOT NULL,
    wraps_midnight BOOLEAN NOT NULL DEFAULT FALSE,
    priority INTEGER NOT NULL DEFAULT 10,
    volatility_level VARCHAR(20),
    volume_impact VARCHAR(20),
    typical_duration_min INTEGER,
    trading_pattern VARCHAR(20),
    dominant_actors VARCHAR(20) DEFAULT 'RETAIL',
    news_sensitivity VARCHAR(20) DEFAULT 'HIGH',
    category VARCHAR(20) DEFAULT 'SESSION',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_social_events_time ON public.dictionary_social_events (utc_start, utc_end);
CREATE INDEX IF NOT EXISTS ix_social_events_priority ON public.dictionary_social_events (priority);
CREATE INDEX IF NOT EXISTS ix_social_events_region ON public.dictionary_social_events (region_code);

COMMENT ON TABLE public.dictionary_social_events IS 'Słownik wydarzeń związanych z aktywnością w mediach społecznościowych';

