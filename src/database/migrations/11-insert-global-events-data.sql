-- Migracja: Wstawienie danych do dictionary_global_events
-- ============================================

INSERT INTO public.dictionary_global_events (phase_code, region_code, label, description, utc_start, utc_end, wraps_midnight, priority, volatility_level, volume_impact, typical_duration_min, trading_pattern, dominant_actors, news_sensitivity, category) VALUES
    ('GLOBAL_ASIAN_SESSION', 'GLOBAL', 'Global Asian Session', 'Pełna azjatycka sesja handlowa (Tokio, Hongkong, Singapur, Seul)', '00:00', '08:00', FALSE, 10, 'MEDIUM', 'MEDIUM', 480, 'MIXED', 'RETAIL', 'MEDIUM', 'SESSION'),
    ('GLOBAL_EUROPE_SESSION', 'GLOBAL', 'Global Europe Session', 'Pełna europejska sesja handlowa (Londyn, Frankfurt, Paryż)', '08:00', '16:00', FALSE, 10, 'MEDIUM', 'HIGH', 480, 'TRENDING', 'INSTITUTIONAL', 'HIGH', 'SESSION'),
    ('GLOBAL_US_SESSION', 'GLOBAL', 'Global US Session', 'Pełna amerykańska sesja handlowa (NYC, Chicago)', '13:00', '21:00', FALSE, 10, 'HIGH', 'HIGH', 480, 'VOLATILE', 'INSTITUTIONAL', 'HIGH', 'SESSION'),
    ('GLOBAL_ASIAN_PEAK', 'GLOBAL', 'Global Asian Peak', 'Szczyt aktywności azjatyckiej', '02:00', '04:00', FALSE, 8, 'MEDIUM', 'HIGH', 120, 'MIXED', 'RETAIL', 'MEDIUM', 'SESSION'),
    ('GLOBAL_EUROPE_PEAK', 'GLOBAL', 'Global Europe Peak', 'Szczyt aktywności europejskiej', '08:00', '11:00', FALSE, 8, 'MEDIUM', 'HIGH', 180, 'TRENDING', 'INSTITUTIONAL', 'HIGH', 'SESSION'),
    ('GLOBAL_US_PEAK', 'GLOBAL', 'Global US Peak', 'Szczyt aktywności amerykańskiej', '14:00', '17:00', FALSE, 8, 'HIGH', 'HIGH', 180, 'VOLATILE', 'INSTITUTIONAL', 'HIGH', 'SESSION'),
    ('GLOBAL_ASIA_EU_OVERLAP', 'GLOBAL', 'Asia-Europe Overlap', 'Nakładanie się sesji azjatyckiej i europejskiej - przejście płynności', '06:00', '08:00', FALSE, 4, 'MEDIUM', 'MEDIUM', 120, 'MIXED', 'MIXED', 'MEDIUM', 'OVERLAP'),
    ('GLOBAL_EU_US_OVERLAP', 'GLOBAL', 'EU-US Overlap', 'Nakładanie się sesji europejskiej i amerykańskiej - największa płynność i zmienność', '13:00', '17:00', FALSE, 3, 'HIGH', 'HIGH', 240, 'VOLATILE', 'INSTITUTIONAL', 'HIGH', 'OVERLAP'),
    ('GLOBAL_US_ASIA_OVERLAP', 'GLOBAL', 'US-Asia Overlap', 'Nakładanie się sesji amerykańskiej i azjatyckiej - przejście nocne', '21:00', '00:00', TRUE, 5, 'MEDIUM', 'LOW', 180, 'RANGING', 'RETAIL', 'LOW', 'OVERLAP'),
    ('GLOBAL_LIQUIDITY_TROUGH', 'GLOBAL', 'Global Liquidity Trough', 'Najniższa płynność globalna - niebezpieczne flash crashe', '04:00', '06:00', FALSE, 20, 'LOW', 'LOW', 120, 'RANGING', 'ALGO', 'LOW', 'LIQUIDITY'),
    ('GLOBAL_WEEKEND_LOW', 'GLOBAL', 'Weekend Liquidity Low', 'Weekendowa niska płynność (sobota-niedziela)', '00:00', '23:59', FALSE, 25, 'LOW', 'LOW', 1440, 'RANGING', 'RETAIL', 'LOW', 'WEEKEND'),
    ('GLOBAL_SUNDAY_GAP_RISK', 'GLOBAL', 'Sunday Gap Risk', 'Ryzyko luki cenowej przed poniedziałkiem', '18:00', '23:59', FALSE, 15, 'MEDIUM', 'LOW', 360, 'VOLATILE', 'RETAIL', 'MEDIUM', 'WEEKEND'),
    ('GLOBAL_VOLATILITY_PEAK', 'GLOBAL', 'Global Volatility Peak', 'Okno najwyższej zmienności dziennej', '14:30', '16:00', FALSE, 6, 'HIGH', 'HIGH', 90, 'VOLATILE', 'MIXED', 'HIGH', 'SESSION'),
    ('GLOBAL_VOLATILITY_ASIAN', 'GLOBAL', 'Asian Volatility Window', 'Okno zmienności azjatyckiej (2-3 w nocy UTC)', '01:00', '03:00', FALSE, 12, 'HIGH', 'MEDIUM', 120, 'VOLATILE', 'RETAIL', 'MEDIUM', 'SESSION')
ON CONFLICT (phase_code) DO NOTHING;

