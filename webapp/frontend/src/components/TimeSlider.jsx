import React, { useRef, memo } from 'react'
import { format, parseISO } from 'date-fns'
import './TimeSlider.css'

const TimeSlider = memo(function TimeSlider({ timestamps, currentIndex, onTimeChange, isPlaying }) {
  const throttleTimeoutRef = useRef(null)
  const lastUpdateRef = useRef(Date.now())
  
  const handleSliderChange = (e) => {
    const newIndex = parseInt(e.target.value)
    
    // Throttle - aktualizuj maksymalnie co 16ms (60 FPS)
    const now = Date.now()
    const timeSinceLastUpdate = now - lastUpdateRef.current
    
    if (timeSinceLastUpdate >= 16) {
      // Aktualizuj natychmiast
      onTimeChange(newIndex)
      lastUpdateRef.current = now
      
      // Anuluj poprzedni timeout
      if (throttleTimeoutRef.current) {
        clearTimeout(throttleTimeoutRef.current)
      }
    } else {
      // Zaplanuj aktualizację na koniec throttle period
      if (throttleTimeoutRef.current) {
        clearTimeout(throttleTimeoutRef.current)
      }
      
      throttleTimeoutRef.current = setTimeout(() => {
        onTimeChange(newIndex)
        lastUpdateRef.current = Date.now()
      }, 16 - timeSinceLastUpdate)
    }
  }

  const currentTimestamp = timestamps[currentIndex]
  const currentDate = currentTimestamp ? parseISO(currentTimestamp) : new Date()
  const totalPoints = timestamps.length

  return (
    <div className="time-slider-container">
      <div className="time-slider-info">
        <span className="time-display">
          {format(currentDate, 'yyyy-MM-dd HH:mm:ss')} UTC
        </span>
        <span className="time-index">
          {currentIndex + 1} / {totalPoints}
        </span>
      </div>
      <input
        type="range"
        min="0"
        max={totalPoints - 1}
        value={currentIndex}
        onChange={handleSliderChange}
        className="time-slider"
        disabled={isPlaying}
      />
      <div className="time-slider-labels">
        <span>{format(parseISO(timestamps[0]), 'MM-dd HH:mm')}</span>
        <span>{format(parseISO(timestamps[timestamps.length - 1]), 'MM-dd HH:mm')}</span>
      </div>
    </div>
  )
})

export default TimeSlider

