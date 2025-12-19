-- INSERT-y dla tabeli dictionary_macro_events
INSERT INTO dictionary_macro_events (phase_code, region_code, label, description, utc_start, utc_end, wraps_midnight, priority, volatility_level, volume_impact, typical_duration_min, trading_pattern, dominant_actors, news_sensitivity, category) VALUES
    ('CN_PBC_ANNOUNCEMENT', 'CN', 'PBC Announcement Window', 'Okno ogłoszeń Ludowego Banku Chin', '01:00', '03:00', FALSE, 7, 'HIGH', 'HIGH', 120, 'VOLATILE', 'INSTITUTIONAL', 'HIGH', 'MACRO'),
    ('JP_BOJ_WATCH', 'JP', 'BOJ Announcement Watch', 'Okno potencjalnych ogłoszeń Banku Japonii', '23:00', '02:00', TRUE, 6, 'HIGH', 'HIGH', 180, 'VOLATILE', 'INSTITUTIONAL', 'HIGH', 'MACRO'),
    ('MACRO_US_NFP', 'MACRO', 'US Nonfarm Payrolls', 'Publikacja danych o zatrudnieniu w USA (1. piątek miesiąca)', '12:30', '14:00', FALSE, 2, 'EXTREME', 'HIGH', 90, 'VOLATILE', 'INSTITUTIONAL', 'HIGH', 'MACRO'),
    ('MACRO_US_CPI', 'MACRO', 'US CPI Release', 'Publikacja danych o inflacji CPI w USA', '12:30', '14:00', FALSE, 2, 'EXTREME', 'HIGH', 90, 'VOLATILE', 'INSTITUTIONAL', 'HIGH', 'MACRO'),
    ('MACRO_US_FOMC', 'MACRO', 'FOMC Decision', 'Decyzja FOMC dot. stóp procentowych', '18:00', '20:00', FALSE, 1, 'EXTREME', 'HIGH', 120, 'VOLATILE', 'INSTITUTIONAL', 'HIGH', 'MACRO'),
    ('MACRO_US_FOMC_MINUTES', 'MACRO', 'FOMC Minutes Release', 'Publikacja minutek FOMC', '18:00', '19:30', FALSE, 3, 'HIGH', 'HIGH', 90, 'VOLATILE', 'INSTITUTIONAL', 'HIGH', 'MACRO'),
    ('MACRO_EU_ECB', 'MACRO', 'ECB Decision', 'Decyzja EBC dot. stóp procentowych', '12:15', '14:00', FALSE, 2, 'HIGH', 'HIGH', 105, 'VOLATILE', 'INSTITUTIONAL', 'HIGH', 'MACRO'),
    ('MACRO_EU_CPI', 'MACRO', 'EU CPI Release', 'Publikacja danych o inflacji w strefie euro', '09:00', '10:30', FALSE, 4, 'MEDIUM', 'MEDIUM', 90, 'VOLATILE', 'INSTITUTIONAL', 'HIGH', 'MACRO'),
    ('MACRO_JP_BOJ', 'MACRO', 'BOJ Decision', 'Decyzja Banku Japonii', '03:00', '05:00', FALSE, 3, 'HIGH', 'MEDIUM', 120, 'VOLATILE', 'INSTITUTIONAL', 'HIGH', 'MACRO'),
    ('MACRO_CN_PMI', 'MACRO', 'China PMI Release', 'Publikacja PMI z Chin', '01:00', '02:30', FALSE, 5, 'MEDIUM', 'MEDIUM', 90, 'VOLATILE', 'INSTITUTIONAL', 'MEDIUM', 'MACRO');
