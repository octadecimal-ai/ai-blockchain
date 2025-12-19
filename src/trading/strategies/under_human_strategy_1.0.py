from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger

from .base_strategy import BaseStrategy, TradingSignal, SignalType
from src.collectors.exchange.dydx_collector import DydxCollector


class UnderhumanStrategyV10(BaseStrategy):
    """
    UNDERHUMAN STRATEGY v1.0 (dYdX)
    Handluje zmianę stanu rynku poprzez wykrywanie anomalii strukturalnych:
    - impulse_failure
    - energy_divergence
    - asymmetric_response
    - reaction_delay

    Wymaga (optymalnie) danych:
    - OHLCV (df)
    - orderbook (bids/asks)
    - funding_rate
    - open_interest
    """

    name = "UnderhumanStrategyV10"
    description = "Strategia zmiany stanu rynku + anomalie (UNDERHUMAN v1.0)"
    timeframe = "1m"  # Używamy danych minutowych

    def __init__(self, config: dict = None):
        super().__init__(config)

        # === RSI tylko jako czujnik przegrzania ===
        self.rsi_period = self.config.get("rsi_period", 14)

        # === Okna/parametry anomalii ===
        self.lookback_state = self.config.get("lookback_state", 36)          # np. 36 świec = 3h na 5m
        self.lookback_short = self.config.get("lookback_short", 6)           # krótkie okno (30 min)
        self.lookback_impulse = self.config.get("lookback_impulse", 4)       # impuls (20 min)

        self.impulse_threshold_pct = self.config.get("impulse_threshold_pct", 0.8)
        self.min_anomalies_to_trade = self.config.get("min_anomalies_to_trade", 2)

        # Orderbook
        self.orderbook_levels = self.config.get("orderbook_levels", 10)
        self.imbalance_threshold = self.config.get("imbalance_threshold", 0.18)  # 0.18 = dość mocno

        # Funding/OI
        self.funding_divergence_z = self.config.get("funding_divergence_z", 1.2)
        self.oi_divergence_z = self.config.get("oi_divergence_z", 1.2)

        # Reaction delay
        self.delay_threshold = self.config.get("delay_threshold", 1.35)

        # Money/risk
        self.target_profit_usd_min = self.config.get("target_profit_usd_min", 400.0)
        self.target_profit_usd_max = self.config.get("target_profit_usd_max", 1000.0)
        self.max_loss_usd = self.config.get("max_loss_usd", 500.0)

        self.max_hold_seconds = self.config.get("max_hold_seconds", 900)
        self.cooldown_seconds = self.config.get("cooldown_seconds", 120)

        self.slippage_percent = self.config.get("slippage_percent", 0.1)
        self.min_confidence_for_trade = self.config.get("min_confidence_for_trade", 7.0)

        self.position_size_btc = self.config.get("position_size_btc", 0.1)
        self.last_close_time: Optional[datetime] = None
        self.paper_trading_engine = None
        
        # Tryb backtestingu - nie pobieraj danych z API
        self._backtest_mode = self.config.get("_backtest_mode", False)
        
        # Inicjalizuj DydxCollector dla danych rynkowych (tylko jeśli nie jesteśmy w trybie backtestingu)
        if not self._backtest_mode:
            try:
                self.dydx_collector = DydxCollector(testnet=False)
                logger.info("DydxCollector zainicjalizowany dla UNDERHUMAN")
            except Exception as e:
                logger.warning(f"Nie udało się zainicjalizować DydxCollector: {e}")
                self.dydx_collector = None
        else:
            self.dydx_collector = None
            logger.info("Tryb backtestingu - pomijam inicjalizację DydxCollector")
        
        # Cache dla danych z bazy (tylko w trybie backtestingu)
        # Używamy jednej instancji DatabaseManager zamiast tworzyć nową przy każdym wywołaniu
        self._db_manager = None
        self._funding_rates_cache: Optional[pd.DataFrame] = None
        self._open_interest_cache: Optional[pd.DataFrame] = None
        self._cache_date_range: Optional[Tuple[datetime, datetime]] = None

        logger.info(f"Strategia {self.name} zainicjalizowana (UNDERHUMAN).")

    def set_paper_trading_engine(self, engine):
        self.paper_trading_engine = engine

    # =========================
    # INDICATORS / FEATURES
    # =========================

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def _zscore(self, s: pd.Series, window: int) -> pd.Series:
        m = s.rolling(window).mean()
        sd = s.rolling(window).std().replace(0, np.nan)
        return (s - m) / sd

    def _pct_change_n(self, s: pd.Series, n: int) -> float:
        if len(s) < n + 1:
            return 0.0
        a = float(s.iloc[-1])
        b = float(s.iloc[-n-1])
        if b == 0:
            return 0.0
        return ((a - b) / b) * 100.0

    def _orderbook_imbalance(self, orderbook: Optional[Dict[str, Any]]) -> Optional[float]:
        """
        Imbalance = (sum(bid_qty) - sum(ask_qty)) / (sum(bid_qty)+sum(ask_qty))
        Zakładamy listy: bids=[(price, size), ...], asks=[(price, size), ...]
        """
        if not orderbook:
            return None
        bids = orderbook.get("bids") or []
        asks = orderbook.get("asks") or []
        if not bids or not asks:
            return None

        bids = bids[: self.orderbook_levels]
        asks = asks[: self.orderbook_levels]

        bid_qty = sum(float(x[1]) for x in bids)
        ask_qty = sum(float(x[1]) for x in asks)
        denom = (bid_qty + ask_qty)
        if denom == 0:
            return None
        return (bid_qty - ask_qty) / denom

    def _price_reaction_to_volume(self, df: pd.DataFrame, window: int) -> float:
        """
        Jak mocno cena reaguje na wolumen w krótkim oknie:
        reaction = |return| / (volume_z + eps)
        -> wysokie = rynek "rusza się" na wolumen
        -> niskie  = wolumen nie pcha ceny (potencjalne impulse_failure)
        """
        close = df["close"]
        vol = df.get("volume", pd.Series([0]*len(df)))
        rets = close.pct_change().abs()
        vol_z = self._zscore(vol, window).abs()
        v = float((rets / (vol_z + 1e-6)).iloc[-1])
        return v

    # =========================
    # ANOMALIES
    # =========================

    def _detect_impulse(self, df: pd.DataFrame) -> Dict[str, Any]:
        close = df["close"]
        pct = self._pct_change_n(close, self.lookback_impulse)
        detected = abs(pct) >= self.impulse_threshold_pct
        direction = "up" if pct > 0 else ("down" if pct < 0 else None)
        return {"detected": detected, "direction": direction, "magnitude_pct": round(pct, 3)}

    def _impulse_failure(self, df: pd.DataFrame) -> bool:
        """
        Impuls był, ale po nim brak kontynuacji:
        - był ruch >= threshold (lookback_impulse)
        - a ostatnie 1-2 świece mają mały follow-through
        """
        imp = self._detect_impulse(df)
        if not imp["detected"]:
            return False

        close = df["close"]
        # follow-through: zmiana ostatnich 2 świec
        ft = abs(self._pct_change_n(close, 2))
        # jeżeli był impuls, ale follow-through jest mały, to failure
        return ft < (self.impulse_threshold_pct * 0.25)

    def _energy_divergence(self, df: pd.DataFrame, market_ctx: Optional[Dict[str, Any]]) -> Tuple[bool, Dict[str, bool]]:
        """
        Divergencje:
        - cena ~ stoi, a OI rośnie
        - cena ~ stoi, a funding odjeżdża
        """
        details = {
            "oi_vs_price_divergence": False,
            "funding_vs_price_divergence": False
        }
        if not market_ctx:
            return False, details

        close = df["close"]
        # "stoi": mała zmienność w krótkim oknie
        drift = abs(self._pct_change_n(close, self.lookback_short))

        oi = market_ctx.get("open_interest", None)
        fr = market_ctx.get("funding_rate", None)

        # Jeśli nie masz historii OI/FR w df, to minimalnie:
        # traktuj jako "punktowe" i nie licz z-score -> brak sygnału
        # Najlepiej: doklej OI/FR do df jako kolumny historyczne.
        # Tu: jeśli df ma te kolumny, użyj ich.
        oi_div = False
        fr_div = False

        if "open_interest" in df.columns:
            oi_z = float(self._zscore(df["open_interest"], self.lookback_state).iloc[-1])
            if drift < 0.15 and oi_z > self.oi_divergence_z:
                oi_div = True

        if "funding_rate" in df.columns:
            fr_z = float(self._zscore(df["funding_rate"], self.lookback_state).iloc[-1])
            if drift < 0.15 and abs(fr_z) > self.funding_divergence_z:
                fr_div = True

        # fallback (punktowe) – konserwatywnie: nie sygnalizuj
        details["oi_vs_price_divergence"] = oi_div
        details["funding_vs_price_divergence"] = fr_div

        return (oi_div or fr_div), details

    def _asymmetric_response(self, df: pd.DataFrame) -> bool:
        """
        Porównaj reakcję rynku na wzrosty vs spadki w krótkim oknie.
        Jeśli jedna strona ma wyraźnie słabszą reakcję, jest asymetria.
        """
        if len(df) < self.lookback_short + 2:
            return False

        close = df["close"]
        vol = df.get("volume", pd.Series([0]*len(df)))

        rets = close.pct_change()
        up = rets.where(rets > 0, 0).tail(self.lookback_short)
        dn = (-rets.where(rets < 0, 0)).tail(self.lookback_short)

        vol_s = vol.tail(self.lookback_short)

        up_energy = float((up.abs() / (vol_s + 1e-6)).mean())
        dn_energy = float((dn.abs() / (vol_s + 1e-6)).mean())

        if up_energy == 0 or dn_energy == 0:
            return False

        ratio = max(up_energy, dn_energy) / min(up_energy, dn_energy)
        # im większy ratio, tym bardziej asymetrycznie
        return ratio > 1.45

    def _reaction_delay(self, df: pd.DataFrame) -> bool:
        """
        Heurystyka: jeśli "reakcja ceny na wolumen" spada vs swoją medianę,
        rynek reaguje wolniej/słabiej na bodźce.
        """
        if len(df) < self.lookback_state + 5:
            return False
        r_now = self._price_reaction_to_volume(df, self.lookback_short)

        # historyczna baza
        vals = []
        for i in range(10, 0, -1):
            sub = df.iloc[:-i]
            if len(sub) < self.lookback_short + 5:
                continue
            vals.append(self._price_reaction_to_volume(sub, self.lookback_short))

        if not vals:
            return False

        baseline = float(np.median(vals))
        if baseline <= 0:
            return False

        # jeśli obecna reakcja jest znacząco mniejsza od bazowej -> opóźnienie
        return (baseline / (r_now + 1e-9)) > self.delay_threshold

    def _market_state(self, df: pd.DataFrame, rsi_value: float) -> str:
        """
        Prosta klasyfikacja stanu:
        - STABLE: niska zmienność, RSI ~ środek
        - OVEREXTENDED: duży drift + RSI wysokie
        - PANIC: duży drift + RSI niskie
        - CHAOS: wysoka zmienność (ATR proxy) i brak kierunku
        - EXHAUSTION: po impulsie + malejąca reakcja
        """
        close = df["close"]
        drift_short = abs(self._pct_change_n(close, self.lookback_short))
        drift_state = abs(self._pct_change_n(close, self.lookback_state))

        # prosty proxy zmienności: std returns
        vol = float(close.pct_change().tail(self.lookback_short).std() or 0)

        if drift_short < 0.25 and 40 <= rsi_value <= 60:
            return "STABLE"

        if drift_short >= 0.8 and rsi_value > 65:
            return "OVEREXTENDED"

        if drift_short >= 0.8 and rsi_value < 35:
            return "PANIC"

        if vol > 0.012 and drift_state < 0.4:
            return "CHAOS"

        # default: jeśli było mocno i teraz gaśnie -> EXHAUSTION
        if drift_state >= 1.2 and drift_short < 0.25:
            return "EXHAUSTION"

        return "STABLE"

    # =========================
    # POSITION / COOLDOWN / SLTP
    # =========================

    def _get_current_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.paper_trading_engine:
            return None
        open_positions = self.paper_trading_engine.get_open_positions()
        position = next((p for p in open_positions if p.symbol == symbol), None)
        if not position:
            return None

        current_price = self.paper_trading_engine.get_current_price(symbol)
        pnl, pnl_percent = position.calculate_pnl(current_price)
        seconds_open = (datetime.now() - position.opened_at).total_seconds()

        return {
            "position": position,
            "side": position.side.value,
            "entry_price": position.entry_price,
            "current_price": current_price,
            "size": position.size,
            "pnl_usd": pnl,
            "pnl_percent": pnl_percent,
            "seconds_open": seconds_open,
        }

    def _is_in_cooldown(self) -> bool:
        if self.last_close_time is None:
            return False
        return (datetime.now() - self.last_close_time).total_seconds() < self.cooldown_seconds

    def _calculate_sl_tp(self, entry_price: float, side: str, size_btc: float, confidence: float) -> Dict[str, float]:
        """
        TP adaptacyjne: im większy confidence, tym bliżej max.
        """
        conf = max(1.0, min(10.0, confidence))
        tp_usd = self.target_profit_usd_min + (self.target_profit_usd_max - self.target_profit_usd_min) * ((conf - 1.0) / 9.0)

        size = size_btc if size_btc > 0 else self.position_size_btc
        slippage_factor = 1 + (self.slippage_percent / 100)

        if side == "long":
            take_profit = entry_price + (tp_usd / size) / slippage_factor
            stop_loss = entry_price - (self.max_loss_usd / size) * slippage_factor
        else:
            take_profit = entry_price - (tp_usd / size) / slippage_factor
            stop_loss = entry_price + (self.max_loss_usd / size) * slippage_factor

        return {"take_profit": round(take_profit, 2), "stop_loss": round(stop_loss, 2), "tp_usd": round(tp_usd, 2)}

    # =========================
    # ENRICHMENT: OI + FUNDING
    # =========================
    
    def _get_db_manager(self):
        """Pobiera lub tworzy instancję DatabaseManager (tylko raz)."""
        if self._db_manager is None:
            from src.database.manager import DatabaseManager
            import os
            from pathlib import Path
            from dotenv import load_dotenv
            
            # Załaduj .env
            env_path = Path(__file__).parent.parent.parent.parent / '.env'
            if env_path.exists():
                load_dotenv(env_path)
            
            database_url = os.getenv('DATABASE_URL')
            use_timescale = os.getenv('USE_TIMESCALE', 'false').lower() == 'true'
            self._db_manager = DatabaseManager(database_url=database_url, use_timescale=use_timescale)
        
        return self._db_manager
    
    def _load_market_data_cache(self, start_date: datetime, end_date: datetime):
        """
        Ładuje dane funding rates i open interest do cache (tylko raz dla całego okresu).
        
        Args:
            start_date: Data początkowa
            end_date: Data końcowa
        """
        # Sprawdź czy cache jest już załadowany dla tego zakresu dat
        # Rozszerzamy cache jeśli nowy zakres jest szerszy
        if (self._cache_date_range is not None and 
            self._cache_date_range[0] <= start_date and 
            self._cache_date_range[1] >= end_date and
            self._funding_rates_cache is not None and
            self._open_interest_cache is not None):
            return  # Cache już załadowany dla tego zakresu
        
        try:
            db = self._get_db_manager()
            
            # Jeśli cache istnieje, rozszerz go jeśli potrzeba
            if self._cache_date_range is not None:
                # Rozszerz zakres jeśli nowy jest szerszy
                cache_start = min(self._cache_date_range[0], start_date)
                cache_end = max(self._cache_date_range[1], end_date)
            else:
                cache_start = start_date
                cache_end = end_date
            
            # Pobierz funding rates z bazy (z tabeli tickers)
            funding_df = db.get_funding_rates(
                exchange="binance",
                symbol="BTC/USDC",  # Tickers używają symbolu spot
                start_date=cache_start,
                end_date=cache_end
            )
            
            # Pobierz open interest z bazy
            oi_df = db.get_open_interest(
                exchange="binance",
                symbol="BTC/USDT:USDT",  # Perpetual futures
                start_date=cache_start,
                end_date=cache_end
            )
            
            # Zapisz do cache
            self._funding_rates_cache = funding_df
            self._open_interest_cache = oi_df
            self._cache_date_range = (cache_start, cache_end)
            
            if len(funding_df) > 0 or len(oi_df) > 0:
                logger.debug(f"✅ Załadowano/rozszerzono cache: {len(funding_df)} funding rates, {len(oi_df)} open interest dla okresu {cache_start.date()} → {cache_end.date()}")
            
        except Exception as e:
            logger.warning(f"Nie udało się załadować danych do cache: {e}, pozostawiamy None (zgodnie z zasadą projektu)")
            if self._funding_rates_cache is None:
                self._funding_rates_cache = pd.DataFrame()
            if self._open_interest_cache is None:
                self._open_interest_cache = pd.DataFrame()
    
    def _enrich_df_with_market_data(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Dokleja historię OI i funding rate do DataFrame.
        
        To jest kluczowe dla wykrywania energy_divergence.
        W trybie backtestingu pobiera dane z bazy danych (zgodnie z zasadą projektu).
        Jeśli dane nie są dostępne, pozostawia None zamiast symulować.
        
        Używa cache'owanych danych zamiast tworzyć nowe połączenia do bazy.
        """
        df_enriched = df.copy()
        
        # W trybie backtestingu nie pobieramy danych z API (za wolne, rate limiting)
        # Zgodnie z zasadą projektu: NIE używamy symulowanych danych
        # Jeśli brak DydxCollector, próbujemy pobrać z bazy danych
        if self.dydx_collector is None:
            logger.debug("Brak DydxCollector - próbuję pobrać dane z bazy danych")
            # Przejdź do logiki pobierania z bazy (poniżej)
        
        try:
            # W trybie backtestingu odczytaj dane z bazy danych
            if hasattr(self, '_backtest_mode') and self._backtest_mode:
                # Użyj cache'owanych danych zamiast tworzyć nowe połączenie
                if isinstance(df_enriched.index, pd.DatetimeIndex) and len(df_enriched) > 0:
                    start_date = df_enriched.index.min()
                    end_date = df_enriched.index.max()
                    
                    # Załaduj cache jeśli jeszcze nie jest załadowany (tylko raz dla całego okresu)
                    # Cache będzie rozszerzany automatycznie jeśli potrzeba
                    self._load_market_data_cache(start_date, end_date)
                    
                    # Użyj cache'owanych danych
                    if self._funding_rates_cache is not None and not self._funding_rates_cache.empty:
                        # Reindex bez forward fill - tylko dokładne dopasowanie timestamp
                        df_enriched['funding_rate'] = self._funding_rates_cache['funding_rate'].reindex(df_enriched.index)
                    else:
                        df_enriched['funding_rate'] = None
                    
                    if self._open_interest_cache is not None and not self._open_interest_cache.empty:
                        # Reindex bez forward fill - tylko dokładne dopasowanie timestamp
                        df_enriched['open_interest'] = self._open_interest_cache['open_interest'].reindex(df_enriched.index)
                    else:
                        df_enriched['open_interest'] = None
                else:
                    df_enriched['funding_rate'] = None
                    df_enriched['open_interest'] = None
                    logger.warning("Brak DatetimeIndex - nie można dopasować danych")
                
                return df_enriched
            
            # Pobierz historię funding rates
            # Funding rates są co 8 godzin, więc potrzebujemy więcej danych
            funding_df = self.dydx_collector.get_funding_rates(symbol, limit=200)
            
            if not funding_df.empty and 'funding_rate' in funding_df.columns:
                # Merge funding rates z df na podstawie timestamp
                # Funding rates są co 8 godzin, więc forward fill do świec
                
                # Upewnij się, że df ma index jako timestamp
                # fetch_candles zwraca DataFrame z indexem jako timestamp (DatetimeIndex)
                df_index_was_timestamp = False
                original_index_name = None
                
                # Sprawdź czy index jest DatetimeIndex (obsługuj różne timezone)
                if isinstance(df_enriched.index, pd.DatetimeIndex):
                    df_index_was_timestamp = True
                    original_index_name = df_enriched.index.name
                    # Normalizuj timezone jeśli potrzeba
                    if df_enriched.index.tz is not None:
                        df_enriched.index = df_enriched.index.tz_localize(None)
                elif hasattr(df_enriched.index, 'dtype'):
                    # Sprawdź czy dtype zawiera datetime
                    dtype_str = str(df_enriched.index.dtype)
                    if 'datetime' in dtype_str:
                        df_index_was_timestamp = True
                        original_index_name = df_enriched.index.name
                        # Normalizuj timezone jeśli potrzeba
                        if hasattr(df_enriched.index, 'tz') and df_enriched.index.tz is not None:
                            df_enriched.index = df_enriched.index.tz_localize(None)
                elif 'timestamp' in df_enriched.columns:
                    df_enriched['timestamp'] = pd.to_datetime(df_enriched['timestamp'])
                    original_index_name = df_enriched.index.name
                    df_enriched = df_enriched.set_index('timestamp')
                    df_index_was_timestamp = True
                else:
                    # Spróbuj użyć pierwszej kolumny datetime
                    for col in df_enriched.columns:
                        if 'time' in col.lower() or 'date' in col.lower():
                            df_enriched[col] = pd.to_datetime(df_enriched[col])
                            original_index_name = df_enriched.index.name
                            df_enriched = df_enriched.set_index(col)
                            df_index_was_timestamp = True
                            break
                
                if df_index_was_timestamp:
                    # Forward fill funding rates do timestamp świec
                    # Funding rates są rzadkie (co 8h), więc forward fill
                    funding_series = funding_df['funding_rate']
                    
                    # Zgodnie z zasadą: używamy tylko rzeczywistych danych, nie forward fill
                    # Reindex bez forward fill - tylko dokładne dopasowanie timestamp
                    df_enriched['funding_rate'] = funding_series.reindex(df_enriched.index)
                    
                    # Zgodnie z zasadą: jeśli nie ma funding rates, pozostawiamy None
                    if df_enriched['funding_rate'].isna().any():
                        logger.warning(f"⚠️ Brak funding rates dla {df_enriched['funding_rate'].isna().sum()} rekordów - pozostawiamy None (zgodnie z zasadą projektu)")
                    
                    funding_count = df_enriched['funding_rate'].notna().sum()
                    if funding_count > 0:
                        logger.info(f"✅ Dodano historię funding rates ({funding_count}/{len(df_enriched)} wartości)")
                    else:
                        logger.warning("⚠️ Nie udało się dodać funding rates do DataFrame")
                else:
                    logger.warning("Nie można dopasować funding rates - brak timestamp w df")
            
            # Open Interest - dYdX API nie ma historii, więc użyjemy aktualnej wartości
            # i wypełnimy wstecz (forward fill)
            try:
                ticker_data = self.dydx_collector.get_ticker(symbol)
                current_oi = float(ticker_data.get('open_interest', 0))
                
                if current_oi > 0:
                    # Wypełnij całą historię aktualną wartością (uproszczenie)
                    # W rzeczywistości OI zmienia się, ale bez historii API musimy użyć tego
                    df_enriched['open_interest'] = current_oi
                    logger.info(f"✅ Dodano Open Interest: {current_oi:,.0f}")
            except Exception as e:
                logger.warning(f"Nie udało się pobrać Open Interest: {e}")
            
        except Exception as e:
            logger.warning(f"Błąd wzbogacania danych rynkowych: {e}")
        
        return df_enriched
    
    def _get_orderbook(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Pobiera orderbook z dYdX.
        
        Returns:
            Dict z bids i asks lub None
        """
        if self.dydx_collector is None:
            return None
        
        try:
            orderbook = self.dydx_collector.get_orderbook(symbol)
            return {
                'bids': orderbook.get('bids', []),
                'asks': orderbook.get('asks', [])
            }
        except Exception as e:
            logger.warning(f"Nie udało się pobrać orderbook: {e}")
            return None

    # =========================
    # MAIN
    # =========================

    def analyze(self, df: pd.DataFrame, symbol: str = "BTC-USD", market_ctx: Optional[Dict[str, Any]] = None) -> Optional[TradingSignal]:
        if df is None or df.empty:
            return None

        min_bars = max(self.rsi_period, self.lookback_state, self.lookback_short, self.lookback_impulse) + 5
        if len(df) < min_bars:
            return None
        
        # Wzbogać df o historię OI i funding rate
        df = self._enrich_df_with_market_data(df, symbol)
        
        # Pobierz orderbook (jeśli nie został przekazany w market_ctx)
        if market_ctx is None:
            market_ctx = {}
        
        if 'orderbook' not in market_ctx:
            market_ctx['orderbook'] = self._get_orderbook(symbol)
        
        # Dodaj aktualne OI i funding do market_ctx (dla kompatybilności)
        try:
            if self.dydx_collector:
                ticker_data = self.dydx_collector.get_ticker(symbol)
                # Zgodnie z zasadą: używamy None zamiast 0 dla brakujących danych
                open_interest = ticker_data.get('open_interest')
                market_ctx['open_interest'] = float(open_interest) if open_interest is not None else None
                
                # Pobierz ostatni funding rate
                funding_rates = self.dydx_collector.get_funding_rates(symbol, limit=1)
                if not funding_rates.empty:
                    market_ctx['funding_rate'] = float(funding_rates['funding_rate'].iloc[-1])
        except Exception as e:
            logger.debug(f"Nie udało się pobrać aktualnych danych rynkowych: {e}")

        close = df["close"]
        current_price = float(close.iloc[-1])

        rsi = self._calculate_rsi(close, self.rsi_period)
        current_rsi = float(rsi.iloc[-1])

        state = self._market_state(df, current_rsi)

        anomalies = {
            "impulse_failure": self._impulse_failure(df),
            "asymmetric_response": self._asymmetric_response(df),
            "reaction_delay": self._reaction_delay(df),
            "energy_divergence": False,
        }
        energy_div, energy_details = self._energy_divergence(df, market_ctx)
        anomalies["energy_divergence"] = energy_div

        anomaly_count = sum(1 for v in anomalies.values() if v)

        # orderbook imbalance (wspiera confidence, nie jest anomalią samą w sobie)
        ob_imb = self._orderbook_imbalance((market_ctx or {}).get("orderbook"))
        ob_bias = 0.0
        if ob_imb is not None:
            if abs(ob_imb) >= self.imbalance_threshold:
                ob_bias = float(ob_imb)

        anomalies_str = ", ".join([f"{k}={v}" for k, v in anomalies.items()])
        ob_imb_str = f"{ob_imb:.3f}" if ob_imb is not None else "None"
        logger.info(
            f"[{self.name}] {symbol} state={state}, RSI={current_rsi:.1f}, "
            f"anomalies={anomaly_count}/{len(anomalies)} ({anomalies_str}), ob_imb={ob_imb_str}"
        )

        pos = self._get_current_position(symbol)
        if pos:
            return self._check_exit(pos, df, state, anomalies, symbol)

        # entry
        if self._is_in_cooldown():
            return None

        if anomaly_count < self.min_anomalies_to_trade:
            return None

        # decyzja kierunku: nie "RSI", tylko stan + wypadkowa
        action = None
        reason = []

        # SHORT: OVEREXTENDED/EXHAUSTION i rynek przestaje reagować na popyt
        if state in ("OVEREXTENDED", "EXHAUSTION"):
            action = SignalType.SELL
            reason.append(f"state={state} + anomalies={anomaly_count}")

        # LONG: PANIC/CHAOS/EXHAUSTION (po spadku) i sprzedaż przestaje działać
        if state in ("PANIC", "CHAOS"):
            action = SignalType.BUY
            reason.append(f"state={state} + anomalies={anomaly_count}")

        if action is None:
            # EXHAUSTION bez kierunku: użyj bias z orderbook lub znak ostatniego impulsu
            imp = self._detect_impulse(df)
            if ob_bias > 0:
                action = SignalType.BUY
                reason.append("orderbook imbalance -> bids dominate")
            elif ob_bias < 0:
                action = SignalType.SELL
                reason.append("orderbook imbalance -> asks dominate")
            else:
                # fallback: kontra ostatni impuls
                if imp["detected"] and imp["direction"] == "up":
                    action = SignalType.SELL
                    reason.append("impulse detected -> fade (mean reversion)")
                elif imp["detected"] and imp["direction"] == "down":
                    action = SignalType.BUY
                    reason.append("impulse detected -> fade (mean reversion)")
                else:
                    return None

        # confidence scoring (AI-owe ważenie, bez emocji)
        confidence = 5.0
        confidence += 1.2 * anomaly_count
        if anomalies["impulse_failure"]:
            confidence += 1.0
        if anomalies["energy_divergence"]:
            confidence += 1.0
        if ob_imb is not None and abs(ob_imb) >= self.imbalance_threshold:
            confidence += 0.8

        # RSI tylko jako czujnik przegrzania / paniki (nie warunek)
        if action == SignalType.SELL and current_rsi > 60:
            confidence += 0.4
        if action == SignalType.BUY and current_rsi < 40:
            confidence += 0.4

        confidence = float(max(1.0, min(10.0, confidence)))
        if confidence < self.min_confidence_for_trade:
            return None

        side = "long" if action == SignalType.BUY else "short"
        sltp = self._calculate_sl_tp(current_price, side, self.position_size_btc, confidence)

        reason_str = (
            f"{' / '.join(reason)} | "
            f"anom={anomalies} | "
            f"energy_details={energy_details} | "
            f"RSI={current_rsi:.1f} | "
            f"ob_imb={None if ob_imb is None else round(ob_imb, 3)}"
        )

        logger.info(f"🎯 [{self.name}] ENTRY {action.value.upper()} conf={confidence:.1f} {reason_str}")

        return TradingSignal(
            signal_type=action,
            symbol=symbol,
            confidence=confidence,
            price=current_price,
            stop_loss=sltp["stop_loss"],
            take_profit=sltp["take_profit"],
            size_percent=15.0,
            reason=reason_str,
            strategy=self.name,
        )

    def _check_exit(
        self,
        position_info: Dict[str, Any],
        df: pd.DataFrame,
        state: str,
        anomalies: Dict[str, bool],
        symbol: str
    ) -> Optional[TradingSignal]:
        pnl = float(position_info["pnl_usd"])
        seconds_open = float(position_info["seconds_open"])
        side = position_info["side"]

        # 1) hard stop/profit (paper engine i tak ma SL/TP, ale trzymamy logikę)
        if pnl <= -self.max_loss_usd:
            self.last_close_time = datetime.now()
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=10.0,
                price=float(df["close"].iloc[-1]),
                reason=f"STOP LOSS hit pnl={pnl:.2f}",
                strategy=self.name
            )

        # 2) wyjście strukturalne: zanik anomalii
        anomaly_count = sum(1 for v in anomalies.values() if v)
        if anomaly_count == 0:
            self.last_close_time = datetime.now()
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=8.5,
                price=float(df["close"].iloc[-1]),
                reason=f"STRUCTURE NORMALIZED (anomalies vanished) pnl={pnl:.2f}",
                strategy=self.name
            )

        # 3) timeout jeśli brak sensownego progresu
        if seconds_open >= self.max_hold_seconds and pnl < 0.3 * self.target_profit_usd_max:
            self.last_close_time = datetime.now()
            return TradingSignal(
                signal_type=SignalType.CLOSE,
                symbol=symbol,
                confidence=8.0,
                price=float(df["close"].iloc[-1]),
                reason=f"TIMEOUT {seconds_open:.0f}s pnl={pnl:.2f} state={state}",
                strategy=self.name
            )

        return None