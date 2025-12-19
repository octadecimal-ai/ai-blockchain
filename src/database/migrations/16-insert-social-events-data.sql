-- Migracja: Wstawienie danych do dictionary_social_events
-- ============================================

INSERT INTO public.dictionary_social_events (phase_code, region_code, label, description, utc_start, utc_end, wraps_midnight, priority, volatility_level, volume_impact, typical_duration_min, trading_pattern, dominant_actors, news_sensitivity, category) VALUES
    ('SOCIAL_US_PEAK', 'SOCIAL', 'US Social Media Peak', 'Szczyt aktywności social media w USA (Twitter/X)', '14:00', '22:00', FALSE, 14, 'MEDIUM', 'MEDIUM', 480, 'MIXED', 'RETAIL', 'HIGH', 'SESSION'),
    ('SOCIAL_ASIA_PEAK', 'SOCIAL', 'Asia Social Media Peak', 'Szczyt aktywności social media w Azji', '00:00', '06:00', FALSE, 14, 'MEDIUM', 'MEDIUM', 360, 'MIXED', 'RETAIL', 'HIGH', 'SESSION'),
    ('SOCIAL_EUROPE_PEAK', 'SOCIAL', 'Europe Social Media Peak', 'Szczyt aktywności social media w Europie', '08:00', '14:00', FALSE, 14, 'MEDIUM', 'MEDIUM', 360, 'MIXED', 'RETAIL', 'HIGH', 'SESSION')
ON CONFLICT (phase_code) DO NOTHING;

