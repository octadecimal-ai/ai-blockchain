-- Migracja: Wstawienie danych do dictionary_algo_events
-- ============================================

-- Uwaga: ALGO_HOURLY_SPIKE i ALGO_15MIN_PATTERN mają wzorce czasowe co godzinę/15min
-- które nie mogą być reprezentowane jako TIME. Używamy 00:00 jako placeholder.
INSERT INTO public.dictionary_algo_events (phase_code, region_code, label, description, utc_start, utc_end, wraps_midnight, priority, volatility_level, volume_impact, typical_duration_min, trading_pattern, dominant_actors, news_sensitivity, category) VALUES
    ('ALGO_HOURLY_SPIKE', 'ALGO', 'Hourly Algo Spike', 'Wzrost aktywności algorytmicznej na pełne godziny (wzorzec: co godzinę o pełnej godzinie)', '00:00', '00:05', FALSE, 15, 'MEDIUM', 'MEDIUM', 5, 'VOLATILE', 'ALGO', 'LOW', 'ALGO'),
    ('ALGO_15MIN_PATTERN', 'ALGO', '15-Minute Algo Pattern', 'Cykliczny wzorzec algorytmiczny co 15 minut (wzorzec: co 15 minut)', '00:00', '00:15', FALSE, 18, 'LOW', 'LOW', 15, 'MIXED', 'ALGO', 'LOW', 'ALGO'),
    ('ALGO_REBALANCE_DAILY', 'ALGO', 'Daily Rebalancing Window', 'Okno dziennego rebalancingu funduszy i ETF', '20:00', '21:00', FALSE, 10, 'MEDIUM', 'HIGH', 60, 'VOLATILE', 'INSTITUTIONAL', 'LOW', 'ALGO'),
    ('ALGO_WEEKEND_REDUCED', 'ALGO', 'Weekend Algo Reduction', 'Zmniejszona aktywność algorytmów w weekend', '00:00', '23:59', FALSE, 20, 'LOW', 'LOW', 1440, 'RANGING', 'RETAIL', 'LOW', 'ALGO')
ON CONFLICT (phase_code) DO NOTHING;

