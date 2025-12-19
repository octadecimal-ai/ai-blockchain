-- INSERT-y dla tabeli dictionary_options_events
INSERT INTO dictionary_options_events (phase_code, region_code, label, description, utc_start, utc_end, wraps_midnight, priority, volatility_level, volume_impact, typical_duration_min, trading_pattern, dominant_actors, news_sensitivity, category) VALUES
    ('OPTIONS_DERIBIT_DAILY', 'OPTIONS', 'Deribit Daily Expiry', 'Dzienne wygaśnięcie opcji na Deribit', '08:00', '08:30', FALSE, 8, 'MEDIUM', 'MEDIUM', 30, 'VOLATILE', 'INSTITUTIONAL', 'LOW', 'EVENT'),
    ('OPTIONS_DERIBIT_WEEKLY', 'OPTIONS', 'Deribit Weekly Expiry', 'Tygodniowe wygaśnięcie opcji na Deribit (piątek)', '08:00', '09:00', FALSE, 5, 'HIGH', 'HIGH', 60, 'VOLATILE', 'INSTITUTIONAL', 'LOW', 'EVENT'),
    ('OPTIONS_DERIBIT_MONTHLY', 'OPTIONS', 'Deribit Monthly Expiry', 'Miesięczne wygaśnięcie opcji na Deribit (ostatni piątek)', '08:00', '10:00', FALSE, 3, 'EXTREME', 'HIGH', 120, 'VOLATILE', 'INSTITUTIONAL', 'LOW', 'EVENT'),
    ('OPTIONS_CME_MONTHLY', 'OPTIONS', 'CME Monthly Expiry', 'Miesięczne wygaśnięcie opcji CME na BTC', '15:00', '16:00', FALSE, 3, 'EXTREME', 'HIGH', 60, 'VOLATILE', 'INSTITUTIONAL', 'LOW', 'EVENT'),
    ('OPTIONS_CME_QUARTERLY', 'OPTIONS', 'CME Quarterly Expiry', 'Kwartalne wygaśnięcie futures CME', '15:00', '17:00', FALSE, 2, 'EXTREME', 'HIGH', 120, 'VOLATILE', 'INSTITUTIONAL', 'LOW', 'EVENT'),
    ('OPTIONS_BINANCE_QUARTERLY', 'OPTIONS', 'Binance Quarterly Expiry', 'Kwartalne wygaśnięcie kontraktów Binance Futures', '08:00', '10:00', FALSE, 4, 'HIGH', 'HIGH', 120, 'VOLATILE', 'MIXED', 'LOW', 'EVENT');
