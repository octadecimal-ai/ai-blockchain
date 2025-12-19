# Data Updater Daemon

Daemon do automatycznej aktualizacji danych OHLCV i tickers w tle.

## Funkcjonalności

- ✅ Aktualizuje dane OHLCV (1m timeframe) co 1 minutę
- ✅ Aktualizuje tickers (aktualne ceny) co 1 minutę
- ✅ Działa w tle nawet po wylogowaniu
- ✅ Obsługuje wiele giełd (Binance, dYdX)
- ✅ Obsługuje wiele symboli (BTC-USD, ETH-USD, etc.)
- ✅ Automatyczne logowanie do plików
- ✅ Statystyki działania
- ✅ Graceful shutdown

## Sposoby uruchomienia

### 1. Prosty start (nohup)

```bash
# Uruchom w tle
./scripts/start_data_updater.sh

# Sprawdź status
./scripts/start_data_updater.sh --status

# Zatrzymaj
./scripts/start_data_updater.sh --stop
```

### 2. macOS LaunchAgent (automatyczny start przy logowaniu)

```bash
# Zainstaluj jako LaunchAgent
./scripts/install_data_updater_service.sh

# Odinstaluj
./scripts/install_data_updater_service.sh --uninstall
```

### 3. Bezpośrednie uruchomienie (testowanie)

```bash
python scripts/data_updater_daemon.py
python scripts/data_updater_daemon.py --symbols=BTC-USD,ETH-USD --interval=30
```

## Parametry

### start_data_updater.sh

- `--symbols=SYMBOL1,SYMBOL2` - Symbole do aktualizacji (domyślnie: BTC-USD,ETH-USD)
- `--exchanges=EXCHANGE1,EXCHANGE2` - Giełdy (domyślnie: binance,dydx)
- `--interval=SEKUNDY` - Interwał aktualizacji (domyślnie: 60)
- `--stop` - Zatrzymaj daemon
- `--status` - Sprawdź status
- `--restart` - Zatrzymaj i uruchom ponownie

### data_updater_daemon.py

- `--symbols=SYMBOL1,SYMBOL2` - Symbole do aktualizacji
- `--exchanges=EXCHANGE1,EXCHANGE2` - Giełdy
- `--interval=SEKUNDY` - Interwał aktualizacji
- `--database-url=URL` - URL bazy danych
- `--verbose, -v` - Szczegółowe logowanie

## Pliki

- `scripts/data_updater_daemon.py` - Główny skrypt daemona
- `scripts/start_data_updater.sh` - Skrypt do zarządzania daemonem
- `scripts/com.octadecimal.data_updater.plist` - LaunchAgent plist (macOS)
- `scripts/install_data_updater_service.sh` - Instalator LaunchAgent
- `data/data_updater.pid` - PID file daemona
- `logs/data_updater_YYYY-MM-DD.log` - Logi daemona

## Przykłady użycia

### Podstawowe uruchomienie

```bash
./scripts/start_data_updater.sh
```

### Z niestandardowymi parametrami

```bash
./scripts/start_data_updater.sh \
  --symbols=BTC-USD,ETH-USD,SOL-USD \
  --exchanges=binance,dydx \
  --interval=30
```

### Sprawdzenie statusu

```bash
./scripts/start_data_updater.sh --status
```

### Zatrzymanie

```bash
./scripts/start_data_updater.sh --stop
```

### Restart

```bash
./scripts/start_data_updater.sh --restart
```

## Instalacja jako LaunchAgent (macOS)

LaunchAgent uruchamia daemon automatycznie przy logowaniu użytkownika.

```bash
# Zainstaluj
./scripts/install_data_updater_service.sh

# Sprawdź status
launchctl list com.octadecimal.data_updater

# Zatrzymaj
launchctl unload ~/Library/LaunchAgents/com.octadecimal.data_updater.plist

# Uruchom ponownie
launchctl load ~/Library/LaunchAgents/com.octadecimal.data_updater.plist

# Odinstaluj
./scripts/install_data_updater_service.sh --uninstall
```

## Logi

Logi są zapisywane do:
- `logs/data_updater_YYYY-MM-DD.log` - Główne logi
- `logs/data_updater_launchd.log` - Logi LaunchAgent (tylko macOS)

## Statystyki

Daemon pokazuje statystyki co 10 cykli:
- Uptime
- Liczba cykli
- OHLCV zapisane
- Tickers zapisane
- Błędy

## Troubleshooting

### Daemon nie uruchamia się

1. Sprawdź logi: `tail -f logs/data_updater_*.log`
2. Sprawdź czy venv jest aktywne
3. Sprawdź czy baza danych jest dostępna
4. Sprawdź czy kolektory są dostępne

### Daemon zatrzymuje się

1. Sprawdź logi pod kątem błędów
2. Sprawdź czy API giełd są dostępne
3. Sprawdź czy nie ma problemów z siecią

### Brak danych w bazie

1. Sprawdź czy daemon działa: `./scripts/start_data_updater.sh --status`
2. Sprawdź logi: `tail -f logs/data_updater_*.log`
3. Sprawdź czy symbole są poprawne
4. Sprawdź czy giełdy są dostępne

## Wymagania

- Python 3.9+
- Aktywne venv z zainstalowanymi zależnościami
- Dostęp do bazy danych
- Dostęp do API giełd (Binance, dYdX)

