"""
Trading Bot
===========
Bot do automatycznego tradingu na dYdX (paper trading).
"""

import time
import signal
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from threading import Thread, Event
from loguru import logger

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.collectors.exchange.dydx_collector import DydxCollector
from src.trading.paper_trading import PaperTradingEngine
from src.trading.strategies.base_strategy import BaseStrategy, TradingSignal, SignalType
from src.trading.strategies.piotrek_strategy import PiotrekBreakoutStrategy
from src.trading.models import PaperPosition, OrderSide


class TradingBot:
    """
    Bot tradingowy dla paper trading na dYdX.
    
    Funkcje:
    - Monitorowanie rynku w czasie rzeczywistym
    - Wykonywanie strategii
    - Zarządzanie pozycjami (SL/TP)
    - Logowanie wszystkich akcji
    """
    
    def __init__(
        self,
        database_url: str = "sqlite:///data/paper_trading.db",
        account_name: str = "piotrek_bot",
        initial_balance: float = 10000.0,
        symbols: List[str] = None,
        strategy: Optional[BaseStrategy] = None,
        check_interval: int = 60,  # sekundy
        position_size_config: Optional[dict] = None
    ):
        """
        Inicjalizacja bota.
        
        Args:
            database_url: URL bazy danych
            account_name: Nazwa konta paper trading
            initial_balance: Początkowy kapitał
            symbols: Lista symboli do monitorowania
            strategy: Strategia tradingowa
            check_interval: Interwał sprawdzania (sekundy)
        """
        self.symbols = symbols or ["BTC-USD", "ETH-USD"]
        self.check_interval = check_interval
        self.running = False
        self._stop_event = Event()
        
        # Baza danych
        self.engine = create_engine(database_url, echo=False)
        
        # Utwórz tabele - wszystkie Base muszą być zaimportowane
        from src.trading.models import Base as TradingBase
        from src.database.models import Base as DatabaseBase
        
        # Import modeli z models_extended (używają DatabaseBase)
        from src.trading.models_extended import Strategy, TradeRegister, TradingSession
        
        TradingBase.metadata.create_all(self.engine)
        DatabaseBase.metadata.create_all(self.engine)  # To tworzy też tabele z models_extended
        
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # dYdX collector
        self.dydx = DydxCollector(testnet=False)
        
        # Paper trading engine
        # Pobierz slippage z konfiguracji strategii lub użyj domyślnego
        slippage_percent = 0.75
        if strategy and hasattr(strategy, 'config'):
            slippage_percent = strategy.config.get('slippage_percent', 0.75)
        
        self.engine_pt = PaperTradingEngine(
            session=self.session,
            account_name=account_name,
            dydx_collector=self.dydx,
            slippage_percent=slippage_percent
        )
        
        # Strategia
        self.strategy = strategy or PiotrekBreakoutStrategy({
            'breakout_threshold': 1.0,
            'consolidation_threshold': 0.5,
            'min_confidence': 6
        })
        
        # Jeśli strategia potrzebuje dydx_collector, przekaż go
        if hasattr(self.strategy, 'config') and self.strategy.config.get('use_real_funding_rate'):
            if not self.strategy.config.get('dydx_collector'):
                self.strategy.config['dydx_collector'] = self.dydx
                # Re-inicjalizuj strategię z nową konfiguracją
                self.strategy.__init__(self.strategy.config)
        
        # Jeśli strategia to PromptStrategy, przekaż paper trading engine
        if hasattr(self.strategy, 'set_paper_trading_engine'):
            self.strategy.set_paper_trading_engine(self.engine_pt)
        
        # Konfiguracja
        self.max_positions = 3  # Maksymalna liczba otwartych pozycji
        self.position_size_percent = 10.0  # % kapitału na pozycję
        self.default_leverage = 2.0  # Domyślna dźwignia
        self.position_size_config = position_size_config  # Stały rozmiar pozycji (np. {'symbol': 'BTC', 'size': 1.0})
        
        # Trading session (będzie utworzona przy starcie)
        self.trading_session = None
        
        logger.info(f"🤖 Trading Bot zainicjalizowany: {account_name}")
        logger.info(f"   Symbole: {self.symbols}")
        logger.info(f"   Strategia: {self.strategy.name}")
        logger.info(f"   Interwał: {self.check_interval}s")
    
    def get_market_data(self, symbol: str, limit: int = 50) -> Any:
        """Pobiera dane rynkowe używając timeframe strategii."""
        try:
            # Użyj timeframe z strategii (domyślnie 1h)
            timeframe = getattr(self.strategy, 'timeframe', '1h')
            df = self.dydx.fetch_candles(symbol, timeframe, limit=limit)
            return df
        except Exception as e:
            logger.error(f"Błąd pobierania danych dla {symbol}: {e}")
            return None
    
    def process_signal(self, signal: TradingSignal) -> bool:
        """
        Przetwarza sygnał tradingowy.
        
        Args:
            signal: Sygnał do przetworzenia
            
        Returns:
            True jeśli wykonano akcję
        """
        if signal.signal_type == SignalType.BUY:
            return self._handle_buy_signal(signal)
        elif signal.signal_type == SignalType.SELL:
            return self._handle_sell_signal(signal)
        elif signal.signal_type == SignalType.CLOSE:
            return self._handle_close_signal(signal)
        
        return False
    
    def _handle_buy_signal(self, signal: TradingSignal) -> bool:
        """Obsługuje sygnał kupna."""
        # Sprawdź czy nie mamy za dużo pozycji
        open_positions = self.engine_pt.get_open_positions()
        if len(open_positions) >= self.max_positions:
            logger.warning(f"Maksymalna liczba pozycji ({self.max_positions}) - ignoruję sygnał BUY")
            return False
        
        # Sprawdź czy nie mamy już pozycji na tym symbolu
        symbol_positions = [p for p in open_positions if p.symbol == signal.symbol]
        if symbol_positions:
            logger.warning(f"Już mamy otwartą pozycję na {signal.symbol} - ignoruję")
            return False
        
        # Oblicz rozmiar pozycji
        if self.position_size_config:
            # Stały rozmiar pozycji (np. 1 BTC)
            symbol_base = signal.symbol.split("-")[0]  # BTC z BTC-USD
            if symbol_base == self.position_size_config['symbol']:
                size = self.position_size_config['size']
                logger.info(f"Używam stałego rozmiaru pozycji: {size} {symbol_base}")
            else:
                # Dla innych symboli użyj procentu
                account = self.engine_pt.get_account_summary()
                capital_to_use = account['current_balance'] * (self.position_size_percent / 100)
                size = capital_to_use / signal.price
        else:
            # Procent kapitału
            account = self.engine_pt.get_account_summary()
            capital_to_use = account['current_balance'] * (self.position_size_percent / 100)
            size = capital_to_use / signal.price
        
        # Otwórz pozycję
        position = self.engine_pt.open_position(
            symbol=signal.symbol,
            side="long",
            size=size,
            leverage=self.default_leverage,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            strategy=signal.strategy,
            notes=signal.reason
        )
        
        if position:
            logger.success(f"✅ Otwarto pozycję na sygnał: {signal}")
            return True
        
        return False
    
    def _handle_sell_signal(self, signal: TradingSignal) -> bool:
        """Obsługuje sygnał sprzedaży (SHORT)."""
        # Sprawdź czy nie mamy za dużo pozycji
        open_positions = self.engine_pt.get_open_positions()
        if len(open_positions) >= self.max_positions:
            logger.warning(f"Maksymalna liczba pozycji ({self.max_positions}) - ignoruję sygnał SELL")
            return False
        
        # Sprawdź czy nie mamy już pozycji na tym symbolu
        symbol_positions = [p for p in open_positions if p.symbol == signal.symbol]
        if symbol_positions:
            logger.warning(f"Już mamy otwartą pozycję na {signal.symbol} - ignoruję")
            return False
        
        # Oblicz rozmiar pozycji
        if self.position_size_config:
            # Stały rozmiar pozycji (np. 1 BTC)
            symbol_base = signal.symbol.split("-")[0]  # BTC z BTC-USD
            if symbol_base == self.position_size_config['symbol']:
                size = self.position_size_config['size']
                logger.info(f"Używam stałego rozmiaru pozycji: {size} {symbol_base}")
            else:
                # Dla innych symboli użyj procentu
                account = self.engine_pt.get_account_summary()
                capital_to_use = account['current_balance'] * (self.position_size_percent / 100)
                size = capital_to_use / signal.price
        else:
            # Procent kapitału
            account = self.engine_pt.get_account_summary()
            capital_to_use = account['current_balance'] * (self.position_size_percent / 100)
            size = capital_to_use / signal.price
        
        # Otwórz pozycję SHORT
        position = self.engine_pt.open_position(
            symbol=signal.symbol,
            side="short",
            size=size,
            leverage=self.default_leverage,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            strategy=signal.strategy,
            notes=signal.reason
        )
        
        if position:
            logger.success(f"✅ Otwarto pozycję SHORT na sygnał: {signal}")
            return True
        
        return False
    
    def _handle_close_signal(self, signal: TradingSignal) -> bool:
        """Obsługuje sygnał zamknięcia."""
        closed_any = False
        
        for position in self.engine_pt.get_open_positions(signal.symbol or None):
            trade = self.engine_pt.close_position(
                position.id,
                exit_reason="strategy_signal",
                notes=signal.reason
            )
            if trade:
                closed_any = True
        
        return closed_any
    
    def check_positions_for_exit(self):
        """Sprawdza otwarte pozycje pod kątem sygnałów wyjścia."""
        for position in self.engine_pt.get_open_positions():
            # Pobierz aktualne dane
            df = self.get_market_data(position.symbol, limit=20)
            if df is None or df.empty:
                continue
            
            current_price = df['close'].iloc[-1]
            pnl, pnl_percent = position.calculate_pnl(current_price)
            
            # Sprawdź strategię pod kątem wyjścia
            side = "long" if position.side == OrderSide.LONG else "short"
            exit_signal = self.strategy.should_close_position(
                df=df,
                entry_price=position.entry_price,
                side=side,
                current_pnl_percent=pnl_percent
            )
            
            if exit_signal:
                exit_signal.symbol = position.symbol
                logger.info(f"📊 Sygnał wyjścia dla {position.symbol}: {exit_signal.reason}")
                self.engine_pt.close_position(
                    position.id,
                    exit_reason="consolidation",
                    notes=exit_signal.reason
                )
    
    def run_cycle(self):
        """Wykonuje jeden cykl sprawdzania."""
        logger.debug("--- Rozpoczynam cykl sprawdzania ---")
        
        # 1. Sprawdź SL/TP dla otwartych pozycji
        closed_trades = self.engine_pt.check_stop_loss_take_profit()
        for trade in closed_trades:
            logger.info(f"🛑 Pozycja zamknięta przez SL/TP: {trade}")
        
        # 2. Sprawdź pozycje pod kątem strategii wyjścia
        self.check_positions_for_exit()
        
        # 3. Szukaj nowych okazji
        for symbol in self.symbols:
            df = self.get_market_data(symbol, limit=50)
            if df is None or df.empty:
                logger.warning(f"⚠️  Brak danych dla {symbol} - pomijam")
                continue
            
            # Dla PromptStrategy: aktualizuj historię cen
            if hasattr(self.strategy, 'update_price_history'):
                self.strategy.update_price_history(symbol, df)
            
            # Loguj analizę strategii
            timeframe = getattr(self.strategy, 'timeframe', '1h')
            logger.debug(f"📊 Analizuję {symbol} (strategia: {self.strategy.name}, timeframe: {timeframe}, dane: {len(df)} świec)")
            
            signal = self.strategy.analyze(df, symbol)
            
            if signal:
                logger.info(f"🎯 [{self.strategy.name}] Sygnał dla {symbol}: {signal}")
                logger.info(f"   Powód: {signal.reason}")
                self.process_signal(signal)
            else:
                logger.debug(f"   [{self.strategy.name}] Brak sygnału dla {symbol}")
        
        # 4. Pokaż podsumowanie
        summary = self.engine_pt.get_account_summary()
        logger.info(
            f"💰 Konto: ${summary['equity']:.2f} | "
            f"PnL: ${summary['total_pnl']:.2f} | "
            f"Pozycje: {summary['open_positions']}"
        )
        
        # 5. Pokaż statystyki API LLM (jeśli używane)
        try:
            from src.utils.api_logger import get_api_logger
            api_logger = get_api_logger()
            api_logger.print_session_stats()
        except Exception:
            pass  # Ignoruj błędy jeśli API logger nie jest dostępny
    
    def start(self, daemon: bool = False):
        """
        Uruchamia bota.
        
        Args:
            daemon: Czy uruchomić jako daemon (w tle)
        """
        self.running = True
        self._stop_event.clear()
        
        logger.info("🚀 Uruchamiam Trading Bot...")
        
        # Utwórz TradingSession (tylko jeśli nie istnieje)
        if not self.trading_session:
            self._create_trading_session()
        
        # Pokaż początkowe podsumowanie
        summary = self.engine_pt.get_account_summary()
        logger.info(f"📊 Stan początkowy: ${summary['current_balance']:.2f}")
        
        if daemon:
            thread = Thread(target=self._run_loop, daemon=True)
            thread.start()
            return thread
        else:
            self._run_loop()
    
    def _create_trading_session(self):
        """Tworzy sesję tradingową w bazie danych."""
        try:
            from src.trading.models_extended import TradingSession, Strategy
            from datetime import datetime, timezone
            
            # Pobierz strategię z bazy
            strategy = self.session.query(Strategy).filter_by(
                name=self.strategy.name.lower().replace(" ", "_")
            ).first()
            
            # Utwórz unikalne session_id
            session_id = f"{self.engine_pt.account_name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            
            summary = self.engine_pt.get_account_summary()
            
            trading_session = TradingSession(
                session_id=session_id,
                account_id=self.engine_pt.account.id,
                strategy_id=strategy.id if strategy else None,
                mode="paper",
                symbols=self.symbols,
                started_at=datetime.now(timezone.utc),
                time_limit_seconds=None,  # Będzie ustawione w EnhancedTradingBot
                max_loss_limit=None,  # Będzie ustawione w EnhancedTradingBot
                max_positions=self.max_positions,
                starting_balance=summary['current_balance'],
                peak_balance=summary['current_balance']
            )
            
            self.session.add(trading_session)
            self.session.commit()
            self.trading_session = trading_session
            
            logger.info(f"📝 Utworzono TradingSession: {session_id}")
        except Exception as e:
            logger.warning(f"Nie udało się utworzyć TradingSession: {e}")
            self.trading_session = None
    
    def _run_loop(self):
        """Główna pętla bota."""
        try:
            while self.running and not self._stop_event.is_set():
                try:
                    self.run_cycle()
                except Exception as e:
                    logger.error(f"Błąd w cyklu: {e}")
                
                # Czekaj na następny cykl
                self._stop_event.wait(self.check_interval)
        except KeyboardInterrupt:
            logger.info("Przerwano przez użytkownika")
        finally:
            self.stop()
    
    def stop(self):
        """Zatrzymuje bota."""
        logger.info("🛑 Zatrzymuję Trading Bot...")
        self.running = False
        self._stop_event.set()
        
        # Zamknij TradingSession
        self._close_trading_session()
        
        # Pokaż końcowe podsumowanie
        summary = self.engine_pt.get_account_summary()
        stats = self.engine_pt.get_performance_stats()
        
        logger.info("=" * 50)
        logger.info("📊 PODSUMOWANIE KOŃCOWE")
        logger.info("=" * 50)
        logger.info(f"Saldo końcowe: ${summary['equity']:.2f}")
        logger.info(f"Całkowity PnL: ${summary['total_pnl']:.2f}")
        logger.info(f"ROI: {summary['roi']:.2f}%")
        logger.info(f"Liczba transakcji: {stats['total_trades']}")
        logger.info(f"Win rate: {stats['win_rate']:.1f}%")
        logger.info(f"Max drawdown: {summary['max_drawdown']:.2f}%")
    
    def _close_trading_session(self):
        """Zamyka sesję tradingową w bazie danych."""
        if not self.trading_session:
            return
        
        try:
            from datetime import datetime, timezone
            
            # Odśwież sesję z bazy
            self.trading_session = self.session.query(type(self.trading_session)).filter_by(
                id=self.trading_session.id
            ).first()
            
            if not self.trading_session:
                return
            
            summary = self.engine_pt.get_account_summary()
            stats = self.engine_pt.get_performance_stats()
            
            # Upewnij się, że started_at jest timezone-aware
            started_at = self.trading_session.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            
            duration = (datetime.now(timezone.utc) - started_at).total_seconds()
            
            self.trading_session.ended_at = datetime.now(timezone.utc)
            self.trading_session.duration_seconds = int(duration)
            self.trading_session.ending_balance = summary['equity']
            self.trading_session.peak_balance = summary.get('peak_balance', summary['equity'])
            self.trading_session.max_drawdown = summary['max_drawdown']
            self.trading_session.total_trades = stats.get('total_trades', 0)
            self.trading_session.winning_trades = stats.get('winning_trades', 0)
            self.trading_session.losing_trades = stats.get('losing_trades', 0)
            self.trading_session.total_pnl = summary['total_pnl']
            self.trading_session.end_reason = "manual"
            
            self.session.commit()
            logger.info(f"📝 Zamknięto TradingSession: {self.trading_session.session_id}")
        except Exception as e:
            logger.warning(f"Nie udało się zamknąć TradingSession: {e}")
        logger.info("=" * 50)


def main():
    """Główna funkcja uruchamiająca bota."""
    import os
    
    # Konfiguracja logowania
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )
    logger.add(
        "logs/trading_bot_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="7 days",
        level="DEBUG"
    )
    
    # Utwórz katalogi
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # Konfiguracja bota
    bot = TradingBot(
        database_url="sqlite:///data/paper_trading.db",
        account_name="piotrek_bot",
        initial_balance=10000.0,
        symbols=["BTC-USD", "ETH-USD"],
        strategy=PiotrekBreakoutStrategy({
            'breakout_threshold': 0.8,
            'consolidation_threshold': 0.4,
            'min_confidence': 5,
            'risk_reward_ratio': 2.0
        }),
        check_interval=300  # 5 minut
    )
    
    # Obsługa SIGINT (Ctrl+C)
    def signal_handler(sig, frame):
        bot.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Uruchom
    try:
        bot.start()
    except KeyboardInterrupt:
        bot.stop()


if __name__ == "__main__":
    main()

