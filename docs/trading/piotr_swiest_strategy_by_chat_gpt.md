Jesteś programistą pracującym w repozytorium Python (ai-blockchain). Masz dostęp do kodu projektu w Cursorze.
Twoje zadanie: ZAPROJEKTOWAĆ i ZAIMPLEMENTOWAĆ nową strategię tradingową “Piotra Święsa” (mean-reversion po impulsie + RSI).

KONTEKST:
- Aktualnie istnieje strategia: src/trading/strategies/prompt_strategy_v12.py (LLM). Użyj jej jako wzorca jak wygląda BaseStrategy, TradingSignal, SignalType, integracja z paper_trading_engine i jak wygląda metoda analyze(df, symbol).
- Nowa strategia ma NIE używać LLM. Ma być deterministyczna.
- Strategia ma działać w ticku co 10–30 sekund. Bot dostaje 50 świec (najczęściej 1m/5m/15m) i current_price z df['close'].iloc[-1].

OPIS METODY “PIOTRA ŚWIĘSA”:
1) Jeżeli RSI(14) > 70: rynek wykupiony -> preferuj SHORT (SELL)
2) Jeżeli RSI(14) < 30: rynek wyprzedany -> preferuj LONG (BUY)
3) Wejście powinno być po “impulsie” (gwałtowny ruch w jedną stronę), a wejście jest w stronę przeciwną.
   - Impuls zdefiniuj algorytmicznie na podstawie danych świec: np. zmiana ceny w ostatnich N świecach przekracza próg oparty o ATR lub procent (konfigurowalne).
   - Przykład: abs(close[-1] - close[-k]) / close[-k] * 100 >= impulse_threshold_pct
     lub abs(close[-1]-close[-k]) >= impulse_atr_mult * ATR
4) Trade jest krótki: target zysku 500–2000 USD (parametr), dopuszczalna strata 300–1000 USD (parametr).
   - W implementacji używaj mechanizmu: stop_loss i take_profit jako ceny, ale wielkości liczone w oparciu o USD risk/reward oraz size.
5) Position sizing: kolega używa wartości pozycji ~ 1 BTC, ale u nas to ma być konfigurowalne:
   - Domyślnie: position_notional_usd albo position_size_base (np. 1 BTC).
   - Jeżeli w systemie engine obsługuje size_percent, użyj size_percent. Jeśli nie, dodaj w strategii obliczenie z balance.
6) “Slippage”: dodaj prostą poprawkę: przy ustawianiu TP/SL uwzględnij slippage_percent (np. 0.05%–0.2%), tak aby TP był trochę mniej ambitny, a SL trochę bliżej.

WYMAGANIA IMPLEMENTACYJNE:
A) Utwórz nowy plik strategii:
   src/trading/strategies/piotr_swiec_strategy.py
   z klasą: PiotrSwiecStrategy(BaseStrategy)
B) Strategia ma:
   - liczyć RSI(14) z close,
   - liczyć ATR(14) z high/low/close (jeśli dostępne),
   - wykrywać impuls (parametry: impulse_lookback, impulse_threshold_pct, impulse_atr_mult),
   - generować sygnał: BUY / SELL / HOLD / CLOSE (CLOSE gdy pozycja otwarta i warunki wyjścia spełnione)
C) Wejście (gdy brak pozycji):
   - Jeśli RSI > 70 i wykryto impuls wzrostowy -> SELL
   - Jeśli RSI < 30 i wykryto impuls spadkowy -> BUY
   - W pozostałych przypadkach -> HOLD
D) Wyjście (gdy pozycja otwarta):
   - Zamknij, gdy osiągnięty take profit (zysk >= target_usd) albo stop loss (strata <= -risk_usd)
   - Dodatkowo: “spłaszczenie”/sideways exit:
       jeśli po upływie max_hold_seconds i cena nie poszła w stronę zysku (PnL w pobliżu 0), to CLOSE
E) Zadbaj o to, żeby strategia NIE SPAMOWAŁA transakcji:
   - Dodaj cooldown_seconds po zamknięciu pozycji.
   - Dodaj minimalny odstęp od ostatniego wejścia.
F) Logowanie:
   - loguj RSI, czy wykryto impuls, próg impulsu, decyzję (BUY/SELL/HOLD/CLOSE) i powód.

INTEGRACJA Z ENGINE:
- Użyj paper_trading_engine podobnie jak w prompt_strategy_v12:
  - get_open_positions()
  - get_current_price(symbol)
  - position.calculate_pnl(current_price)
  - position.opened_at
  - position.side / entry_price / size / stop_loss / take_profit
Jeśli nazwy metod/atrybutów różnią się w projekcie, znajdź właściwe w kodzie i dopasuj.

KONFIGURACJA:
- Dodaj w __init__ odczyt z config dict dla:
  rsi_period=14
  atr_period=14
  impulse_lookback=3..5
  impulse_threshold_pct=0.5..1.0 (dla BTC)
  impulse_atr_mult=1.5..3.0
  target_profit_usd=500
  max_loss_usd=500
  max_hold_seconds=600..1800
  cooldown_seconds=60..180
  slippage_percent=0.1
  min_confidence_for_trade (opcjonalnie; tu możesz zawsze dać np. 8.0 gdy sygnał spełniony)

TESTY / WALIDACJA:
- Dodaj minimalne testy jednostkowe (jeśli repo ma test framework) albo prosty skrypt weryfikacyjny:
  - RSI > 70 + impuls up -> SELL
  - RSI < 30 + impuls down -> BUY
  - brak impulsu -> HOLD

WYJŚCIE:
- Zrób implementację, a na koniec wypisz krótkie podsumowanie zmian oraz jak uruchomić strategię.
- Nie zmieniaj PromptStrategyV12 poza ewentualnym wspólnym helperem, jeśli to konieczne; preferuj izolację.

ZACZNIJ:
1) Przejrzyj BaseStrategy, TradingSignal, SignalType i paper_trading_engine API w repo.
2) Zaimplementuj PiotrSwiecStrategy zgodnie z powyższą specyfikacją.
3) Dodaj konfigurację i przykładowe użycie.