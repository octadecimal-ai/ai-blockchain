-# Metoda Piotra Święsa - Prompt dla Trading Bota

## 🎯 Podsumowanie strategii

Strategia opiera się na **kontrariańskim podejściu** do gwałtownych ruchów ceny:
- Gdy RSI przekracza 70 (przekupienie) → **SHORT** (gramy na spadek)
- Gdy RSI spada poniżej 30 (wyprzedanie) → **LONG** (gramy na wzrost)
- Kluczowe: wchodzimy **po gwałtownym ruchu**, nie przed nim

---

## 📝 PROMPT DLA AI

```
Jesteś traderem używającym Metody Piotra Święsa na giełdzie dYdX.

=== ZASADY STRATEGII ===

**KIEDY OTWORZYĆ POZYCJĘ:**

1. SHORT (sprzedaż) gdy:
   - RSI_14 WŁAŚNIE przekroczyło 70 (w ostatnich 1-3 świecach)
   - Nastąpił gwałtowny ruch w górę (cena wzrosła >1% w krótkim czasie)
   - To jest moment "przegrzania" - cena prawdopodobnie spadnie

2. LONG (kupno) gdy:
   - RSI_14 WŁAŚNIE spadło poniżej 30 (w ostatnich 1-3 świecach)
   - Nastąpił gwałtowny ruch w dół (cena spadła >1% w krótkim czasie)
   - To jest moment "paniki" - cena prawdopodobnie odbije

**KIEDY ZAMKNĄĆ POZYCJĘ:**

- ZYSK: Zamknij gdy zarobisz 500-2000 USD (typowo 700-1000 USD)
- STRATA: Zamknij gdy stracisz 300-1000 USD (typowo max 500 USD)
- CZAS: Jeśli po 5-10 minutach pozycja nie idzie w Twoją stronę, rozważ wyjście
- RSI: Zamknij LONG gdy RSI > 60, zamknij SHORT gdy RSI < 40

**KIEDY CZEKAĆ (HOLD/WAIT):**

- RSI między 35-65 (strefa neutralna)
- Brak gwałtownego ruchu ceny
- RSI powoli zbliża się do progu, ale jeszcze go nie przekroczyło

=== PARAMETRY POZYCJI ===

- Rozmiar: 1 BTC (stały)
- Max strata: 500 USD (absolutne max: 1000 USD)
- Oczekiwany zysk: 500-2000 USD
- Slippage: Licz się z 2-3% straty przy wyjściu

=== ANALIZA RSI ===

Kluczowe pytania:
1. Czy RSI WŁAŚNIE przekroczyło 70 lub spadło poniżej 30?
2. Czy ruch był GWAŁTOWNY (szybki pump/dump)?
3. Czy to wygląda na "przeregulowanie" które się cofnie?

NIE wchodź gdy:
- RSI jest >70 lub <30 od dłuższego czasu (trend, nie odbicie)
- Ruch był powolny i stopniowy
- RSI dopiero zbliża się do progu

=== FORMAT ODPOWIEDZI ===

{
    "action": "LONG" | "SHORT" | "CLOSE" | "WAIT",
    "confidence": 1-10,
    "rsi_analysis": {
        "current": <wartość RSI>,
        "crossed_threshold": true/false,
        "threshold_crossed": 70 | 30 | null,
        "candles_since_cross": <liczba świec od przekroczenia>
    },
    "price_movement": {
        "is_sharp": true/false,
        "percent_change": <zmiana % w ostatnich świecach>,
        "direction": "UP" | "DOWN" | "SIDEWAYS"
    },
    "position_params": {
        "entry_price": <cena wejścia>,
        "stop_loss_usd": 500,
        "take_profit_usd": 1000
    },
    "reason": "<krótkie uzasadnienie w 1-2 zdaniach>"
}

=== PRZYKŁADY ===

**Przykład 1: Sygnał SHORT**
RSI = 73, był 65 dwie świece temu, cena skoczyła +2% w 3 minuty
→ ACTION: SHORT, confidence: 8
→ Reason: "RSI właśnie przebiło 70 po gwałtownym pumpie. Klasyczny sygnał na spadek."

**Przykład 2: Sygnał LONG**  
RSI = 28, był 35 świecę temu, cena spadła -1.5% w 2 minuty
→ ACTION: LONG, confidence: 7
→ Reason: "RSI poniżej 30 po gwałtownej panice sprzedażowej. Czas na odbicie."

**Przykład 3: WAIT**
RSI = 55, cena stabilna, brak wyraźnego ruchu
→ ACTION: WAIT, confidence: 2
→ Reason: "RSI w strefie neutralnej, brak gwałtownych ruchów. Czekam na sygnał."

**Przykład 4: FALSE SIGNAL**
RSI = 72, ale był >70 od 20 świec, cena powoli rosła
→ ACTION: WAIT, confidence: 3
→ Reason: "RSI wysoko, ale to silny trend - nie wchodzę przeciwko. Czekam na wyraźny szczyt."
```

---

## 🔧 ZALECENIA IMPLEMENTACYJNE

### 1. Zmień timeframe świec

```python
# BYŁO (za wolne):
candle_interval = "1h"  # świece godzinowe

# POWINNO BYĆ:
candle_interval = "1m"   # świece minutowe
# lub
candle_interval = "5m"   # świece 5-minutowe
```

### 2. Zwiększ częstotliwość sprawdzania

```python
# BYŁO:
check_interval = 3600  # co godzinę

# POWINNO BYĆ:
check_interval = 30    # co 30 sekund
# lub
check_interval = 60    # co minutę
```

### 3. Dodaj wykrywanie "przekroczenia progu"

```python
def detect_rsi_cross(rsi_history: list[float]) -> dict:
    """
    Wykrywa czy RSI WŁAŚNIE przekroczyło próg 70 lub 30
    """
    current = rsi_history[-1]
    previous = rsi_history[-2] if len(rsi_history) > 1 else current
    
    result = {
        "crossed_70": current > 70 and previous <= 70,
        "crossed_30": current < 30 and previous >= 30,
        "currently_above_70": current > 70,
        "currently_below_30": current < 30,
        "candles_above_70": sum(1 for r in rsi_history[-10:] if r > 70),
        "candles_below_30": sum(1 for r in rsi_history[-10:] if r < 30),
    }
    
    # Sygnał jest silny tylko gdy przekroczenie było NIEDAWNO (1-3 świece)
    result["strong_short_signal"] = result["crossed_70"] or (
        result["currently_above_70"] and result["candles_above_70"] <= 3
    )
    result["strong_long_signal"] = result["crossed_30"] or (
        result["currently_below_30"] and result["candles_below_30"] <= 3
    )
    
    return result
```

### 4. Dodaj wykrywanie gwałtowności ruchu

```python
def detect_sharp_move(candles: list[dict], lookback: int = 5) -> dict:
    """
    Wykrywa czy nastąpił gwałtowny ruch ceny
    """
    if len(candles) < lookback:
        return {"is_sharp": False}
    
    recent = candles[-lookback:]
    price_start = recent[0]["open"]
    price_end = recent[-1]["close"]
    
    percent_change = ((price_end - price_start) / price_start) * 100
    
    # Gwałtowny ruch = >1% w ciągu lookback świec
    is_sharp = abs(percent_change) > 1.0
    
    return {
        "is_sharp": is_sharp,
        "percent_change": round(percent_change, 2),
        "direction": "UP" if percent_change > 0 else "DOWN" if percent_change < 0 else "SIDEWAYS"
    }
```

### 5. Uproszczony prompt (zamiast obecnego)

```python
def build_piotr_prompt(
    current_price: float,
    rsi_data: dict,
    sharp_move: dict,
    position: dict | None,
    pnl_usd: float | None
) -> str:
    
    prompt = f"""Metoda Piotra Święsa - Analiza

=== AKTUALNE DANE ===
Cena: ${current_price:,.2f}
RSI(14): {rsi_data['current']:.1f}
RSI przekroczyło 70: {"TAK" if rsi_data.get('crossed_70') else "NIE"}
RSI spadło <30: {"TAK" if rsi_data.get('crossed_30') else "NIE"}
Świec od przekroczenia: {rsi_data.get('candles_above_70', 0) or rsi_data.get('candles_below_30', 0)}

Gwałtowny ruch: {"TAK" if sharp_move['is_sharp'] else "NIE"}
Zmiana ceny: {sharp_move['percent_change']:+.2f}%
Kierunek: {sharp_move['direction']}
"""
    
    if position:
        prompt += f"""
=== OTWARTA POZYCJA ===
Typ: {position['side']}
PnL: ${pnl_usd:+.2f}

Czy zamknąć? (max strata: -$500, cel zysku: +$500-1000)
"""
    else:
        prompt += """
=== BRAK POZYCJI ===
Szukam sygnału do wejścia.

SYGNAŁ SHORT: RSI > 70 + gwałtowny pump
SYGNAŁ LONG: RSI < 30 + gwałtowny dump
"""

    prompt += """
=== DECYZJA ===
Odpowiedz JSON: {"action": "LONG|SHORT|CLOSE|WAIT", "confidence": 1-10, "reason": "..."}
"""
    
    return prompt
```

### 6. Stały rozmiar pozycji

```python
# BYŁO (% kapitału):
size = capital * 0.15  # 15% kapitału

# POWINNO BYĆ (stały rozmiar w BTC):
POSITION_SIZE_BTC = 1.0  # zawsze 1 BTC
```

### 7. Stop loss w USD, nie w %

```python
# BYŁO:
stop_loss_percent = 0.015  # 1.5%

# POWINNO BYĘ:
MAX_LOSS_USD = 500  # max strata w dolarach
TARGET_PROFIT_USD = 1000  # cel zysku w dolarach

def calculate_stop_loss(entry_price: float, side: str, max_loss_usd: float, size_btc: float) -> float:
    """Oblicza cenę stop loss na podstawie max straty w USD"""
    price_move = max_loss_usd / size_btc
    
    if side == "LONG":
        return entry_price - price_move
    else:  # SHORT
        return entry_price + price_move
```

---

## ⚠️ WAŻNE UWAGI

### Model AI

Haiku jest OK do szybkich decyzji, ale rozważ:
- **Claude 3.5 Sonnet** - lepsze rozumienie kontekstu, ale droższy i wolniejszy
- **GPT-4o-mini** - szybki, tani, dobry do prostych decyzji

Dla tej prostej strategii Haiku powinien wystarczyć, o ile prompt jest jasny.

### Latencja

Pamiętaj o opóźnieniach:
- API call do LLM: ~1-3 sekundy
- API call do dYdX: ~0.5-1 sekunda
- Przy sprawdzaniu co 30s, masz ~26s na decyzję

### Slippage

Piotr wspomniał o 2-3% slippage. Uwzględnij to:
```python
expected_profit = gross_profit * 0.97  # -3% slippage
```

---

## 📊 Przykładowa architektura

```
┌─────────────────────────────────────────────────────────┐
│                    MAIN LOOP (co 30s)                   │
├─────────────────────────────────────────────────────────┤
│  1. Pobierz świece 1m/5m z dYdX                         │
│  2. Oblicz RSI(14) z ostatnich świec                    │
│  3. Wykryj przekroczenie progu (70/30)                  │
│  4. Wykryj gwałtowność ruchu                            │
│  5. Sprawdź czy masz otwartą pozycję                    │
│  6. Wyślij prosty prompt do AI                          │
│  7. Wykonaj akcję (LONG/SHORT/CLOSE/WAIT)               │
└─────────────────────────────────────────────────────────┘
```

---

## 🧪 Testowanie

Przed uruchomieniem na mainnet:

1. **Paper trading** - testuj na testnet dYdX
2. **Backtesting** - sprawdź strategię na historycznych danych
3. **Małe pozycje** - zacznij od 0.1 BTC, nie 1 BTC
4. **Monitoruj** - obserwuj przez kilka dni zanim zostawisz bez nadzoru
