"""
Sentiment Wave Tracker
======================
Główny skrypt integrujący:
- GDELT Collector (pobieranie danych sentymentu z całego świata)
- Sentiment Propagation Analyzer (wykrywanie lag-ów między regionami)
- CryptoDataDownload (dane cenowe BTC)
- DatabaseManager (zapis do bazy)

Cel: Wykrycie "fal" sentymentu rozprzestrzeniających się między regionami
i korelacja z ruchami cenowymi BTC.

Użycie:
    python sentiment_wave_tracker.py --days 7 --query "bitcoin"
    python sentiment_wave_tracker.py --analyze-only  # tylko analiza cached danych
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
import json

import pandas as pd
import numpy as np
from loguru import logger

# Import lokalnych modułów
from gdelt_collector import GDELTCollector
from sentiment_propagation_analyzer import (
    SentimentPropagationAnalyzer,
    PropagationDirection,
    LagResult,
    PropagationWave
)

# Spróbuj zaimportować moduły z projektu użytkownika
try:
    # Zakładamy, że skrypt jest w src/collectors/sentiment/
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from src.database.manager import DatabaseManager
    from src.collectors.exchange.cryptodatadownload_collector import CryptoDataDownloadCollector
    from src.database.models import SentimentScore
    PROJECT_AVAILABLE = True
except ImportError:
    PROJECT_AVAILABLE = False
    logger.warning("Moduły projektu niedostępne - używam standalone mode")


class SentimentWaveTracker:
    """
    Główna klasa do śledzenia fal sentymentu.
    
    Integruje:
    - Pobieranie danych z GDELT
    - Analizę propagacji
    - Korelację z cenami
    - Zapis do bazy danych
    
    Przykład:
        tracker = SentimentWaveTracker()
        
        # Pobierz dane i przeanalizuj
        results = tracker.run_full_analysis(
            query="bitcoin OR cryptocurrency",
            days_back=7,
            countries=["US", "CN", "JP", "KR", "DE", "GB"]
        )
        
        # Generuj raport
        tracker.print_report(results)
    """
    
    # Domyślne kraje do analizy (główne rynki crypto)
    DEFAULT_COUNTRIES = ["US", "CN", "JP", "KR", "DE", "GB", "RU", "SG"]
    
    def __init__(
        self,
        cache_dir: Path = None,
        db_manager: Optional[Any] = None,
        use_database: bool = True
    ):
        """
        Inicjalizuje tracker.
        
        Args:
            cache_dir: Katalog cache
            db_manager: Opcjonalny DatabaseManager
            use_database: Czy zapisywać do bazy
        """
        self.cache_dir = cache_dir or Path("data/sentiment_waves")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicjalizuj kolektory
        self.gdelt = GDELTCollector(cache_dir=self.cache_dir / "gdelt")
        self.analyzer = SentimentPropagationAnalyzer(
            time_resolution_hours=1.0,
            max_lag_hours=48,
            min_correlation=0.3
        )
        
        # Database
        self.db = db_manager
        self.use_database = use_database and PROJECT_AVAILABLE
        
        if self.use_database and self.db is None:
            try:
                self.db = DatabaseManager()
                self.db.create_tables()
                logger.info("Połączono z bazą danych")
            except Exception as e:
                logger.warning(f"Nie można połączyć z bazą: {e}")
                self.use_database = False
        
        # Price collector
        self.price_collector = None
        if PROJECT_AVAILABLE:
            try:
                self.price_collector = CryptoDataDownloadCollector(exchange="Binance")
            except Exception:
                pass
        
        logger.info("SentimentWaveTracker zainicjalizowany")
    
    def fetch_multi_country_sentiment(
        self,
        query: str = "bitcoin OR cryptocurrency",
        countries: List[str] = None,
        days_back: int = 7,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Pobiera dane sentymentu dla wielu krajów.
        
        Args:
            query: Zapytanie wyszukiwania
            countries: Lista kodów krajów
            days_back: Dni wstecz
            use_cache: Czy używać cache
            
        Returns:
            DataFrame z kolumnami dla każdego kraju (wartości = tone)
        """
        if countries is None:
            countries = self.DEFAULT_COUNTRIES
        
        # Sprawdź cache
        cache_file = self.cache_dir / f"sentiment_{query.replace(' ', '_')}_{days_back}d.parquet"
        
        if use_cache and cache_file.exists():
            # Sprawdź czy cache nie jest za stary (max 1h)
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age < timedelta(hours=1):
                logger.info(f"Używam cache: {cache_file}")
                return pd.read_parquet(cache_file)
        
        # Pobierz świeże dane
        logger.info(f"Pobieram dane GDELT dla {len(countries)} krajów...")
        
        df = self.gdelt.fetch_multi_country_timeseries(
            query=query,
            countries=countries,
            days_back=days_back,
            metric="tone"
        )
        
        if not df.empty:
            # Zapisz cache
            df.to_parquet(cache_file)
            logger.success(f"Zapisano cache: {cache_file}")
        
        return df
    
    def fetch_btc_prices(
        self,
        days_back: int = 30
    ) -> pd.DataFrame:
        """
        Pobiera ceny BTC z CryptoDataDownload.
        
        Args:
            days_back: Dni wstecz
            
        Returns:
            DataFrame z cenami OHLCV
        """
        if self.price_collector is None:
            logger.warning("Price collector niedostępny")
            return pd.DataFrame()
        
        try:
            start_date = datetime.now() - timedelta(days=days_back)
            df = self.price_collector.fetch_historical(
                symbol="BTC-USD",
                timeframe="1h",
                start_date=start_date
            )
            return df
        except Exception as e:
            logger.error(f"Błąd pobierania cen: {e}")
            return pd.DataFrame()
    
    def run_full_analysis(
        self,
        query: str = "bitcoin OR cryptocurrency",
        countries: List[str] = None,
        days_back: int = 7,
        include_price_correlation: bool = True
    ) -> Dict[str, Any]:
        """
        Uruchamia pełną analizę propagacji sentymentu.
        
        Args:
            query: Zapytanie wyszukiwania
            countries: Lista krajów
            days_back: Dni wstecz
            include_price_correlation: Czy korelować z ceną
            
        Returns:
            Słownik z wynikami analizy
        """
        results = {
            "query": query,
            "countries": countries or self.DEFAULT_COUNTRIES,
            "days_back": days_back,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sentiment_data": None,
            "lag_matrix": {},
            "leader_region": None,
            "waves": [],
            "price_correlations": {},
            "summary": {}
        }
        
        # 1. Pobierz dane sentymentu
        logger.info("=" * 50)
        logger.info("KROK 1: Pobieranie danych sentymentu")
        logger.info("=" * 50)
        
        sentiment_df = self.fetch_multi_country_sentiment(
            query=query,
            countries=countries,
            days_back=days_back
        )
        
        if sentiment_df.empty:
            logger.error("Brak danych sentymentu!")
            return results
        
        results["sentiment_data"] = sentiment_df
        logger.success(f"Pobrano dane dla {len(sentiment_df.columns)} krajów, {len(sentiment_df)} punktów")
        
        # 2. Analiza lag-ów
        logger.info("\n" + "=" * 50)
        logger.info("KROK 2: Analiza lag-ów między regionami")
        logger.info("=" * 50)
        
        lag_matrix = self.analyzer.compute_lag_matrix(sentiment_df)
        results["lag_matrix"] = {
            f"{k[0]}-{k[1]}": {
                "lag_hours": v.lag_hours,
                "correlation": v.correlation,
                "direction": v.direction.value,
                "confidence": v.confidence
            }
            for k, v in lag_matrix.items()
        }
        
        # Znajdź lidera
        leader, avg_lead = self.analyzer.find_leader_region(lag_matrix)
        results["leader_region"] = {"region": leader, "avg_lead_hours": avg_lead}
        logger.success(f"Leader region: {leader} (avg lead: {avg_lead:.1f}h)")
        
        # 3. Wykrywanie fal
        logger.info("\n" + "=" * 50)
        logger.info("KROK 3: Wykrywanie fal sentymentu")
        logger.info("=" * 50)
        
        waves = self.analyzer.detect_sentiment_waves(sentiment_df)
        results["waves"] = [
            {
                "origin": w.origin_region,
                "time": w.wave_time.isoformat(),
                "affected_regions": w.affected_regions,
                "arrival_times": w.arrival_times,
                "sentiment_change": w.sentiment_change,
                "strength": w.strength
            }
            for w in waves
        ]
        logger.success(f"Wykryto {len(waves)} fal sentymentu")
        
        # 4. Korelacja z ceną (opcjonalnie)
        if include_price_correlation:
            logger.info("\n" + "=" * 50)
            logger.info("KROK 4: Korelacja z ceną BTC")
            logger.info("=" * 50)
            
            price_df = self.fetch_btc_prices(days_back=days_back + 7)
            
            if not price_df.empty:
                for region in sentiment_df.columns[:5]:  # Top 5 regionów
                    corr_result = self.analyzer.correlate_with_price(
                        sentiment_df, price_df, region
                    )
                    if corr_result:
                        results["price_correlations"][region] = {
                            "optimal_lag": corr_result["optimal_lag_hours"],
                            "correlation": corr_result["max_correlation"]
                        }
                        logger.info(f"  {region}: lag={corr_result['optimal_lag_hours']}h, r={corr_result['max_correlation']:.3f}")
            else:
                logger.warning("Brak danych cenowych")
        
        # 5. Podsumowanie
        results["summary"] = self._generate_summary(results)
        
        # 6. Zapisz do bazy (opcjonalnie)
        if self.use_database:
            self._save_to_database(results)
        
        return results
    
    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generuje podsumowanie wyników."""
        summary = {
            "total_data_points": 0,
            "countries_analyzed": 0,
            "significant_lags": 0,
            "waves_detected": len(results["waves"]),
            "leader_region": results["leader_region"]["region"] if results["leader_region"] else None,
            "trading_signals": []
        }
        
        if results["sentiment_data"] is not None:
            summary["total_data_points"] = len(results["sentiment_data"])
            summary["countries_analyzed"] = len(results["sentiment_data"].columns)
        
        # Policz znaczące lagi
        for key, lag_info in results["lag_matrix"].items():
            if lag_info["confidence"] > 0.5 and abs(lag_info["lag_hours"]) > 2:
                summary["significant_lags"] += 1
        
        # Generuj sygnały tradingowe
        if results["waves"]:
            recent_waves = [
                w for w in results["waves"]
                if datetime.fromisoformat(w["time"]) > datetime.now(timezone.utc) - timedelta(hours=24)
            ]
            
            for wave in recent_waves:
                signal = {
                    "type": "bullish" if wave["sentiment_change"] > 0 else "bearish",
                    "origin": wave["origin"],
                    "strength": wave["strength"],
                    "expected_propagation": wave["affected_regions"][1:] if len(wave["affected_regions"]) > 1 else [],
                    "message": self._generate_signal_message(wave)
                }
                summary["trading_signals"].append(signal)
        
        return summary
    
    def _generate_signal_message(self, wave: Dict) -> str:
        """Generuje czytelny komunikat o sygnale."""
        direction = "pozytywna" if wave["sentiment_change"] > 0 else "negatywna"
        
        if len(wave["affected_regions"]) > 1:
            next_regions = wave["affected_regions"][1:3]
            times = [wave["arrival_times"].get(r, 0) for r in next_regions]
            
            msg = f"Fala {direction} z {wave['origin']}. "
            msg += f"Oczekiwana propagacja do {', '.join(next_regions)} "
            msg += f"w ciągu {max(times):.1f}h."
            return msg
        
        return f"Fala {direction} wykryta w {wave['origin']}."
    
    def _save_to_database(self, results: Dict[str, Any]):
        """Zapisuje wyniki do bazy danych."""
        if not self.db:
            return
        
        try:
            with self.db.get_session() as session:
                # Zapisz agregowany sentyment
                timestamp = datetime.now(timezone.utc)
                
                for region, lag_info in results["lag_matrix"].items():
                    if "-" in region:
                        continue  # Pomijamy pary, zapisujemy tylko per-region
                
                # Zapisz sygnały
                for signal in results.get("summary", {}).get("trading_signals", []):
                    from src.database.models import Signal
                    
                    session.add(Signal(
                        timestamp=timestamp,
                        exchange="gdelt",
                        symbol="BTC-USD",
                        signal_type=signal["type"],
                        strategy="sentiment_wave",
                        price_at_signal=0,  # Brak ceny z GDELT
                        notes=signal["message"]
                    ))
                
                logger.success("Zapisano wyniki do bazy danych")
                
        except Exception as e:
            logger.error(f"Błąd zapisu do bazy: {e}")
    
    def print_report(self, results: Dict[str, Any]):
        """Drukuje czytelny raport z wyników."""
        print("\n" + "=" * 70)
        print("🌊 SENTIMENT WAVE TRACKER - RAPORT")
        print("=" * 70)
        
        print(f"\n📅 Analiza: {results['query']}")
        print(f"📆 Okres: ostatnie {results['days_back']} dni")
        print(f"🌍 Kraje: {', '.join(results['countries'])}")
        print(f"⏰ Timestamp: {results['timestamp']}")
        
        # Lider
        if results["leader_region"]:
            leader = results["leader_region"]
            print(f"\n👑 REGION LIDER: {leader['region']}")
            print(f"   Średnio wyprzedza inne regiony o {leader['avg_lead_hours']:.1f}h")
        
        # Top lagi
        print("\n📊 TOP 10 ZNACZĄCYCH LAG-ÓW:")
        lags = [
            (k, v) for k, v in results["lag_matrix"].items()
            if v["direction"] == "leads" and v["confidence"] > 0.3
        ]
        lags_sorted = sorted(lags, key=lambda x: -abs(x[1]["lag_hours"]))[:10]
        
        for pair, info in lags_sorted:
            regions = pair.split("-")
            print(f"   {regions[0]} → {regions[1]}: {info['lag_hours']:+.1f}h (r={info['correlation']:.3f}, conf={info['confidence']:.2f})")
        
        # Fale
        if results["waves"]:
            print(f"\n🌊 WYKRYTE FALE SENTYMENTU ({len(results['waves'])}):")
            for i, wave in enumerate(results["waves"][:5], 1):
                direction = "📈" if wave["sentiment_change"] > 0 else "📉"
                print(f"\n   {direction} Fala {i}:")
                print(f"      Origin: {wave['origin']} @ {wave['time'][:16]}")
                print(f"      Propagacja: {' → '.join(wave['affected_regions'])}")
                print(f"      Zmiana: {wave['sentiment_change']:+.2f} | Siła: {wave['strength']:.2f}")
        
        # Korelacja z ceną
        if results["price_correlations"]:
            print("\n💰 KORELACJA Z CENĄ BTC:")
            for region, corr in results["price_correlations"].items():
                direction = "wyprzedza" if corr["optimal_lag"] < 0 else "opóźniony"
                print(f"   {region}: {direction} cenę o {abs(corr['optimal_lag'])}h (r={corr['correlation']:.3f})")
        
        # Sygnały
        if results["summary"].get("trading_signals"):
            print("\n🚨 SYGNAŁY TRADINGOWE:")
            for signal in results["summary"]["trading_signals"]:
                emoji = "🟢" if signal["type"] == "bullish" else "🔴"
                print(f"   {emoji} {signal['message']}")
        
        print("\n" + "=" * 70)
        print("✅ Koniec raportu")
        print("=" * 70)
    
    def save_results_json(self, results: Dict[str, Any], filename: str = None):
        """Zapisuje wyniki do pliku JSON."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.cache_dir / f"analysis_{timestamp}.json"
        
        # Konwertuj DataFrame na dict
        results_clean = results.copy()
        if results_clean.get("sentiment_data") is not None:
            results_clean["sentiment_data"] = results_clean["sentiment_data"].to_dict()
        
        with open(filename, "w") as f:
            json.dump(results_clean, f, indent=2, default=str)
        
        logger.info(f"Zapisano wyniki: {filename}")
        return filename


# === CLI ===

def main():
    parser = argparse.ArgumentParser(
        description="Sentiment Wave Tracker - analiza propagacji sentymentu crypto"
    )
    
    parser.add_argument(
        "--query", "-q",
        default="bitcoin OR cryptocurrency",
        help="Zapytanie wyszukiwania (default: bitcoin OR cryptocurrency)"
    )
    
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=7,
        help="Ile dni wstecz analizować (default: 7)"
    )
    
    parser.add_argument(
        "--countries", "-c",
        nargs="+",
        default=["US", "CN", "JP", "KR", "DE", "GB"],
        help="Kody krajów do analizy (default: US CN JP KR DE GB)"
    )
    
    parser.add_argument(
        "--no-price",
        action="store_true",
        help="Pomiń korelację z ceną BTC"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Plik wyjściowy JSON (opcjonalnie)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose logging"
    )
    
    args = parser.parse_args()
    
    # Konfiguracja logowania
    logger.remove()
    level = "DEBUG" if args.verbose else "INFO"
    logger.add(sys.stderr, level=level, format="{time:HH:mm:ss} | {level} | {message}")
    
    # Uruchom analizę
    tracker = SentimentWaveTracker()
    
    results = tracker.run_full_analysis(
        query=args.query,
        countries=args.countries,
        days_back=args.days,
        include_price_correlation=not args.no_price
    )
    
    # Wydrukuj raport
    tracker.print_report(results)
    
    # Zapisz JSON jeśli podano
    if args.output:
        tracker.save_results_json(results, args.output)


if __name__ == "__main__":
    main()
