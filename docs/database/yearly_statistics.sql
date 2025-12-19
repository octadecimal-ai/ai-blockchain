-- Statystyki roczne dla tabeli ohlcv
-- Wyświetla: rok | liczba rekordów
SELECT 
    EXTRACT(YEAR FROM timestamp) AS rok,
    COUNT(*) AS liczba_rekordow
FROM ohlcv
WHERE exchange = 'binance' AND symbol = 'BTC/USDC'
GROUP BY EXTRACT(YEAR FROM timestamp)
ORDER BY rok;

-- Statystyki roczne dla tabeli tickers
-- Wyświetla: rok | liczba rekordów
SELECT 
    EXTRACT(YEAR FROM timestamp) AS rok,
    COUNT(*) AS liczba_rekordow
FROM tickers
WHERE exchange = 'binance' AND symbol = 'BTC/USDC'
GROUP BY EXTRACT(YEAR FROM timestamp)
ORDER BY rok;

-- Statystyki roczne dla ohlcv (wszystkie exchange i symbol)
SELECT 
    EXTRACT(YEAR FROM timestamp) AS rok,
    COUNT(*) AS liczba_rekordow
FROM ohlcv
GROUP BY EXTRACT(YEAR FROM timestamp)
ORDER BY rok;

-- Statystyki roczne dla tickers (wszystkie exchange i symbol)
SELECT 
    EXTRACT(YEAR FROM timestamp) AS rok,
    COUNT(*) AS liczba_rekordow
FROM tickers
GROUP BY EXTRACT(YEAR FROM timestamp)
ORDER BY rok;

-- Porównanie ohlcv vs tickers (dla BTC/USDC)
SELECT 
    EXTRACT(YEAR FROM o.timestamp) AS rok,
    COUNT(DISTINCT o.id) AS ohlcv_rekordy,
    COUNT(DISTINCT t.id) AS tickers_rekordy,
    COUNT(DISTINCT t.id) - COUNT(DISTINCT o.id) AS roznica
FROM ohlcv o
LEFT JOIN tickers t ON 
    EXTRACT(YEAR FROM o.timestamp) = EXTRACT(YEAR FROM t.timestamp)
    AND o.exchange = t.exchange
    AND o.symbol = t.symbol
WHERE o.exchange = 'binance' AND o.symbol = 'BTC/USDC'
GROUP BY EXTRACT(YEAR FROM o.timestamp)
ORDER BY rok;

-- Statystyki roczne z dodatkowymi informacjami (ohlcv)
SELECT 
    EXTRACT(YEAR FROM timestamp) AS rok,
    COUNT(*) AS liczba_rekordow,
    MIN(timestamp) AS pierwsza_data,
    MAX(timestamp) AS ostatnia_data,
    COUNT(DISTINCT timeframe) AS liczba_timeframe
FROM ohlcv
WHERE exchange = 'binance' AND symbol = 'BTC/USDC'
GROUP BY EXTRACT(YEAR FROM timestamp)
ORDER BY rok;

-- Statystyki roczne z dodatkowymi informacjami (tickers)
SELECT 
    EXTRACT(YEAR FROM timestamp) AS rok,
    COUNT(*) AS liczba_rekordow,
    MIN(timestamp) AS pierwsza_data,
    MAX(timestamp) AS ostatnia_data,
    COUNT(*) FILTER (WHERE funding_rate IS NOT NULL) AS z_funding_rate,
    COUNT(*) FILTER (WHERE open_interest IS NOT NULL) AS z_open_interest
FROM tickers
WHERE exchange = 'binance' AND symbol = 'BTC/USDC'
GROUP BY EXTRACT(YEAR FROM timestamp)
ORDER BY rok;

