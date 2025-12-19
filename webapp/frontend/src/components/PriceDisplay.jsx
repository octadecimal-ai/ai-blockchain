import React, { useState, useEffect, useRef, memo } from 'react'
import axios from 'axios'
import './PriceDisplay.css'

// Funkcja pomocnicza: konwersja resolutionHours na timeframe string
function resolutionHoursToTimeframe(resolutionHours) {
  const minutes = Math.round(resolutionHours * 60)
  if (minutes === 1) return '1m'
  if (minutes === 5) return '5m'
  if (minutes === 15) return '15m'
  if (minutes === 30) return '30m'
  if (minutes === 60) return '1h'
  if (minutes === 180) return '3h'
  if (minutes === 360) return '6h'
  if (minutes === 720) return '12h'
  if (minutes === 1440) return '1d'
  if (minutes === 2880) return '2d'
  // Dla innych wartości zwróć najbliższy timeframe
  if (minutes < 5) return '1m'
  if (minutes < 15) return '5m'
  if (minutes < 30) return '15m'
  if (minutes < 60) return '30m'
  if (minutes < 180) return '1h'
  if (minutes < 360) return '3h'
  if (minutes < 720) return '6h'
  if (minutes < 1440) return '12h'
  return '1d'
}

const PriceDisplay = memo(function PriceDisplay({ timestamp, resolutionHours = 1/60 }) {
  const [priceData, setPriceData] = useState(null)
  const [loading, setLoading] = useState(false)
  const timeoutRef = useRef(null)
  const lastTimestampRef = useRef(null)
  const hasDataRef = useRef(false) // Ref do śledzenia, czy już mamy dane

  useEffect(() => {
    if (!timestamp) return

    // Anuluj poprzedni timeout, jeśli istnieje
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }

    // Jeśli timestamp się nie zmienił, nie pobieraj ponownie
    if (lastTimestampRef.current === timestamp) {
      console.log('📊 PriceDisplay: timestamp bez zmian, pomijam pobieranie:', timestamp)
      return
    }

    console.log('📊 PriceDisplay: timestamp się zmienił, pobieram dane:', {
      old: lastTimestampRef.current,
      new: timestamp,
      resolutionHours: resolutionHours
    })

    // Konwertuj resolutionHours na timeframe
    const timeframe = resolutionHoursToTimeframe(resolutionHours)
    
    // Usuń debounce - kurs musi się zmieniać przy każdej zmianie slidera/klatki
    // Tylko minimalny debounce (50ms) żeby uniknąć zbyt wielu requestów podczas szybkiego przesuwania
    const debounceTime = 50

    // Nie pokazuj "Ładowanie..." jeśli już mamy dane - to zapobiega miganiu
    // Tylko ustaw loading jeśli nie mamy żadnych danych
    if (!hasDataRef.current) {
      setLoading(true)
    }

    timeoutRef.current = setTimeout(() => {
      const fetchPrice = async () => {
        try {
          // Ustaw loading tylko jeśli nie mamy danych (żeby nie migać)
          if (!hasDataRef.current) {
            setLoading(true)
          }
          console.log('📊 PriceDisplay: Pobieram dane dla timestamp:', {
            timestamp: timestamp,
            timeframe: timeframe,
            resolutionHours: resolutionHours
          })
          const response = await axios.get('/api/btc/price', {
            params: {
              timestamp: timestamp,
              exchange: 'binance',
              symbol: 'BTC/USDC',
              timeframe: timeframe,
              resolution_hours: resolutionHours, // Przekaż resolution_hours do backendu
              lookback_hours: 100
            }
          })
          console.log('✅ PriceDisplay: Otrzymano dane:', {
            price: response.data?.price,
            timestamp: timestamp,
            timeframe: timeframe
          })
          setPriceData(response.data)
          hasDataRef.current = true // Oznacz, że mamy dane
          lastTimestampRef.current = timestamp
        } catch (err) {
          console.error('❌ PriceDisplay: Błąd pobierania kursu BTC:', err)
          // Nie ustawiaj priceData na null jeśli już mamy dane - pokaż poprzednie dane
          // setPriceData(null)
        } finally {
          setLoading(false)
        }
      }

      fetchPrice()
    }, debounceTime)

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [timestamp, resolutionHours]) // Dodano resolutionHours do zależności

  if (loading) {
    return (
      <div className="price-display loading">
        <div className="spinner-small"></div>
        <span>Ładowanie kursu...</span>
      </div>
    )
  }

  if (!priceData || !priceData.price) {
    const errorMsg = priceData?.error || 'Brak danych kursu'
    return (
      <div className="price-display no-data">
        <span>{errorMsg}</span>
        {priceData?.debug && (
          <div className="debug-info" style={{ fontSize: '0.75rem', color: '#999', marginTop: '0.5rem' }}>
            Próbowano: {priceData.debug.tried_exchange} / {priceData.debug.tried_symbol}
          </div>
        )}
      </div>
    )
  }

  const { price, open, high, low, close, volume, indicators } = priceData
  const priceChange = price - open
  const priceChangePercent = ((price - open) / open) * 100

  return (
    <div className="price-display">
      <div className="price-main">
        <div className="price-header">
          <span className="symbol">₿ BTC/USDC</span>
          <span className={`price ${priceChange >= 0 ? 'positive' : 'negative'}`}>
            ${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="price-change">
          <span className={`change ${priceChange >= 0 ? 'positive' : 'negative'}`}>
            {priceChange >= 0 ? '↑' : '↓'} ${Math.abs(priceChange).toFixed(2)} ({priceChangePercent >= 0 ? '+' : ''}{priceChangePercent.toFixed(2)}%)
          </span>
          {indicators?.price_change_24h_percent && (
            <span className="change-24h">
              24h: {indicators.price_change_24h_percent >= 0 ? '+' : ''}{indicators.price_change_24h_percent.toFixed(2)}%
            </span>
          )}
        </div>
      </div>

      <div className="price-details">
        <div className="ohlc">
          <div className="ohlc-item">
            <span className="label">O</span>
            <span className="value">${open.toFixed(2)}</span>
          </div>
          <div className="ohlc-item">
            <span className="label">H</span>
            <span className="value">${high.toFixed(2)}</span>
          </div>
          <div className="ohlc-item">
            <span className="label">L</span>
            <span className="value">${low.toFixed(2)}</span>
          </div>
          <div className="ohlc-item">
            <span className="label">C</span>
            <span className="value">${close.toFixed(2)}</span>
          </div>
        </div>
      </div>

      <div className="indicators">
        <div className="indicators-section">
          <h4>Trend</h4>
          <div className="indicators-grid">
            {indicators?.sma_20 && (
              <div className="indicator-item">
                <span className="indicator-label">SMA 20</span>
                <span className="indicator-value">${indicators.sma_20.toFixed(2)}</span>
              </div>
            )}
            {indicators?.sma_50 && (
              <div className="indicator-item">
                <span className="indicator-label">SMA 50</span>
                <span className="indicator-value">${indicators.sma_50.toFixed(2)}</span>
              </div>
            )}
            {indicators?.ema_12 && (
              <div className="indicator-item">
                <span className="indicator-label">EMA 12</span>
                <span className="indicator-value">${indicators.ema_12.toFixed(2)}</span>
              </div>
            )}
            {indicators?.ema_26 && (
              <div className="indicator-item">
                <span className="indicator-label">EMA 26</span>
                <span className="indicator-value">${indicators.ema_26.toFixed(2)}</span>
              </div>
            )}
          </div>
        </div>

        <div className="indicators-section">
          <h4>Momentum</h4>
          <div className="indicators-grid">
            {indicators?.rsi !== undefined && indicators.rsi !== null && (
              <div className="indicator-item">
                <span className="indicator-label">RSI (14)</span>
                <span className={`indicator-value ${indicators.rsi > 70 ? 'overbought' : indicators.rsi < 30 ? 'oversold' : ''}`}>
                  {indicators.rsi.toFixed(2)}
                </span>
              </div>
            )}
            {indicators?.macd !== undefined && indicators.macd !== null && (
              <div className="indicator-item">
                <span className="indicator-label">MACD</span>
                <span className="indicator-value">{indicators.macd.toFixed(2)}</span>
              </div>
            )}
            {indicators?.macd_signal !== undefined && indicators.macd_signal !== null && (
              <div className="indicator-item">
                <span className="indicator-label">MACD Signal</span>
                <span className="indicator-value">{indicators.macd_signal.toFixed(2)}</span>
              </div>
            )}
            {indicators?.macd_histogram !== undefined && indicators.macd_histogram !== null && (
              <div className="indicator-item">
                <span className="indicator-label">MACD Hist</span>
                <span className={`indicator-value ${indicators.macd_histogram >= 0 ? 'positive' : 'negative'}`}>
                  {indicators.macd_histogram.toFixed(2)}
                </span>
              </div>
            )}
          </div>
        </div>

        <div className="indicators-section">
          <h4>Volatility</h4>
          <div className="indicators-grid">
            {indicators?.bb_upper && (
              <div className="indicator-item">
                <span className="indicator-label">BB Upper</span>
                <span className="indicator-value">${indicators.bb_upper.toFixed(2)}</span>
              </div>
            )}
            {indicators?.bb_middle && (
              <div className="indicator-item">
                <span className="indicator-label">BB Middle</span>
                <span className="indicator-value">${indicators.bb_middle.toFixed(2)}</span>
              </div>
            )}
            {indicators?.bb_lower && (
              <div className="indicator-item">
                <span className="indicator-label">BB Lower</span>
                <span className="indicator-value">${indicators.bb_lower.toFixed(2)}</span>
              </div>
            )}
            {indicators?.bb_width !== undefined && indicators.bb_width !== null && (
              <div className="indicator-item">
                <span className="indicator-label">BB Width</span>
                <span className="indicator-value">{indicators.bb_width.toFixed(2)}%</span>
              </div>
            )}
            {indicators?.atr_percent !== undefined && indicators.atr_percent !== null && (
              <div className="indicator-item">
                <span className="indicator-label">ATR</span>
                <span className="indicator-value">{indicators.atr_percent.toFixed(2)}%</span>
              </div>
            )}
          </div>
        </div>

        <div className="indicators-section">
          <h4>Volume</h4>
          <div className="indicators-grid">
            <div className="indicator-item">
              <span className="indicator-label">Volume</span>
              <span className="indicator-value">{volume.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
            </div>
            {indicators?.volume_ratio !== undefined && indicators.volume_ratio !== null && (
              <div className="indicator-item">
                <span className="indicator-label">Vol Ratio</span>
                <span className={`indicator-value ${indicators.volume_ratio > 1.5 ? 'high' : indicators.volume_ratio < 0.5 ? 'low' : ''}`}>
                  {indicators.volume_ratio.toFixed(2)}x
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
})

export default PriceDisplay

