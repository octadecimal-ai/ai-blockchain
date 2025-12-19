import React, { memo } from 'react'
import './TimeZoneOverlay.css'

/**
 * Komponent pokazujący informacje o strefach czasowych i światłocieniu.
 * Google Maps automatycznie pokazuje światłocień w trybie 3D,
 * ale możemy dodać dodatkowe informacje.
 */
const TimeZoneOverlay = memo(function TimeZoneOverlay({ currentTimestamp }) {
  if (!currentTimestamp) return null

  const currentDate = new Date(currentTimestamp)
  const utcHours = currentDate.getUTCHours()
  const utcMinutes = currentDate.getUTCMinutes()
  
  // Oblicz pozycję słońca (przybliżona)
  // Słońce jest w zenicie około 12:00 UTC na południku 0°
  const sunLongitude = ((utcHours * 60 + utcMinutes) / 1440) * 360 - 180

  return (
    <div className="timezone-overlay">
      <div className="timezone-info">
        <span className="timezone-label">UTC Time:</span>
        <span className="timezone-value">
          {utcHours.toString().padStart(2, '0')}:{utcMinutes.toString().padStart(2, '0')}
        </span>
      </div>
      <div className="timezone-info">
        <span className="timezone-label">Sun Position:</span>
        <span className="timezone-value">
          {sunLongitude.toFixed(1)}° E
        </span>
      </div>
      <div className="timezone-note">
        💡 Google Maps automatycznie pokazuje światłocień w trybie 3D
      </div>
    </div>
  )
})

export default TimeZoneOverlay

