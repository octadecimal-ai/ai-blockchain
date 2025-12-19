#!/usr/bin/env python3
"""
Strategy Optimization Script
============================
Skrypt do optymalizacji parametrów strategii tradingowych.
Testuje różne kombinacje parametrów i znajduje najlepsze ustawienia.
"""

import os
import sys
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from itertools import product
from typing import Dict, List, Any, Tuple
from dotenv import load_dotenv

# Dodaj ścieżkę projektu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Załaduj .env jeśli istnieje
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

from loguru import logger
from src.trading.backtesting import BacktestEngine, BacktestResult
from src.trading.strategies.piotrek_strategy import PiotrekBreakoutStrategy
from src.trading.strategies.scalping_strategy import ScalpingStrategy


def setup_logging(verbose: bool = False):
    """Konfiguruje logowanie."""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level=level,
        colorize=True
    )


# Definicje parametrów do testowania dla każdej strategii
SCALPING_PARAMS = {
    'min_confidence': [2.0, 3.0, 4.0, 5.0, 6.0],
    'rsi_oversold': [20, 25, 30, 35, 40],
    'rsi_overbought': [60, 65, 70, 75, 80],
    'atr_multiplier': [1.0, 1.5, 2.0, 2.5],
    'min_volume_ratio': [1.0, 1.2, 1.5, 2.0],
}

BREAKOUT_PARAMS = {
    'min_confidence': [3.0, 4.0, 5.0, 6.0, 7.0],
    'breakout_threshold': [0.3, 0.5, 0.8, 1.0, 1.5],
    'consolidation_threshold': [0.2, 0.3, 0.4, 0.5],
    'rsi_oversold': [25, 30, 35, 40],
    'rsi_overbought': [60, 65, 70, 75],
}


def generate_param_combinations(params_dict: Dict[str, List[Any]], max_combinations: int = None) -> List[Dict[str, Any]]:
    """
    Generuje wszystkie kombinacje parametrów.
    
    Args:
        params_dict: Słownik z listami wartości parametrów
        max_combinations: Maksymalna liczba kombinacji (None = wszystkie)
        
    Returns:
        Lista słowników z kombinacjami parametrów
    """
    keys = list(params_dict.keys())
    values = [params_dict[key] for key in keys]
    
    all_combinations = list(product(*values))
    
    if max_combinations and len(all_combinations) > max_combinations:
        # Losowo wybierz kombinacje
        import random
        random.shuffle(all_combinations)
        all_combinations = all_combinations[:max_combinations]
    
    result = []
    for combo in all_combinations:
        result.append(dict(zip(keys, combo)))
    
    return result


def run_backtest_for_params(
    engine: BacktestEngine,
    strategy_class,
    strategy_name: str,
    params: Dict[str, Any],
    symbol: str,
    df,
    position_size_percent: float = 10.0
) -> Tuple[Dict[str, Any], BacktestResult]:
    """
    Uruchamia backtest dla danej kombinacji parametrów.
    
    Returns:
        Tuple (params_dict, BacktestResult)
    """
    # Utwórz strategię z parametrami
    strategy = strategy_class(params)
    
    # Uruchom backtest
    result = engine.run_backtest(
        strategy=strategy,
        symbol=symbol,
        df=df,
        position_size_percent=position_size_percent,
        max_positions=1
    )
    
    return params, result


def optimize_strategy(
    strategy_name: str,
    symbol: str,
    days: int,
    max_combinations: int = None,
    position_size_percent: float = 10.0,
    verbose: bool = False
) -> List[Tuple[Dict[str, Any], BacktestResult]]:
    """
    Optymalizuje strategię testując różne kombinacje parametrów.
    
    Returns:
        Lista tupli (params, result) posortowana po total_return (malejąco)
    """
    logger.info(f"🔍 Optymalizacja strategii: {strategy_name}")
    
    # Wybierz parametry do testowania
    if strategy_name == "scalping_strategy":
        params_dict = SCALPING_PARAMS
        strategy_class = ScalpingStrategy
        default_params = {
            'timeframe': '1min',
            'min_price_change': 0.1,
            'max_price_change': 0.5,
            'rsi_period': 7,
            'macd_fast': 8,
            'macd_slow': 21,
            'macd_signal': 5,
            'atr_period': 7,
            'atr_take_profit': 2.0,
            'volume_period': 10,
            'max_hold_seconds': 300,
            'min_hold_seconds': 30,
            'risk_reward_ratio': 1.5,
            'slippage_percent': 0.1,
        }
    else:  # piotrek_breakout_strategy
        params_dict = BREAKOUT_PARAMS
        strategy_class = PiotrekBreakoutStrategy
        default_params = {
            'timeframe': '1h',
            'risk_reward_ratio': 2.0,
            'lookback_period': 20,
            'consolidation_candles': 3,
            'use_rsi': True,
            'rsi_period': 14,
            'rsi_momentum_threshold': 5.0,
            'max_loss_usd': 500,
            'min_profit_target_usd': 500,
            'max_profit_target_usd': 2000,
            'slippage_percent': 0.75,
            'account_for_slippage': True,
        }
    
    # Generuj kombinacje parametrów
    combinations = generate_param_combinations(params_dict, max_combinations)
    logger.info(f"📊 Wygenerowano {len(combinations)} kombinacji parametrów do testowania")
    
    # Pobierz dane historyczne
    engine = BacktestEngine(initial_balance=10000.0)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    timeframe = default_params.get('timeframe', '1h')
    logger.info(f"📥 Pobieram dane historyczne: {symbol} {timeframe} ({days} dni)...")
    
    df = engine.fetch_historical_data(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date
    )
    
    if df.empty:
        logger.error("❌ Nie udało się pobrać danych historycznych")
        return []
    
    logger.info(f"✅ Pobrano {len(df)} świec")
    
    # Testuj każdą kombinację
    results = []
    total = len(combinations)
    
    for i, params_combo in enumerate(combinations, 1):
        # Połącz z domyślnymi parametrami
        full_params = {**default_params, **params_combo}
        
        if verbose:
            logger.info(f"[{i}/{total}] Testuję: {params_combo}")
        else:
            if i % 10 == 0 or i == 1:
                logger.info(f"Postęp: {i}/{total} ({i/total*100:.1f}%)")
        
        try:
            params, result = run_backtest_for_params(
                engine=engine,
                strategy_class=strategy_class,
                strategy_name=strategy_name,
                params=full_params,
                symbol=symbol,
                df=df,
                position_size_percent=position_size_percent
            )
            
            results.append((params_combo, result))
            
            if verbose:
                logger.info(f"  → Zwrot: {result.total_return:.2f}%, Trades: {result.total_trades}, Win Rate: {result.win_rate:.1f}%")
        
        except Exception as e:
            logger.warning(f"  ❌ Błąd dla {params_combo}: {e}")
            continue
    
    # Sortuj po total_return (malejąco)
    results.sort(key=lambda x: x[1].total_return, reverse=True)
    
    return results


def print_optimization_results(
    strategy_name: str,
    results: List[Tuple[Dict[str, Any], BacktestResult]],
    top_n: int = 10
):
    """Wyświetla najlepsze wyniki optymalizacji."""
    print("\n" + "=" * 80)
    print(f"🏆 TOP {top_n} KONFIGURACJI DLA: {strategy_name.upper()}")
    print("=" * 80)
    
    if not results:
        print("❌ Brak wyników do wyświetlenia")
        return
    
    for i, (params, result) in enumerate(results[:top_n], 1):
        print(f"\n📊 POZYCJA #{i}")
        print(f"   Zwrot: {result.total_return:+.2f}%")
        print(f"   PnL: ${result.total_pnl:+,.2f}")
        print(f"   Transakcje: {result.total_trades} (Win Rate: {result.win_rate:.1f}%)")
        print(f"   Profit Factor: {result.profit_factor:.2f}")
        print(f"   Max Drawdown: {result.max_drawdown:.2f}%")
        print(f"   Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print(f"   Parametry:")
        for key, value in sorted(params.items()):
            print(f"     - {key}: {value}")
    
    print("\n" + "=" * 80)
    print(f"📈 STATYSTYKI WSZYSTKICH {len(results)} TESTÓW:")
    print("=" * 80)
    
    returns = [r[1].total_return for r in results]
    trades = [r[1].total_trades for r in results]
    win_rates = [r[1].win_rate for r in results if r[1].total_trades > 0]
    
    print(f"   Średni zwrot: {sum(returns)/len(returns):.2f}%")
    print(f"   Najlepszy zwrot: {max(returns):.2f}%")
    print(f"   Najgorszy zwrot: {min(returns):.2f}%")
    print(f"   Średnia liczba transakcji: {sum(trades)/len(trades):.1f}")
    if win_rates:
        print(f"   Średni Win Rate: {sum(win_rates)/len(win_rates):.1f}%")
    
    # Zlicz zyskownych
    profitable = sum(1 for r in returns if r > 0)
    print(f"   Zyskownych konfiguracji: {profitable}/{len(results)} ({profitable/len(results)*100:.1f}%)")


def save_results_to_file(
    strategy_name: str,
    results: List[Tuple[Dict[str, Any], BacktestResult]],
    filename: str = None
):
    """Zapisuje wyniki do pliku JSON."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"optimization_{strategy_name}_{timestamp}.json"
    
    output_path = Path("data/optimization") / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        'strategy': strategy_name,
        'timestamp': datetime.now().isoformat(),
        'results': []
    }
    
    for params, result in results:
        data['results'].append({
            'params': params,
            'total_return': result.total_return,
            'total_pnl': result.total_pnl,
            'total_trades': result.total_trades,
            'win_rate': result.win_rate,
            'profit_factor': result.profit_factor,
            'max_drawdown': result.max_drawdown,
            'sharpe_ratio': result.sharpe_ratio,
            'total_profit': result.total_profit,
            'total_loss': result.total_loss,
        })
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.success(f"💾 Zapisano wyniki do: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Optymalizacja parametrów strategii tradingowych",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  # Optymalizacja scalping (wszystkie kombinacje)
  python scripts/optimize_strategy.py --strategy=scalping_strategy --symbol=BTC-USD --days=30

  # Optymalizacja breakout (max 100 kombinacji)
  python scripts/optimize_strategy.py --strategy=piotrek_breakout_strategy --symbol=BTC-USD --days=60 --max-combinations=100

  # Test obu strategii
  python scripts/optimize_strategy.py --strategy=all --symbol=BTC-USD --days=30
        """
    )
    
    parser.add_argument(
        "--strategy",
        default="all",
        choices=["scalping_strategy", "piotrek_breakout_strategy", "all"],
        help="Strategia do optymalizacji"
    )
    
    parser.add_argument(
        "--symbol",
        default="BTC-USD",
        help="Symbol pary (np. BTC-USD, ETH-USD)"
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Liczba dni danych historycznych (domyślnie: 30)"
    )
    
    parser.add_argument(
        "--max-combinations",
        type=int,
        help="Maksymalna liczba kombinacji do testowania (domyślnie: wszystkie)"
    )
    
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Liczba najlepszych wyników do wyświetlenia (domyślnie: 10)"
    )
    
    parser.add_argument(
        "--position-size",
        type=float,
        default=10.0,
        help="% kapitału na pozycję (domyślnie: 10%)"
    )
    
    parser.add_argument(
        "--save",
        action="store_true",
        help="Zapisz wyniki do pliku JSON"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Szczegółowe logi"
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    strategies_to_test = []
    if args.strategy == "all":
        strategies_to_test = ["scalping_strategy", "piotrek_breakout_strategy"]
    else:
        strategies_to_test = [args.strategy]
    
    all_results = {}
    
    for strategy_name in strategies_to_test:
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 OPTYMALIZACJA: {strategy_name}")
        logger.info(f"{'='*80}\n")
        
        results = optimize_strategy(
            strategy_name=strategy_name,
            symbol=args.symbol,
            days=args.days,
            max_combinations=args.max_combinations,
            position_size_percent=args.position_size,
            verbose=args.verbose
        )
        
        all_results[strategy_name] = results
        
        # Wyświetl wyniki
        print_optimization_results(strategy_name, results, top_n=args.top_n)
        
        # Zapisz jeśli wymagane
        if args.save:
            save_results_to_file(strategy_name, results)
    
    # Podsumowanie
    if len(strategies_to_test) > 1:
        print("\n" + "=" * 80)
        print("📊 PODSUMOWANIE WSZYSTKICH STRATEGII")
        print("=" * 80)
        
        for strategy_name, results in all_results.items():
            if results:
                best = results[0][1]
                print(f"\n{strategy_name}:")
                print(f"  Najlepszy zwrot: {best.total_return:+.2f}%")
                print(f"  Transakcje: {best.total_trades}")
                print(f"  Win Rate: {best.win_rate:.1f}%")
                print(f"  Profit Factor: {best.profit_factor:.2f}")


if __name__ == "__main__":
    main()

