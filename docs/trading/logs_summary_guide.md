# Przewodnik po Podsumowaniach i Logach Tradingu

## 📊 Podsumowanie na Żywo (Live Summary)

Podsumowanie wyświetlane podczas działania bota tradingowego zawiera następujące metryki:

### Stan Konta

#### **Saldo Początkowe (Initial Balance)**
- **Co to jest**: Kapitał początkowy na koncie paper trading
- **Przykład**: `$10,000.00`
- **Uwaga**: Ustawiane przy pierwszym uruchomieniu bota

#### **Saldo Aktualne (Current Balance)**
- **Co to jest**: Aktualne dostępne środki na koncie (po odjęciu zablokowanego marginu)
- **Przykład**: `$9,500.00`
- **Obliczanie**: `initial_balance - margin_used - fees + realized_pnl`
- **Uwaga**: Nie uwzględnia unrealized PnL z otwartych pozycji

#### **Unrealized PnL**
- **Co to jest**: Niestabilny zysk/strata z otwartych pozycji (niezrealizowany)
- **Przykład**: `$+150.50` (zielony) lub `$-75.25` (czerwony)
- **Obliczanie**: Suma PnL wszystkich otwartych pozycji
- **Uwaga**: Może się zmieniać w czasie rzeczywistym wraz z ceną

#### **Equity (Wartość Portfela)**
- **Co to jest**: Całkowita wartość konta (saldo + unrealized PnL)
- **Przykład**: `$9,650.50`
- **Obliczanie**: `current_balance + unrealized_pnl`
- **Uwaga**: Najlepszy wskaźnik aktualnej wartości konta

### Statystyki Wydajności

#### **Całkowity PnL (Total PnL)**
- **Co to jest**: Suma wszystkich zrealizowanych zysków i strat
- **Przykład**: `$+250.00` (zielony) lub `$-100.00` (czerwony)
- **Obliczanie**: Suma `net_pnl` wszystkich zamkniętych transakcji
- **Uwaga**: Uwzględnia opłaty i slippage

#### **ROI (Return on Investment)**
- **Co to jest**: Procentowy zwrot z inwestycji
- **Przykład**: `+2.50%` lub `-1.00%`
- **Obliczanie**: `((current_balance - initial_balance) / initial_balance) * 100`
- **Uwaga**: Pokazuje efektywność strategii

#### **Win Rate**
- **Co to jest**: Procent wygranych transakcji
- **Przykład**: `65.5%` (13 wygranych z 20 transakcji)
- **Obliczanie**: `(wins / total_trades) * 100`
- **Uwaga**: Wysoki win rate nie zawsze oznacza zysk (możliwe małe zyski, duże straty)

#### **Max Drawdown**
- **Co to jest**: Maksymalna procentowa strata od szczytu wartości konta
- **Przykład**: `-5.25%`
- **Obliczanie**: `((peak_balance - lowest_balance) / peak_balance) * 100`
- **Uwaga**: Ważny wskaźnik ryzyka - pokazuje najgorszą możliwą sytuację

#### **Profit Factor**
- **Co to jest**: Stosunek całkowitych zysków do całkowitych strat
- **Przykład**: `1.85` (zyski są 1.85x większe niż straty)
- **Obliczanie**: `total_wins / total_losses`
- **Uwaga**: 
  - `> 1.0` = zyskowny
  - `= 1.0` = break-even
  - `< 1.0` = stratny

#### **Średni Zysk (Avg Win)**
- **Co to jest**: Średnia wartość zysku z wygranej transakcji
- **Przykład**: `$+125.50`
- **Obliczanie**: `sum(wins) / count(wins)`

#### **Średnia Strata (Avg Loss)**
- **Co to jest**: Średnia wartość straty z przegranej transakcji
- **Przykład**: `$-75.25`
- **Obliczanie**: `sum(losses) / count(losses)`
- **Uwaga**: Ważne dla zarządzania ryzykiem - powinna być mniejsza niż średni zysk

#### **Najlepsza Transakcja (Best Trade)**
- **Co to jest**: Największy zysk z pojedynczej transakcji
- **Przykład**: `$+500.00`

#### **Najgorsza Transakcja (Worst Trade)**
- **Co to jest**: Największa strata z pojedynczej transakcji
- **Przykład**: `$-200.00`

### Otwarte Pozycje

Dla każdej otwartej pozycji wyświetlane są:

- **Symbol**: Para handlowa (np. `BTC-USD`)
- **Strona**: `LONG` (kupno) lub `SHORT` (sprzedaż)
- **Rozmiar**: Ilość bazowej waluty (np. `0.010696 BTC`)
- **Cena Wejścia**: Cena przy otwarciu pozycji
- **Cena Aktualna**: Bieżąca cena rynkowa
- **PnL**: Zysk/strata (zielony/czerwony)
  - Wartość w USD
  - Procent zmiany

### Szczegóły Zamkniętej Transakcji

Gdy pozycja jest zamykana, wyświetlane są:

- **Symbol**: Para handlowa
- **Strona**: `LONG` lub `SHORT`
- **Rozmiar**: Ilość bazowej waluty
- **Wejście**: Cena wejścia
- **Wyjście**: Cena wyjścia
- **Zmiana**: Procentowa zmiana ceny
- **PnL (brutto)**: Zysk/strata przed opłatami
- **Opłaty**: Suma opłat za wejście i wyjście
- **PnL (netto)**: Zysk/strata po opłatach i slippage
- **Czas trwania**: Jak długo pozycja była otwarta
- **Powód wyjścia**: 
  - `stop_loss` - osiągnięto stop loss
  - `take_profit` - osiągnięto take profit
  - `consolidation` - wykryto konsolidację
  - `strategy_signal` - sygnał strategii
  - `manual` - ręczne zamknięcie

## 🎯 Interpretacja Metryk

### Dobra Strategia
- ✅ **ROI > 0%** - generuje zyski
- ✅ **Win Rate > 50%** - więcej wygranych niż przegranych
- ✅ **Profit Factor > 1.5** - zyski znacznie większe niż straty
- ✅ **Max Drawdown < 20%** - akceptowalne ryzyko
- ✅ **Avg Win > Avg Loss** - średni zysk większy niż średnia strata

### Ostrzeżenia
- ⚠️ **Niski Win Rate (< 40%)** - ale może być OK jeśli Profit Factor > 2.0
- ⚠️ **Wysoki Max Drawdown (> 30%)** - wysokie ryzyko
- ⚠️ **Avg Loss > Avg Win** - problem z zarządzaniem ryzykiem
- ⚠️ **Profit Factor < 1.0** - strategia stratna

## 📝 Przykładowe Podsumowanie

```
📊 PODSUMOWANIE NA ŻYWO (czas: 5m 30s)
──────────────────────────────────────────────────────────────────────
💰 Konto:            $10,250.50
📈 Saldo:            $10,000.00
💵 Unrealized PnL:   $+250.50
📊 Equity:           $10,250.50
──────────────────────────────────────────────────────────────────────
📊 Statystyki:
   Całkowity PnL:    $+250.50
   ROI:              +2.51%
   Win Rate:         65.0%
   Profit Factor:    1.85
   Max Drawdown:     -2.15%
   Transakcje:       20 (13W / 7L)
──────────────────────────────────────────────────────────────────────
📈 Otwarte pozycje:
  🟢 BTC-USD LONG: 0.010696 @ $93,487.39 → $93,750.00 | PnL: $+150.50 (+0.28%)
```

## 🔍 Gdzie Znaleźć Te Dane w Bazie

Wszystkie te metryki są zapisywane w bazie danych:

- **`paper_accounts`** - saldo, total_pnl, win_rate, max_drawdown
- **`paper_positions`** - otwarte pozycje z unrealized PnL
- **`paper_trades`** - zamknięte transakcje z pełnymi szczegółami
- **`trade_registers`** - kompletny rejestr wszystkich transakcji
- **`trading_sessions`** - statystyki sesji tradingowej

## 📚 Powiązane Dokumenty

- [Przewodnik po skrypcie trade.sh](./trade_script_guide.md)
- [Mapowanie parametrów tradingu](./trading_parameters_mapping.md)
- [Konfiguracja bazy danych](./database_setup.md)

