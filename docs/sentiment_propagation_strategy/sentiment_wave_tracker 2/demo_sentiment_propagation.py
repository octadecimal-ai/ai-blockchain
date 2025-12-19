"""
DEMO: Sentiment Propagation Analysis
====================================
Demonstracja pełnej funkcjonalności analizatora propagacji sentymentu.

Używa syntetycznych danych do pokazania wszystkich możliwości systemu,
ponieważ GDELT API ma ograniczenia dla niektórych krajów.

W produkcji można użyć:
- GDELT (darmowy, ale ograniczony)
- NewsAPI (płatny, lepsza jakość)
- Własne scrapery
- Dane z Kaggle (historyczne)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Import modułów
sys.path.insert(0, str(Path(__file__).parent))
from sentiment_propagation_analyzer import (
    SentimentPropagationAnalyzer,
    PropagationDirection,
    MATPLOTLIB_AVAILABLE
)
from loguru import logger

logger.remove()
logger.add(sys.stderr, level='INFO', format='{time:HH:mm:ss} | {level} | {message}')


def generate_realistic_sentiment_data(
    days: int = 30,
    countries: list = None,
    base_volatility: float = 1.0,
    event_probability: float = 0.05
) -> pd.DataFrame:
    """
    Generuje realistyczne dane sentymentu z:
    - Różnymi opóźnieniami między krajami
    - "Eventami" które propagują się globalnie
    - Szumem specyficznym dla każdego kraju
    
    Symulacja:
    - US jest "liderem" (najszybciej reaguje na newsy)
    - CN opóźnione o ~6h (różnica stref czasowych + filtrowanie)
    - JP opóźnione o ~3h
    - KR opóźnione o ~4h
    - DE opóźnione o ~1-2h (podobna strefa czasowa do źródeł EN)
    - GB prawie synchroniczne z US
    """
    if countries is None:
        countries = ["US", "GB", "DE", "JP", "KR", "CN", "RU", "SG"]
    
    np.random.seed(42)  # Dla powtarzalności
    
    hours = days * 24
    timestamps = pd.date_range(
        start=datetime.now() - timedelta(days=days),
        periods=hours,
        freq='H'
    )
    
    # Bazowy sygnał sentymentu (wspólny dla wszystkich)
    # Używamy random walk z tendencją do powrotu do średniej
    base_signal = np.zeros(hours)
    for i in range(1, hours):
        # Mean reversion + random walk
        base_signal[i] = base_signal[i-1] * 0.95 + np.random.randn() * base_volatility
    
    # Dodaj "eventy" - nagłe zmiany sentymentu
    event_indices = np.random.choice(
        range(24, hours - 24),  # Nie na początku/końcu
        size=int(hours * event_probability),
        replace=False
    )
    
    for idx in event_indices:
        # Event może być pozytywny lub negatywny
        event_magnitude = np.random.choice([-1, 1]) * np.random.uniform(3, 8)
        # Event trwa kilka godzin
        event_duration = np.random.randint(3, 12)
        base_signal[idx:idx+event_duration] += event_magnitude
    
    # Opóźnienia dla każdego kraju (w godzinach)
    country_lags = {
        "US": 0,    # Lider
        "GB": 1,    # Bardzo blisko US
        "DE": 2,    # Europa
        "JP": 3,    # Azja (wczesna)
        "KR": 4,    # Azja
        "CN": 6,    # Chiny (filtrowanie + strefa czasowa)
        "RU": 5,    # Rosja
        "SG": 3,    # Singapur
        "AU": 4,    # Australia
        "BR": 2,    # Brazylia
    }
    
    # Współczynniki korelacji (jak bardzo kraj śledzi globalny sentyment)
    country_correlation = {
        "US": 1.0,
        "GB": 0.95,
        "DE": 0.85,
        "JP": 0.80,
        "KR": 0.85,
        "CN": 0.70,  # Mniej skorelowany (inny ekosystem medialny)
        "RU": 0.60,
        "SG": 0.85,
        "AU": 0.90,
        "BR": 0.75,
    }
    
    # Generuj serie dla każdego kraju
    data = {}
    for country in countries:
        lag = country_lags.get(country, 3)
        corr = country_correlation.get(country, 0.8)
        
        # Przesuń sygnał o lag
        shifted = np.roll(base_signal, lag)
        
        # Dodaj specyficzny szum dla kraju
        country_noise = np.random.randn(hours) * (1 - corr) * base_volatility * 2
        
        # Kombinacja: bazowy sygnał * korelacja + szum
        country_signal = shifted * corr + country_noise
        
        # Dodaj baseline specyficzny dla kraju
        # (np. US media są bardziej negatywne, Azja bardziej neutralna)
        country_bias = {
            "US": -0.5,
            "GB": -0.3,
            "DE": 0.0,
            "JP": 0.2,
            "KR": 0.1,
            "CN": 0.3,
            "RU": -0.2,
            "SG": 0.1,
        }
        country_signal += country_bias.get(country, 0)
        
        data[country] = country_signal
    
    df = pd.DataFrame(data, index=timestamps)
    
    logger.info(f"Wygenerowano syntetyczne dane: {len(df)} godzin, {len(df.columns)} krajów")
    logger.info(f"Symulowane opóźnienia: {country_lags}")
    
    return df


def run_full_demo():
    """Uruchamia pełną demonstrację systemu."""
    
    print("\n" + "="*70)
    print("🌊 SENTIMENT PROPAGATION ANALYZER - PEŁNA DEMONSTRACJA")
    print("="*70)
    
    # 1. Generuj dane
    print("\n📊 KROK 1: Generowanie realistycznych danych syntetycznych")
    print("-" * 50)
    
    df = generate_realistic_sentiment_data(
        days=14,
        countries=["US", "GB", "DE", "JP", "KR", "CN"],
        base_volatility=1.5,
        event_probability=0.03
    )
    
    print(f"   Wygenerowano dane dla: {list(df.columns)}")
    print(f"   Okres: {df.index.min()} do {df.index.max()}")
    print(f"   Punktów: {len(df)}")
    
    # 2. Statystyki podstawowe
    print("\n📈 KROK 2: Statystyki sentymentu per kraj")
    print("-" * 50)
    
    for country in df.columns:
        mean = df[country].mean()
        std = df[country].std()
        print(f"   {country}: mean={mean:+.2f}, std={std:.2f}")
    
    # 3. Inicjalizacja analizatora
    analyzer = SentimentPropagationAnalyzer(
        time_resolution_hours=1.0,
        max_lag_hours=24,
        min_correlation=0.3
    )
    
    # 4. Analiza lag-ów
    print("\n🔍 KROK 3: Analiza opóźnień między regionami")
    print("-" * 50)
    
    lag_matrix = analyzer.compute_lag_matrix(df)
    
    # Posortuj po absolute lag
    significant_lags = [
        (k, v) for k, v in lag_matrix.items()
        if v.direction == PropagationDirection.LEADS and v.confidence > 0.3
    ]
    significant_lags.sort(key=lambda x: -abs(x[1].lag_hours))
    
    print("   TOP 10 par z największym lag-iem:")
    for (a, b), result in significant_lags[:10]:
        bar = "█" * int(abs(result.lag_hours) / 2)
        print(f"   {a} → {b}: {result.lag_hours:+.1f}h {bar} (r={result.correlation:.3f})")
    
    # 5. Identyfikacja lidera
    print("\n👑 KROK 4: Identyfikacja regionu lidera")
    print("-" * 50)
    
    leader, avg_lead = analyzer.find_leader_region(lag_matrix)
    print(f"   🏆 LIDER: {leader}")
    print(f"   Średnio wyprzedza inne regiony o: {avg_lead:.1f}h")
    
    # Ranking krajów
    region_scores = {}
    for region in df.columns:
        leads = [
            result.lag_hours for (a, b), result in lag_matrix.items()
            if a == region and result.direction == PropagationDirection.LEADS
        ]
        region_scores[region] = np.mean(leads) if leads else 0
    
    print("\n   Ranking (średni lead time):")
    for i, (region, score) in enumerate(sorted(region_scores.items(), key=lambda x: -x[1]), 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        bar = "▓" * int(score * 2) if score > 0 else ""
        print(f"   {emoji} {i}. {region}: {score:+.1f}h {bar}")
    
    # 6. Wykrywanie fal
    print("\n🌊 KROK 5: Wykrywanie fal sentymentu")
    print("-" * 50)
    
    waves = analyzer.detect_sentiment_waves(df, threshold_std=1.5)
    print(f"   Wykryto {len(waves)} fal propagacji")
    
    if waves:
        print("\n   Szczegóły pierwszych 3 fal:")
        for i, wave in enumerate(waves[:3], 1):
            direction = "📈 BULLISH" if wave.sentiment_change > 0 else "📉 BEARISH"
            print(f"\n   Fala {i}: {direction}")
            print(f"      Origin: {wave.origin_region} @ {wave.wave_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"      Zmiana sentymentu: {wave.sentiment_change:+.2f}")
            print(f"      Siła: {wave.strength:.2f}")
            print(f"      Propagacja: {' → '.join(wave.affected_regions)}")
            
            # Timeline propagacji
            print(f"      Timeline:")
            for region in wave.affected_regions:
                time_offset = wave.arrival_times[region]
                bar = "─" * int(abs(time_offset) * 2) + "●"
                print(f"         {region}: {time_offset:+.1f}h {bar}")
    
    # 7. Generowanie raportu
    print("\n📄 KROK 6: Generowanie raportu")
    print("-" * 50)
    
    report = analyzer.generate_report(df)
    print(report)
    
    # 8. Wizualizacje (jeśli matplotlib dostępny)
    if MATPLOTLIB_AVAILABLE:
        print("\n📊 KROK 7: Generowanie wizualizacji")
        print("-" * 50)
        
        output_dir = Path("/home/claude/output")
        output_dir.mkdir(exist_ok=True)
        
        # Timeseries
        fig1 = analyzer.plot_timeseries_comparison(df, regions=["US", "CN", "JP", "DE"])
        fig1.savefig(output_dir / "sentiment_timeseries.png", dpi=150, bbox_inches='tight')
        print(f"   ✅ Zapisano: {output_dir}/sentiment_timeseries.png")
        
        # Lag heatmap
        fig2 = analyzer.plot_lag_heatmap(lag_matrix)
        fig2.savefig(output_dir / "lag_heatmap.png", dpi=150, bbox_inches='tight')
        print(f"   ✅ Zapisano: {output_dir}/lag_heatmap.png")
        
        # Wave propagation
        if waves:
            fig3 = analyzer.plot_wave_propagation(waves[0])
            fig3.savefig(output_dir / "wave_propagation.png", dpi=150, bbox_inches='tight')
            print(f"   ✅ Zapisano: {output_dir}/wave_propagation.png")
    
    # 9. Podsumowanie i wnioski
    print("\n" + "="*70)
    print("📋 PODSUMOWANIE I WNIOSKI TRADINGOWE")
    print("="*70)
    
    print(f"""
    1. REGION LIDER: {leader}
       → Sentyment z tego regionu najczęściej WYPRZEDZA inne regiony
       → Monitorowanie mediów z tego regionu może dać przewagę informacyjną
    
    2. OPÓŹNIENIA PROPAGACJI:
       → Średnie opóźnienie US → CN: ~{abs(lag_matrix.get(('US', 'CN'), lag_matrix.get(('CN', 'US'))).lag_hours if ('US', 'CN') in lag_matrix or ('CN', 'US') in lag_matrix else 0):.0f}h
       → Średnie opóźnienie US → JP: ~{abs(lag_matrix.get(('US', 'JP'), lag_matrix.get(('JP', 'US'))).lag_hours if ('US', 'JP') in lag_matrix or ('JP', 'US') in lag_matrix else 0):.0f}h
       → To okno czasowe na reakcję przed pełną propagacją
    
    3. WYKRYTE FALE: {len(waves)}
       → Każda fala to potencjalna okazja tradingowa
       → Fala bullish z US → oczekuj wzrostu sentymentu w Azji za kilka godzin
    
    4. STRATEGIA:
       → Monitoruj sentyment z US/GB w czasie rzeczywistym
       → Przy nagłej zmianie sentymentu, otwórz pozycję PRZED propagacją do Azji
       → Stop loss na poziomie przed-falowym
       → Take profit gdy fala dotrze do CN (max propagacja)
    """)
    
    print("="*70)
    print("✅ Demo zakończone!")
    print("="*70)
    
    return df, analyzer, lag_matrix, waves


if __name__ == "__main__":
    df, analyzer, lag_matrix, waves = run_full_demo()
