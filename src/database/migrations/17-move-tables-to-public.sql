-- Migracja: Przeniesienie tabel regions i słowników z schematu crypto do public
-- ============================================
-- Przenosi wszystkie tabele ze schematu crypto do public, aby mieć wszystkie tabele razem

-- Sprawdź czy tabele istnieją w schemacie crypto i przenieś je do public
DO $$
BEGIN
    -- Przenieś tabelę regions
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'crypto' AND table_name = 'regions') THEN
        ALTER TABLE crypto.regions SET SCHEMA public;
        RAISE NOTICE 'Przeniesiono tabelę regions do schematu public';
    END IF;
    
    -- Przenieś tabele słownikowe
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'crypto' AND table_name = 'dictionary_region_events') THEN
        ALTER TABLE crypto.dictionary_region_events SET SCHEMA public;
        RAISE NOTICE 'Przeniesiono tabelę dictionary_region_events do schematu public';
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'crypto' AND table_name = 'dictionary_global_events') THEN
        ALTER TABLE crypto.dictionary_global_events SET SCHEMA public;
        RAISE NOTICE 'Przeniesiono tabelę dictionary_global_events do schematu public';
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'crypto' AND table_name = 'dictionary_macro_events') THEN
        ALTER TABLE crypto.dictionary_macro_events SET SCHEMA public;
        RAISE NOTICE 'Przeniesiono tabelę dictionary_macro_events do schematu public';
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'crypto' AND table_name = 'dictionary_options_events') THEN
        ALTER TABLE crypto.dictionary_options_events SET SCHEMA public;
        RAISE NOTICE 'Przeniesiono tabelę dictionary_options_events do schematu public';
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'crypto' AND table_name = 'dictionary_algo_events') THEN
        ALTER TABLE crypto.dictionary_algo_events SET SCHEMA public;
        RAISE NOTICE 'Przeniesiono tabelę dictionary_algo_events do schematu public';
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'crypto' AND table_name = 'dictionary_special_events') THEN
        ALTER TABLE crypto.dictionary_special_events SET SCHEMA public;
        RAISE NOTICE 'Przeniesiono tabelę dictionary_special_events do schematu public';
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'crypto' AND table_name = 'dictionary_social_events') THEN
        ALTER TABLE crypto.dictionary_social_events SET SCHEMA public;
        RAISE NOTICE 'Przeniesiono tabelę dictionary_social_events do schematu public';
    END IF;
END $$;

-- Zaktualizuj foreign key w dictionary_region_events (jeśli istnieje)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'dictionary_region_events_region_code_fkey'
        AND table_schema = 'public'
    ) THEN
        -- Usuń stary foreign key
        ALTER TABLE public.dictionary_region_events 
        DROP CONSTRAINT IF EXISTS dictionary_region_events_region_code_fkey;
        
        -- Dodaj nowy foreign key wskazujący na public.regions
        ALTER TABLE public.dictionary_region_events 
        ADD CONSTRAINT dictionary_region_events_region_code_fkey 
        FOREIGN KEY (region_code) REFERENCES public.regions(region_code) ON DELETE CASCADE;
        
        RAISE NOTICE 'Zaktualizowano foreign key w dictionary_region_events';
    END IF;
END $$;

COMMENT ON TABLE public.regions IS 'Słownik regionów geograficznych z informacjami przydatnymi dla strategii BTC';
COMMENT ON TABLE public.dictionary_region_events IS 'Słownik wydarzeń specyficznych dla poszczególnych regionów';
COMMENT ON TABLE public.dictionary_global_events IS 'Słownik wydarzeń globalnych wpływających na cały rynek BTC';
COMMENT ON TABLE public.dictionary_macro_events IS 'Słownik wydarzeń makroekonomicznych wpływających na rynek BTC';
COMMENT ON TABLE public.dictionary_options_events IS 'Słownik wydarzeń związanych z wygaśnięciem opcji i futures na BTC';
COMMENT ON TABLE public.dictionary_algo_events IS 'Słownik wydarzeń związanych z handlem algorytmicznym';
COMMENT ON TABLE public.dictionary_special_events IS 'Słownik specjalnych wydarzeń rynkowych (Halving, CME Gap, Funding Rate, etc.)';
COMMENT ON TABLE public.dictionary_social_events IS 'Słownik wydarzeń związanych z aktywnością w mediach społecznościowych';

