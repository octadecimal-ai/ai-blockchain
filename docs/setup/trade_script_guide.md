# Przewodnik po skrypcie trade.sh

> 📚 **Zobacz też**: [Przewodnik po podsumowaniach i logach](../trading/logs_summary_guide.md) - szczegółowe wyjaśnienie wszystkich metryk wyświetlanych w podsumowaniach

## Wprowadzenie

Skrypt `trade.sh` to główne narzędzie do uruchamiania automatycznego tradingu na dYdX w trybie **paper trading** (wirtualne pieniądze). Działa podobnie do interfejsu dYdX w przeglądarce, ale automatyzuje proces podejmowania decyzji tradingowych na podstawie wybranej strategii.

## Jak działa skrypt

Skrypt `trade.sh` jest wrapperem, który:
1. **Przyjmuje parametry** z linii poleceń
2. **Waliduje konfigurację** (baza danych, tryb pracy)
3. **Uruchamia bota Python** (`run_paper_trading_enhanced.py`) z przekazanymi parametrami

Bot działa w pętlach:
- Co określony **interwał** (domyślnie 5 minut) sprawdza rynek
- Analizuje ceny i wskaźniki techniczne dla wybranych par
- Otwiera/zamyka pozycje zgodnie ze strategią
- Monitoruje otwarte pozycje (Stop Loss, Take Profit)
- Zatrzymuje się po osiągnięciu limitów (czas, strata)

## Parametry i ich wpływ na działanie

### `--strategy=NAZWA`
**Domyślnie:** `piotrek_breakout_strategy`

Określa strategię tradingową używaną przez bota. Dostępne strategie:

1. **piotrek_breakout_strategy** (domyślna) - strategia breakout:
   - Szuka momentów wybicia z konsolidacji
   - Otwiera pozycje LONG gdy cena przebija opór
   - Zamyka pozycje gdy następuje konsolidacja lub osiągnięty zostanie SL/TP
   - Działa dobrze na średnich interwałach (5-15 min)
   - Zalecana dla początkujących

2. **scalping_strategy** - strategia scalpingowa:
   - **Najszybsza strategia** - generuje wiele małych transakcji
   - Działa na bardzo krótkich interwałach (30 sek - 5 min)
   - Wykrywa małe ruchy cenowe (0.1-0.5%)
   - Szybko zamyka pozycje (małe zyski, ale częste)
   - Używa RSI (7 okres), MACD (8/21/5), ATR dla szybkich sygnałów
   - **Wymaga:** bardzo krótkich interwałów (`--interval=30sek` lub `1min`)
   - **Zalecana dla:** doświadczonych traderów, którzy mogą monitorować bot w czasie rzeczywistym

**Wpływ:** Strategia decyduje o tym, **kiedy** i **jak** bot otwiera pozycje. Różne strategie reagują inaczej na te same warunki rynkowe.

**Przykład użycia scalping:**
```bash
./scripts/trade.sh \
  --strategy=scalping_strategy \
  --interval=30sek \
  --time-limit=30min \
  --max-loss=200
```

---

### `--mode=MODE`
**Domyślnie:** `paper`

Określa tryb tradingu:
- **paper** - wirtualne pieniądze (bezpieczne testowanie)
- **real** - prawdziwe pieniądze (wymaga API keys, obecnie nie zaimplementowane)

**Wpływ:** 
- W trybie `paper` wszystkie transakcje są symulowane - nie używasz prawdziwych środków
- W trybie `real` (gdy będzie dostępny) bot będzie wykonywał prawdziwe transakcje na dYdX

**Uwaga:** Obecnie tylko tryb `paper` jest dostępny. Próba użycia `--mode=real` zakończy się błędem.

---

### `--time-limit=CZAS`
**Domyślnie:** brak limitu (bot działa do ręcznego zatrzymania)

Określa maksymalny czas trwania sesji tradingowej.

**Format czasu:**
- `10h` - 10 godzin
- `30min` - 30 minut
- `45sek` - 45 sekund
- `2h 30min 15sek` - kombinacja (2 godziny, 30 minut, 15 sekund)

**Przykłady:**
```bash
--time-limit=1h        # Bot działa przez 1 godzinę
--time-limit=30min     # Bot działa przez 30 minut
--time-limit=24h        # Bot działa przez całą dobę
```

**Wpływ:**
- Po osiągnięciu limitu czasu bot automatycznie zatrzymuje się
- Pokazuje końcowe podsumowanie (PnL, liczba transakcji, ROI)
- Przydatne do testowania strategii przez określony czas bez konieczności ręcznego zatrzymywania

---

### `--interval=CZAS`
**Domyślnie:** `5min` (300 sekund)

Określa jak często bot sprawdza rynek i podejmuje decyzje.

**Format:** taki sam jak `--time-limit`

**Przykłady:**
```bash
--interval=1min        # Sprawdzanie co 1 minutę (agresywny trading)
--interval=5min        # Sprawdzanie co 5 minut (domyślne)
--interval=15min       # Sprawdzanie co 15 minut (spokojniejszy trading)
--interval=30sek       # Sprawdzanie co 30 sekund (bardzo agresywny)
```

**Wpływ:**
- **Mniejszy interwał** (np. 1min) = więcej sprawdzeń = więcej możliwości wejścia/wyjścia, ale też więcej "szumu" i potencjalnie więcej transakcji
- **Większy interwał** (np. 15min) = mniej sprawdzeń = mniej transakcji, ale bardziej przemyślane decyzje
- Zbyt mały interwał może prowadzić do nadmiernego tradingu (overtrading)
- Zbyt duży interwał może spowodować przegapienie okazji

**Zalecenie:** Dla strategii breakout 5-15 minut to dobry kompromis.

---

### `--max-loss=KWOTA`
**Domyślnie:** brak limitu

Określa maksymalną dopuszczalną stratę w USD. Gdy całkowity PnL (zysk/strata) spadnie poniżej tej wartości, bot automatycznie się zatrzyma.

**Format:**
- Liczba z opcjonalną jednostką: `100`, `50.50`, `100USDC`, `50USD`
- Jednostka jest ignorowana (zawsze traktowane jako USD)

**Przykłady:**
```bash
--max-loss=100         # Zatrzymaj gdy strata osiągnie $100
--max-loss=50.50       # Zatrzymaj gdy strata osiągnie $50.50
--max-loss=500USDC    # Zatrzymaj gdy strata osiągnie $500
```

**Wpływ:**
- **Ochrona kapitału** - zapobiega dalszym stratom gdy strategia nie działa
- Bot sprawdza całkowity PnL (realized + unrealized) po każdym cyklu
- Po osiągnięciu limitu bot zatrzymuje się i pokazuje podsumowanie
- Przydatne do testowania strategii z kontrolą ryzyka

**Uwaga:** Limit dotyczy **całkowitej straty** (suma wszystkich zamkniętych transakcji + niezrealizowane straty z otwartych pozycji).

---

### `--symbols=LISTA`
**Domyślnie:** `BTC-USD,ETH-USD`

Określa które pary walutowe bot będzie monitorował i na których będzie handlował.

**Format:** Lista symboli oddzielonych przecinkami (bez spacji lub ze spacjami)

**Przykłady:**
```bash
--symbols=BTC-USD,ETH-USD              # BTC i ETH (domyślnie)
--symbols=BTC-USD,ETH-USD,SOL-USD      # BTC, ETH i SOL
--symbols=BTC-USD                      # Tylko BTC
--symbols=SOL-USD,AVAX-USD,MATIC-USD   # Tylko altcoiny
```

**Wpływ:**
- Bot analizuje **wszystkie** podane symbole w każdym cyklu
- Może otworzyć pozycje na **każdym** z symboli (z ograniczeniem max pozycji)
- Więcej symboli = więcej możliwości, ale też więcej zasobów
- Różne pary mają różną zmienność i charakterystykę rynku

**Uwaga:** Symbole muszą być w formacie dYdX (np. `BTC-USD`, nie `BTC/USDT`).

---

### `--balance=KWOTA`
**Domyślnie:** `10000` (10,000 USD)

Określa początkowy kapitał wirtualnego konta (tylko dla paper trading).

**Format:** Liczba (może być z kropką dziesiętną)

**Przykłady:**
```bash
--balance=10000        # $10,000 (domyślnie)
--balance=50000        # $50,000
--balance=1000         # $1,000 (mały kapitał)
--balance=100000       # $100,000 (duży kapitał)
```

**Wpływ:**
- Większy kapitał = większe pozycje (rozmiar pozycji to % kapitału)
- Większy kapitał = większe potencjalne zyski/straty w wartościach bezwzględnych
- Mniejszy kapitał = szybsze testowanie strategii, łatwiejsze śledzenie zmian
- Kapitał wpływa na **rozmiar pozycji**, nie na **częstotliwość** transakcji

**Uwaga:** Ten parametr działa tylko w trybie `paper`. W trybie `real` kapitał będzie pochodził z Twojego prawdziwego konta dYdX.

---

### `--leverage=LICZBA`
**Domyślnie:** `2` (2x dźwignia)

Określa domyślną dźwignię używaną przy otwieraniu pozycji.

**Format:** Liczba od 1 do 20 (zgodnie z limitami dYdX)

**Przykłady:**
```bash
--leverage=1           # Bez dźwigni (1x)
--leverage=2           # 2x dźwignia (domyślnie)
--leverage=5           # 5x dźwignia (agresywne)
--leverage=10          # 10x dźwignia (bardzo agresywne)
--leverage=20          # 20x dźwignia (maksymalna na dYdX)
```

**Wpływ:**
- **Dźwignia** działa tak samo jak na dYdX w przeglądarce:
  - 2x dźwignia = z $1000 możesz kontrolować pozycję o wartości $2000
  - Zyski i straty są **mnożone** przez dźwignię
- **Wyższa dźwignia** = większe zyski/straty, większe ryzyko
- **Niższa dźwignia** = mniejsze zyski/straty, mniejsze ryzyko
- Dźwignia wpływa na **margin** (zabezpieczenie) wymagane do otwarcia pozycji

**Przykład:**
- Kapitał: $10,000
- Dźwignia: 2x
- Rozmiar pozycji: 10% kapitału = $1,000
- Z dźwignią 2x: kontrolujesz pozycję o wartości $2,000
- Margin (zabezpieczenie): $1,000
- Jeśli cena wzrośnie o 5%: zysk = $2,000 × 5% = $100 (10% zysku na kapitale)
- Jeśli cena spadnie o 5%: strata = $2,000 × 5% = $100 (10% straty na kapitale)

**Zalecenie:** Dla testów zacznij od 2-3x. Wyższa dźwignia zwiększa ryzyko.

---

### `--account=NAZWA`
**Domyślnie:** `piotrek_bot`

Określa nazwę konta paper trading w bazie danych.

**Format:** Dowolna nazwa (bez spacji, najlepiej alfanumeryczna)

**Przykłady:**
```bash
--account=piotrek_bot      # Domyślne konto
--account=test_bot         # Konto testowe
--account=production_bot   # Konto produkcyjne
--account=my_strategy_v1   # Konto dla konkretnej strategii
```

**Wpływ:**
- Każde konto ma **osobną historię** transakcji i saldo
- Możesz mieć **wiele kont** do testowania różnych strategii
- Historia jest przechowywana w bazie danych (SQLite lub PostgreSQL)
- Przydatne do porównywania wyników różnych konfiguracji

**Uwaga:** Jeśli konto nie istnieje, zostanie utworzone automatycznie z początkowym saldem określonym przez `--balance`.

---

### `--verbose` lub `-v`
**Domyślnie:** wyłączone

Włącza szczegółowe logowanie (poziom DEBUG).

**Wpływ:**
- **Bez `--verbose`:** Bot pokazuje tylko ważne informacje (INFO level)
  - Otwarcie/zamknięcie pozycji
  - Podsumowania co 60 sekund
  - Błędy i ostrzeżenia
  
- **Z `--verbose`:** Bot pokazuje wszystkie szczegóły (DEBUG level)
  - Wszystkie sprawdzenia rynku
  - Analizy strategii (nawet gdy nie ma sygnału)
  - Szczegóły obliczeń
  - Komunikaty z API dYdX
  - Przydatne do debugowania i zrozumienia działania strategii

**Zalecenie:** Użyj `--verbose` gdy:
- Testujesz nową strategię
- Chcesz zrozumieć dlaczego bot podejmuje określone decyzje
- Debugujesz problemy

---

## Przykłady użycia

### Podstawowe uruchomienie
```bash
./scripts/trade.sh
```
Uruchamia bota z domyślnymi ustawieniami:
- Strategia: piotrek_breakout_strategy
- Tryb: paper
- Symbole: BTC-USD, ETH-USD
- Interwał: 5 minut
- Kapitał: $10,000
- Dźwignia: 2x
- Bez limitu czasu i straty

---

### Krótki test (10 minut)
```bash
./scripts/trade.sh --time-limit=10min
```
Idealne do szybkiego sprawdzenia czy wszystko działa. Bot zatrzyma się automatycznie po 10 minutach.

---

### Agresywny trading
```bash
./scripts/trade.sh --interval=1min --leverage=5 --time-limit=1h
```
- Sprawdzanie co 1 minutę (szybkie reakcje)
- Dźwignia 5x (większe zyski/straty)
- Limit czasu 1 godzina

**Uwaga:** Wysoka dźwignia i mały interwał = wysokie ryzyko. Używaj tylko w paper trading!

---

### Konserwatywny trading
```bash
./scripts/trade.sh --interval=15min --leverage=1 --balance=50000 --max-loss=1000
```
- Sprawdzanie co 15 minut (spokojniejsze podejście)
- Bez dźwigni (1x)
- Większy kapitał ($50,000)
- Ochrona przed stratą ($1,000)

---

### Testowanie wielu par
```bash
./scripts/trade.sh --symbols=BTC-USD,ETH-USD,SOL-USD,AVAX-USD --max-loss=200
```
Monitoruje 4 pary jednocześnie. Zatrzyma się gdy strata osiągnie $200.

---

### Debugowanie z pełnymi logami
```bash
./scripts/trade.sh --verbose --interval=30sek --time-limit=5min
```
Pełne logi + szybkie sprawdzanie (30 sekund) + krótki test (5 minut). Przydatne do zrozumienia działania strategii.

---

### Długa sesja z dużym kapitałem
```bash
./scripts/trade.sh --balance=100000 --time-limit=24h --max-loss=5000
```
- Kapitał: $100,000
- Czas: 24 godziny
- Maksymalna strata: $5,000

---

## Jak bot podejmuje decyzje

1. **Co określony interwał** bot:
   - Pobiera aktualne ceny z dYdX dla wszystkich symboli
   - Pobiera dane historyczne (świece OHLCV)
   - Analizuje dane używając strategii

2. **Strategia analizuje:**
   - Wzorce cenowe (breakout, konsolidacja)
   - Wskaźniki techniczne
   - Warunki wejścia/wyjścia

3. **Jeśli strategia generuje sygnał:**
   - Bot sprawdza czy może otworzyć pozycję (limit pozycji, czy już jest pozycja na tym symbolu)
   - Oblicza rozmiar pozycji (procent kapitału)
   - Otwiera pozycję z określoną dźwignią
   - Ustawia Stop Loss i Take Profit (jeśli strategia je określa)

4. **Dla otwartych pozycji:**
   - Bot sprawdza czy cena osiągnęła Stop Loss lub Take Profit
   - Bot sprawdza czy strategia generuje sygnał wyjścia
   - Jeśli tak - zamyka pozycję

5. **Po każdym cyklu:**
   - Bot pokazuje podsumowanie (co 60 sekund)
   - Sprawdza limity (czas, strata)
   - Jeśli limit osiągnięty - zatrzymuje się

---

## Jak skrypt wykrywa charakterystyczne momenty

Strategia `piotrek_breakout_strategy` używa kilku mechanizmów do wykrywania momentów wejścia i wyjścia. Poniżej opisano jak każdy z nich działa:

### 1. Identyfikacja poziomów wsparcia i oporu (Support/Resistance)

**Co to jest:**
- **Opór (Resistance)** - poziom cenowy, przy którym cena ma tendencję do zatrzymania się lub odbicia w dół
- **Wsparcie (Support)** - poziom cenowy, przy którym cena ma tendencję do zatrzymania się lub odbicia w górę

**Jak bot to wykrywa:**
1. Analizuje ostatnie 20 świec (domyślnie)
2. Szuka **lokalnych maksimów** (szczyty) - to są poziomy oporu
3. Szuka **lokalnych minimów** (dołki) - to są poziomy wsparcia
4. Grupuje podobne poziomy (jeśli są blisko siebie, uśrednia je)

**Przykład:**
```
Cena BTC-USD:
- Ostatnie maksima: $45,000, $45,200, $45,100
- Bot identyfikuje opór w okolicy $45,100 (uśrednione)
- Ostatnie minima: $44,000, $44,100, $44,050
- Bot identyfikuje wsparcie w okolicy $44,050 (uśrednione)
```

**Dlaczego to ważne:**
- Poziomy S/R to miejsca, gdzie cena często "reaguje"
- Przebicie oporu może oznaczać kontynuację wzrostu
- Spadek do wsparcia może oznaczać odbicie

---

### 2. Wykrywanie breakoutu (przebicia oporu)

**Co to jest breakout:**
Breakout to moment, gdy cena **przebija** poziom oporu z impetem, co często oznacza kontynuację ruchu wzrostowego.

**Jak bot to wykrywa:**
1. Sprawdza czy **poprzednia świeca** zamknęła się **poniżej** poziomu oporu
2. Sprawdza czy **aktualna świeca** zamknęła się **powyżej** poziomu oporu
3. Oblicza **siłę breakoutu** - o ile procent cena przebiła opór
4. Jeśli siła breakoutu ≥ próg (domyślnie 1.0%), generuje sygnał BUY

**Przykład:**
```
Poziom oporu: $45,000
Poprzednia świeca: zamknięcie $44,950 (poniżej oporu) ✅
Aktualna świeca: zamknięcie $45,500 (powyżej oporu) ✅
Siła breakoutu: (45,500 - 45,000) / 45,000 = 1.11% ✅

Wynik: BREAKOUT wykryty! Sygnał BUY
```

**Parametry wpływające:**
- `breakout_threshold` (domyślnie 1.0%) - minimalna siła breakoutu
- Im wyższy próg, tym mniej sygnałów, ale bardziej pewne
- Im niższy próg, tym więcej sygnałów, ale mniej pewne

---

### 3. Obliczanie momentum (pędu cenowego)

**Co to jest momentum:**
Momentum mierzy **szybkość zmiany ceny** - czy cena rośnie szybko, wolno, czy spada.

**Jak bot to oblicza:**
1. Porównuje cenę aktualną z ceną sprzed N świec (domyślnie 5)
2. Oblicza procentową zmianę: `(cena_aktualna - cena_przeszła) / cena_przeszła × 100`
3. Dodatnie momentum = cena rośnie
4. Ujemne momentum = cena spada

**Przykład:**
```
Cena 5 świec temu: $44,000
Cena aktualna: $45,000
Momentum: (45,000 - 44,000) / 44,000 × 100 = +2.27%

Interpretacja: Cena rośnie z momentum +2.27%
```

**Jak to wpływa na decyzje:**
- Wysokie dodatnie momentum = silny trend wzrostowy = większa pewność sygnału
- Niskie lub ujemne momentum = słaby trend = mniejsza pewność lub sygnał wyjścia

---

### 4. Potwierdzenie wolumenem

**Co to jest:**
Wolumen to **ilość transakcji** w danym okresie. Wysoki wolumen przy breakoutu potwierdza siłę ruchu.

**Jak bot to sprawdza:**
1. Oblicza średni wolumen z ostatnich 20 świec
2. Porównuje aktualny wolumen ze średnim
3. Oblicza współczynnik: `aktualny_wolumen / średni_wolumen`
4. Współczynnik > 1.0 = wolumen powyżej średniej (dobry znak)
5. Współczynnik < 1.0 = wolumen poniżej średniej (słabszy znak)

**Przykład:**
```
Średni wolumen (20 świec): 1,000 BTC
Aktualny wolumen: 1,500 BTC
Współczynnik: 1,500 / 1,000 = 1.5

Interpretacja: Wolumen jest 50% wyższy niż średnia - silne potwierdzenie
```

**Dlaczego to ważne:**
- Breakout z wysokim wolumenem = silny, prawdopodobnie kontynuuje się
- Breakout z niskim wolumenem = słaby, może być fałszywy (false breakout)

---

### 5. Obliczanie pewności sygnału (Confidence)

**Co to jest:**
Confidence to **ocena siły sygnału** w skali 0-10. Im wyższa, tym bardziej pewny sygnał.

**Jak bot to oblicza:**
Bot sumuje trzy składniki:
1. **Siła breakoutu** - im większe przebicie, tym wyższa ocena
2. **Momentum** - im silniejsze momentum, tym wyższa ocena
3. **Wolumen** - im wyższy wolumen, tym wyższa ocena

**Formuła (uproszczona):**
```
Confidence = min(10, (
    (siła_breakoutu / próg_breakoutu) × 3 +
    (momentum / 2) +
    (współczynnik_wolumenu × 2)
))
```

**Przykład:**
```
Siła breakoutu: 1.5% (próg: 1.0%)
Momentum: +3.0%
Wolumen: 1.5x średniej

Confidence = min(10, (
    (1.5 / 1.0) × 3 +    # = 4.5
    (3.0 / 2) +           # = 1.5
    (1.5 × 2)            # = 3.0
)) = min(10, 9.0) = 9.0

Wynik: Sygnał z confidence 9.0/10 - bardzo pewny!
```

**Parametr `min_confidence`:**
- Domyślnie: 6.0
- Bot otworzy pozycję tylko jeśli confidence ≥ min_confidence
- Wyższy próg = mniej transakcji, ale bardziej pewne
- Niższy próg = więcej transakcji, ale mniej pewne

---

### 6. Wykrywanie konsolidacji (wypłaszczenia)

**Co to jest konsolidacja:**
Konsolidacja to moment, gdy cena **"stoi w miejscu"** - małe ruchy cenowe przez kilka świec. W strategii Piotrka to sygnał do **wyjścia**.

**Jak bot to wykrywa:**
1. Analizuje ostatnie N świec (domyślnie 3)
2. Oblicza **zakres cenowy**: `maksimum - minimum`
3. Oblicza **procentowy zakres**: `(zakres / średnia_cena) × 100`
4. Jeśli zakres < próg (domyślnie 0.5%), to konsolidacja

**Przykład:**
```
Ostatnie 3 świece:
- Świeca 1: $45,000 - $45,200
- Świeca 2: $45,100 - $45,250
- Świeca 3: $45,150 - $45,300

Maksimum: $45,300
Minimum: $45,000
Zakres: $300
Średnia cena: $45,150
Zakres procentowy: (300 / 45,150) × 100 = 0.66%

Próg konsolidacji: 0.5%
0.66% > 0.5% → NIE jest to konsolidacja (jeszcze)

Ale jeśli zakres byłby $200:
Zakres procentowy: (200 / 45,150) × 100 = 0.44%
0.44% < 0.5% → KONSOLIDACJA wykryta! Sygnał wyjścia
```

**Dlaczego to sygnał wyjścia:**
- "Dalej to loteria" - gdy cena się wypłaszcza, nie wiadomo co będzie dalej
- Lepiej zamknąć z zyskiem niż ryzykować utratę profitu
- Konsolidacja po wzroście często poprzedza spadek

**Parametry:**
- `consolidation_threshold` (domyślnie 0.5%) - próg wykrycia
- `consolidation_candles` (domyślnie 3) - ile świec analizować
- Im niższy próg, tym wcześniej wykryje konsolidację
- Im więcej świec, tym bardziej konserwatywne wykrywanie

---

### 7. Wykrywanie utraty momentum (sygnał wyjścia)

**Co to jest:**
Gdy cena traci pęd (momentum spada), może to oznaczać koniec trendu.

**Jak bot to wykrywa:**
1. Oblicza momentum z ostatnich 3 świec
2. Jeśli momentum < -0.5% (cena spada) **I** pozycja jest w zysku > 1%
3. Generuje sygnał wyjścia

**Przykład:**
```
Pozycja LONG otwarta: $45,000
Aktualna cena: $45,500
PnL: +1.1% (w zysku) ✅

Momentum (3 świece): -0.8% (spada) ✅

Wynik: Sygnał wyjścia - momentum spadające przy zysku
```

**Dlaczego to ważne:**
- Lepiej wyjść wcześniej z zyskiem niż czekać na odwrócenie
- "Nie czekaj na idealne szczyty" - strategia Piotrka

---

## Podsumowanie mechanizmów wykrywania

| Mechanizm | Co wykrywa | Kiedy używa | Parametry |
|-----------|------------|-------------|-----------|
| **Support/Resistance** | Poziomy cenowe | Zawsze (analiza) | `lookback_period` (20) |
| **Breakout** | Przebicie oporu | Wejście (BUY) | `breakout_threshold` (1.0%) |
| **Momentum** | Szybkość zmiany | Wejście + Wyjście | Okres (5 świec) |
| **Wolumen** | Potwierdzenie | Wejście (BUY) | Okres (20 świec) |
| **Confidence** | Siła sygnału | Wejście (BUY) | `min_confidence` (6.0) |
| **Konsolidacja** | Wypłaszczenie | Wyjście (CLOSE) | `consolidation_threshold` (0.5%) |
| **Utrata momentum** | Spadek pędu | Wyjście (CLOSE) | Próg (-0.5%) |

**Przepływ decyzji:**

```
1. Pobierz dane (świece OHLCV)
   ↓
2. Znajdź poziomy S/R
   ↓
3. Sprawdź breakout
   ↓
4. Jeśli breakout:
   - Oblicz momentum
   - Sprawdź wolumen
   - Oblicz confidence
   - Jeśli confidence ≥ min_confidence → BUY
   ↓
5. Dla otwartych pozycji:
   - Sprawdź konsolidację
   - Sprawdź utratę momentum
   - Jeśli wykryto → CLOSE
```

**Wizualizacja na wykresie:**

```
Cena
  ↑
  |     ┌─ Opór (Resistance) ──────────────── $45,200
  |     │
  |     │  🔴 Breakout! → BUY @ $45,300
  |     │  │
  |     │  │  📈 Trend wzrostowy (momentum +)
  |     │  │  │
  |     │  │  │  📊 Konsolidacja → CLOSE @ $45,800
  |     │  │  │  │
  |     │  │  │  │  ⬇️ Momentum spada → CLOSE
  |     │  │  │  │  │
  |─────┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──→ Czas
  │
  └─ Wsparcie (Support) ──────────────────── $44,000
```

---

## Gdzie w kodzie jest realizowana ta logika?

Wszystkie mechanizmy wykrywania charakterystycznych momentów są zaimplementowane w pliku **`src/trading/strategies/piotrek_strategy.py`**. Poniżej znajduje się mapa kodu z dokładnymi lokalizacjami:

### Główny plik strategii

**Plik:** `src/trading/strategies/piotrek_strategy.py`

#### 1. Identyfikacja poziomów wsparcia i oporu

```57:99:src/trading/strategies/piotrek_strategy.py
def find_support_resistance_levels(
    self,
    df: pd.DataFrame,
    lookback: int = None
) -> Tuple[List[float], List[float]]:
    """
    Znajduje poziomy wsparcia i oporu.
    """
    # ... kod znajduje lokalne maksima i minima ...
    # Znajdź lokalne maksima (opory)
    resistance_levels = []
    for i in range(2, len(highs) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            resistance_levels.append(highs[i])
    
    # Znajdź lokalne minima (wsparcia)
    support_levels = []
    for i in range(2, len(lows) - 2):
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            support_levels.append(lows[i])
```

**Funkcja pomocnicza do grupowania poziomów:**

```101:116:src/trading/strategies/piotrek_strategy.py
def _cluster_levels(self, levels: List[float], tolerance: float = 0.005) -> List[float]:
    """Grupuje podobne poziomy cenowe."""
    # ... kod grupuje podobne poziomy ...
```

#### 2. Wykrywanie breakoutu

```118:152:src/trading/strategies/piotrek_strategy.py
def detect_breakout(
    self,
    df: pd.DataFrame,
    resistance_levels: List[float]
) -> Tuple[bool, float, float]:
    """
    Wykrywa przebicie poziomu oporu.
    """
    current_close = df['close'].iloc[-1]
    prev_close = df['close'].iloc[-2]
    
    for resistance in resistance_levels:
        # Breakout: poprzednia świeca pod oporem, aktualna nad oporem
        if prev_close < resistance and current_close > resistance:
            breakout_strength = ((current_close - resistance) / resistance) * 100
            
            if breakout_strength >= self.breakout_threshold:
                return True, breakout_strength, resistance
```

#### 3. Wykrywanie konsolidacji

```154:182:src/trading/strategies/piotrek_strategy.py
def detect_consolidation(self, df: pd.DataFrame) -> Tuple[bool, float]:
    """
    Wykrywa konsolidację (wypłaszczenie).
    """
    recent = df.tail(self.consolidation_candles)
    
    # Oblicz zakres ruchów
    price_range = recent['high'].max() - recent['low'].min()
    avg_price = recent['close'].mean()
    range_percent = (price_range / avg_price) * 100
    
    is_consolidating = bool(range_percent < self.consolidation_threshold)
```

#### 4. Obliczanie momentum

```184:202:src/trading/strategies/piotrek_strategy.py
def calculate_momentum(self, df: pd.DataFrame, period: int = 5) -> float:
    """
    Oblicza momentum cenowe.
    """
    current_price = df['close'].iloc[-1]
    past_price = df['close'].iloc[-period]
    
    momentum = ((current_price - past_price) / past_price) * 100
    return momentum
```

#### 5. Potwierdzenie wolumenem

```204:223:src/trading/strategies/piotrek_strategy.py
def calculate_volume_confirmation(self, df: pd.DataFrame) -> float:
    """
    Sprawdza potwierdzenie wolumenem.
    """
    avg_volume = df['volume'].iloc[-20:].mean()
    current_volume = df['volume'].iloc[-1]
    
    if avg_volume == 0:
        return 1.0
    
    return current_volume / avg_volume
```

#### 6. Główna funkcja analizy (łączy wszystkie mechanizmy)

```225:284:src/trading/strategies/piotrek_strategy.py
def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD") -> Optional[TradingSignal]:
    """
    Analizuje dane i generuje sygnał.
    """
    # Znajdź poziomy
    supports, resistances = self.find_support_resistance_levels(df)
    
    # Sprawdź breakout
    is_breakout, breakout_strength, broken_level = self.detect_breakout(df, resistances)
    
    if is_breakout:
        # Oblicz dodatkowe metryki
        momentum = self.calculate_momentum(df)
        volume_ratio = self.calculate_volume_confirmation(df)
        
        # Oblicz confidence (0-10)
        confidence = min(10, (
            (breakout_strength / self.breakout_threshold) * 3 +  # Siła breakoutu
            (momentum / 2) +  # Momentum
            (volume_ratio * 2)  # Wolumen
        ))
        
        if confidence >= self.min_confidence:
            # Oblicz stop loss i take profit
            # ... zwraca TradingSignal ...
```

#### 7. Funkcja wyjścia z pozycji

```286:342:src/trading/strategies/piotrek_strategy.py
def should_close_position(
    self,
    df: pd.DataFrame,
    entry_price: float,
    side: str,
    current_pnl_percent: float
) -> Optional[TradingSignal]:
    """
    Sprawdza czy należy zamknąć pozycję.
    """
    # Sprawdź konsolidację
    is_consolidating, range_percent = self.detect_consolidation(df)
    
    # Jeśli jesteśmy w zysku i cena się wypłaszcza - zamykamy
    if is_consolidating and current_pnl_percent > 0.5:
        return TradingSignal(...)
    
    # Sprawdź utratę momentum
    momentum = self.calculate_momentum(df, period=3)
    
    # Dla LONG: jeśli momentum spada poniżej 0 przy zysku
    if side.lower() == "long" and momentum < -0.5 and current_pnl_percent > 1.0:
        return TradingSignal(...)
```

---

### Gdzie strategia jest używana?

#### 1. Bot tradingowy (główna pętla)

**Plik:** `src/trading/trading_bot.py`

**Cykl sprawdzania rynku:**

```213:243:src/trading/trading_bot.py
def run_cycle(self):
    """Wykonuje jeden cykl sprawdzania."""
    # 1. Sprawdź SL/TP dla otwartych pozycji
    closed_trades = self.engine_pt.check_stop_loss_take_profit()
    
    # 2. Sprawdź pozycje pod kątem strategii wyjścia
    self.check_positions_for_exit()
    
    # 3. Szukaj nowych okazji
    for symbol in self.symbols:
        df = self.get_market_data(symbol, limit=50)
        signal = self.strategy.analyze(df, symbol)  # ← Tu wywoływana strategia
        
        if signal:
            self.process_signal(signal)
```

**Sprawdzanie pozycji pod kątem wyjścia:**

```184:211:src/trading/trading_bot.py
def check_positions_for_exit(self):
    """Sprawdza otwarte pozycje pod kątem sygnałów wyjścia."""
    for position in self.engine_pt.get_open_positions():
        df = self.get_market_data(position.symbol, limit=20)
        current_price = df['close'].iloc[-1]
        pnl, pnl_percent = position.calculate_pnl(current_price)
        
        # Sprawdź strategię pod kątem wyjścia
        exit_signal = self.strategy.should_close_position(  # ← Tu wywoływana funkcja wyjścia
            df=df,
            entry_price=position.entry_price,
            side=side,
            current_pnl_percent=pnl_percent
        )
```

#### 2. Inicjalizacja strategii

**Plik:** `scripts/run_paper_trading_enhanced.py`

```346:352:scripts/run_paper_trading_enhanced.py
# Strategia
strategy = PiotrekBreakoutStrategy({
    'breakout_threshold': 0.8,
    'consolidation_threshold': 0.4,
    'min_confidence': 5,
    'risk_reward_ratio': 2.0
})
```

---

### Struktura plików

```
src/trading/
├── strategies/
│   ├── base_strategy.py          # Bazowa klasa strategii
│   └── piotrek_strategy.py      # ← GŁÓWNA LOGIKA WYKRYWANIA
│
├── trading_bot.py                # Bot wykonujący strategię
├── paper_trading.py              # Silnik paper trading
└── models.py                     # Modele danych

scripts/
└── run_paper_trading_enhanced.py # Skrypt uruchamiający bota
```

---

### Przepływ danych

```
1. Bot uruchamia cykl (trading_bot.py:run_cycle)
   ↓
2. Pobiera dane rynkowe (trading_bot.py:get_market_data)
   ↓
3. Wywołuje strategię (trading_bot.py:run_cycle → strategy.analyze)
   ↓
4. Strategia analizuje (piotrek_strategy.py:analyze)
   ├─→ find_support_resistance_levels()  # Poziomy S/R
   ├─→ detect_breakout()                 # Breakout
   ├─→ calculate_momentum()              # Momentum
   ├─→ calculate_volume_confirmation()    # Wolumen
   └─→ Oblicza confidence                 # Pewność sygnału
   ↓
5. Zwraca TradingSignal (lub None)
   ↓
6. Bot przetwarza sygnał (trading_bot.py:process_signal)
   ↓
7. Otwiera/zamyka pozycję (paper_trading.py)
```

---

### Jak modyfikować logikę?

Jeśli chcesz zmienić sposób wykrywania charakterystycznych momentów:

1. **Edytuj parametry** - zmień wartości w konfiguracji strategii:
   ```python
   strategy = PiotrekBreakoutStrategy({
       'breakout_threshold': 1.5,      # Zwiększ próg breakoutu
       'min_confidence': 7,             # Zwiększ minimalną pewność
       'consolidation_threshold': 0.3,  # Zmniejsz próg konsolidacji
   })
   ```

2. **Modyfikuj funkcje** - edytuj metody w `piotrek_strategy.py`:
   - `find_support_resistance_levels()` - zmień sposób znajdowania poziomów
   - `detect_breakout()` - zmień warunki breakoutu
   - `calculate_momentum()` - zmień sposób obliczania momentum
   - `analyze()` - zmień formułę confidence

3. **Dodaj nowe mechanizmy** - stwórz nowe metody w klasie `PiotrekBreakoutStrategy`

---

## Różnice między botem a dYdX w przeglądarce

| Aspekt | dYdX w przeglądarce | Bot (trade.sh) |
|--------|---------------------|----------------|
| **Decyzje** | Ty podejmujesz | Strategia automatyczna |
| **Czas** | Musisz być online | Działa 24/7 |
| **Emocje** | Wpływają na decyzje | Brak emocji |
| **Szybkość** | Zależy od Ciebie | Reaguje w określonych interwałach |
| **Monitoring** | Musisz sprawdzać | Automatyczny |
| **Paper Trading** | Ograniczone | Pełna symulacja |
| **Strategia** | Twoja intuicja | Zdefiniowana strategia |

---

## Ważne uwagi

1. **Paper Trading = Wirtualne pieniądze**
   - Wszystkie transakcje są symulowane
   - Nie używasz prawdziwych środków
   - Idealne do testowania strategii

2. **Wyniki w paper trading ≠ wyniki w real trading**
   - W paper trading nie ma slippage (różnica między ceną zlecenia a wykonania)
   - W paper trading zawsze możesz zamknąć pozycję po cenie rynkowej
   - W real trading mogą być problemy z płynnością

3. **Dźwignia zwiększa ryzyko**
   - Wyższa dźwignia = większe zyski, ale też większe straty
   - Możesz stracić więcej niż początkowy kapitał (margin call)
   - Zawsze testuj z niską dźwignią na początku

4. **Interwał wpływa na wyniki**
   - Zbyt mały interwał = overtrading (za dużo transakcji)
   - Zbyt duży interwał = przegapione okazje
   - Testuj różne interwały dla swojej strategii

5. **Limity chronią Twój kapitał**
   - Zawsze ustaw `--max-loss` w real trading
   - `--time-limit` pomaga testować strategie przez określony czas
   - Nie polegaj tylko na automatycznych limitach - monitoruj bota

---

## Rozwiązywanie problemów

### Bot nie uruchamia się
- Sprawdź czy masz aktywne środowisko wirtualne Python
- Sprawdź czy baza danych jest zainicjalizowana
- Sprawdź logi w katalogu `logs/`

### Bot nie otwiera pozycji
- Sprawdź czy strategia generuje sygnały (użyj `--verbose`)
- Sprawdź czy nie osiągnąłeś limitu pozycji
- Sprawdź czy masz wystarczający kapitał

### Bot traci za dużo
- Zmniejsz dźwignię (`--leverage=1`)
- Zwiększ interwał (`--interval=15min`)
- Ustaw niższy limit straty (`--max-loss=50`)
- Sprawdź czy strategia działa poprawnie

### Bot nie zatrzymuje się
- Sprawdź czy limit czasu jest poprawnie ustawiony
- Użyj Ctrl+C aby zatrzymać ręcznie
- Sprawdź logi czy są błędy

---

## Podsumowanie

Skrypt `trade.sh` to potężne narzędzie do automatycznego tradingu na dYdX. Kluczowe parametry:

- **`--interval`** - jak często bot sprawdza rynek
- **`--leverage`** - jak agresywnie bot handluje
- **`--max-loss`** - ochrona przed nadmiernymi stratami
- **`--time-limit`** - kontrola czasu działania
- **`--symbols`** - które pary monitorować
- **`--balance`** - początkowy kapitał

Zacznij od prostych konfiguracji i stopniowo eksperymentuj z parametrami, aby znaleźć optymalne ustawienia dla swojej strategii.

