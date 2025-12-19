-- Migracja: Utworzenie view BTCUSDC
-- ===================================
-- View do łatwego dostępu do danych BTC/USDC z tabeli ohlcv

-- Utworzenie view dla BTC/USDC (1h timeframe)
CREATE OR REPLACE VIEW btcusdc_1h AS
SELECT 
    timestamp,
    open,
    high,
    low,
    close,
    volume,
    quote_volume,
    trades_count,
    created_at
FROM ohlcv
WHERE exchange = 'binance'
  AND symbol = 'BTC/USDC'
  AND timeframe = '1h'
ORDER BY timestamp DESC;

-- Utworzenie indeksu dla lepszej wydajności (jeśli jeszcze nie istnieje)
CREATE INDEX IF NOT EXISTS ix_ohlcv_btcusdc_1h 
ON ohlcv (timestamp DESC) 
WHERE exchange = 'binance' AND symbol = 'BTC/USDC' AND timeframe = '1h';

-- Komentarz do view
COMMENT ON VIEW btcusdc_1h IS 'View z danymi BTC/USDC 1h z Binance';

