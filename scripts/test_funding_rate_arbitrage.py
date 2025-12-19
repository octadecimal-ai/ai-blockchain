#!/usr/bin/env python3
"""
Skrypt do testowania strategii Funding Rate Arbitrage
na danych z 2022 i 2023 roku
"""

import sys
from pathlib import Path
import pandas as pd

# Dodaj ścieżkę projektu
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.trading.strategies.funding_rate_arbitrage_strategy import FundingRateArbitrageStrategy
from src.trading.backtesting import BacktestEngine


def run_backtest(year: int, config: dict, label: str):
    """Uruchamia backtest dla danego roku."""
    print(f"\n{'='*80}")
    print(f"📊 Backtest {year} - {label}")
    print(f"{'='*80}")
    
    # Próbuj najpierw z bazy danych
    df = None
    try:
        from src.database.btcusdc_loader import load_btcusdc_from_db
        print("📂 Wczytuję dane BTC/USDC z bazy danych...")
        df = load_btcusdc_from_db()
        
        if not df.empty:
            # Filtruj dane dla danego roku
            df['year'] = df.index.year
            df = df[df['year'] == year]
            df = df.drop(columns=['year'])
            
            if not df.empty:
                print(f"✅ Wczytano {len(df)} świec z bazy danych dla roku {year}")
                print(f"   Okres: {df.index[0]} → {df.index[-1]}")
    except Exception as e:
        print(f"⚠️  Nie udało się wczytać z bazy danych: {e}")
    
    # Fallback do CSV
    if df is None or df.empty:
        csv_path = Path(f"data/backtest_periods/binance/BTCUSDC_{year}_1h.csv")
        if not csv_path.exists():
            csv_path = Path(f"data/backtest_periods/binance/BTCUSDC_{year}_1h.csv")
        
        if not csv_path.exists():
            print(f"❌ Plik {csv_path} nie istnieje i brak danych w bazie")
            return None
        
        print(f"📂 Wczytuję dane z CSV: {csv_path}")
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        df = df.sort_index()
        print(f"✅ Wczytano {len(df)} świec z CSV")
        print(f"   Okres: {df.index[0]} → {df.index[-1]}")
    
    # Utwórz strategię
    strategy = FundingRateArbitrageStrategy(config)
    
    # Utwórz engine
    engine = BacktestEngine(initial_balance=10000.0)
    
    # Uruchom backtest
    result = engine.run_backtest(df=df, strategy=strategy, symbol="BTC/USDC")
    
    # Wyświetl wyniki
    print(f"\n📈 WYNIKI:")
    print(f"   Zwrot: {result.return_:.2f}%")
    print(f"   Transakcje: {result.trades}")
    print(f"   Win Rate: {result.win_rate:.1f}%")
    print(f"   Max Drawdown: {result.max_dd:.2f}%")
    print(f"   Profit Factor: {result.profit_factor:.2f}" if result.profit_factor != float('inf') else "   Profit Factor: inf")
    
    return result


def main():
    """Główna funkcja."""
    print("🚀 Testowanie strategii Funding Rate Arbitrage")
    print("=" * 80)
    
    # Konfiguracje do testowania
    configs = {
        'default': {
            'min_funding_rate': 0.01,
            'target_funding_rate': 0.05,
            'max_position_size': 50.0,
            'funding_interval_hours': 8,
            'min_holding_hours': 24
        },
        'conservative': {
            'min_funding_rate': 0.03,
            'target_funding_rate': 0.08,
            'max_position_size': 30.0,
            'funding_interval_hours': 8,
            'min_holding_hours': 48
        },
        'aggressive': {
            'min_funding_rate': 0.005,
            'target_funding_rate': 0.03,
            'max_position_size': 70.0,
            'funding_interval_hours': 8,
            'min_holding_hours': 12
        }
    }
    
    results = {}
    
    # Testuj dla każdego roku i konfiguracji
    for year in [2022, 2023]:
        results[year] = {}
        for config_name, config in configs.items():
            result = run_backtest(year, config, config_name)
            if result:
                results[year][config_name] = result
    
    # Porównanie wyników
    print(f"\n{'='*80}")
    print("📊 PORÓWNANIE WYNIKÓW")
    print(f"{'='*80}")
    
    for config_name in configs.keys():
        print(f"\n{config_name.upper()}:")
        for year in [2022, 2023]:
            if year in results and config_name in results[year]:
                r = results[year][config_name]
                print(f"  {year}: Zwrot={r.return_:.2f}%, Trades={r.trades}, WR={r.win_rate:.1f}%, DD={r.max_dd:.2f}%")
    
    print(f"\n{'='*80}")
    print("✅ Testy zakończone")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()

