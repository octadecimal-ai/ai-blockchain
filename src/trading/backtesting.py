"""
Backtesting Engine
==================
Silnik do testowania strategii na danych historycznych.
Pozwala szybko przetestować różne parametry strategii bez ryzyka.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from loguru import logger

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    # Fallback bez progress bar
    def tqdm(iterable, desc=""):
        return iterable

from src.trading.strategies.base_strategy import BaseStrategy, TradingSignal, SignalType
from src.collectors.exchange.dydx_collector import DydxCollector
from src.trading.models import OrderSide


@dataclass
class BacktestResult:
    """Wyniki backtestingu."""
    # Podstawowe statystyki
    initial_balance: float = 10000.0
    final_balance: float = 0.0
    total_pnl: float = 0.0
    total_return: float = 0.0  # %
    
    # Transakcje
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0  # %
    
    # Zyski/straty
    total_profit: float = 0.0
    total_loss: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    profit_factor: float = 0.0  # total_profit / abs(total_loss)
    
    # Drawdown
    max_drawdown: float = 0.0  # %
    max_drawdown_duration: int = 0  # dni
    
    # Sharpe Ratio
    sharpe_ratio: float = 0.0
    
    # Inne
    total_fees: float = 0.0
    average_trade_duration: float = 0.0  # sekundy
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # Szczegóły transakcji
    trades: List[Dict[str, Any]] = field(default_factory=list)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)
    
    def __repr__(self):
        return (
            f"BacktestResult("
            f"return={self.total_return:.2f}%, "
            f"trades={self.total_trades}, "
            f"win_rate={self.win_rate:.1f}%, "
            f"max_dd={self.max_drawdown:.2f}%)"
        )


class BacktestEngine:
    """
    Silnik backtestingu dla strategii tradingowych.
    
    Funkcje:
    - Testowanie strategii na danych historycznych
    - Symulacja transakcji z uwzględnieniem opłat i slippage
    - Generowanie szczegółowych statystyk
    - Szybkie przetwarzanie (rok w ~10 sekund)
    """
    
    def __init__(
        self,
        initial_balance: float = 10000.0,
        taker_fee: float = 0.0005,  # 0.05% dYdX
        maker_fee: float = 0.0,  # 0% dla maker
        slippage_percent: float = 0.1,  # 0.1% slippage
        leverage: float = 1.0
    ):
        """
        Inicjalizacja silnika backtestingu.
        
        Args:
            initial_balance: Początkowy kapitał
            taker_fee: Opłata taker (0.0005 = 0.05%)
            maker_fee: Opłata maker
            slippage_percent: Slippage w % (0.1 = 0.1%)
            leverage: Dźwignia (1.0 = brak dźwigni)
        """
        self.initial_balance = initial_balance
        self.taker_fee = taker_fee
        self.maker_fee = maker_fee
        self.slippage_percent = slippage_percent / 100  # Konwersja na ułamek
        self.leverage = leverage
        
        # Collector do pobierania danych
        self.dydx = DydxCollector(testnet=False)
        
        logger.info(f"BacktestEngine zainicjalizowany: balance=${initial_balance:.2f}, fee={taker_fee*100:.3f}%, slippage={slippage_percent:.2f}%")
    
    def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Pobiera dane historyczne z dYdX używając fetch_historical_candles.
        
        Args:
            symbol: Symbol pary (np. BTC-USD)
            timeframe: Timeframe (1m, 5m, 1h, 1d)
            start_date: Data początkowa
            end_date: Data końcowa
            
        Returns:
            DataFrame z danymi OHLCV
        """
        logger.info(f"Pobieram dane historyczne: {symbol} {timeframe} od {start_date.date()} do {end_date.date()}")
        
        # Użyj istniejącej metody fetch_historical_candles
        df = self.dydx.fetch_historical_candles(
            ticker=symbol,
            resolution=timeframe,
            start_date=start_date,
            end_date=end_date
        )
        
        if df.empty:
            logger.error(f"Nie udało się pobrać danych dla {symbol}")
            return pd.DataFrame()
        
        # Upewnij się, że mamy kolumnę timestamp
        if df.index.name == 'timestamp' or (hasattr(df.index, 'name') and df.index.name == 'timestamp'):
            df = df.reset_index()
        
        if 'timestamp' not in df.columns:
            if 'time' in df.columns:
                df['timestamp'] = pd.to_datetime(df['time'])
                df = df.drop('time', axis=1)
            elif df.index.dtype == 'datetime64[ns]':
                df['timestamp'] = df.index
            else:
                logger.error("Nie można znaleźć kolumny timestamp w danych")
                return pd.DataFrame()
        
        # Upewnij się, że timestamp jest datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Sortuj chronologicznie
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        logger.success(f"Pobrano {len(df)} świec dla {symbol}")
        return df
    
    def run_backtest(
        self,
        strategy: BaseStrategy,
        symbol: str,
        df: pd.DataFrame,
        position_size_percent: float = 10.0,
        max_positions: int = 1
    ) -> BacktestResult:
        """
        Uruchamia backtest strategii na danych historycznych.
        
        Args:
            strategy: Strategia do testowania
            symbol: Symbol pary
            df: DataFrame z danymi OHLCV (posortowane chronologicznie)
            position_size_percent: % kapitału na pozycję
            max_positions: Maksymalna liczba równoczesnych pozycji
            
        Returns:
            BacktestResult z wynikami
        """
        if df.empty or len(df) < 50:
            logger.error(f"Za mało danych: {len(df)} świec")
            return BacktestResult()
        
        # Logi tylko do pliku (jeśli logger jest skonfigurowany)
        logger.info(f"Uruchamiam backtest: {strategy.name} na {symbol} ({len(df)} świec)")
        
        # Stan symulacji
        balance = self.initial_balance
        equity = balance
        peak_equity = balance
        
        # Pozycje (symbol -> dict z danymi pozycji)
        open_positions: Dict[str, Dict[str, Any]] = {}
        
        # Statystyki
        trades = []
        equity_curve = [(df.iloc[0]['timestamp'] if 'timestamp' in df.columns else df.index[0], balance)]
        
        total_profit = 0.0
        total_loss = 0.0
        consecutive_wins = 0
        consecutive_losses = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        
        # Przetwarzaj każdą świecę (z progress barem)
        iterator = range(50, len(df))
        if TQDM_AVAILABLE:
            iterator = tqdm(iterator, desc="Backtesting")
        
        for i in iterator:
            current_candle = df.iloc[i]
            current_price = float(current_candle['close'])
            current_time = current_candle.get('timestamp', df.index[i])
            
            # Przygotuj DataFrame do analizy (ostatnie N świec)
            lookback = min(100, i + 1)
            df_window = df.iloc[max(0, i - lookback + 1):i + 1].copy()
            
            # 1. Sprawdź otwarte pozycje (SL/TP, exit signals)
            positions_to_close = []
            for pos_symbol, position in open_positions.items():
                if pos_symbol != symbol:
                    continue
                
                # Oblicz PnL
                entry_price = position['entry_price']
                side = position['side']
                
                if side == 'long':
                    pnl_percent = ((current_price - entry_price) / entry_price) * 100
                else:  # short
                    pnl_percent = ((entry_price - current_price) / entry_price) * 100
                
                # Sprawdź SL/TP
                should_close = False
                exit_reason = ""
                
                if position.get('stop_loss'):
                    if (side == 'long' and current_price <= position['stop_loss']) or \
                       (side == 'short' and current_price >= position['stop_loss']):
                        should_close = True
                        exit_reason = "stop_loss"
                
                if position.get('take_profit'):
                    if (side == 'long' and current_price >= position['take_profit']) or \
                       (side == 'short' and current_price <= position['take_profit']):
                        should_close = True
                        exit_reason = "take_profit"
                
                # Sprawdź strategię wyjścia
                if not should_close:
                    exit_signal = strategy.should_close_position(
                        df=df_window,
                        entry_price=entry_price,
                        side=side,
                        current_pnl_percent=pnl_percent
                    )
                    if exit_signal:
                        should_close = True
                        exit_reason = "strategy_signal"
                
                if should_close:
                    positions_to_close.append((pos_symbol, position, exit_reason))
            
            # Zamknij pozycje
            for pos_symbol, position, exit_reason in positions_to_close:
                entry_price = position['entry_price']
                entry_size = position['size']
                side = position['side']
                
                # Oblicz cenę wyjścia z slippage
                if side == 'long':
                    exit_price = current_price * (1 - self.slippage_percent)
                    pnl = (exit_price - entry_price) * entry_size
                else:  # short
                    exit_price = current_price * (1 + self.slippage_percent)
                    pnl = (entry_price - exit_price) * entry_size
                
                # Opłaty
                entry_fee = entry_price * entry_size * self.taker_fee
                exit_fee = exit_price * entry_size * self.taker_fee
                total_fees = entry_fee + exit_fee
                
                net_pnl = pnl - total_fees
                
                # Zwróć margin (który został odliczony przy otwarciu)
                margin = (entry_price * entry_size) / self.leverage
                
                # Aktualizuj balance: zwróć margin + net_pnl
                balance += margin + net_pnl
                equity = balance
                
                # Statystyki
                if net_pnl > 0:
                    total_profit += net_pnl
                    consecutive_wins += 1
                    consecutive_losses = 0
                    max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
                else:
                    total_loss += abs(net_pnl)
                    consecutive_losses += 1
                    consecutive_wins = 0
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                
                # Zapisz transakcję
                trade = {
                    'entry_time': position['entry_time'],
                    'exit_time': current_time,
                    'symbol': symbol,
                    'side': side,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'size': entry_size,
                    'pnl': net_pnl,
                    'pnl_percent': (net_pnl / (entry_price * entry_size)) * 100,
                    'fees': total_fees,
                    'exit_reason': exit_reason,
                    'duration_seconds': (current_time - position['entry_time']).total_seconds() if hasattr(current_time, 'total_seconds') else 0
                }
                trades.append(trade)
                
                # Usuń pozycję
                del open_positions[pos_symbol]
            
            # 2. Sprawdź nowe sygnały (tylko jeśli mamy miejsce)
            if len(open_positions) < max_positions:
                signal = strategy.analyze(df_window, symbol)
                
                if signal and signal.signal_type in [SignalType.BUY, SignalType.SELL]:
                    # Oblicz rozmiar pozycji
                    position_value = balance * (position_size_percent / 100)
                    size = position_value / current_price
                    
                    # Oblicz cenę wejścia z slippage
                    if signal.signal_type == SignalType.BUY:
                        entry_price = current_price * (1 + self.slippage_percent)
                        side = 'long'
                    else:  # SELL
                        entry_price = current_price * (1 - self.slippage_percent)
                        side = 'short'
                    
                    # Opłata wejścia
                    entry_fee = entry_price * size * self.taker_fee
                    
                    # Sprawdź czy mamy wystarczające środki
                    required = (entry_price * size) / self.leverage + entry_fee
                    if required <= balance:
                        # Otwórz pozycję
                        open_positions[symbol] = {
                            'entry_time': current_time,
                            'entry_price': entry_price,
                            'size': size,
                            'side': side,
                            'stop_loss': signal.stop_loss,
                            'take_profit': signal.take_profit,
                            'strategy': signal.strategy,
                            'confidence': signal.confidence
                        }
                        
                        # Odlicz margin i fee
                        balance -= required
            
            # Aktualizuj equity (z unrealized PnL)
            unrealized_pnl = 0.0
            for pos_symbol, position in open_positions.items():
                if pos_symbol == symbol:
                    entry_price = position['entry_price']
                    side = position['side']
                    
                    if side == 'long':
                        unrealized_pnl += (current_price - entry_price) * position['size']
                    else:
                        unrealized_pnl += (entry_price - current_price) * position['size']
            
            equity = balance + unrealized_pnl
            
            # Drawdown
            if equity > peak_equity:
                peak_equity = equity
            
            # Equity curve (co N świec, aby nie zapisywać każdej)
            if i % max(1, len(df) // 1000) == 0:  # Max 1000 punktów na wykres
                equity_curve.append((current_time, equity))
        
        # Zamknij wszystkie otwarte pozycje na końcu
        final_price = float(df.iloc[-1]['close'])
        final_time = df.iloc[-1].get('timestamp', df.index[-1])
        
        for pos_symbol, position in list(open_positions.items()):
            entry_price = position['entry_price']
            entry_size = position['size']
            side = position['side']
            
            if side == 'long':
                exit_price = final_price * (1 - self.slippage_percent)
                pnl = (exit_price - entry_price) * entry_size
            else:
                exit_price = final_price * (1 + self.slippage_percent)
                pnl = (entry_price - exit_price) * entry_size
            
            entry_fee = entry_price * entry_size * self.taker_fee
            exit_fee = exit_price * entry_size * self.taker_fee
            total_fees = entry_fee + exit_fee
            net_pnl = pnl - total_fees
            
            # Zwróć margin (który został odliczony przy otwarciu)
            margin = (entry_price * entry_size) / self.leverage
            
            # Aktualizuj balance: zwróć margin + net_pnl
            balance += margin + net_pnl
            
            if net_pnl > 0:
                total_profit += net_pnl
            else:
                total_loss += abs(net_pnl)
            
            entry_time = position['entry_time']
            if isinstance(entry_time, pd.Timestamp):
                entry_time = entry_time.to_pydatetime()
            if isinstance(final_time, pd.Timestamp):
                final_time_dt = final_time.to_pydatetime()
            else:
                final_time_dt = final_time
            
            duration_sec = 0
            if hasattr(final_time_dt, '__sub__'):
                try:
                    duration_sec = (final_time_dt - entry_time).total_seconds()
                except:
                    pass
            
            trades.append({
                'entry_time': entry_time,
                'exit_time': final_time_dt,
                'symbol': symbol,
                'side': side,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'size': entry_size,
                'pnl': net_pnl,
                'pnl_percent': (net_pnl / (entry_price * entry_size)) * 100 if entry_price * entry_size > 0 else 0,
                'fees': total_fees,
                'exit_reason': 'end_of_data',
                'duration_seconds': duration_sec,
                'strategy': position.get('strategy', strategy.name)
            })
        
        # Oblicz statystyki końcowe
        final_balance = balance
        total_pnl = final_balance - self.initial_balance
        total_return = (total_pnl / self.initial_balance) * 100
        
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]
        
        win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0.0
        
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0.0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0.0
        
        largest_win = max([t['pnl'] for t in trades], default=0.0)
        largest_loss = min([t['pnl'] for t in trades], default=0.0)
        
        profit_factor = total_profit / abs(total_loss) if total_loss > 0 else float('inf')
        
        # Oblicz max drawdown
        equity_values = [e[1] for e in equity_curve]
        if equity_values:
            peak = equity_values[0]
            max_dd = 0.0
            for eq in equity_values:
                if eq > peak:
                    peak = eq
                dd = ((peak - eq) / peak) * 100
                max_dd = max(max_dd, dd)
        else:
            max_dd = 0.0
        
        # Sharpe Ratio (uproszczony)
        if len(equity_curve) > 1:
            returns = np.diff([e[1] for e in equity_curve]) / [e[1] for e in equity_curve[:-1]]
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0.0
        else:
            sharpe = 0.0
        
        avg_duration = np.mean([t['duration_seconds'] for t in trades]) if trades else 0.0
        total_fees_sum = sum([t['fees'] for t in trades])
        
        result = BacktestResult(
            initial_balance=self.initial_balance,
            final_balance=final_balance,
            total_pnl=total_pnl,
            total_return=total_return,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            total_profit=total_profit,
            total_loss=total_loss,
            average_win=avg_win,
            average_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            profit_factor=profit_factor,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            total_fees=total_fees_sum,
            average_trade_duration=avg_duration,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
            trades=trades,
            equity_curve=equity_curve
        )
        
        logger.success(f"Backtest zakończony: {result}")
        return result
    
    def print_results(self, result: BacktestResult):
        """Wyświetla wyniki backtestingu w czytelnej formie."""
        print("\n" + "=" * 70)
        print("📊 WYNIKI BACKTESTINGU")
        print("=" * 70)
        strategy_name = 'N/A'
        if result.trades:
            strategy_name = result.trades[0].get('strategy', 'N/A')
        print(f"Strategia: {strategy_name}")
        print(f"Okres: {len(result.equity_curve)} świec")
        print()
        print("💰 FINANSE:")
        print(f"  Początkowy kapitał:  ${result.initial_balance:,.2f}")
        print(f"  Końcowy kapitał:      ${result.final_balance:,.2f}")
        print(f"  Całkowity PnL:        ${result.total_pnl:+,.2f}")
        print(f"  Zwrot:                {result.total_return:+.2f}%")
        print(f"  Opłaty:               ${result.total_fees:,.2f}")
        print()
        print("📈 TRANSAKCJE:")
        print(f"  Wszystkie:            {result.total_trades}")
        print(f"  Zyskowne:             {result.winning_trades} ({result.win_rate:.1f}%)")
        print(f"  Stratne:              {result.losing_trades}")
        print()
        print("💵 ZYSKI/STRATY:")
        print(f"  Całkowity zysk:       ${result.total_profit:,.2f}")
        print(f"  Całkowita strata:     ${result.total_loss:,.2f}")
        print(f"  Średni zysk:          ${result.average_win:,.2f}")
        print(f"  Średnia strata:       ${result.average_loss:,.2f}")
        print(f"  Najlepsza:            ${result.largest_win:+,.2f}")
        print(f"  Najgorsza:            ${result.largest_loss:+,.2f}")
        print(f"  Profit Factor:        {result.profit_factor:.2f}")
        print()
        print("📉 RYZYKO:")
        print(f"  Max Drawdown:         {result.max_drawdown:.2f}%")
        print(f"  Sharpe Ratio:         {result.sharpe_ratio:.2f}")
        print(f"  Max kolejne zyski:    {result.max_consecutive_wins}")
        print(f"  Max kolejne straty:   {result.max_consecutive_losses}")
        print()
        print("⏱️  CZAS:")
        print(f"  Średni czas pozycji:  {result.average_trade_duration/60:.1f} min")
        print()
        
        # Wyświetl szczegóły transakcji z datami
        if result.trades:
            print("📋 SZCZEGÓŁY TRANSAKCJI:")
            print("-" * 100)
            print(f"{'#':<4} {'Data wejścia':<20} {'Data wyjścia':<20} {'Side':<6} {'Entry $':>10} {'Exit $':>10} {'PnL':>12} {'PnL %':>8} {'Powód':<15}")
            print("-" * 100)
            
            for idx, trade in enumerate(result.trades, 1):
                # Formatuj daty
                entry_time = trade.get('entry_time')
                exit_time = trade.get('exit_time')
                
                # Konwertuj na datetime jeśli potrzeba
                if isinstance(entry_time, pd.Timestamp):
                    entry_time = entry_time.to_pydatetime()
                if isinstance(exit_time, pd.Timestamp):
                    exit_time = exit_time.to_pydatetime()
                
                # Formatuj datę i godzinę
                if hasattr(entry_time, 'strftime'):
                    entry_str = entry_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    entry_str = str(entry_time)[:19] if len(str(entry_time)) >= 19 else str(entry_time)
                
                if hasattr(exit_time, 'strftime'):
                    exit_str = exit_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    exit_str = str(exit_time)[:19] if len(str(exit_time)) >= 19 else str(exit_time)
                
                side = trade.get('side', 'N/A').upper()
                entry_price = trade.get('entry_price', 0.0)
                exit_price = trade.get('exit_price', 0.0)
                pnl = trade.get('pnl', 0.0)
                pnl_percent = trade.get('pnl_percent', 0.0)
                exit_reason = trade.get('exit_reason', 'N/A')
                
                # Formatuj PnL
                pnl_sign = "+" if pnl >= 0 else ""
                pnl_str = f"{pnl_sign}${pnl:,.2f}"
                pnl_pct_str = f"{pnl_sign}{pnl_percent:.2f}%"
                
                print(f"{idx:<4} {entry_str:<20} {exit_str:<20} {side:<6} ${entry_price:>9,.2f} ${exit_price:>9,.2f} {pnl_str:>12} {pnl_pct_str:>8} {exit_reason:<15}")
            
            print("-" * 100)
            print()
        
        print("=" * 70)

