#!/bin/bash

# Skrypt do szybkiego testowania strategii scalping

# Uruchom bota z parametrami optymalnymi dla scalping
./scripts/trade.sh \
  --strategy=scalping_strategy \
  --mode=paper \
  --balance=10000000 \
  --symbols=BTC-USD,ETH-USD \
  --interval=30sek \
  --time-limit=10h \
  --max-loss=1000000 \
  --verbose

