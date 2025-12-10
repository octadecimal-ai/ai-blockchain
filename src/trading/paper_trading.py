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
        dydx_collector: Optional[DydxCollector] = None
    ):
        """
        Inicjalizacja silnika.
        
        Args:
            session: Sesja SQLAlchemy
            account_name: Nazwa konta paper trading
            dydx_collector: Kolektor dYdX (opcjonalnie, do pobierania cen)
        """
        self.session = session
        self.account_name = account_name
        self.dydx = dydx_collector or DydxCollector(testnet=False)
        
        # Pobierz lub utwórz konto
        self.account = self._get_or_create_account(account_name)
        
        logger.info(f"Paper Trading Engine zainicjalizowany: {self.account}")
    
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
        ticker = self.dydx.get_ticker(symbol)
        return ticker.get('oracle_price', 0.0)
    
    def get_account_summary(self) -> Dict[str, Any]:
        """Zwraca podsumowanie konta."""
        # Oblicz unrealized PnL dla otwartych pozycji
        open_positions = self.get_open_positions()
        total_unrealized_pnl = 0.0
        
        for pos in open_positions:
            current_price = self.get_current_price(pos.symbol)
            pnl, _ = pos.calculate_pnl(current_price)
            total_unrealized_pnl += pnl
        
        equity = self.account.current_balance + total_unrealized_pnl
        
        return {
            'account_name': self.account.name,
            'initial_balance': self.account.initial_balance,
            'current_balance': self.account.current_balance,
            'unrealized_pnl': total_unrealized_pnl,
            'equity': equity,
            'total_pnl': self.account.total_pnl,
            'roi': self.account.roi,
            'total_trades': self.account.total_trades,
            'win_rate': self.account.win_rate,
            'max_drawdown': self.account.max_drawdown,
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
        
        # Oblicz wymagany margin
        position_value = size * current_price
        required_margin = position_value / leverage
        
        # Opłata za wejście
        entry_fee = position_value * self.account.taker_fee
        total_required = required_margin + entry_fee
        
        # Sprawdź dostępne środki
        if total_required > self.account.current_balance:
            logger.warning(
                f"Niewystarczające środki: potrzeba ${total_required:.2f}, "
                f"dostępne ${self.account.current_balance:.2f}"
            )
            return None
        
        # Konwersja strony
        order_side = OrderSide.LONG if side.lower() == "long" else OrderSide.SHORT
        
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
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=strategy,
            notes=notes
        )
        
        # Zaktualizuj saldo konta (zablokuj margin + opłata)
        self.account.current_balance -= total_required
        
        self.session.add(position)
        self.session.commit()
        
        logger.success(
            f"Otwarto pozycję {order_side.value.upper()} {symbol}: "
            f"{size} @ ${current_price:.2f} (margin: ${required_margin:.2f}, fee: ${entry_fee:.2f})"
        )
        
        return position
    
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
        
        # Oblicz PnL
        pnl, pnl_percent = position.calculate_pnl(current_price)
        
        # Opłaty
        position_value = position.size * current_price
        exit_fee = position_value * self.account.taker_fee
        entry_fee = position.size * position.entry_price * self.account.taker_fee
        total_fees = entry_fee + exit_fee
        net_pnl = pnl - total_fees
        
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
            exit_price=current_price,
            exit_time=utcnow(),
            entry_fee=entry_fee,
            exit_fee=exit_fee,
            total_fees=total_fees,
            pnl=pnl,
            pnl_percent=pnl_percent,
            net_pnl=net_pnl,
            strategy=position.strategy,
            exit_reason=exit_reason,
            notes=notes
        )
        
        # Zaktualizuj saldo konta
        # Zwróć margin + dodaj/odejmij PnL (już po opłatach za wejście odciągniętych)
        self.account.current_balance += position.margin_used + pnl - exit_fee
        
        # Aktualizuj statystyki
        self.account.total_trades += 1
        self.account.total_pnl += net_pnl
        
        if net_pnl > 0:
            self.account.winning_trades += 1
        else:
            self.account.losing_trades += 1
        
        # Aktualizuj peak i drawdown
        if self.account.current_balance > (self.account.peak_balance or 0):
            self.account.peak_balance = self.account.current_balance
        else:
            drawdown = ((self.account.peak_balance - self.account.current_balance) 
                       / self.account.peak_balance) * 100
            if drawdown > self.account.max_drawdown:
                self.account.max_drawdown = drawdown
        
        self.session.add(trade)
        self.session.commit()
        
        emoji = "🟢" if net_pnl > 0 else "🔴"
        logger.success(
            f"{emoji} Zamknięto pozycję {position.symbol}: "
            f"PnL ${net_pnl:.2f} ({pnl_percent:.2f}%) | "
            f"Powód: {exit_reason}"
        )
        
        return trade
    
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

