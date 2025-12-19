#!/bin/bash
# Skrypt do uruchomienia aplikacji webowej

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Uruchamiam aplikację Sentiment Visualization..."

# Sprawdź czy .env istnieje
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "❌ Brak pliku .env w katalogu głównym projektu!"
    echo "   Utwórz plik .env z DATABASE_URL"
    exit 1
fi

# Sprawdź czy backend venv istnieje
if [ ! -d "$SCRIPT_DIR/backend/venv" ]; then
    echo "📦 Tworzę virtual environment dla backendu..."
    cd "$SCRIPT_DIR/backend"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# Sprawdź czy frontend node_modules istnieje
if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
    echo "📦 Instaluję zależności frontendu..."
    cd "$SCRIPT_DIR/frontend"
    npm install
fi

# Uruchom backend w tle
echo "🔧 Uruchamiam backend API..."
cd "$SCRIPT_DIR/backend"
source venv/bin/activate
python app.py &
BACKEND_PID=$!

# Poczekaj chwilę na uruchomienie backendu
sleep 3

# Uruchom frontend
echo "🎨 Uruchamiam frontend..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Aplikacja uruchomiona!"
echo "   Backend: http://localhost:5001"
echo "   Frontend: http://localhost:3000"
echo ""
echo "Aby zatrzymać, naciśnij Ctrl+C"

# Funkcja czyszczenia przy wyjściu
cleanup() {
    echo ""
    echo "🛑 Zatrzymuję aplikację..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Czekaj na zakończenie
wait

