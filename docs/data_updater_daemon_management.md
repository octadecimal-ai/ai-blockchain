# Zarządzanie Data Updater Daemon

## Sposoby zatrzymania i uruchomienia daemona

### Metoda 1: Użycie skryptu `start_data_updater.sh` (Zalecane)

#### Zatrzymanie daemona:
```bash
./scripts/start_data_updater.sh --stop
```

#### Uruchomienie daemona:
```bash
./scripts/start_data_updater.sh
```

#### Restart daemona (zatrzymaj i uruchom ponownie):
```bash
./scripts/start_data_updater.sh --restart
```

#### Sprawdzenie statusu:
```bash
./scripts/start_data_updater.sh --status
```

### Metoda 2: Bezpośrednie użycie `launchctl` (macOS LaunchAgent)

#### Zatrzymanie daemona:
```bash
launchctl unload ~/Library/LaunchAgents/com.octadecimal.data_updater.plist
```

#### Uruchomienie daemona:
```bash
launchctl load ~/Library/LaunchAgents/com.octadecimal.data_updater.plist
```

#### Restart daemona:
```bash
launchctl unload ~/Library/LaunchAgents/com.octadecimal.data_updater.plist && \
launchctl load ~/Library/LaunchAgents/com.octadecimal.data_updater.plist
```

#### Sprawdzenie statusu:
```bash
launchctl list com.octadecimal.data_updater
```

### Metoda 3: Przez proces (jeśli daemon nie jest LaunchAgent)

#### Znajdź proces:
```bash
ps aux | grep data_updater
```

#### Zatrzymanie procesu (używając PID):
```bash
kill <PID>
```

#### Wymuszone zatrzymanie (jeśli zwykłe kill nie działa):
```bash
kill -9 <PID>
```

## Przykłady użycia

### Szybki restart:
```bash
cd /Users/piotradamczyk/Projects/Octadecimal/ai-blockchain
./scripts/start_data_updater.sh --restart
```

### Zatrzymanie i sprawdzenie logów:
```bash
./scripts/start_data_updater.sh --stop
tail -50 logs/data_updater_$(date +%Y-%m-%d).log
```

### Uruchomienie z niestandardowymi parametrami:
```bash
./scripts/start_data_updater.sh --symbols=BTC-USD,ETH-USD --interval=30
```

## Sprawdzanie czy daemon działa

### Sprawdź proces:
```bash
ps aux | grep "[d]ata_updater"
```

### Sprawdź logi:
```bash
tail -f logs/data_updater_$(date +%Y-%m-%d).log
```

### Sprawdź LaunchAgent:
```bash
launchctl list | grep data_updater
```

## Uwagi

- **LaunchAgent**: Jeśli daemon jest zainstalowany jako LaunchAgent (przez `install_data_updater_service.sh`), użyj `launchctl` lub skryptu `start_data_updater.sh`
- **Automatyczne uruchamianie**: LaunchAgent automatycznie uruchamia daemon po zalogowaniu do systemu
- **Logi**: Logi są zapisywane w `logs/data_updater_YYYY-MM-DD.log`
- **Błędy**: Sprawdź `logs/data_updater_launchd.error.log` jeśli daemon nie działa

## Rozwiązywanie problemów

### Daemon nie zatrzymuje się:
```bash
# Znajdź PID
ps aux | grep data_updater

# Wymuś zatrzymanie
kill -9 <PID>

# Usuń plik PID jeśli istnieje
rm -f data/data_updater_daemon.pid
```

### Daemon nie uruchamia się:
```bash
# Sprawdź logi błędów
cat logs/data_updater_launchd.error.log

# Sprawdź czy plist jest poprawny
plutil -lint ~/Library/LaunchAgents/com.octadecimal.data_updater.plist

# Przeinstaluj service
./scripts/install_data_updater_service.sh --uninstall
./scripts/install_data_updater_service.sh --install
```

