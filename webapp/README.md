# Sentiment Visualization - 3D Map

Aplikacja webowa do wizualizacji sentymentu kryptowalutowego na mapie 3D z Google Maps.

## Funkcje

- 🌍 **Mapa 3D Google Maps** - widok satelitarny z trybem 3D
- 🎨 **Wizualizacja sentymentu** - kolorowanie regionów według sentymentu
- ⏰ **Suwak czasu** - przewijanie wstecz do dostępnych danych
- ▶️ **Animacja Play** - automatyczna animacja zmian sentymentu
- 💰 **Kurs BTC** - wyświetlanie kursu BTC zsynchronizowanego z czasem
- 📊 **Wskaźniki techniczne** - RSI, MACD, SMA, EMA, Bollinger Bands, ATR, Volume
- 🌓 **Światłocień stref dobowych** - wizualizacja stref czasowych na planecie

## Wymagania

### Backend
- Python 3.9+
- PostgreSQL z danymi sentymentu
- Zmienne środowiskowe:
  - `DATABASE_URL` - URL do bazy PostgreSQL
  - `FLASK_PORT` - Port dla Flask API (domyślnie: 5001, 5000 zajęty przez AirPlay na macOS)
  - `FLASK_DEBUG` - Tryb debug (domyślnie: False)

### Frontend
- Node.js 18+
- Google Maps API Key

## Instalacja

### Backend

```bash
cd webapp/backend
python -m venv venv
source venv/bin/activate  # Na Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend

```bash
cd webapp/frontend
npm install
```

## Konfiguracja

### 1. Google Maps API Key i Map ID

1. Utwórz plik `.env` w katalogu `webapp/frontend/`:
```bash
VITE_GOOGLE_MAPS_API_KEY=twoj_klucz_api
VITE_GOOGLE_MAPS_MAP_ID=twoj_map_id  # Wymagany dla AdvancedMarkerElement
```

2. Włącz następujące API w Google Cloud Console:
   - Maps JavaScript API
   - Maps Embed API

3. Utwórz Map ID w Google Cloud Console:
   - Przejdź do [Google Cloud Console](https://console.cloud.google.com/google/maps-apis)
   - Wybierz "Map Management" → "Create Map ID"
   - Wybierz typ mapy (np. "Vector")
   - Skopiuj Map ID i dodaj do `.env` jako `VITE_GOOGLE_MAPS_MAP_ID`
   
   **UWAGA**: Map ID jest wymagany dla `AdvancedMarkerElement` (nowe markery Google Maps).

4. **Tajny klucz podpisywania URL (opcjonalnie)**:
   - **Dla standardowego planu (nie Premium)**: NIE jest wymagany
   - **Dla planu Premium**: TAK, wymagany jest tajny klucz do podpisywania URL
   - **Dla Maps Static API / Street View Static API**: TAK, wymagane podpisywanie
   
   W naszym przypadku (Maps JavaScript API, standardowy plan) **NIE potrzebujemy** tajnego klucza.
   
   Jeśli używasz planu Premium, możesz dodać:
   ```bash
   VITE_GOOGLE_MAPS_SIGNING_SECRET=twoj_tajny_klucz
   ```
   
   **Uwaga**: Tajny klucz NIGDY nie powinien być dostępny w kodzie frontendowym!
   Jeśli używasz Premium, podpisywanie URL powinno być wykonywane po stronie backendu.

### 2. Zmienne środowiskowe Backend

Upewnij się, że masz ustawione zmienne w `.env` w głównym katalogu projektu:
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/ai_blockchain
FLASK_PORT=5000
FLASK_DEBUG=false
```

## Uruchomienie

### Szybki start (zalecane)

Użyj skryptu `dev_server.sh` do zarządzania serwerami:

```bash
cd webapp
./dev_server.sh --start      # Uruchom backend i frontend
./dev_server.sh --status      # Sprawdź status
./dev_server.sh --stop        # Zatrzymaj wszystko
./dev_server.sh --restart     # Zrestartuj wszystko
./dev_server.sh --help        # Pokaż pomoc
```

### Ręczne uruchomienie

#### Backend

```bash
cd webapp/backend
source venv/bin/activate
python app.py
```

Backend będzie dostępny na `http://localhost:5001`

#### Frontend

```bash
cd webapp/frontend
npm run dev
```

Frontend będzie dostępny na `http://localhost:3000`

## API Endpoints

### GET `/api/health`
Health check endpoint.

### GET `/api/sentiment/timeseries`
Pobiera dane sentymentu jako time series.

**Query params:**
- `symbol` - Symbol kryptowaluty (domyślnie: BTC/USDC)
- `regions` - Lista regionów oddzielona przecinkami (domyślnie: wszystkie)
- `days_back` - Dni wstecz (domyślnie: 7)
- `resolution_hours` - Rozdzielczość w godzinach (domyślnie: 1.0)
- `source` - Źródło danych: 'llm' lub 'gdelt' (domyślnie: 'llm')

### GET `/api/btc/price`
Pobiera kurs BTC dla danego timestampu wraz ze wskaźnikami technicznymi.

**Query params:**
- `timestamp` - Timestamp ISO format (domyślnie: najnowszy)
- `exchange` - Giełda (domyślnie: binance)
- `symbol` - Symbol (domyślnie: BTC/USDC)
- `timeframe` - Interwał (domyślnie: 1h)
- `lookback_hours` - Ile godzin wstecz pobrać dla wskaźników (domyślnie: 200)

### GET `/api/sentiment/range`
Pobiera zakres dostępnych danych (min/max timestamp).

**Query params:**
- `symbol` - Symbol kryptowaluty (domyślnie: BTC/USDC)
- `source` - Źródło danych: 'llm' lub 'gdelt' (domyślnie: 'llm')

### GET `/api/regions`
Zwraca listę dostępnych regionów z ich współrzędnymi.

## Wskaźniki techniczne

Aplikacja wyświetla następujące wskaźniki:

### Trend
- **SMA 20, 50, 200** - Simple Moving Average
- **EMA 12, 26** - Exponential Moving Average

### Momentum
- **RSI (14)** - Relative Strength Index
- **MACD** - Moving Average Convergence Divergence
- **MACD Signal** - Linia sygnału MACD
- **MACD Histogram** - Histogram MACD

### Volatility
- **Bollinger Bands** - Upper, Middle, Lower, Width
- **ATR** - Average True Range

### Volume
- **Volume** - Aktualny wolumen
- **Volume Ratio** - Stosunek do średniej 20 okresowej

## Skala kolorów sentymentu

- 🔴 **Very Bearish** (-1.0 do -0.6) - Ciemny czerwony
- 🟠 **Bearish** (-0.6 do -0.2) - Czerwono-pomarańczowy
- ⚪ **Neutral** (-0.2 do 0.2) - Szary
- 🟢 **Bullish** (0.2 do 0.6) - Zielony
- 🟢 **Very Bullish** (0.6 do 1.0) - Ciemny zielony

## Struktura projektu

```
webapp/
├── backend/
│   ├── app.py              # Flask API
│   └── requirements.txt    # Zależności Python
└── frontend/
    ├── src/
    │   ├── components/     # Komponenty React
    │   │   ├── PriceDisplay.jsx
    │   │   ├── TimeSlider.jsx
    │   │   └── Legend.jsx
    │   ├── styles/         # Style CSS
    │   ├── App.jsx         # Główny komponent
    │   └── main.jsx        # Entry point
    ├── package.json
    └── vite.config.js
```

## Rozwój

### Dodawanie nowych wskaźników

Wskaźniki są obliczane w funkcji `calculate_indicators()` w `backend/app.py`. Możesz dodać nowe wskaźniki modyfikując tę funkcję.

### Dodawanie nowych regionów

Regiony są zdefiniowane w słowniku `REGION_COORDINATES` w `backend/app.py`. Dodaj nowe regiony z ich współrzędnymi geograficznymi.

## Licencja

Projekt prywatny - Octadecimal

