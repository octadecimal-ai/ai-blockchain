"""
Paper Trading Engine
====================
Silnik do symulacji handlu na dYdX bez prawdziwych pieniędzy.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from decimal import Decimal
from loguru import logger

from sqlalchemy.orm import Session

from src.trading.models import (
    PaperAccount, PaperPosition, PaperOrder, PaperTrade,
    OrderSide, OrderType, OrderStatus, PositionStatus
)
from src.collectors.exchange.dydx_collector import DydxCollector
from src.utils.sound_notifier import get_sound_notifier


def utcnow():
    """Zwraca aktualny czas UTC."""
    return datetime.now(timezone.utc)


class PaperTradingEngine:
    """
    Silnik paper trading dla dYdX.
    
    Obsługuje:
    - Tworzenie i zarządzanie wirtualnym kontem
    - Otwieranie i zamykanie pozycji
    - Obliczanie PnL
    - Stop Loss / Take Profit
    - Tracking historii transakcji
    """
    
    def __init__(
        self,
        session: Session,
        account_name: str = "default",
        dydx_collector: Optional[DydxCollector] = None,
        slippage_percent: float = 0.75
    ):
        """
        Inicjalizacja silnika.
        
        Args:
            session: Sesja SQLAlchemy
            account_name: Nazwa konta paper trading
            dydx_collector: Kolektor dYdX (opcjonalnie, do pobierania cen)
            slippage_percent: Procent slippage przy zamykaniu pozycji (default 0.75%)
        """
        self.session = session
        self.account_name = account_name
        self.dydx = dydx_collector or DydxCollector(testnet=False)
        self.slippage_percent = slippage_percent
        
        # Pobierz lub utwórz konto
        self.account = self._get_or_create_account(account_name)
        
        logger.info(f"Paper Trading Engine zainicjalizowany: {self.account} (slippage: {slippage_percent}%)")
    
    def _get_or_create_account(
        self,
        name: str,
        initial_balance: float = 10000.0,
        leverage: float = 1.0
    ) -> PaperAccount:
        """Pobiera lub tworzy konto paper trading."""
        account = self.session.query(PaperAccount).filter_by(name=name).first()
        
        if not account:
            account = PaperAccount(
                name=name,
                initial_balance=initial_balance,
                current_balance=initial_balance,
                leverage=leverage,
                peak_balance=initial_balance
            )
            self.session.add(account)
            self.session.commit()
            logger.info(f"Utworzono nowe konto paper trading: {name} (${initial_balance})")
        
        return account
    
    def get_current_price(self, symbol: str = "BTC-USD") -> float:
        """Pobiera aktualną cenę z dYdX."""
        try:
            ticker = self.dydx.get_ticker(symbol)
            price = ticker.get('oracle_price', 0.0) if ticker else 0.0
            # Konwertuj numpy types na standardowy Python float
            if hasattr(price, 'item'):  # numpy scalar
                return float(price.item())
            return float(price)
        except Exception as e:
            logger.warning(f"Błąd pobierania ceny dla {symbol}: {e}")
            return 0.0
    
    def get_account_summary(self) -> Dict[str, Any]:
        """Zwraca podsumowanie konta."""
        # Oblicz unrealized PnL dla otwartych pozycji
        open_positions = self.get_open_positions()
        total_unrealized_pnl = 0.0
        
        for pos in open_positions:
            current_price = self.get_current_price(pos.symbol)
            pnl, _ = pos.calculate_pnl(current_price)
            total_unrealized_pnl += float(pnl)  # Konwertuj na float
        
        equity = float(self.account.current_balance) + float(total_unrealized_pnl)
        
        return {
            'account_name': self.account.name,
            'initial_balance': self.account.initial_balance,
            'current_balance': float(self.account.current_balance),
            'unrealized_pnl': total_unrealized_pnl,
            'equity': equity,
            'total_pnl': float(self.account.total_pnl or 0),
            'roi': self.account.roi,
            'total_trades': self.account.total_trades,
            'win_rate': self.account.win_rate,
            'max_drawdown': float(self.account.max_drawdown or 0),
            'open_positions': len(open_positions)
        }
    
    def get_open_positions(self, symbol: Optional[str] = None) -> List[PaperPosition]:
        """Pobiera otwarte pozycje."""
        query = self.session.query(PaperPosition).filter(
            PaperPosition.account_id == self.account.id,
            PaperPosition.status == PositionStatus.OPEN
        )
        
        if symbol:
            query = query.filter(PaperPosition.symbol == symbol)
        
        return query.all()
    
    def open_position(
        self,
        symbol: str,
        side: str,  # "long" lub "short"
        size: float,
        leverage: float = 1.0,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        strategy: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[PaperPosition]:
        """
        Otwiera nową pozycję.
        
        Args:
            symbol: Symbol (np. "BTC-USD")
            side: "long" lub "short"
            size: Rozmiar pozycji w jednostkach bazowych (np. 0.1 BTC)
            leverage: Dźwignia (1-20x)
            stop_loss: Cena stop loss
            take_profit: Cena take profit
            strategy: Nazwa strategii
            notes: Notatki
            
        Returns:
            PaperPosition lub None jeśli niewystarczające środki
        """
        # Pobierz aktualną cenę
        current_price = self.get_current_price(symbol)
        if current_price <= 0:
            logger.error(f"Nie można pobrać ceny dla {symbol}")
            return None
        
        # Konwertuj wszystkie wartości na standardowe Python types (nie numpy)
        current_price = float(current_price)
        size = float(size)
        leverage = float(leverage)
        
        # Oblicz wymagany margin
        position_value = float(size * current_price)
        required_margin = float(position_value / leverage)
        
        # Opłata za wejście
        entry_fee = float(position_value * self.account.taker_fee)
        total_required = float(required_margin + entry_fee)
        
        # Sprawdź dostępne środki
        current_balance = float(self.account.current_balance)
        if total_required > current_balance:
            logger.warning(
                f"Niewystarczające środki: potrzeba ${total_required:.2f}, "
                f"dostępne ${current_balance:.2f}"
            )
            return None
        
        # Konwersja strony
        order_side = OrderSide.LONG if side.lower() == "long" else OrderSide.SHORT
        
        # Konwertuj stop_loss i take_profit na float (mogą być numpy types)
        stop_loss_float = float(stop_loss) if stop_loss is not None else None
        take_profit_float = float(take_profit) if take_profit is not None else None
        
        # Utwórz pozycję
        position = PaperPosition(
            account_id=self.account.id,
            symbol=symbol,
            side=order_side,
            size=size,
            entry_price=current_price,
            current_price=current_price,
            leverage=leverage,
            margin_used=required_margin,
            stop_loss=stop_loss_float,
            take_profit=take_profit_float,
            strategy=strategy,
            notes=notes
        )
        
        # Zaktualizuj saldo konta (zablokuj margin + opłata)
        self.account.current_balance = float(self.account.current_balance) - float(total_required)
        
        self.session.add(position)
        self.session.commit()
        
        # Odtwórz dźwięk powiadomienia
        sound_notifier = get_sound_notifier()
        sound_notifier.notify_position_opened(symbol, side)
        
        # Utwórz TradeRegister (jeśli dostępny trading_session)
        self._create_trade_register_entry(
            position=position,
            entry_price=current_price,
            entry_size=size,
            entry_value_usd=position_value,
            margin_required=required_margin,
            margin_available_before=float(self.account.current_balance) + float(total_required),
            entry_fee=entry_fee,
            strategy_name=strategy,
            notes=notes
        )
        
        logger.success(
            f"Otwarto pozycję {order_side.value.upper()} {symbol}: "
            f"{size} @ ${current_price:.2f} (margin: ${required_margin:.2f}, fee: ${entry_fee:.2f})"
        )
        
        return position
    
    def _create_trade_register_entry(
        self,
        position: 'PaperPosition',
        entry_price: float,
        entry_size: float,
        entry_value_usd: float,
        margin_required: float,
        margin_available_before: float,
        entry_fee: float,
        strategy_name: Optional[str] = None,
        notes: Optional[str] = None
    ):
        """Tworzy wpis w TradeRegister przy otwieraniu pozycji."""
        logger.debug(f"🔍 Próba utworzenia TradeRegister dla {position.symbol} @ {entry_price}")
        try:
            from src.trading.models_extended import TradeRegister, Strategy, TradingSession
            logger.debug("✅ Import TradeRegister OK")
            
            # Pobierz strategię z bazy
            strategy = None
            if strategy_name:
                strategy = self.session.query(Strategy).filter_by(
                    name=strategy_name.lower().replace(" ", "_")
                ).first()
                logger.debug(f"Strategia: {strategy.name if strategy else 'nie znaleziona'}")
            
            # Pobierz aktywną sesję (jeśli istnieje)
            trading_session = self.session.query(TradingSession).filter_by(
                account_id=self.account.id,
                ended_at=None
            ).order_by(TradingSession.started_at.desc()).first()
            logger.debug(f"TradingSession: {trading_session.session_id if trading_session else 'nie znaleziona'}")
            
            # Utwórz TradeRegister
            logger.debug(f"Tworzenie TradeRegister: symbol={position.symbol}, side={position.side.value}")
            trade_register = TradeRegister(
                account_id=self.account.id,
                strategy_id=strategy.id if strategy else None,
                symbol=position.symbol,
                side=position.side.value,
                mode="paper",
                entry_timestamp=position.opened_at,
                entry_price=entry_price,
                entry_size=entry_size,
                entry_value_usd=entry_value_usd,
                leverage=position.leverage,
                margin_required=margin_required,
                margin_available_before=margin_available_before,
                stop_loss_price=position.stop_loss,
                take_profit_price=position.take_profit,
                fee_entry=entry_fee,
                signal_reason=notes,
                session_id=trading_session.session_id if trading_session else None,
                notes=notes
            )
            
            self.session.add(trade_register)
            self.session.commit()
            
            logger.debug(f"✅ Utworzono TradeRegister ID: {trade_register.id} dla pozycji {position.symbol}")
            
            # Zapisz ID TradeRegister w pozycji (dla późniejszego zaktualizowania)
            if position.notes:
                position.notes = f"{position.notes} | TradeRegisterID: {trade_register.id}"
            else:
                position.notes = f"TradeRegisterID: {trade_register.id}"
            self.session.commit()
            
        except Exception as e:
            import traceback
            logger.error(f"❌ Nie udało się utworzyć TradeRegister: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Nie przerywamy procesu - TradeRegister jest opcjonalny
    
    def close_position(
        self,
        position_id: int,
        exit_reason: str = "manual",
        notes: Optional[str] = None
    ) -> Optional[PaperTrade]:
        """
        Zamyka pozycję.
        
        Args:
            position_id: ID pozycji
            exit_reason: Powód zamknięcia (manual, stop_loss, take_profit, liquidation)
            notes: Notatki
            
        Returns:
            PaperTrade lub None
        """
        position = self.session.query(PaperPosition).filter_by(
            id=position_id,
            account_id=self.account.id,
            status=PositionStatus.OPEN
        ).first()
        
        if not position:
            logger.error(f"Nie znaleziono otwartej pozycji o ID {position_id}")
            return None
        
        # Pobierz aktualną cenę
        current_price = self.get_current_price(position.symbol)
        
        # Konwertuj wszystkie wartości na standardowe Python types (nie numpy)
        current_price = float(current_price)
        position_size = float(position.size)
        position_entry_price = float(position.entry_price)
        
        # Oblicz slippage (strata wynikająca z poślizgu ceny przy zamykaniu)
        position_value = float(position_size * current_price)
        slippage_amount = float(position_value * (self.slippage_percent / 100))
        
        # Dla LONG: slippage zmniejsza cenę wyjścia (sprzedajemy taniej)
        # Dla SHORT: slippage zwiększa cenę wyjścia (kupujemy drożej)
        if position.side == OrderSide.LONG:
            effective_exit_price = float(current_price * (1 - self.slippage_percent / 100))
        else:  # SHORT
            effective_exit_price = float(current_price * (1 + self.slippage_percent / 100))
        
        # Oblicz PnL z uwzględnieniem slippage
        pnl, pnl_percent = position.calculate_pnl(effective_exit_price)
        pnl = float(pnl)
        pnl_percent = float(pnl_percent)
        
        # Opłaty
        exit_fee = float(position_value * self.account.taker_fee)
        entry_fee = float(position_size * position_entry_price * self.account.taker_fee)
        total_fees = float(entry_fee + exit_fee)
        
        # Net PnL = PnL - opłaty - slippage
        net_pnl = float(pnl - total_fees - slippage_amount)
        
        logger.debug(
            f"Slippage dla {position.symbol}: {slippage_amount:.2f} USD "
            f"({self.slippage_percent}% z ${position_value:.2f})"
        )
        
        # Zamknij pozycję
        position.status = PositionStatus.CLOSED
        position.closed_at = utcnow()
        position.current_price = current_price
        position.unrealized_pnl = pnl
        position.unrealized_pnl_percent = pnl_percent
        
        # Utwórz rekord trade
        trade = PaperTrade(
            account_id=self.account.id,
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            entry_time=position.opened_at,
            size=position.size,
            leverage=position.leverage,
            exit_price=effective_exit_price,  # Użyj ceny z uwzględnieniem slippage
            exit_time=utcnow(),
            entry_fee=entry_fee,
            exit_fee=exit_fee,
            total_fees=total_fees,
            pnl=pnl,
            pnl_percent=pnl_percent,
            net_pnl=net_pnl,
            strategy=position.strategy,
            exit_reason=exit_reason,
            notes=f"{notes} | Slippage: {slippage_amount:.2f} USD" if notes else f"Slippage: {slippage_amount:.2f} USD"
        )
        
        # Zaktualizuj saldo konta
        # Zwróć margin + dodaj/odejmij PnL (już po opłatach za wejście odciągniętych)
        margin_used = float(position.margin_used)
        self.account.current_balance = float(self.account.current_balance) + float(margin_used) + float(pnl) - float(exit_fee)
        
        # Aktualizuj statystyki
        self.account.total_trades += 1
        self.account.total_pnl = float(self.account.total_pnl) + float(net_pnl)
        
        if net_pnl > 0:
            self.account.winning_trades += 1
        else:
            self.account.losing_trades += 1
        
        # Aktualizuj peak i drawdown
        current_balance = float(self.account.current_balance)
        peak_balance = float(self.account.peak_balance or 0)
        
        if current_balance > peak_balance:
            self.account.peak_balance = current_balance
        else:
            drawdown = float(((peak_balance - current_balance) / peak_balance) * 100) if peak_balance > 0 else 0.0
            max_drawdown = float(self.account.max_drawdown or 0)
            if drawdown > max_drawdown:
                self.account.max_drawdown = drawdown
        
        self.session.add(trade)
        self.session.commit()
        
        # Zaktualizuj TradeRegister (jeśli istnieje)
        self._update_trade_register_on_exit(
            position=position,
            trade=trade,
            exit_price=effective_exit_price,
            exit_reason=exit_reason,
            pnl_gross=pnl,
            pnl_net=net_pnl,
            pnl_percent=pnl_percent,
            exit_fee=exit_fee,
            slippage_amount=slippage_amount,
            notes=notes
        )
        
        emoji = "🟢" if net_pnl > 0 else "🔴"
        logger.success(
            f"{emoji} Zamknięto pozycję {position.symbol}: "
            f"PnL ${net_pnl:.2f} ({pnl_percent:.2f}%) | "
            f"Slippage: ${slippage_amount:.2f} | "
            f"Powód: {exit_reason}"
        )
        
        # Odtwórz dźwięk powiadomienia
        sound_notifier = get_sound_notifier()
        if net_pnl > 0:
            sound_notifier.notify_position_closed_profit(position.symbol, net_pnl)
        else:
            sound_notifier.notify_position_closed_loss(position.symbol, net_pnl)
        
        return trade
    
    def _update_trade_register_on_exit(
        self,
        position: 'PaperPosition',
        trade: 'PaperTrade',
        exit_price: float,
        exit_reason: str,
        pnl_gross: float,
        pnl_net: float,
        pnl_percent: float,
        exit_fee: float,
        slippage_amount: float,
        notes: Optional[str] = None
    ):
        """Aktualizuje TradeRegister przy zamykaniu pozycji."""
        try:
            from src.trading.models_extended import TradeRegister
            from datetime import datetime, timezone
            
            # Znajdź TradeRegister dla tej pozycji (po symbolu i czasie wejścia)
            trade_register = self.session.query(TradeRegister).filter_by(
                account_id=self.account.id,
                symbol=position.symbol,
                entry_timestamp=position.opened_at,
                exit_timestamp=None  # Tylko otwarte
            ).order_by(TradeRegister.created_at.desc()).first()
            
            if trade_register:
                # Oblicz czas trwania - upewnij się, że obie daty mają timezone
                exit_time = datetime.now(timezone.utc)
                entry_time = trade_register.entry_timestamp
                
                # Jeśli entry_timestamp nie ma timezone, dodaj UTC
                if entry_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=timezone.utc)
                
                duration = (exit_time - entry_time).total_seconds()
                
                # Zaktualizuj TradeRegister
                trade_register.paper_trade_id = trade.id
                trade_register.exit_timestamp = exit_time
                trade_register.exit_price = exit_price
                trade_register.exit_reason = exit_reason
                trade_register.pnl_gross = pnl_gross
                trade_register.pnl_net = pnl_net
                trade_register.pnl_percent = pnl_percent
                trade_register.fee_exit = exit_fee
                trade_register.fee_total = trade_register.fee_entry + exit_fee
                trade_register.duration_seconds = int(duration)
                trade_register.actual_exit_price = exit_price
                trade_register.exit_slippage_percent = (slippage_amount / (position.size * exit_price)) * 100 if position.size * exit_price > 0 else 0
                
                # Sprawdź czy SL/TP zostały uruchomione
                if exit_reason == "stop_loss":
                    trade_register.stop_loss_triggered = True
                elif exit_reason == "take_profit":
                    trade_register.take_profit_triggered = True
                
                if notes:
                    trade_register.notes = f"{trade_register.notes or ''} | {notes}".strip()
                
                self.session.commit()
                logger.debug(f"Zaktualizowano TradeRegister ID: {trade_register.id}")
            else:
                logger.debug(f"Nie znaleziono TradeRegister dla pozycji {position.symbol} @ {position.entry_price}")
                
        except Exception as e:
            logger.warning(f"Nie udało się zaktualizować TradeRegister: {e}")
            # Nie przerywamy procesu - TradeRegister jest opcjonalny
    
    def check_stop_loss_take_profit(self) -> List[PaperTrade]:
        """
        Sprawdza wszystkie otwarte pozycje pod kątem SL/TP.
        
        Returns:
            Lista zamkniętych transakcji
        """
        closed_trades = []
        open_positions = self.get_open_positions()
        
        for position in open_positions:
            current_price = self.get_current_price(position.symbol)
            
            # Sprawdź likwidację
            if position.is_liquidated(current_price):
                trade = self.close_position(
                    position.id,
                    exit_reason="liquidation",
                    notes=f"Likwidacja przy ${current_price:.2f}"
                )
                if trade:
                    closed_trades.append(trade)
                continue
            
            # Sprawdź Stop Loss
            if position.stop_loss:
                if position.side == OrderSide.LONG and current_price <= position.stop_loss:
                    trade = self.close_position(
                        position.id,
                        exit_reason="stop_loss",
                        notes=f"SL triggered @ ${current_price:.2f}"
                    )
                    if trade:
                        closed_trades.append(trade)
                    continue
                    
                if position.side == OrderSide.SHORT and current_price >= position.stop_loss:
                    trade = self.close_position(
                        position.id,
                        exit_reason="stop_loss",
                        notes=f"SL triggered @ ${current_price:.2f}"
                    )
                    if trade:
                        closed_trades.append(trade)
                    continue
            
            # Sprawdź Take Profit
            if position.take_profit:
                if position.side == OrderSide.LONG and current_price >= position.take_profit:
                    trade = self.close_position(
                        position.id,
                        exit_reason="take_profit",
                        notes=f"TP triggered @ ${current_price:.2f}"
                    )
                    if trade:
                        closed_trades.append(trade)
                    continue
                    
                if position.side == OrderSide.SHORT and current_price <= position.take_profit:
                    trade = self.close_position(
                        position.id,
                        exit_reason="take_profit",
                        notes=f"TP triggered @ ${current_price:.2f}"
                    )
                    if trade:
                        closed_trades.append(trade)
                    continue
            
            # Aktualizuj unrealized PnL
            pnl, pnl_percent = position.calculate_pnl(current_price)
            position.current_price = current_price
            position.unrealized_pnl = pnl
            position.unrealized_pnl_percent = pnl_percent
        
        self.session.commit()
        return closed_trades
    
    def get_trade_history(
        self,
        limit: int = 50,
        symbol: Optional[str] = None
    ) -> List[PaperTrade]:
        """Pobiera historię transakcji."""
        query = self.session.query(PaperTrade).filter(
            PaperTrade.account_id == self.account.id
        ).order_by(PaperTrade.exit_time.desc())
        
        if symbol:
            query = query.filter(PaperTrade.symbol == symbol)
        
        return query.limit(limit).all()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Oblicza statystyki wydajności."""
        trades = self.get_trade_history(limit=1000)
        
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'avg_trade_duration_minutes': 0,
                'best_trade': 0,
                'worst_trade': 0
            }
        
        wins = [t for t in trades if t.net_pnl > 0]
        losses = [t for t in trades if t.net_pnl <= 0]
        
        avg_win = sum(t.net_pnl for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.net_pnl for t in losses) / len(losses) if losses else 0
        
        total_wins = sum(t.net_pnl for t in wins)
        total_losses = abs(sum(t.net_pnl for t in losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        avg_duration = sum(t.duration_minutes for t in trades) / len(trades)
        
        return {
            'total_trades': len(trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': (len(wins) / len(trades)) * 100 if trades else 0,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'avg_trade_duration_minutes': avg_duration,
            'best_trade': max(t.net_pnl for t in trades) if trades else 0,
            'worst_trade': min(t.net_pnl for t in trades) if trades else 0,
            'total_pnl': sum(t.net_pnl for t in trades),
            'total_fees': sum(t.total_fees for t in trades)
        }
    
    def reset_account(self, initial_balance: float = 10000.0):
        """Resetuje konto do stanu początkowego."""
        # Zamknij wszystkie pozycje
        for position in self.get_open_positions():
            position.status = PositionStatus.CLOSED
            position.closed_at = utcnow()
        
        # Reset statystyk
        self.account.current_balance = initial_balance
        self.account.initial_balance = initial_balance
        self.account.total_trades = 0
        self.account.winning_trades = 0
        self.account.losing_trades = 0
        self.account.total_pnl = 0.0
        self.account.max_drawdown = 0.0
        self.account.peak_balance = initial_balance
        
        self.session.commit()
        logger.info(f"Konto {self.account.name} zresetowane do ${initial_balance}")

