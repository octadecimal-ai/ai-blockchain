#!/usr/bin/env python3
"""
Automatyczny optymalizator strategii tradingowej.
Testuje, poprawia i iteracyjnie optymalizuje strategię aż do osiągnięcia założonych wyników.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import json
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

# Dodaj ścieżkę projektu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Załaduj .env jeśli istnieje
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

from src.trading.backtesting import BacktestEngine, BacktestResult
from src.trading.strategies.piotrek_strategy import PiotrekBreakoutStrategy
from src.collectors.exchange.binance_collector import BinanceCollector


class StrategyAutoOptimizer:
    """
    Automatyczny optymalizator strategii.
    
    Iteracyjnie testuje i poprawia strategię aż do osiągnięcia założonych wyników.
    """
    
    def __init__(
        self,
        initial_balance: float = 10000.0,
        target_win_rate: float = 50.0,
        target_profit_factor: float = 1.5,
        target_return: float = 5.0,
        max_iterations: int = 50,
        slippage_percent: float = 0.1
    ):
        """
        Inicjalizacja optymalizatora.
        
        Args:
            initial_balance: Początkowy kapitał
            target_win_rate: Docelowy Win Rate (%)
            target_profit_factor: Docelowy Profit Factor
            target_return: Docelowy zwrot (%)
            max_iterations: Maksymalna liczba iteracji
            slippage_percent: Slippage w %
        """
        self.initial_balance = initial_balance
        self.target_win_rate = target_win_rate
        self.target_profit_factor = target_profit_factor
        self.target_return = target_return
        self.max_iterations = max_iterations
        self.slippage_percent = slippage_percent
        
        self.engine = BacktestEngine(
            initial_balance=initial_balance,
            slippage_percent=slippage_percent
        )
        
        self.binance = BinanceCollector(sandbox=False)
        
        self.iteration_history: List[Dict[str, Any]] = []
        
        logger.info(f"StrategyAutoOptimizer zainicjalizowany:")
        logger.info(f"  Target Win Rate: {target_win_rate}%")
        logger.info(f"  Target Profit Factor: {target_profit_factor}")
        logger.info(f"  Target Return: {target_return}%")
        logger.info(f"  Max Iterations: {max_iterations}")
    
    def find_best_test_period(self, symbol: str = "BTC/USDC", timeframe: str = "1h") -> Tuple[datetime, datetime, pd.DataFrame]:
        """
        Znajduje najlepszy okres do testowania strategii breakout.
        
        Szuka okresów z wyraźnymi breakoutami i trendami wzrostowymi.
        Używa bazy danych PostgreSQL, z fallback do CSV.
        """
        logger.info(f"🔍 Szukam najlepszego okresu do testowania dla {symbol}...")
        
        df = None
        
        # Próbuj najpierw z bazy danych
        try:
            from src.database.btcusdc_loader import load_btcusdc_from_db
            logger.info("📂 Wczytuję dane BTC/USDC z bazy danych...")
            df = load_btcusdc_from_db()
            
            if not df.empty:
                logger.info(f"✅ Wczytano {len(df)} świec z bazy danych")
                logger.info(f"   Okres: {df.index[0]} → {df.index[-1]}")
        except Exception as e:
            logger.warning(f"Nie udało się wczytać z bazy danych: {e}, próbuję CSV...")
        
        # Fallback do CSV
        if df is None or df.empty:
            csv_files = list(Path("data/backtest_periods/binance").glob("BTCUSDC_*_1h.csv"))
            if not csv_files:
                csv_files = list(Path("data/backtest_periods/binance").glob("BTCUSDC_*_1h.csv"))
            
            if not csv_files:
                logger.error("Nie znaleziono zapisanych danych CSV. Użyję danych z 2023 roku.")
                csv_file = Path("data/backtest_periods/binance/BTCUSDC_2023_1h.csv")
                if not csv_file.exists():
                    csv_file = Path("data/backtest_periods/binance/BTCUSDC_2023_1h.csv")
            else:
                # Wybierz najnowszy plik
                csv_file = max(csv_files, key=lambda p: p.stat().st_mtime)
                logger.info(f"Używam danych z CSV: {csv_file}")
            
            if not csv_file.exists():
                logger.error(f"Plik {csv_file} nie istnieje")
                return None, None, pd.DataFrame()
            
            # Wczytaj dane z CSV
            logger.info(f"Wczytuję dane z CSV: {csv_file}")
            df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
            df = df.sort_index()
        
        if df.empty:
            logger.error("Nie udało się wczytać danych historycznych")
            return None, None, pd.DataFrame()
        
        # Znajdź okresy z największymi breakoutami
        df['price_change'] = df['close'].pct_change() * 100
        df['volatility'] = df['price_change'].rolling(24).std()
        
        # Szukaj okresów z:
        # 1. Wysoką zmiennością (breakouty)
        # 2. Trendem wzrostowym
        # 3. Wystarczającą ilością danych (min 500 świec dla lepszych testów)
        
        best_period_start = None
        best_period_end = None
        best_score = -1
        
        # Użyj większego okna dla lepszych testów (500-1000 świec)
        window_size = min(1000, len(df) - 100)  # ~40 dni dla 1h, ale nie więcej niż dostępne dane
        
        # Przeszukaj różne okna, ale nie za często (co 100 świec)
        step = max(50, window_size // 10)
        for i in range(window_size, len(df) - 100, step):
            window_df = df.iloc[i-window_size:i]
            
            # Oblicz metryki
            price_change = ((window_df['close'].iloc[-1] - window_df['close'].iloc[0]) / window_df['close'].iloc[0]) * 100
            volatility = window_df['volatility'].mean()
            max_breakout = window_df['price_change'].abs().max()
            
            # Score = zmiana ceny + volatility + max breakout
            score = price_change + volatility * 10 + max_breakout * 2
            
            if score > best_score and price_change > 5:  # Tylko trendy wzrostowe
                best_score = score
                best_period_start = window_df.index[0]
                best_period_end = window_df.index[-1]
        
        if best_period_start is None:
            # Fallback: użyj większego okna (500-1000 świec)
            window_fallback = min(1000, len(df) - 100)
            logger.warning(f"Nie znaleziono idealnego okresu, używam ostatnich {window_fallback} świec")
            best_period_start = df.index[-window_fallback]
            best_period_end = df.index[-1]
        
        test_df = df.loc[best_period_start:best_period_end].copy()
        
        logger.success(f"✅ Znaleziono okres testowy:")
        logger.info(f"   Start: {best_period_start}")
        logger.info(f"   End: {best_period_end}")
        logger.info(f"   Świec: {len(test_df)}")
        logger.info(f"   Zmiana ceny: {((test_df['close'].iloc[-1] - test_df['close'].iloc[0]) / test_df['close'].iloc[0]) * 100:.2f}%")
        
        return best_period_start, best_period_end, test_df
    
    def evaluate_strategy(
        self,
        strategy: PiotrekBreakoutStrategy,
        test_df: pd.DataFrame,
        symbol: str = "BTC/USDC"
    ) -> BacktestResult:
        """Ocenia strategię na danych testowych."""
        # Przygotuj DataFrame dla backtestingu
        if 'timestamp' not in test_df.columns:
            test_df['timestamp'] = test_df.index
        
        result = self.engine.run_backtest(
            strategy=strategy,
            symbol=symbol,
            df=test_df,
            position_size_percent=10.0,
            max_positions=1
        )
        
        return result
    
    def check_success_criteria(self, result: BacktestResult) -> Tuple[bool, Dict[str, Any]]:
        """
        Sprawdza czy strategia spełnia kryteria sukcesu.
        
        Returns:
            (is_successful, criteria_status)
        """
        criteria = {
            'win_rate_ok': result.win_rate >= self.target_win_rate,
            'profit_factor_ok': result.profit_factor >= self.target_profit_factor,
            'return_ok': result.total_return >= self.target_return,
            'has_trades': result.total_trades > 0,
            'not_bankrupt': result.total_return > -100.0
        }
        
        is_successful = all(criteria.values())
        
        return is_successful, criteria
    
    def improve_strategy(
        self,
        current_params: Dict[str, Any],
        result: BacktestResult,
        iteration: int
    ) -> Dict[str, Any]:
        """
        Poprawia parametry strategii na podstawie wyników.
        
        Args:
            current_params: Obecne parametry strategii
            result: Wyniki backtestingu
            iteration: Numer iteracji
            
        Returns:
            Nowe parametry strategii
        """
        new_params = current_params.copy()
        
        # Analiza problemów i poprawki
        
        # 1. Jeśli Win Rate jest niski - zwiększ min_confidence i breakout_threshold
        if result.win_rate < self.target_win_rate and result.win_rate > 0:
            new_params['min_confidence'] = min(
                new_params.get('min_confidence', 5.0) + 0.5,
                10.0
            )
            new_params['breakout_threshold'] = min(
                new_params.get('breakout_threshold', 0.8) + 0.1,
                3.0
            )
            logger.info(f"  ⬆️ Zwiększam min_confidence i breakout_threshold (Win Rate: {result.win_rate:.1f}% < {self.target_win_rate}%)")
        
        # 2. Jeśli Profit Factor jest niski - popraw risk/reward i zwiększ progi
        if result.profit_factor < self.target_profit_factor and result.profit_factor > 0:
            new_params['risk_reward_ratio'] = min(
                new_params.get('risk_reward_ratio', 2.0) + 0.3,
                5.0
            )
            # Również zwiększ progi, aby zmniejszyć liczbę stratnych transakcji
            new_params['min_confidence'] = min(
                new_params.get('min_confidence', 5.0) + 0.3,
                10.0
            )
            logger.info(f"  ⬆️ Zwiększam risk_reward_ratio i min_confidence (Profit Factor: {result.profit_factor:.2f} < {self.target_profit_factor})")
        
        # 3. Jeśli brak transakcji - zmniejsz progi
        if result.total_trades == 0:
            new_params['min_confidence'] = max(
                new_params.get('min_confidence', 5.0) - 1.5,
                2.0
            )
            new_params['breakout_threshold'] = max(
                new_params.get('breakout_threshold', 0.8) - 0.3,
                0.3
            )
            logger.info(f"  ⬇️ Zmniejszam progi (brak transakcji)")
        
        # 4. Jeśli bankructwo lub duża strata - drastyczne zmiany
        if result.total_return <= -50.0:
            new_params['min_confidence'] = min(
                new_params.get('min_confidence', 5.0) + 1.5,
                10.0
            )
            new_params['breakout_threshold'] = min(
                new_params.get('breakout_threshold', 0.8) + 0.4,
                3.0
            )
            new_params['consolidation_threshold'] = min(
                new_params.get('consolidation_threshold', 0.4) + 0.2,
                1.0
            )
            # Zwiększ risk/reward, aby zyski były większe niż straty
            new_params['risk_reward_ratio'] = min(
                new_params.get('risk_reward_ratio', 2.0) + 0.5,
                5.0
            )
            logger.warning(f"  ⚠️ Drastyczne zmiany (duża strata: {result.total_return:.2f}%)")
        
        # 5. Jeśli zbyt wiele transakcji - zwiększ progi
        if result.total_trades > 300:
            new_params['min_confidence'] = min(
                new_params.get('min_confidence', 5.0) + 1.0,
                10.0
            )
            new_params['breakout_threshold'] = min(
                new_params.get('breakout_threshold', 0.8) + 0.2,
                3.0
            )
            logger.info(f"  ⬆️ Zwiększam progi (zbyt wiele transakcji: {result.total_trades})")
        
        # 6. Jeśli Win Rate jest OK, ale Profit Factor niski - problem w risk/reward
        if result.win_rate >= self.target_win_rate * 0.8 and result.profit_factor < self.target_profit_factor:
            new_params['risk_reward_ratio'] = min(
                new_params.get('risk_reward_ratio', 2.0) + 0.4,
                5.0
            )
            logger.info(f"  ⬆️ Zwiększam risk_reward_ratio (Win Rate OK, ale Profit Factor niski)")
        
        # 7. Jeśli zwrot jest ujemny, ale nie bankructwo - zwiększ selektywność
        if result.total_return < 0 and result.total_return > -50:
            new_params['min_confidence'] = min(
                new_params.get('min_confidence', 5.0) + 0.5,
                10.0
            )
            new_params['breakout_threshold'] = min(
                new_params.get('breakout_threshold', 0.8) + 0.2,
                3.0
            )
            logger.info(f"  ⬆️ Zwiększam selektywność (zwrot ujemny: {result.total_return:.2f}%)")
        
        return new_params
    
    def run_optimization(
        self,
        symbol: str = "BTC/USDC",
        initial_params: Optional[Dict[str, Any]] = None
    ) -> Tuple[PiotrekBreakoutStrategy, BacktestResult, Dict[str, Any]]:
        """
        Uruchamia iteracyjną optymalizację strategii.
        
        Returns:
            (best_strategy, best_result, best_params)
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 ROZPOCZYNAM AUTOMATYCZNĄ OPTYMALIZACJĘ STRATEGII")
        logger.info(f"{'='*80}\n")
        
        # Znajdź najlepszy okres testowy
        period_start, period_end, test_df = self.find_best_test_period(symbol)
        
        if test_df.empty:
            logger.error("❌ Nie udało się znaleźć okresu testowego")
            return None, None, None
        
        # Inicjalizuj parametry
        if initial_params is None:
            params = {
                'breakout_threshold': 0.8,
                'consolidation_threshold': 0.4,
                'min_confidence': 5.0,
                'risk_reward_ratio': 2.0,
                'rsi_oversold': 30,
                'rsi_overbought': 70,
                'use_rsi': True,
                'timeframe': '1h'
            }
        else:
            params = initial_params.copy()
        
        best_strategy = None
        best_result = None
        best_params = None
        best_score = -float('inf')
        
        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"📊 ITERACJA #{iteration}/{self.max_iterations}")
            logger.info(f"{'='*80}")
            logger.info(f"Parametry: {params}")
            
            # Utwórz strategię z obecnymi parametrami
            strategy = PiotrekBreakoutStrategy(params)
            
            # Oceń strategię
            result = self.evaluate_strategy(strategy, test_df, symbol)
            
            # Sprawdź kryteria sukcesu
            is_successful, criteria = self.check_success_criteria(result)
            
            # Oblicz score (ważona suma metryk)
            score = (
                result.win_rate * 0.3 +
                min(result.profit_factor, 5.0) * 20 * 0.3 +
                min(result.total_return, 100.0) * 0.4
            )
            
            # Zapisz historię
            history_entry = {
                'iteration': iteration,
                'params': params.copy(),
                'result': {
                    'total_return': result.total_return,
                    'win_rate': result.win_rate,
                    'profit_factor': result.profit_factor,
                    'total_trades': result.total_trades,
                    'max_drawdown': result.max_drawdown
                },
                'criteria': criteria,
                'is_successful': is_successful,
                'score': score
            }
            self.iteration_history.append(history_entry)
            
            # Wyświetl wyniki
            logger.info(f"\n📈 WYNIKI:")
            logger.info(f"   Zwrot: {result.total_return:+.2f}%")
            logger.info(f"   Win Rate: {result.win_rate:.1f}%")
            logger.info(f"   Profit Factor: {result.profit_factor:.2f}")
            logger.info(f"   Transakcje: {result.total_trades}")
            logger.info(f"   Max Drawdown: {result.max_drawdown:.2f}%")
            logger.info(f"   Score: {score:.2f}")
            
            logger.info(f"\n✅ KRYTERIA SUKCESU:")
            for criterion, status in criteria.items():
                status_icon = "✅" if status else "❌"
                logger.info(f"   {status_icon} {criterion}: {status}")
            
            # Sprawdź czy to najlepsza strategia
            if score > best_score:
                best_score = score
                best_strategy = strategy
                best_result = result
                best_params = params.copy()
                logger.success(f"   🏆 NOWA NAJLEPSZA STRATEGIA! (Score: {score:.2f})")
            
            # Jeśli spełnia wszystkie kryteria - sukces!
            if is_successful:
                logger.success(f"\n{'='*80}")
                logger.success(f"🎉 SUKCES! Strategia spełnia wszystkie kryteria!")
                logger.success(f"{'='*80}")
                logger.success(f"Parametry: {params}")
                logger.success(f"Zwrot: {result.total_return:+.2f}%")
                logger.success(f"Win Rate: {result.win_rate:.1f}%")
                logger.success(f"Profit Factor: {result.profit_factor:.2f}")
                break
            
            # Popraw strategię
            logger.info(f"\n🔧 Poprawiam strategię...")
            params = self.improve_strategy(params, result, iteration)
            
            # Sprawdź czy nie ma postępu (zastój)
            if iteration > 5:
                recent_scores = [h['score'] for h in self.iteration_history[-5:]]
                if max(recent_scores) - min(recent_scores) < 1.0:
                    logger.warning("⚠️ Brak postępu w ostatnich iteracjach, zwiększam agresywność zmian")
                    params['min_confidence'] = max(params.get('min_confidence', 5.0) - 1.0, 2.0)
                    params['breakout_threshold'] = max(params.get('breakout_threshold', 0.8) - 0.2, 0.3)
        
        # Podsumowanie
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 PODSUMOWANIE OPTYMALIZACJI")
        logger.info(f"{'='*80}")
        
        if best_result:
            logger.info(f"\n🏆 NAJLEPSZA STRATEGIA:")
            logger.info(f"   Parametry: {best_params}")
            logger.info(f"   Zwrot: {best_result.total_return:+.2f}%")
            logger.info(f"   Win Rate: {best_result.win_rate:.1f}%")
            logger.info(f"   Profit Factor: {best_result.profit_factor:.2f}")
            logger.info(f"   Transakcje: {best_result.total_trades}")
            logger.info(f"   Score: {best_score:.2f}")
        
        return best_strategy, best_result, best_params
    
    def save_results(self, output_file: str = "strategy_optimization_results.json"):
        """Zapisuje wyniki optymalizacji do pliku."""
        output_path = Path("data/optimization") / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'targets': {
                'win_rate': self.target_win_rate,
                'profit_factor': self.target_profit_factor,
                'return': self.target_return
            },
            'iterations': self.iteration_history
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.success(f"💾 Zapisano wyniki do: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Automatyczny optymalizator strategii tradingowej",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--symbol",
        default="BTC/USDC",
        help="Symbol pary (np. BTC/USDC)"
    )
    
    parser.add_argument(
        "--target-win-rate",
        type=float,
        default=50.0,
        help="Docelowy Win Rate (%)"
    )
    
    parser.add_argument(
        "--target-profit-factor",
        type=float,
        default=1.5,
        help="Docelowy Profit Factor"
    )
    
    parser.add_argument(
        "--target-return",
        type=float,
        default=5.0,
        help="Docelowy zwrot (%)"
    )
    
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=50,
        help="Maksymalna liczba iteracji"
    )
    
    parser.add_argument(
        "--slippage",
        type=float,
        default=0.1,
        help="Slippage w %"
    )
    
    parser.add_argument(
        "--save",
        action="store_true",
        help="Zapisz wyniki do pliku"
    )
    
    args = parser.parse_args()
    
    # Utwórz optymalizator
    optimizer = StrategyAutoOptimizer(
        target_win_rate=args.target_win_rate,
        target_profit_factor=args.target_profit_factor,
        target_return=args.target_return,
        max_iterations=args.max_iterations,
        slippage_percent=args.slippage
    )
    
    # Uruchom optymalizację
    best_strategy, best_result, best_params = optimizer.run_optimization(
        symbol=args.symbol
    )
    
    if args.save:
        optimizer.save_results()
    
    if best_result and best_result.total_return > 0:
        logger.success(f"\n✅ Optymalizacja zakończona sukcesem!")
        return 0
    else:
        logger.warning(f"\n⚠️ Optymalizacja zakończona bez pełnego sukcesu")
        return 1


if __name__ == "__main__":
    sys.exit(main())

