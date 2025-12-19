import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { GoogleMap, useJsApiLoader, Circle, InfoWindow } from '@react-google-maps/api'
import axios from 'axios'
import { format, parseISO } from 'date-fns'
import TimeSlider from './components/TimeSlider'
import Legend from './components/Legend'
import PriceDisplay from './components/PriceDisplay'
import TimeZoneOverlay from './components/TimeZoneOverlay'
import DataRangeControls from './components/DataRangeControls'
import './styles/App.css'

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || ''

// Konfiguracja Google Maps API - dodaj marker library dla AdvancedMarkerElement
const libraries = ['places', 'marker']

// Kolory bazowe dla sentymentu (od bardzo niedźwiedziego do bardzo byczego) - RGB dla obliczeń gradientu
const SENTIMENT_BASE_COLORS = {
  veryBearish: { r: 139, g: 0, b: 0 },      // #8B0000 - Ciemny czerwony
  bearish: { r: 255, g: 69, b: 0 },        // #FF4500 - Czerwono-pomarańczowy
  neutral: { r: 128, g: 128, b: 128 },     // #808080 - Szary
  bullish: { r: 50, g: 205, b: 50 },       // #32CD32 - Zielony
  veryBullish: { r: 0, g: 100, b: 0 }       // #006400 - Ciemny zielony
}

// Kolory dla Legend (hex format) - używane przez komponent Legend
const SENTIMENT_COLORS = {
  veryBearish: '#8B0000',  // Ciemny czerwony
  bearish: '#FF4500',      // Czerwono-pomarańczowy
  neutral: '#808080',      // Szary
  bullish: '#32CD32',      // Zielony
  veryBullish: '#006400'   // Ciemny zielony
}

// Funkcja pomocnicza: konwersja RGB na hex
function rgbToHex(r, g, b) {
  return '#' + [r, g, b].map(x => {
    const hex = Math.round(x).toString(16)
    return hex.length === 1 ? '0' + hex : hex
  }).join('')
}

// Funkcja pomocnicza: interpolacja liniowa między dwoma kolorami RGB
function interpolateColor(color1, color2, factor) {
  return {
    r: Math.round(color1.r + (color2.r - color1.r) * factor),
    g: Math.round(color1.g + (color2.g - color1.g) * factor),
    b: Math.round(color1.b + (color2.b - color1.b) * factor)
  }
}

// Funkcja pomocnicza: HSL do RGB (dla modyfikacji nasycenia i jasności)
function hslToRgb(h, s, l) {
  let r, g, b
  if (s === 0) {
    r = g = b = l
  } else {
    const hue2rgb = (p, q, t) => {
      if (t < 0) t += 1
      if (t > 1) t -= 1
      if (t < 1/6) return p + (q - p) * 6 * t
      if (t < 1/2) return q
      if (t < 2/3) return p + (q - p) * (2/3 - t) * 6
      return p
    }
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s
    const p = 2 * l - q
    r = hue2rgb(p, q, h + 1/3)
    g = hue2rgb(p, q, h)
    b = hue2rgb(p, q, h - 1/3)
  }
  return { r: Math.round(r * 255), g: Math.round(g * 255), b: Math.round(b * 255) }
}

// Funkcja pomocnicza: RGB do HSL
function rgbToHsl(r, g, b) {
  r /= 255
  g /= 255
  b /= 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  let h, s, l = (max + min) / 2

  if (max === min) {
    h = s = 0
  } else {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break
      case g: h = ((b - r) / d + 2) / 6; break
      case b: h = ((r - g) / d + 4) / 6; break
    }
  }
  return { h, s, l }
}

// Funkcja do konwersji score (-1.0 do 1.0) na kolor bazowy (z gradientem)
function getBaseColorFromScore(score) {
  // Normalizuj score do zakresu 0-1
  const normalized = (score + 1) / 2  // -1.0 -> 0.0, 1.0 -> 1.0
  
  // Określ, w którym przedziale jest score
  if (normalized <= 0.2) {
    // Very Bearish -> Bearish (0.0 -> 0.2)
    const factor = normalized / 0.2
    return interpolateColor(SENTIMENT_BASE_COLORS.veryBearish, SENTIMENT_BASE_COLORS.bearish, factor)
  } else if (normalized <= 0.4) {
    // Bearish -> Neutral (0.2 -> 0.4)
    const factor = (normalized - 0.2) / 0.2
    return interpolateColor(SENTIMENT_BASE_COLORS.bearish, SENTIMENT_BASE_COLORS.neutral, factor)
  } else if (normalized <= 0.6) {
    // Neutral -> Bullish (0.4 -> 0.6)
    const factor = (normalized - 0.4) / 0.2
    return interpolateColor(SENTIMENT_BASE_COLORS.neutral, SENTIMENT_BASE_COLORS.bullish, factor)
  } else {
    // Bullish -> Very Bullish (0.6 -> 1.0)
    const factor = (normalized - 0.6) / 0.4
    return interpolateColor(SENTIMENT_BASE_COLORS.bullish, SENTIMENT_BASE_COLORS.veryBullish, factor)
  }
}

// Funkcja: oblicza odcień w zależności od pozycji w zakresie
// Graniczne wartości (blisko progów) → ciemniejsze, środkowe → jaśniejsze
function calculateShadeModifier(score) {
  const normalized = (score + 1) / 2
  const thresholds = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
  
  // Znajdź najbliższy próg
  let minDist = Infinity
  let closestThreshold = 0.5
  
  for (const threshold of thresholds) {
    const dist = Math.abs(normalized - threshold)
    if (dist < minDist) {
      minDist = dist
      closestThreshold = threshold
    }
  }
  
  // Jeśli jesteśmy blisko progu (w promieniu 0.05), przyciemnij
  // Jeśli jesteśmy w środku zakresu, rozjaśnij
  if (minDist < 0.05) {
    // Blisko progu → ciemniejszy (mniejsza jasność)
    return -0.15 * (1 - minDist / 0.05)  // -15% do 0%
  } else {
    // W środku → jaśniejszy (większa jasność)
    return 0.1  // +10% jasności
  }
}

// Zaawansowana funkcja do konwersji score i dodatkowych wartości na kolor
function getAdvancedSentimentColor(score, confidence = 0.5, fudLevel = 0, fomoLevel = 0) {
  // 1. Pobierz bazowy kolor z gradientu
  const baseColor = getBaseColorFromScore(score)
  
  // 2. Konwertuj RGB na HSL dla łatwiejszej modyfikacji
  const hsl = rgbToHsl(baseColor.r, baseColor.g, baseColor.b)
  
  // 3. Oblicz modyfikator odcienia (graniczne wartości → ciemniejsze)
  const shadeModifier = calculateShadeModifier(score)
  hsl.l = Math.max(0, Math.min(1, hsl.l + shadeModifier))
  
  // 4. Modyfikacja przez confidence (wysoka → bardziej nasycony, niska → mniej nasycony)
  // confidence: 0.0-1.0 → saturation modifier: -0.3 do +0.2
  const saturationModifier = (confidence - 0.5) * 0.4  // -0.2 do +0.2
  hsl.s = Math.max(0, Math.min(1, hsl.s + saturationModifier))
  
  // 5. Modyfikacja przez FUD (wysoki FUD → przyciemnienie)
  // fudLevel: 0.0-1.0 → brightness modifier: 0 do -0.1
  const fudModifier = -fudLevel * 0.1
  hsl.l = Math.max(0, Math.min(1, hsl.l + fudModifier))
  
  // 6. Modyfikacja przez FOMO (wysoki FOMO → rozjaśnienie)
  // fomoLevel: 0.0-1.0 → brightness modifier: 0 do +0.1
  const fomoModifier = fomoLevel * 0.1
  hsl.l = Math.max(0, Math.min(1, hsl.l + fomoModifier))
  
  // 7. Konwertuj z powrotem na RGB i hex
  const finalRgb = hslToRgb(hsl.h, hsl.s, hsl.l)
  return rgbToHex(finalRgb.r, finalRgb.g, finalRgb.b)
}

// Funkcja do konwersji score (-1.0 do 1.0) na kolor (zachowana dla kompatybilności)
function getSentimentColor(score, confidence = 0.5, fudLevel = 0, fomoLevel = 0) {
  return getAdvancedSentimentColor(score, confidence, fudLevel, fomoLevel)
}

// Funkcja do obliczania scale (rozmiaru) pinezki na podstawie market_impact
function getMarketImpactScale(marketImpact = 2) {
  // marketImpact: 1=low, 2=medium, 3=high
  return 1.0 + (marketImpact - 1) * 0.15  // 1.0, 1.15, 1.3
}

// Funkcja do konwersji score na nazwę sentymentu
function getSentimentLabel(score) {
  if (score <= -0.6) return 'Very Bearish'
  if (score <= -0.2) return 'Bearish'
  if (score <= 0.2) return 'Neutral'
  if (score <= 0.6) return 'Bullish'
  return 'Very Bullish'
}

function App() {
  // Ładowanie Google Maps API
  const { isLoaded, loadError } = useJsApiLoader({
    id: 'google-map-script',
    googleMapsApiKey: GOOGLE_MAPS_API_KEY,
    libraries: libraries
  })

  // Debug: loguj status ładowania
  useEffect(() => {
    console.log('🔍 Google Maps API Status:', {
      isLoaded,
      loadError: loadError?.message || null,
      hasApiKey: !!GOOGLE_MAPS_API_KEY,
      hasMapId: !!(import.meta.env.VITE_GOOGLE_MAPS_MAP_ID && import.meta.env.VITE_GOOGLE_MAPS_MAP_ID !== 'DEMO_MAP_ID')
    })
  }, [isLoaded, loadError, GOOGLE_MAPS_API_KEY])

  const [sentimentData, setSentimentData] = useState(null)
  const [currentTimeIndex, setCurrentTimeIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [timeRange, setTimeRange] = useState({ min: null, max: null })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedRegion, setSelectedRegion] = useState(null) // Dla InfoWindow
  const [showDayNight, setShowDayNight] = useState(true) // Domyślnie włączony 3D view ze światłocieniem
  const [mapReady, setMapReady] = useState(false) // Czy mapa jest gotowa (mapRef.current ustawiony)
  const [daysBack, setDaysBack] = useState(1) // Domyślnie 1 dzień (dla testów z 12h danych)
  const [resolutionHours, setResolutionHours] = useState(1/60) // Domyślnie 1 minuta
  const mapRef = useRef(null) // Ref do mapy dla AdvancedMarkerElement
  const markersRef = useRef([]) // Ref do markerów, żeby je usunąć przy zmianie
  const pinsRef = useRef(new Map()) // Ref do PinElement dla każdego markera (region -> PinElement)
  const colorsRef = useRef(new Map()) // Ref do aktualnych kolorów markerów (region -> color) - do optymalizacji
  const updateTimeoutRef = useRef(null) // Ref do timeout dla debounce aktualizacji kolorów

  // Pobierz dane sentymentu (zależne od daysBack i resolutionHours)
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        // Konwertuj daysBack na int (jeśli jest ułamkowy z godzin, zaokrąglij w górę)
        const daysBackInt = Math.ceil(daysBack)
        const params = {
          symbol: 'BTC/USDC',
          days_back: daysBackInt,
          resolution_hours: resolutionHours,
          source: 'llm'
        }
        
        console.log('📊 Pobieranie danych z parametrami:', params)
        const response = await axios.get('/api/sentiment/timeseries', { params })
        console.log('✅ Otrzymano dane:', {
          timestamps: response.data.timestamps?.length || 0,
          regions: response.data.regions?.length || 0,
          metadata: response.data.metadata
        })
        
        setSentimentData(response.data)
        // Ustaw na ostatni punkt czasowy, ale tylko jeśli dane się zmieniły
        if (response.data.timestamps.length > 0) {
          setCurrentTimeIndex(response.data.timestamps.length - 1)
        }
        setLoading(false)
      } catch (err) {
        console.error('❌ Błąd pobierania danych:', err)
        setError(err.message)
        setLoading(false)
      }
    }

    fetchData()
  }, [daysBack, resolutionHours]) // Pobierz dane gdy zmienią się parametry

  // Pobierz zakres czasowy
  useEffect(() => {
    const fetchRange = async () => {
      try {
        const response = await axios.get('/api/sentiment/range', {
          params: {
            symbol: 'BTC/USDC',
            source: 'llm'
          }
        })
        setTimeRange({
          min: response.data.min_timestamp,
          max: response.data.max_timestamp
        })
      } catch (err) {
        console.error('Błąd pobierania zakresu:', err)
      }
    }
    fetchRange()
  }, [])

  // Animacja play
  useEffect(() => {
    if (!isPlaying || !sentimentData) return

    const interval = setInterval(() => {
      setCurrentTimeIndex(prev => {
        if (prev >= sentimentData.timestamps.length - 1) {
          setIsPlaying(false)
          console.log('⏸️ Animacja zakończona - osiągnięto koniec danych')
          return prev
        }
        const nextIndex = prev + 1
        const nextTimestamp = sentimentData.timestamps[nextIndex]
        console.log('▶️ Animacja: aktualizuję indeks', {
          prev,
          next: nextIndex,
          timestamp: nextTimestamp
        })
        return nextIndex
      })
    }, 500) // Zmiana co 500ms

    return () => clearInterval(interval)
  }, [isPlaying, sentimentData])

  // Tworzenie AdvancedMarkerElement zamiast przestarzałego Marker
  useEffect(() => {
    console.log('🔍 useEffect markerów - sprawdzam warunki:', {
      isLoaded,
      mapReady,
      hasMapRef: !!mapRef.current,
      hasSentimentData: !!sentimentData,
      hasRegions: !!(sentimentData?.regions),
      regionsCount: sentimentData?.regions?.length || 0
    })
    
    if (!isLoaded) {
      console.log('⏸️ Czekam na załadowanie Google Maps API...')
      return
    }
    if (!mapReady || !mapRef.current) {
      console.log('⏸️ Czekam na mapRef.current (mapReady:', mapReady, ')...')
      return
    }
    if (!sentimentData) {
      console.log('⏸️ Czekam na sentimentData...')
      return
    }
    if (!sentimentData.regions) {
      console.log('⏸️ Czekam na sentimentData.regions...')
      return
    }
    
    const map = mapRef.current
    console.log('✅ Wszystkie warunki spełnione, tworzę markery...')
    
    // Sprawdź, czy AdvancedMarkerElement jest dostępny
    if (!window.google?.maps?.marker?.AdvancedMarkerElement) {
      console.warn('AdvancedMarkerElement nie jest dostępny - markery nie będą tworzone')
      return
    }
    
    // Sprawdź, czy mapa ma prawidłowy Map ID (nie DEMO_MAP_ID)
    // Map ID jest dostępny przez map.getMapId() lub możemy sprawdzić opcje
    const MAP_ID = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || 'DEMO_MAP_ID'
    console.log('🔍 Sprawdzam Map ID:', MAP_ID)
    if (!MAP_ID || MAP_ID === 'DEMO_MAP_ID') {
      console.warn('⚠️ AdvancedMarkerElement wymaga prawidłowego Map ID!')
      console.warn('Utwórz Map ID w Google Cloud Console i ustaw VITE_GOOGLE_MAPS_MAP_ID w .env')
      console.warn('Zobacz README.md, sekcja "Google Maps API Key i Map ID"')
      console.warn('Markery nie będą tworzone bez prawidłowego Map ID')
      return
    }
    
    // Sprawdź, czy mapa ma ustawiony Map ID
    try {
      const mapId = map.getMapId()
      console.log('🔍 Map ID z mapy:', mapId)
      if (!mapId || mapId === 'DEMO_MAP_ID') {
        console.warn('⚠️ Mapa nie ma prawidłowego Map ID! Markery mogą nie być widoczne.')
      }
    } catch (error) {
      console.warn('⚠️ Nie można pobrać Map ID z mapy:', error)
    }
    const { AdvancedMarkerElement, PinElement } = window.google.maps.marker
    console.log('✅ AdvancedMarkerElement i PinElement dostępne:', {
      hasAdvancedMarkerElement: !!AdvancedMarkerElement,
      hasPinElement: !!PinElement
    })
    
    // Sprawdź, czy mapa ma ustawiony Map ID
    try {
      const mapId = map.getMapId()
      console.log('🔍 Map ID z mapy:', mapId)
      if (!mapId || mapId === 'DEMO_MAP_ID') {
        console.warn('⚠️ Mapa nie ma prawidłowego Map ID! Markery mogą nie być widoczne.')
      }
    } catch (error) {
      console.warn('⚠️ Nie można pobrać Map ID z mapy:', error)
    }

    // Sprawdź, czy mapa jest gotowa (nie null)
    if (!map || !map.getMapId) {
      console.warn('⚠️ Mapa nie jest gotowa - czekam...')
      return
    }

    // Sprawdź, czy regiony się zmieniły (tylko jeśli markery już istnieją)
    const currentRegions = sentimentData.regions.sort().join(',')
    const hasExistingMarkers = markersRef.current.length > 0
    
    if (hasExistingMarkers) {
      const previousRegions = Array.from(markersRef.current)
        .map(m => {
          // Spróbuj odczytać region z markera (zapisz w title lub data attribute)
          return m.title?.split(':')[0] || null
        })
        .filter(Boolean)
        .sort()
        .join(',')
      
      // Jeśli regiony się zmieniły, usuń stare markery
      if (currentRegions !== previousRegions) {
        console.log('🔄 Regiony się zmieniły - usuwam stare markery:', {
          previous: previousRegions,
          current: currentRegions
        })
        markersRef.current.forEach(marker => {
          marker.map = null
        })
        markersRef.current = []
        pinsRef.current.clear()
        colorsRef.current.clear()
      } else {
        console.log('✅ Regiony bez zmian - aktualizuję istniejące markery')
        // Regiony bez zmian - nie usuwamy markerów, tylko aktualizujemy kolory
        // Przerwij tutaj, żeby nie tworzyć nowych markerów
        return
      }
    } else {
      console.log('🆕 Pierwsze tworzenie markerów - regiony:', currentRegions)
    }

    // Utwórz markery używając AdvancedMarkerElement (tylko raz, bez zależności od currentTimeIndex)
    let createdCount = 0
    sentimentData.regions.forEach(region => {
      const regionData = sentimentData.data[region]
      if (!regionData) {
        console.debug(`Brak regionData dla ${region}`)
        return
      }

      const coords = regionData.coordinates
      if (!coords || !coords.lat || !coords.lng) {
        console.debug(`Brak współrzędnych dla ${region}`)
        return
      }

      try {
        // Sprawdź, czy marker już istnieje dla tego regionu
        const existingMarker = markersRef.current.find(m => {
          const pos = m.position
          return pos && 
                 Math.abs(pos.lat - coords.lat) < 0.001 && 
                 Math.abs(pos.lng - coords.lng) < 0.001 &&
                 m.title?.startsWith(`${region}:`)
        })

        if (existingMarker) {
          console.log(`♻️ Marker dla ${region} już istnieje - pomijam tworzenie`)
          // Zaktualizuj tylko kolor, jeśli się zmienił
          const initialScore = regionData.scores?.[currentTimeIndex] || regionData.scores?.[0] || 0
          const confidence = regionData.confidence?.[currentTimeIndex] ?? regionData.confidence?.[0] ?? 0.5
          const fudLevel = regionData.fud_level?.[currentTimeIndex] ?? regionData.fud_level?.[0] ?? 0
          const fomoLevel = regionData.fomo_level?.[currentTimeIndex] ?? regionData.fomo_level?.[0] ?? 0
          const marketImpact = regionData.market_impact?.[currentTimeIndex] ?? regionData.market_impact?.[0] ?? 2
          
          const initialColor = getSentimentColor(initialScore, confidence, fudLevel, fomoLevel)
          const scale = getMarketImpactScale(marketImpact)
          const oldColor = colorsRef.current.get(region)
          
          if (oldColor !== initialColor) {
            const pinElement = pinsRef.current.get(region)
            if (pinElement) {
              const newPinElement = new PinElement({
                background: initialColor,
                borderColor: '#fff',
                glyphColor: '#fff',
                scale: scale
              })
              existingMarker.content = newPinElement.element
              pinsRef.current.set(region, newPinElement)
              colorsRef.current.set(region, initialColor)
              console.log(`  ✅ Zaktualizowano kolor istniejącego markera ${region}: ${oldColor} → ${initialColor}`)
            }
          }
          return // Marker już istnieje, nie tworzymy nowego
        }

        // Utwórz początkowy PinElement (kolor zostanie zaktualizowany w osobnym useEffect)
        const initialScore = regionData.scores?.[currentTimeIndex] || regionData.scores?.[0] || 0
        const confidence = regionData.confidence?.[currentTimeIndex] ?? regionData.confidence?.[0] ?? 0.5
        const fudLevel = regionData.fud_level?.[currentTimeIndex] ?? regionData.fud_level?.[0] ?? 0
        const fomoLevel = regionData.fomo_level?.[currentTimeIndex] ?? regionData.fomo_level?.[0] ?? 0
        const marketImpact = regionData.market_impact?.[currentTimeIndex] ?? regionData.market_impact?.[0] ?? 2
        
        const initialColor = getSentimentColor(initialScore, confidence, fudLevel, fomoLevel)
        const scale = getMarketImpactScale(marketImpact)
        const pinElement = new PinElement({
          background: initialColor,
          borderColor: '#fff',
          glyphColor: '#fff',
          scale: scale
        })

        // Zapisz PinElement i kolor w ref, żeby móc aktualizować kolory
        pinsRef.current.set(region, pinElement)
        colorsRef.current.set(region, initialColor) // Zapisz początkowy kolor

        // Utwórz AdvancedMarkerElement
        const marker = new AdvancedMarkerElement({
          map: map,
          position: { lat: coords.lat, lng: coords.lng },
          content: pinElement.element,
          title: `${region}: ${getSentimentLabel(initialScore)}`
        })

        // Debug: sprawdź czy marker jest poprawnie utworzony
        console.log(`📍 Marker dla ${region}:`, {
          position: { lat: coords.lat, lng: coords.lng },
          color: initialColor,
          hasMap: !!marker.map,
          visible: marker.visible !== false,
          content: !!marker.content,
          pinElement: !!pinElement.element
        })

        // Dodaj event listener dla kliknięcia
        marker.addListener('click', () => {
          setSelectedRegion(region)
        })

        markersRef.current.push(marker)
        createdCount++
        console.log(`✅ Utworzono marker dla ${region} na pozycji (${coords.lat}, ${coords.lng}) z kolorem ${initialColor}`)
      } catch (error) {
        console.error(`❌ Błąd tworzenia markera dla ${region}:`, error)
      }
    })
    
    console.log(`📍 Utworzono ${createdCount} markerów z ${sentimentData.regions.length} regionów`)

    return () => {
      // Cleanup: usuń markery przy unmount
      markersRef.current.forEach(marker => {
        marker.map = null
      })
      markersRef.current = []
      pinsRef.current.clear()
    }
  }, [isLoaded, mapReady, sentimentData, currentTimeIndex]) // Dodano currentTimeIndex, żeby aktualizować kolory przy zmianie danych

  // Aktualizacja kolorów markerów - tylko kolory, bez odświeżania mapy
  // Używamy debounce, aby zmniejszyć miganie podczas przesuwania slidera
  useEffect(() => {
    if (!sentimentData || !sentimentData.regions || markersRef.current.length === 0) return
    
    // Anuluj poprzedni timeout, jeśli istnieje
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current)
    }
    
    // Debounce aktualizacji - czekamy 50ms przed aktualizacją
    // (to zmniejsza miganie podczas szybkiego przesuwania slidera)
    updateTimeoutRef.current = setTimeout(() => {
      console.log(`🔄 Aktualizuję kolory markerów dla indeksu ${currentTimeIndex} (debounce 50ms)`)
      
      // Pobierz PinElement z window.google.maps.marker (musi być dostępny w tym zakresie)
      if (!window.google?.maps?.marker?.PinElement) {
        console.warn('⚠️ PinElement nie jest dostępny - pomijam aktualizację kolorów')
        return
      }
      const { PinElement } = window.google.maps.marker

      // Użyj requestAnimationFrame, aby zaktualizować wszystkie markery w jednej klatce
      requestAnimationFrame(() => {
        let updatedCount = 0
        sentimentData.regions.forEach(region => {
          const regionData = sentimentData.data[region]
          if (!regionData) return

          const scores = regionData.scores
          if (!scores || !Array.isArray(scores) || currentTimeIndex >= scores.length) return

          const score = scores[currentTimeIndex]
          if (score === null || score === undefined) return

          // Pobierz dodatkowe wartości
          const confidence = regionData.confidence?.[currentTimeIndex] ?? 0.5
          const fudLevel = regionData.fud_level?.[currentTimeIndex] ?? 0
          const fomoLevel = regionData.fomo_level?.[currentTimeIndex] ?? 0
          const marketImpact = regionData.market_impact?.[currentTimeIndex] ?? 2

          const color = getSentimentColor(score, confidence, fudLevel, fomoLevel)
          const scale = getMarketImpactScale(marketImpact)
          const label = getSentimentLabel(score)
          const marker = markersRef.current.find(m => {
            const pos = m.position
            return pos && pos.lat === regionData.coordinates?.lat && pos.lng === regionData.coordinates?.lng
          })

          if (marker) {
            // Sprawdź, czy kolor się zmienił (używamy ref zamiast próbować odczytać z DOM)
            const oldColor = colorsRef.current.get(region)
            
            // Aktualizuj tylko jeśli kolor się zmienił (optymalizacja - unikamy niepotrzebnych aktualizacji)
            if (oldColor !== color) {
              // Utwórz nowy PinElement z nowym kolorem
              const newPinElement = new PinElement({
                background: color,
                borderColor: '#fff',
                glyphColor: '#fff',
                scale: scale
              })
              // Zaktualizuj content markera
              marker.content = newPinElement.element
              pinsRef.current.set(region, newPinElement)
              colorsRef.current.set(region, color) // Zapisz nowy kolor w ref
              updatedCount++
              console.log(`  ✅ Zaktualizowano kolor markera ${region}: ${oldColor || 'brak'} → ${color}`)
            }
            // Aktualizuj tytuł markera (zawsze)
            marker.title = `${region}: ${label} (${score.toFixed(2)})`
          }
        })
        console.log(`✅ Zaktualizowano ${updatedCount} markerów w jednej klatce (requestAnimationFrame)`)
      })
    }, 50) // 50ms debounce
    
    // Cleanup: anuluj timeout przy unmount
    return () => {
      if (updateTimeoutRef.current) {
        clearTimeout(updateTimeoutRef.current)
      }
    }
  }, [currentTimeIndex, sentimentData]) // Tylko gdy zmienia się czas

  const handleTimeChange = useCallback((index) => {
    setCurrentTimeIndex(index)
    setIsPlaying(false)
  }, [])

  const togglePlay = useCallback(() => {
    if (currentTimeIndex >= sentimentData?.timestamps.length - 1) {
      setCurrentTimeIndex(0) // Zrestartuj od początku
    }
    setIsPlaying(!isPlaying)
  }, [currentTimeIndex, sentimentData?.timestamps.length, isPlaying])

  // Funkcja do przełączania stref dnia/nocy (3D view ze światłocieniem)
  const toggleDayNight = useCallback(() => {
    setShowDayNight(prev => {
      const newValue = !prev
      if (mapRef.current) {
        const newTilt = newValue ? 45 : 0 // 45 stopni = 3D view ze światłocieniem
        mapRef.current.setTilt(newTilt)
        console.log(`🌓 Tryb 3D ${newTilt > 0 ? 'włączony' : 'wyłączony'} - światłocień ${newTilt > 0 ? 'widoczny' : 'ukryty'}`)
      }
      return newValue
    })
  }, [])

  const getCurrentSentimentForRegion = (region) => {
    if (!sentimentData || !sentimentData.data || !sentimentData.data[region]) {
      console.debug(`Brak danych dla regionu ${region}`)
      return null
    }
    const scores = sentimentData.data[region].scores
    if (!scores || !Array.isArray(scores)) {
      console.warn(`Brak scores dla regionu ${region}`)
      return null
    }
    if (currentTimeIndex >= scores.length) {
      console.warn(`Indeks ${currentTimeIndex} poza zakresem scores (${scores.length}) dla regionu ${region}`)
      return null
    }
    const score = scores[currentTimeIndex]
    return score
  }

  const mapContainerStyle = {
    width: '100%',
    height: 'calc(100vh - 200px)'
  }

  // Map ID jest wymagany dla AdvancedMarkerElement
  // Możesz utworzyć własny Map ID w Google Cloud Console lub użyć domyślnego
  // Dla testów używamy domyślnego Map ID (można zmienić na własny)
  const MAP_ID = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || 'DEMO_MAP_ID'

  // Map options - tilt kontroluje widoczność światłocienia (strefy dnia/nocy)
  // tilt: 0 = widok płaski (bez światłocienia)
  // tilt: 45 = widok 3D (ze światłocieniem pokazującym strefy dnia/nocy)
  const mapOptions = {
    disableDefaultUI: false,
    zoomControl: true,
    streetViewControl: false,
    mapTypeControl: false, // Wyłącz kontrolę typu mapy - może powodować ostrzeżenia gdy mapId jest ustawiony
    fullscreenControl: true,
    // mapTypeId: 'satellite', // Usunięto - może powodować ostrzeżenia z mapId
    // Typ mapy jest kontrolowany przez mapId w Google Cloud Console
    mapId: MAP_ID, // WYMAGANE dla AdvancedMarkerElement
    tilt: showDayNight ? 45 : 0, // 3D view pokazuje światłocień (strefy dnia/nocy)
    heading: 0,
    // UWAGA: Nie można używać 'styles' gdy mapId jest ustawiony!
    // Style muszą być kontrolowane przez Google Cloud Console dla danego Map ID
    // mapTypeControlOptions zostało usunięte, aby uniknąć ostrzeżeń o stylach mapy
  }

  const center = {
    lat: 20,
    lng: 0
  }

  // Użyj useMemo PRZED warunkowymi returnami - Hooks muszą być wywoływane w tej samej kolejności
  // Użyj useMemo, żeby currentTimestamp nie zmieniał referencji jeśli wartość się nie zmieniła
  const currentTimestamp = useMemo(() => {
    if (!sentimentData || !sentimentData.timestamps || currentTimeIndex >= sentimentData.timestamps.length) {
      return null
    }
    const timestamp = sentimentData.timestamps[currentTimeIndex]
    // Loguj tylko podczas animacji, żeby nie zaśmiecać konsoli
    if (isPlaying) {
      console.log('🕐 currentTimestamp zaktualizowany:', {
        index: currentTimeIndex,
        timestamp: timestamp
      })
    }
    return timestamp
  }, [sentimentData, currentTimeIndex, isPlaying])

  if (loading) {
    return (
      <div className="app-loading">
        <div className="spinner"></div>
        <p>Ładowanie danych sentymentu...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="app-error">
        <h2>Błąd</h2>
        <p>{error}</p>
      </div>
    )
  }

  if (!sentimentData || !sentimentData.timestamps.length) {
    return (
      <div className="app-error">
        <h2>Brak danych</h2>
        <p>Nie znaleziono danych sentymentu dla wybranych parametrów.</p>
      </div>
    )
  }
  const currentDate = currentTimestamp ? parseISO(currentTimestamp) : new Date()

  // Sprawdź błędy ładowania Google Maps
  if (loadError) {
    return (
      <div className="app-error">
        <h2>Błąd ładowania Google Maps</h2>
        <p>{loadError.message || 'Nie można załadować Google Maps API'}</p>
        <p style={{ fontSize: '0.9rem', color: '#999', marginTop: '1rem' }}>
          Sprawdź czy klucz API jest poprawny i czy ma włączone odpowiednie API w Google Cloud Console.
        </p>
      </div>
    )
  }

  if (!GOOGLE_MAPS_API_KEY) {
    return (
      <div className="app-error">
        <h2>⚠️ Brak klucza Google Maps API</h2>
        <p>Ustaw VITE_GOOGLE_MAPS_API_KEY w pliku .env w katalogu webapp/frontend/</p>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>🌍 Sentiment Visualization - 3D Map</h1>
        <div className="time-display">
          <span>{format(currentDate, 'yyyy-MM-dd HH:mm:ss')} UTC</span>
          <button 
            className={`play-button ${isPlaying ? 'playing' : ''}`}
            onClick={togglePlay}
          >
            {isPlaying ? '⏸️ Pauza' : '▶️ Play'}
          </button>
          <button 
            className={`day-night-button ${showDayNight ? 'active' : ''}`}
            onClick={toggleDayNight}
            title={showDayNight ? 'Wyłącz światłocień (strefy dnia/nocy)' : 'Włącz światłocień (strefy dnia/nocy)'}
          >
            {showDayNight ? '🌓 3D ON' : '🌍 3D OFF'}
          </button>
        </div>
      </header>

      <PriceDisplay timestamp={currentTimestamp} resolutionHours={resolutionHours} />

      <div className="map-container">
        {!isLoaded && (
          <div className="map-loading">
            <div className="spinner"></div>
            <p>Ładowanie mapy Google...</p>
            {loadError && (
              <p style={{ color: '#ff6b6b', marginTop: '1rem', fontSize: '0.9rem' }}>
                Błąd: {loadError.message}
              </p>
            )}
          </div>
        )}
        {isLoaded && (
          <>
            <GoogleMap
              onLoad={(map) => {
                console.log('✅ Mapa Google załadowana:', map)
                mapRef.current = map
                setMapReady(true) // Oznacz mapę jako gotową
                console.log('✅ mapRef.current ustawiony:', !!mapRef.current)
                
                // Poczekaj na pełne załadowanie mapy (tilesloaded event)
                const tilesLoadedListener = google.maps.event.addListenerOnce(map, 'tilesloaded', () => {
                  console.log('✅ Tiles załadowane - mapa gotowa do wyświetlenia')
                  // Po załadowaniu tiles, sprawdź czy możemy utworzyć markery
                  if (sentimentData && sentimentData.regions) {
                    console.log('🔄 Tiles załadowane - sprawdzam czy mogę utworzyć markery...')
                  }
                })
                
                // Wymuś renderowanie mapy - może być problem z renderingType: "UNINITIALIZED"
                setTimeout(() => {
                  if (map) {
                    console.log('🔄 Wymuszam renderowanie mapy...')
                    try {
                      // Trigger resize event
                      google.maps.event.trigger(map, 'resize')
                      // Ustaw center ponownie, żeby wymusić renderowanie
                      map.setCenter(center)
                      // Ustaw zoom ponownie
                      map.setZoom(2)
                      console.log('✅ Renderowanie mapy wymuszone')
                    } catch (error) {
                      console.error('❌ Błąd wymuszania renderowania:', error)
                    }
                  }
                }, 500) // Zwiększono timeout do 500ms
              }}
              onError={(error) => {
                console.error('❌ Błąd mapy Google:', error)
              }}
              onUnmount={(map) => {
                console.log('🗑️ Mapa Google odmontowana')
              }}
              mapContainerStyle={{
                ...mapContainerStyle,
                minHeight: '400px' // Minimalna wysokość, żeby mapa była widoczna
              }}
              center={center}
              zoom={2}
              options={mapOptions}
            >
              {/* Renderuj regiony z kolorami sentymentu */}
              {sentimentData && sentimentData.regions && sentimentData.regions.map(region => {
                const score = getCurrentSentimentForRegion(region)
                const regionData = sentimentData.data[region]
                
                // Debug: loguj jeśli brak danych
                if (!regionData) {
                  console.warn(`Brak danych dla regionu: ${region}`)
                  return null
                }
                
                if (score === null || score === undefined) {
                  console.warn(`Brak score dla regionu ${region} w indeksie ${currentTimeIndex}`)
                  return null
                }

                // Pobierz dodatkowe wartości (jeśli dostępne)
                const confidence = regionData.confidence?.[currentTimeIndex] ?? 0.5
                const fudLevel = regionData.fud_level?.[currentTimeIndex] ?? 0
                const fomoLevel = regionData.fomo_level?.[currentTimeIndex] ?? 0
                const marketImpact = regionData.market_impact?.[currentTimeIndex] ?? 2

                const color = getSentimentColor(score, confidence, fudLevel, fomoLevel)
                const scale = getMarketImpactScale(marketImpact)
                const label = getSentimentLabel(score)
                const coords = regionData.coordinates

                if (!coords || !coords.lat || !coords.lng) {
                  console.warn(`Brak współrzędnych dla regionu: ${region}`)
                  return null
                }

                return (
                  <React.Fragment key={region}>
                    <Circle
                      center={{ lat: coords.lat, lng: coords.lng }}
                      radius={800000} // Zwiększono z 500km do 800km dla lepszej widoczności
                      options={{
                        fillColor: color,
                        fillOpacity: 0.7, // Zwiększono z 0.6 dla lepszej widoczności
                        strokeColor: color,
                        strokeOpacity: 1.0, // Zwiększono z 0.8 dla lepszej widoczności
                        strokeWeight: 3, // Zwiększono z 2 dla lepszej widoczności
                        clickable: false,
                        draggable: false,
                        editable: false,
                        zIndex: 1
                      }}
                    />
                    {/* Markery są teraz tworzone przez useEffect używając AdvancedMarkerElement */}
                    {selectedRegion === region && (
                      <InfoWindow
                        position={{ lat: coords.lat, lng: coords.lng }}
                        onCloseClick={() => setSelectedRegion(null)}
                      >
                        <div style={{ 
                          padding: '8px',
                          textAlign: 'center',
                          minWidth: '120px'
                        }}>
                          <div style={{ 
                            fontWeight: 'bold', 
                            fontSize: '14px',
                            marginBottom: '4px',
                            color: '#333'
                          }}>
                            {region}
                          </div>
                          <div style={{ 
                            fontSize: '12px',
                            color: color,
                            fontWeight: '600',
                            marginBottom: '2px'
                          }}>
                            {label}
                          </div>
                          <div style={{ 
                            fontSize: '11px',
                            color: '#666'
                          }}>
                            Score: {score.toFixed(2)}
                          </div>
                        </div>
                      </InfoWindow>
                    )}
                  </React.Fragment>
                )
              })}
            </GoogleMap>
            <TimeZoneOverlay currentTimestamp={currentTimestamp} />
          </>
        )}
      </div>

      <DataRangeControls
        availableRange={timeRange}
        currentDaysBack={daysBack}
        currentResolution={resolutionHours}
        onRangeChange={setDaysBack}
        onResolutionChange={setResolutionHours}
        isLoading={loading}
      />

      <TimeSlider
        timestamps={sentimentData.timestamps}
        currentIndex={currentTimeIndex}
        onTimeChange={handleTimeChange}
        isPlaying={isPlaying}
      />

      <Legend colors={SENTIMENT_COLORS} />
    </div>
  )
}

export default App

