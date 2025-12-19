-- Migracja: Wstawienie danych do dictionary_special_events
-- ============================================

INSERT INTO public.dictionary_special_events (phase_code, region_code, label, description, utc_start, utc_end, wraps_midnight, priority, volatility_level, volume_impact, typical_duration_min, trading_pattern, dominant_actors, news_sensitivity, category) VALUES
    ('EVENT_BTC_HALVING', 'EVENT', 'Bitcoin Halving', 'Halving nagrody blokowej BTC (co ~4 lata)', '00:00', '23:59', FALSE, 1, 'EXTREME', 'HIGH', 1440, 'VOLATILE', 'MIXED', 'HIGH', 'EVENT'),
    ('EVENT_CME_GAP', 'EVENT', 'CME Gap Window', 'Potencjalna luka cenowa CME (poniedziałek open)', '22:00', '23:30', TRUE, 6, 'HIGH', 'MEDIUM', 90, 'VOLATILE', 'INSTITUTIONAL', 'LOW', 'EVENT'),
    ('EVENT_FUNDING_8H', 'EVENT', '8-Hour Funding Rate', 'Rozliczenie funding rate co 8 godzin', '00:00', '00:15', FALSE, 12, 'MEDIUM', 'MEDIUM', 15, 'VOLATILE', 'MIXED', 'LOW', 'EVENT'),
    ('EVENT_FUNDING_8H_2', 'EVENT', '8-Hour Funding Rate 2', 'Drugie rozliczenie funding rate', '08:00', '08:15', FALSE, 12, 'MEDIUM', 'MEDIUM', 15, 'VOLATILE', 'MIXED', 'LOW', 'EVENT'),
    ('EVENT_FUNDING_8H_3', 'EVENT', '8-Hour Funding Rate 3', 'Trzecie rozliczenie funding rate', '16:00', '16:15', FALSE, 12, 'MEDIUM', 'MEDIUM', 15, 'VOLATILE', 'MIXED', 'LOW', 'EVENT'),
    ('EVENT_GRAYSCALE_UNLOCK', 'EVENT', 'Grayscale Unlock Period', 'Okres odblokowania udziałów GBTC (historycznie znaczący)', '13:00', '21:00', FALSE, 5, 'HIGH', 'HIGH', 480, 'VOLATILE', 'INSTITUTIONAL', 'MEDIUM', 'EVENT'),
    ('EVENT_ETF_REBALANCE', 'EVENT', 'ETF Rebalancing', 'Miesięczne/kwartalne rebalancowanie ETF BTC', '19:00', '21:00', FALSE, 6, 'HIGH', 'HIGH', 120, 'VOLATILE', 'INSTITUTIONAL', 'LOW', 'EVENT')
ON CONFLICT (phase_code) DO NOTHING;

