#!/bin/bash
# Szybki test tradingu - agresywne parametry dla szybkiego wygenerowania transakcji
# Użycie: ./scripts/test_trade_quick.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "🚀 Uruchamiam szybki test tradingu z agresywnymi parametrami..."
echo ""

# Uruchom z bardzo agresywnymi parametrami
./scripts/trade.sh \
  --strategy=piotrek_breakout_strategy \
  --mode=paper \
  --balance=10000 \
  --leverage=2 \
  --symbols=BTC-USD,ETH-USD \
  --interval=5sek \
  --time-limit=10min \
  --max-loss=1000 \
  --verbose

