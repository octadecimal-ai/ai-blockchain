# Konfiguracja Google Custom Search Engine (CSE)

## Co to jest CSE_ID?

**CSE_ID** (Custom Search Engine ID) to unikalny identyfikator Twojej własnej wyszukiwarki utworzonej w Google Programmable Search Engine.

**WAŻNE:** To NIE jest to samo co `GOOGLE_API_KEY`! Potrzebujesz OBA:
- `GOOGLE_API_KEY` - już masz w .env ✅
- `GOOGLE_CSE_ID` - musisz utworzyć ⚠️

## Jak utworzyć CSE_ID?

### Krok 1: Utwórz Custom Search Engine

1. Przejdź na: https://programmablesearchengine.google.com/
2. Kliknij **"Add"** lub **"Create a custom search engine"**
3. Wypełnij formularz:
   - **Sites to search**: Możesz zostawić puste lub dodać `*` (wyszukuje cały internet)
   - **Name**: np. "AI Blockchain Search"
   - **Language**: wybierz język
4. Kliknij **"Create"**

### Krok 2: Znajdź CSE_ID

1. Po utworzeniu, przejdź do **"Control Panel"** (Panel sterowania)
2. W sekcji **"Basics"** znajdziesz **"Search engine ID"**
3. To jest Twój **CSE_ID** (wygląda np. tak: `017576662512468239146:omuauf_lfve`)

### Krok 3: Skonfiguruj wyszukiwarkę (opcjonalnie)

1. W **"Setup"** → **"Basics"**:
   - **Search the entire web**: Włącz (jeśli chcesz wyszukiwać cały internet)
   - **Image search**: Włącz (jeśli potrzebujesz)
   - **SafeSearch**: Wyłącz (dla pełnych wyników)

2. W **"Setup"** → **"Advanced"**:
   - Możesz dostosować ustawienia według potrzeb

### Krok 4: Dodaj do .env

Dodaj do pliku `.env`:

```env
# Google Custom Search Engine (dla web search)
GOOGLE_CSE_ID=twoj_cse_id_tutaj
```

**Przykład:**
```env
GOOGLE_CSE_ID=017576662512468239146:omuauf_lfve
```

## Co z istniejących ID w .env?

**NIE** - żadne z istniejących ID w Twoim .env nie jest CSE_ID:
- `GOOGLE_PROJECT_ID` - to ID projektu Google Cloud
- `GOOGLE_CLIENT_ID` - to ID klienta OAuth
- `GOOGLE_DRIVE_project_id` - to ID projektu Google Drive

**CSE_ID** to osobny identyfikator, który musisz utworzyć w Google Programmable Search Engine.

## Weryfikacja

Po dodaniu `GOOGLE_CSE_ID` do `.env`, system automatycznie:
1. Wykryje dostępność Google API
2. Użyje Google jako głównego providera (zamiast DuckDuckGo)
3. DuckDuckGo będzie fallbackiem

## Koszty

- ✅ **Darmowy tier**: 100 zapytań dziennie
- 💰 **Po przekroczeniu**: ~$5 za 1000 zapytań
- ⚠️ Wymaga karty kredytowej (ale darmowy tier nie pobiera opłat)

## Przydatne linki

- Utworzenie CSE: https://programmablesearchengine.google.com/
- Dokumentacja API: https://developers.google.com/custom-search/v1/overview
- Panel sterowania: https://programmablesearchengine.google.com/controlpanel/all

