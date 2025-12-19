import React, { useState, useCallback, memo } from 'react'
import { format, parseISO, subDays, subHours } from 'date-fns'
import './DataRangeControls.css'

const PRESETS = [
  { label: 'Ostatnie 24h', days: 1, hours: 0 },
  { label: 'Ostatnie 7 dni', days: 7, hours: 0 },
  { label: 'Ostatnie 30 dni', days: 30, hours: 0 },
  { label: 'Ostatnie 90 dni', days: 90, hours: 0 },
  { label: 'Wszystko', days: null, hours: null } // null = wszystkie dostępne dane
]

const RESOLUTION_OPTIONS = [
  { value: 1/60, label: 'Co 1 min' },      // 0.0167 godzin
  { value: 5/60, label: 'Co 5 min' },      // 0.0833 godzin
  { value: 15/60, label: 'Co 15 min' },    // 0.25 godzin
  { value: 30/60, label: 'Co 30 min' },    // 0.5 godzin
  { value: 1, label: 'Co 1h' },
  { value: 3, label: 'Co 3h' },
  { value: 6, label: 'Co 6h' },
  { value: 12, label: 'Co 12h' },
  { value: 24, label: 'Co 24h (dziennie)' },
  { value: 48, label: 'Co 48h (co 2 dni)' }
]

const DataRangeControls = memo(function DataRangeControls({
  availableRange,
  currentDaysBack,
  currentResolution,
  onRangeChange,
  onResolutionChange,
  isLoading = false
}) {
  const [selectedPreset, setSelectedPreset] = useState(null)
  const [customDays, setCustomDays] = useState(currentDaysBack || 7)
  const [showCustomInput, setShowCustomInput] = useState(false)

  const handlePresetClick = useCallback((preset) => {
    setSelectedPreset(preset.label)
    setShowCustomInput(false)
    if (preset.days === null) {
      // "Wszystko" - użyj dostępnego zakresu
      if (availableRange?.min && availableRange?.max) {
        const minDate = parseISO(availableRange.min)
        const maxDate = parseISO(availableRange.max)
        const daysDiff = Math.ceil((maxDate - minDate) / (1000 * 60 * 60 * 24))
        onRangeChange(daysDiff)
      } else {
        onRangeChange(365) // Fallback: 1 rok
      }
    } else if (preset.hours && preset.hours > 0) {
      // Preset z godzinami - konwertuj na dni (ułamkowe)
      const days = preset.hours / 24
      onRangeChange(days)
    } else {
      onRangeChange(preset.days)
    }
  }, [availableRange, onRangeChange])

  const handleCustomDaysChange = useCallback((e) => {
    const days = parseFloat(e.target.value) || 1
    setCustomDays(Math.ceil(days)) // Zaokrąglij w górę dla wyświetlania
    setSelectedPreset(null)
    onRangeChange(days) // Przekaż dokładną wartość (może być ułamkowa dla godzin)
  }, [onRangeChange])

  const handleResolutionChange = useCallback((e) => {
    const resolution = parseFloat(e.target.value)
    onResolutionChange(resolution)
  }, [onResolutionChange])

  const handleCustomInputToggle = useCallback(() => {
    setShowCustomInput(!showCustomInput)
    if (!showCustomInput) {
      setSelectedPreset(null)
    }
  }, [showCustomInput])

  return (
    <div className="data-range-controls">
      <div className="controls-section">
        <div className="controls-label">Zakres danych</div>
        <div className="presets-container">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              className={`preset-button ${selectedPreset === preset.label ? 'active' : ''}`}
              onClick={() => handlePresetClick(preset)}
              disabled={isLoading}
            >
              {preset.label}
            </button>
          ))}
          <button
            className={`preset-button custom-toggle ${showCustomInput ? 'active' : ''}`}
            onClick={handleCustomInputToggle}
            disabled={isLoading}
          >
            Własny zakres
          </button>
        </div>
        {showCustomInput && (
          <div className="custom-input-container">
            <label>
              Dni wstecz (można użyć ułamków, np. 0.5 dla 12h):
              <input
                type="number"
                min="0.01"
                max="365"
                step="0.01"
                value={currentDaysBack || 1}
                onChange={handleCustomDaysChange}
                disabled={isLoading}
                className="custom-days-input"
              />
            </label>
            {availableRange?.min && availableRange?.max && (
              <div className="available-range-info">
                Dostępne: {format(parseISO(availableRange.min), 'yyyy-MM-dd HH:mm')} - {format(parseISO(availableRange.max), 'yyyy-MM-dd HH:mm')}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="controls-section">
        <div className="controls-label">Gęstość danych</div>
        <select
          value={currentResolution || 1}
          onChange={handleResolutionChange}
          disabled={isLoading}
          className="resolution-select"
        >
          {RESOLUTION_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <div className="resolution-info">
          {currentResolution && (
            <span>
              {currentResolution < 1/60
                ? `${Math.round(60 * 60 * currentResolution)} sek`
                : currentResolution < 1
                ? `${Math.round(60 * currentResolution)} min`
                : currentResolution === 1
                ? '1 godzina'
                : `${currentResolution} godzin`}
            </span>
          )}
        </div>
      </div>

      {isLoading && (
        <div className="loading-indicator">
          <div className="spinner-small"></div>
          <span>Ładowanie danych...</span>
        </div>
      )}
    </div>
  )
})

export default DataRangeControls

