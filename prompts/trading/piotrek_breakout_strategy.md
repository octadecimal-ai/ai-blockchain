# Strategia Tradingowa Piotrka - Breakout z Exit na Konsolidacji

## 📊 Opis Metody

Strategia oparta na identyfikacji breakoutów z wyjściem w momencie konsolidacji/wypłaszczenia ceny.

---

## 🎯 Prompt dla AI do analizy sygnałów w stylu Piotrka

```
Jesteś doświadczonym traderem kryptowalut stosującym strategię breakout trading na dYdX.

### ZASADY WEJŚCIA (LONG):
1. Identyfikuj kluczowe poziomy wsparcia/oporu (support/resistance) na wykresie
2. Czekaj na wyraźne przebicie poziomu oporu z wolumenem
3. Wchodź w pozycję LONG po potwierdzeniu breakoutu
4. Preferuj sytuacje gdzie cena konsolidowała się przed wybiciem

### ZASADY WYJŚCIA:
1. Zamykaj pozycję gdy cena zaczyna się "wypłaszczać" (konsolidacja na górze)
2. Nie czekaj na idealne szczyty - "dalej to loteria"
3. Lepszy pewny zysk niż ryzyko utraty wypracowanego profitu
4. Jeśli momentum słabnie - wychodź, nawet jeśli cena może jeszcze rosnąć

### SYGNAŁY OSTRZEGAWCZE (EXIT):
- Świece z małymi korpusami po dużym ruchu (doji, spinning top)
- Brak kontynuacji wzrostów przez 2-3 świece
- Cena "stoi w miejscu" - konsolidacja = czas wyjścia
- Wolumen spadający przy wzrostach

### TIMEFRAME:
- Preferowany: 1H-4H
- Styl: Day trading / Swing trading (pozycje trzymane kilka godzin)

### ZARZĄDZANIE RYZYKIEM:
- Akceptuj, że czasem wyjdziesz za wcześnie ("nie należało jeszcze sprzedawać")
- Lepiej zarobić mniej z pewnością niż ryzykować cały zysk
- Nie żałuj utraconych zysków po wyjściu - to część gry

### FORMAT ODPOWIEDZI:
Analizując wykres, podaj:
1. SYGNAŁ: BUY / SELL / HOLD / WAIT
2. PEWNOŚĆ: 1-10
3. POZIOMY: 
   - Entry (wejście)
   - Take Profit (cel)
   - Stop Loss (ochrona)
4. UZASADNIENIE: Krótkie wyjaśnienie decyzji
5. OSTRZEŻENIE: Co może pójść nie tak
```

---

## 📈 Analiza na podstawie rzeczywistych transakcji Piotrka

### Przypadek 1 (z screenów):

| Czas | Komentarz | Cena | Akcja |
|------|-----------|------|-------|
| 18:41 | "obstawiłem że będzie spadać ;)" | Wejście | Otwarcie pozycji (sarkazm - faktycznie LONG) |
| 21:20 | "jest nieźle!" | +wzrost | Pozycja w zysku |
| 21:24 | "lepiej!" | +dalszy wzrost | Zysk rośnie |
| 21:34 | "zarabiam 892 dolary" | Szczyt | Rozważanie wyjścia |
| 22:08 | "sprzedam to teraz, bo już się wypłaszczyło" | Exit | Zamknięcie z zyskiem $620 |
| 22:46 | "nie należało jednak jeszcze sprzedawać" | +wzrost | Refleksja (cena dalej rosła) |

### Wnioski:
1. **Wejście**: Po identyfikacji momentum wzrostowego
2. **Trzymanie**: Dopóki trend jest wyraźny
3. **Wyjście**: Gdy cena zaczyna konsolidować ("wypłaszcza się")
4. **Akceptacja**: Czasem wyjście jest przedwczesne - to OK

---

## 🔧 Implementacja w kodzie

### Sygnały do monitorowania:

```python
class PiotrekStrategy:
    """
    Strategia breakout z exit na konsolidacji.
    Bazowana na stylu tradingowym Piotrka.
    """
    
    def __init__(self):
        self.min_breakout_percent = 2.0  # Minimalne przebicie %
        self.consolidation_threshold = 0.5  # Próg konsolidacji %
        self.consolidation_candles = 3  # Liczba świec do wykrycia konsolidacji
    
    def detect_breakout(self, df, resistance_level):
        """Wykrywa przebicie poziomu oporu."""
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        
        # Breakout gdy cena przebija resistance z impetem
        if prev_price < resistance_level and current_price > resistance_level:
            breakout_strength = (current_price - resistance_level) / resistance_level * 100
            if breakout_strength >= self.min_breakout_percent:
                return True, breakout_strength
        return False, 0
    
    def detect_consolidation(self, df):
        """
        Wykrywa konsolidację - sygnał do wyjścia.
        'Wypłaszczenie' = małe ruchy cenowe przez kilka świec.
        """
        recent_candles = df.tail(self.consolidation_candles)
        
        # Oblicz zakres ruchów
        price_range = recent_candles['high'].max() - recent_candles['low'].min()
        avg_price = recent_candles['close'].mean()
        range_percent = (price_range / avg_price) * 100
        
        # Jeśli zakres mały = konsolidacja
        if range_percent < self.consolidation_threshold:
            return True, "Cena się wypłaszczyła - rozważ wyjście"
        return False, None
    
    def get_signal(self, df, support_levels, resistance_levels):
        """
        Generuje sygnał tradingowy w stylu Piotrka.
        """
        # Sprawdź breakout
        for resistance in resistance_levels:
            is_breakout, strength = self.detect_breakout(df, resistance)
            if is_breakout:
                return {
                    'signal': 'BUY',
                    'reason': f'Breakout powyżej {resistance:.2f} z siłą {strength:.1f}%',
                    'confidence': min(strength * 2, 10)
                }
        
        # Sprawdź konsolidację (sygnał wyjścia)
        is_consolidating, reason = self.detect_consolidation(df)
        if is_consolidating:
            return {
                'signal': 'SELL',
                'reason': reason,
                'confidence': 7
            }
        
        return {
            'signal': 'HOLD',
            'reason': 'Brak wyraźnego sygnału',
            'confidence': 5
        }
```

---

## 📋 Checklist przed transakcją

### Wejście (LONG):
- [ ] Zidentyfikowany poziom oporu
- [ ] Cena przebiła poziom z wolumenem
- [ ] Świeca zamknięta powyżej oporu
- [ ] Brak negatywnych wiadomości/wydarzeń

### Wyjście:
- [ ] Cena zaczyna się "wypłaszczać"
- [ ] 2-3 świece z małym zakresem
- [ ] Wolumen spada
- [ ] Lepiej wcześniej niż za późno!

---

## ⚠️ Ważne uwagi

1. **"Dalej to loteria"** - gdy momentum słabnie, nie zgaduj co będzie dalej
2. **Akceptuj przedwczesne wyjścia** - czasem cena pójdzie dalej, to normalne
3. **Pewny zysk > potencjalny większy zysk** - zarządzanie ryzykiem jest kluczowe
4. **Refleksja po transakcji** - analizuj co mogłeś zrobić lepiej, ale nie żałuj

---

*Prompt utworzony na podstawie analizy rzeczywistych transakcji Piotrka z dnia 2024-12-09*

