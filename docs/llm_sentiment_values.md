# Wartości zwracane przez LLM Sentiment Analysis

## Główne wartości

### `score` (Float: -1.0 do 1.0)
**Główna wartość sentymentu**
- **-1.0 do -0.6**: Very Bearish (bardzo niedźwiedzi)
- **-0.6 do -0.2**: Bearish (niedźwiedzi)
- **-0.2 do 0.2**: Neutral (neutralny)
- **0.2 do 0.6**: Bullish (byczy)
- **0.6 do 1.0**: Very Bullish (bardzo byczy)

**Użycie**: Określa podstawowy kolor pinezki (czerwony → szary → zielony)

---

### `confidence` (Float: 0.0 do 1.0)
**Pewność analizy LLM**
- **0.0-0.3**: Niska pewność (mało danych, sprzeczne sygnały)
- **0.3-0.7**: Średnia pewność
- **0.7-1.0**: Wysoka pewność (spójne sygnały, dużo danych)

**Użycie**: 
- **Wysoka confidence** → ciemniejszy, bardziej nasycony kolor (pewny sentyment)
- **Niska confidence** → jaśniejszy, mniej nasycony kolor (niepewny sentyment)
- Może być używana jako **opacity** lub **saturation** w HSL

---

### `fud_level` (Float: 0.0 do 1.0)
**Poziom strachu, niepewności i wątpliwości (Fear, Uncertainty, Doubt)**
- **0.0-0.3**: Niski FUD (spokojny rynek)
- **0.3-0.7**: Średni FUD
- **0.7-1.0**: Wysoki FUD (panika, strach)

**Użycie**:
- **Wysoki FUD** → może przyciemniać kolor (dodatkowy efekt "ciemności")
- Może być używany jako **mnożnik ciemności** dla kolorów niedźwiedzich
- Dla kolorów byczych → może zmniejszać intensywność (FUD hamuje optymizm)

---

### `fomo_level` (Float: 0.0 do 1.0)
**Poziom FOMO (Fear Of Missing Out)**
- **0.0-0.3**: Niski FOMO (spokojny rynek)
- **0.3-0.7**: Średni FOMO
- **0.7-1.0**: Wysoki FOMO (panika kupna, "nie przegap")

**Użycie**:
- **Wysoki FOMO** → może rozjaśniać/rozjaśniać kolor (dodatkowy efekt "jasności")
- Może być używany jako **mnożnik jasności** dla kolorów byczych
- Dla kolorów niedźwiedzich → może zmniejszać intensywność (FOMO hamuje pesymizm)

---

### `market_impact` (String: "low", "medium", "high")
**Oszacowany wpływ sentymentu na rynek**
- **"low"**: Niski wpływ (lokalne, małe znaczenie)
- **"medium"**: Średni wpływ
- **"high"**: Wysoki wpływ (globalne, duże znaczenie)

**Użycie**:
- **High impact** → większy rozmiar pinezki lub grubsza obwódka
- **Low impact** → mniejszy rozmiar pinezki lub cieńsza obwódka
- Może być używany jako **scale** dla PinElement

---

## Propozycja systemu odcieni kolorów

### 1. Podstawowy kolor (score)
Używamy gradientu zamiast 5 stałych kolorów:
- **-1.0**: Ciemny czerwony (#8B0000)
- **-0.5**: Czerwony (#DC143C)
- **0.0**: Szary (#808080)
- **0.5**: Zielony (#32CD32)
- **1.0**: Ciemny zielony (#006400)

### 2. Odcień w zależności od pozycji w zakresie
- **Graniczne wartości** (blisko -1.0, -0.6, -0.2, 0.2, 0.6, 1.0) → **ciemniejszy odcień**
- **Środek zakresu** (np. -0.4, 0.0, 0.4) → **jaśniejszy odcień**

### 3. Modyfikacja przez confidence
- **Wysoka confidence** (0.7-1.0) → **+20% nasycenia** (bardziej intensywny)
- **Niska confidence** (0.0-0.3) → **-30% nasycenia** (mniej intensywny)

### 4. Modyfikacja przez FUD/FOMO
- **Wysoki FUD** → **-10% jasności** (przyciemnienie)
- **Wysoki FOMO** → **+10% jasności** (rozjaśnienie)

### 5. Modyfikacja przez market_impact
- **High impact** → **scale: 1.3** (większa pinezka)
- **Medium impact** → **scale: 1.2** (normalna)
- **Low impact** → **scale: 1.0** (mniejsza pinezka)

---

## Przykład obliczania koloru

```javascript
// Dane wejściowe
score = 0.65        // Bullish
confidence = 0.85   // Wysoka pewność
fud_level = 0.2     // Niski FUD
fomo_level = 0.7    // Wysoki FOMO
market_impact = "high"

// 1. Podstawowy kolor z gradientu
baseColor = interpolateColor(score)  // #32CD32 (zielony)

// 2. Odcień w zależności od pozycji w zakresie
// 0.65 jest blisko granicy 0.6 → ciemniejszy
shade = calculateShade(score)  // -10% jasności

// 3. Modyfikacja przez confidence
// Wysoka confidence → +20% nasycenia
saturation = 1.0 + (confidence - 0.5) * 0.4  // 1.14

// 4. Modyfikacja przez FUD/FOMO
// Wysoki FOMO → +10% jasności
brightness = 1.0 + (fomo_level - 0.5) * 0.2  // 1.04

// 5. Finalny kolor
finalColor = adjustColor(baseColor, shade, saturation, brightness)
// Wynik: Ciemniejszy, bardziej nasycony zielony z lekkim rozjaśnieniem
```

