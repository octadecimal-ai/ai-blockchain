import React, { memo } from 'react'
import './Legend.css'

const SENTIMENT_LABELS = {
  veryBearish: 'Very Bearish',
  bearish: 'Bearish',
  neutral: 'Neutral',
  bullish: 'Bullish',
  veryBullish: 'Very Bullish'
}

const Legend = memo(function Legend({ colors }) {
  return (
    <div className="legend-container">
      <h3>Sentiment Scale</h3>
      <div className="legend-scale">
        {Object.entries(colors).map(([key, color]) => (
          <div key={key} className="legend-item">
            <div 
              className="legend-color" 
              style={{ backgroundColor: color }}
            />
            <span className="legend-label">{SENTIMENT_LABELS[key]}</span>
          </div>
        ))}
      </div>
      <div className="legend-score-range">
        <span>Score: -1.0 (bearish) to +1.0 (bullish)</span>
      </div>
    </div>
  )
})

export default Legend

