"""
Sentiment Propagation Analyzer
==============================
Moduł do analizy propagacji sentymentu między regionami/krajami.

Główna idea:
- Informacje o kryptowalutach rozprzestrzeniają się z opóźnieniem między regionami
- Wykrycie tego opóźnienia może dać przewagę tradingową
- Cross-correlation pozwala zmierzyć lag między szeregami czasowymi

Funkcje:
- Detekcja lag-u między krajami (cross-correlation)
- Wykrywanie "lidera" sentymentu
- Wizualizacja propagacji "fali" sentymentu
- Korelacja z cenami BTC
"""

import numpy as np
import pandas as pd
from scipy import signal
from scipy.stats import pearsonr, spearmanr
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum
from loguru import logger

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib nie jest zainstalowany. Wizualizacje będą niedostępne.")


class PropagationDirection(Enum):
    """Kierunek propagacji sentymentu."""
    LEADS = "leads"      # Kraj A prowadzi (wyprzedza) kraj B
    LAGS = "lags"        # Kraj A jest opóźniony względem kraju B
    SYNCHRONOUS = "sync" # Brak istotnego opóźnienia


@dataclass
class LagResult:
    """Wynik analizy opóźnienia między dwoma regionami."""
    region_a: str
    region_b: str
    optimal_lag: int           # Optymalny lag w jednostkach czasowych (ujemny = A prowadzi)
    correlation: float         # Korelacja przy optymalnym lag-u
    direction: PropagationDirection
    confidence: float          # Pewność wyniku (0-1)
    lag_hours: float          # Lag przeliczony na godziny (lub skorygowany jeśli TZ-aware)
    
    # Pola dla timezone-aware analysis (opcjonalne)
    raw_lag_hours: float = None        # Surowy lag przed korektą TZ
    wakeup_delay_hours: float = None   # Opóźnienie "przebudzenia" regionu B
    timezone_driven: bool = False       # Czy lag wynika głównie z różnicy stref czasowych
    
    def __repr__(self):
        if self.timezone_driven:
            return (f"<Lag: {self.region_a} → {self.region_b} "
                   f"raw={self.raw_lag_hours:.1f}h, wakeup={self.wakeup_delay_hours:.1f}h, "
                   f"TRUE={self.lag_hours:.1f}h (TZ-adjusted)>")
        elif self.direction == PropagationDirection.LEADS:
            return f"<Lag: {self.region_a} LEADS {self.region_b} by {abs(self.lag_hours):.1f}h (r={self.correlation:.3f})>"
        elif self.direction == PropagationDirection.LAGS:
            return f"<Lag: {self.region_a} LAGS {self.region_b} by {abs(self.lag_hours):.1f}h (r={self.correlation:.3f})>"
        else:
            return f"<Lag: {self.region_a} ≈ {self.region_b} (sync, r={self.correlation:.3f})>"


@dataclass
class PropagationWave:
    """Wykryta fala propagacji sentymentu."""
    origin_region: str         # Region źródłowy
    wave_time: datetime        # Czas rozpoczęcia fali
    affected_regions: List[str]  # Regiony dotknięte falą (w kolejności)
    arrival_times: Dict[str, float]  # Czas dotarcia do każdego regionu (w godzinach od origin)
    sentiment_change: float    # Zmiana sentymentu (dodatnia/ujemna)
    strength: float           # Siła fali (0-1)


class SentimentPropagationAnalyzer:
    """
    Analizator propagacji sentymentu między regionami.
    
    Algorytm:
    1. Dla każdej pary regionów oblicz cross-correlation z różnymi lag-ami
    2. Znajdź optymalny lag (maksymalna korelacja)
    3. Określ kierunek propagacji (kto prowadzi)
    4. Wykryj "fale" - nagłe zmiany sentymentu propagujące się między regionami
    5. [NOWE] Koryguj lagi o "wakeup delay" (strefy czasowe)
    
    Przykład użycia:
    
        analyzer = SentimentPropagationAnalyzer(timezone_aware=True)
        
        # Załaduj dane multi-country
        df = gdelt_collector.fetch_multi_country_timeseries(...)
        
        # Analiza lag-u między USA a Chinami
        lag = analyzer.detect_lag(df, "US", "CN")
        print(f"US {lag.direction.value} CN by {lag.lag_hours}h")
        
        # Z korektą timezone:
        # raw_lag=6h, wakeup_delay=3h, true_propagation=3h
        
        # Pełna macierz lag-ów
        matrix = analyzer.compute_lag_matrix(df)
        
        # Wizualizacja
        analyzer.plot_propagation_map(matrix)
    """
    
    def __init__(
        self,
        time_resolution_hours: float = 1.0,
        max_lag_hours: int = 72,
        min_correlation: float = 0.3,
        min_samples: int = 24,
        timezone_aware: bool = False
    ):
        """
        Inicjalizuje analizator.
        
        Args:
            time_resolution_hours: Rozdzielczość czasowa danych (w godzinach)
            max_lag_hours: Maksymalny lag do sprawdzenia (w godzinach)
            min_correlation: Minimalna korelacja do uznania za istotną
            min_samples: Minimalna liczba próbek do analizy
            timezone_aware: Czy korygować lagi o strefy czasowe
        """
        self.time_resolution = time_resolution_hours
        self.max_lag = int(max_lag_hours / time_resolution_hours)
        self.min_correlation = min_correlation
        self.min_samples = min_samples
        self.timezone_aware = timezone_aware
        
        # Inicjalizuj timezone analyzer jeśli potrzebny
        self.tz_analyzer = None
        if timezone_aware:
            try:
                from timezone_aware_analyzer import TimezoneAwareAnalyzer
                self.tz_analyzer = TimezoneAwareAnalyzer()
                logger.info("TimezoneAwareAnalyzer aktywny - lagi będą korygowane o strefy czasowe")
            except ImportError:
                logger.warning("timezone_aware_analyzer.py nie znaleziony - wyłączam korektę stref czasowych")
                self.timezone_aware = False
        
        logger.info(f"SentimentPropagationAnalyzer: max_lag={max_lag_hours}h, min_corr={min_correlation}, tz_aware={self.timezone_aware}")
    
    def detect_lag(
        self,
        df: pd.DataFrame,
        region_a: str,
        region_b: str,
        normalize: bool = True
    ) -> Optional[LagResult]:
        """
        Wykrywa opóźnienie między dwoma regionami używając cross-correlation.
        
        Ujemny lag oznacza, że region_a WYPRZEDZA region_b.
        Dodatni lag oznacza, że region_a jest OPÓŹNIONY względem region_b.
        
        Args:
            df: DataFrame z kolumnami dla każdego regionu
            region_a: Kod pierwszego regionu
            region_b: Kod drugiego regionu
            normalize: Czy normalizować serie przed korelacją
            
        Returns:
            LagResult z optymalnym lag-iem i korelacją
        """
        if region_a not in df.columns or region_b not in df.columns:
            logger.warning(f"Brak danych dla {region_a} lub {region_b}")
            return None
        
        # Pobierz serie i usuń NaN
        series_a = df[region_a].dropna()
        series_b = df[region_b].dropna()
        
        # Znajdź wspólny zakres czasowy
        common_idx = series_a.index.intersection(series_b.index)
        
        if len(common_idx) < self.min_samples:
            logger.warning(f"Za mało wspólnych próbek: {len(common_idx)} < {self.min_samples}")
            return None
        
        a = series_a.loc[common_idx].values
        b = series_b.loc[common_idx].values
        
        # Normalizacja (zero mean, unit variance)
        if normalize:
            a = (a - np.mean(a)) / (np.std(a) + 1e-10)
            b = (b - np.mean(b)) / (np.std(b) + 1e-10)
        
        # Cross-correlation
        # Używamy scipy.signal.correlate dla pełnej cross-correlation
        correlation = signal.correlate(a, b, mode='full')
        
        # Normalizuj przez liczbę próbek
        n = len(a)
        correlation = correlation / n
        
        # Lagi odpowiadające każdej wartości korelacji
        lags = signal.correlation_lags(len(a), len(b), mode='full')
        
        # Ogranicz do max_lag
        valid_mask = np.abs(lags) <= self.max_lag
        correlation = correlation[valid_mask]
        lags = lags[valid_mask]
        
        # Znajdź maksymalną korelację
        max_idx = np.argmax(np.abs(correlation))
        optimal_lag = lags[max_idx]
        max_corr = correlation[max_idx]
        
        # Określ kierunek
        if abs(optimal_lag) <= 1:  # Próg dla "synchronous"
            direction = PropagationDirection.SYNCHRONOUS
        elif optimal_lag < 0:
            direction = PropagationDirection.LEADS  # A wyprzedza B
        else:
            direction = PropagationDirection.LAGS   # A opóźniony względem B
        
        # Oblicz confidence na podstawie peak prominence
        # Im wyraźniejszy peak, tym większa pewność
        peak_value = abs(max_corr)
        mean_corr = np.mean(np.abs(correlation))
        confidence = min(1.0, (peak_value - mean_corr) / (1 - mean_corr + 1e-10))
        confidence = max(0.0, confidence)
        
        lag_hours = optimal_lag * self.time_resolution
        
        # Korekta o strefy czasowe (jeśli włączona)
        adjusted_lag_hours = lag_hours
        wakeup_delay = 0.0
        timezone_driven = False
        
        if self.timezone_aware and self.tz_analyzer:
            tz_result = self.tz_analyzer.calculate_timezone_aware_lag(
                df, region_a, region_b, lag_hours, max_corr
            )
            adjusted_lag_hours = tz_result.adjusted_lag_hours
            wakeup_delay = tz_result.wakeup_delay_hours
            timezone_driven = tz_result.timezone_driven
            
            if timezone_driven:
                logger.debug(
                    f"TZ-corrected {region_a}-{region_b}: "
                    f"raw={lag_hours:.1f}h, wakeup={wakeup_delay:.1f}h, "
                    f"true={adjusted_lag_hours:.1f}h"
                )
        
        result = LagResult(
            region_a=region_a,
            region_b=region_b,
            optimal_lag=int(optimal_lag),
            correlation=float(max_corr),
            direction=direction,
            confidence=float(confidence),
            lag_hours=float(adjusted_lag_hours if self.timezone_aware else lag_hours)
        )
        
        # Dodaj dodatkowe atrybuty dla timezone-aware
        if self.timezone_aware:
            result.raw_lag_hours = lag_hours
            result.wakeup_delay_hours = wakeup_delay
            result.timezone_driven = timezone_driven
        
        logger.debug(f"Lag {region_a}-{region_b}: {optimal_lag} units ({lag_hours:.1f}h), r={max_corr:.3f}")
        
        return result
    
    def compute_lag_matrix(
        self,
        df: pd.DataFrame,
        regions: List[str] = None
    ) -> Dict[Tuple[str, str], LagResult]:
        """
        Oblicza macierz lag-ów dla wszystkich par regionów.
        
        Args:
            df: DataFrame z kolumnami dla każdego regionu
            regions: Lista regionów do analizy (domyślnie wszystkie kolumny)
            
        Returns:
            Słownik (region_a, region_b) -> LagResult
        """
        if regions is None:
            regions = list(df.columns)
        
        lag_matrix = {}
        
        for i, region_a in enumerate(regions):
            for region_b in regions[i+1:]:
                result = self.detect_lag(df, region_a, region_b)
                if result:
                    lag_matrix[(region_a, region_b)] = result
                    # Dodaj też odwrotną relację
                    lag_matrix[(region_b, region_a)] = LagResult(
                        region_a=region_b,
                        region_b=region_a,
                        optimal_lag=-result.optimal_lag,
                        correlation=result.correlation,
                        direction=PropagationDirection.LAGS if result.direction == PropagationDirection.LEADS else 
                                  PropagationDirection.LEADS if result.direction == PropagationDirection.LAGS else
                                  PropagationDirection.SYNCHRONOUS,
                        confidence=result.confidence,
                        lag_hours=-result.lag_hours
                    )
        
        logger.info(f"Obliczono {len(lag_matrix)} par lag-ów")
        return lag_matrix
    
    def find_leader_region(
        self,
        lag_matrix: Dict[Tuple[str, str], LagResult],
        regions: List[str] = None
    ) -> Tuple[str, float]:
        """
        Znajduje region, który najczęściej "prowadzi" (wyprzedza inne).
        
        Args:
            lag_matrix: Macierz lag-ów z compute_lag_matrix()
            regions: Lista regionów do analizy
            
        Returns:
            (najlepszy_region, średni_lead_time_w_godzinach)
        """
        if regions is None:
            regions = list(set([k[0] for k in lag_matrix.keys()]))
        
        # Policz ile razy każdy region prowadzi
        lead_scores = {region: [] for region in regions}
        
        for (a, b), result in lag_matrix.items():
            if result.direction == PropagationDirection.LEADS and result.confidence > 0.5:
                lead_scores[a].append(abs(result.lag_hours))
        
        # Oblicz średni lead time dla każdego regionu
        region_scores = {}
        for region, leads in lead_scores.items():
            if leads:
                region_scores[region] = np.mean(leads)
            else:
                region_scores[region] = 0
        
        # Znajdź lidera
        if not region_scores:
            return ("", 0.0)
        
        leader = max(region_scores, key=region_scores.get)
        avg_lead = region_scores[leader]
        
        logger.info(f"Leader region: {leader} (średnio wyprzedza o {avg_lead:.1f}h)")
        return (leader, avg_lead)
    
    def detect_sentiment_waves(
        self,
        df: pd.DataFrame,
        threshold_std: float = 2.0,
        min_affected_regions: int = 2
    ) -> List[PropagationWave]:
        """
        Wykrywa "fale" sentymentu - nagłe zmiany propagujące się między regionami.
        
        Args:
            df: DataFrame z kolumnami dla każdego regionu
            threshold_std: Próg w odchyleniach standardowych dla wykrycia zmiany
            min_affected_regions: Minimalna liczba regionów dotkniętych falą
            
        Returns:
            Lista wykrytych fal propagacji
        """
        regions = list(df.columns)
        waves = []
        
        # Oblicz zmiany (diff) i znormalizuj
        changes = df.diff()
        
        for region in regions:
            series = changes[region].dropna()
            if len(series) < 10:
                continue
            
            mean_change = series.mean()
            std_change = series.std()
            
            # Znajdź anomalie (duże zmiany)
            threshold = mean_change + threshold_std * std_change
            anomalies = series[abs(series) > abs(threshold)]
            
            for timestamp, change in anomalies.items():
                # Sprawdź czy podobna zmiana wystąpiła w innych regionach
                affected = [region]
                arrival_times = {region: 0.0}
                
                # Szukaj w oknie ±24h
                window_start = timestamp - timedelta(hours=24)
                window_end = timestamp + timedelta(hours=24)
                
                for other_region in regions:
                    if other_region == region:
                        continue
                    
                    other_series = changes[other_region]
                    window_data = other_series[window_start:window_end]
                    
                    # Czy jest podobna zmiana (ten sam znak)?
                    same_sign_changes = window_data[np.sign(window_data) == np.sign(change)]
                    
                    if len(same_sign_changes) > 0:
                        # Znajdź najbliższą zmianę
                        closest_idx = same_sign_changes.index[0]
                        time_diff = (closest_idx - timestamp).total_seconds() / 3600
                        
                        if abs(time_diff) < 24:  # W ciągu 24h
                            affected.append(other_region)
                            arrival_times[other_region] = time_diff
                
                # Zapisz falę jeśli dotknęła wystarczająco dużo regionów
                if len(affected) >= min_affected_regions:
                    # Sortuj affected według czasu dotarcia
                    sorted_regions = sorted(arrival_times.keys(), key=lambda x: arrival_times[x])
                    
                    wave = PropagationWave(
                        origin_region=region,
                        wave_time=timestamp,
                        affected_regions=sorted_regions,
                        arrival_times=arrival_times,
                        sentiment_change=float(change),
                        strength=min(1.0, abs(change) / (threshold * 2))
                    )
                    waves.append(wave)
        
        # Usuń duplikaty (fale wykryte z różnych regionów)
        unique_waves = self._deduplicate_waves(waves)
        
        logger.info(f"Wykryto {len(unique_waves)} unikalnych fal sentymentu")
        return unique_waves
    
    def _deduplicate_waves(
        self,
        waves: List[PropagationWave],
        time_threshold_hours: float = 6.0
    ) -> List[PropagationWave]:
        """Usuwa duplikaty fal (wykryte z różnych regionów)."""
        if not waves:
            return []
        
        # Sortuj po czasie
        waves = sorted(waves, key=lambda w: w.wave_time)
        
        unique = [waves[0]]
        for wave in waves[1:]:
            # Sprawdź czy to nie jest duplikat ostatniej fali
            last = unique[-1]
            time_diff = abs((wave.wave_time - last.wave_time).total_seconds() / 3600)
            
            if time_diff > time_threshold_hours:
                unique.append(wave)
            elif len(wave.affected_regions) > len(last.affected_regions):
                # Zamień na lepszą wersję
                unique[-1] = wave
        
        return unique
    
    def correlate_with_price(
        self,
        sentiment_df: pd.DataFrame,
        price_df: pd.DataFrame,
        region: str,
        price_column: str = "close",
        max_lag_hours: int = 48
    ) -> Dict[str, Any]:
        """
        Koreluje sentyment regionu z ceną BTC.
        
        Args:
            sentiment_df: DataFrame z sentymentem (kolumny = regiony)
            price_df: DataFrame z cenami (index = timestamp)
            region: Region do analizy
            price_column: Kolumna z ceną
            max_lag_hours: Maksymalny lag do sprawdzenia
            
        Returns:
            Słownik z wynikami korelacji
        """
        if region not in sentiment_df.columns:
            return {}
        
        # Resample obu serii do wspólnej częstotliwości
        sentiment = sentiment_df[region].resample("1H").mean()
        
        if price_column in price_df.columns:
            price = price_df[price_column].resample("1H").last()
            price_returns = price.pct_change()
        else:
            return {}
        
        # Znajdź wspólny zakres
        common_idx = sentiment.index.intersection(price_returns.index)
        
        if len(common_idx) < self.min_samples:
            return {}
        
        sentiment_aligned = sentiment.loc[common_idx].values
        returns_aligned = price_returns.loc[common_idx].values
        
        # Usuń NaN
        mask = ~(np.isnan(sentiment_aligned) | np.isnan(returns_aligned))
        sentiment_aligned = sentiment_aligned[mask]
        returns_aligned = returns_aligned[mask]
        
        if len(sentiment_aligned) < self.min_samples:
            return {}
        
        # Cross-correlation
        max_lag = int(max_lag_hours)
        correlations = []
        
        for lag in range(-max_lag, max_lag + 1):
            if lag < 0:
                # Sentiment wyprzedza cenę
                s = sentiment_aligned[:lag]
                r = returns_aligned[-lag:]
            elif lag > 0:
                # Cena wyprzedza sentiment
                s = sentiment_aligned[lag:]
                r = returns_aligned[:-lag]
            else:
                s = sentiment_aligned
                r = returns_aligned
            
            if len(s) < 10:
                correlations.append(0)
                continue
            
            corr, _ = pearsonr(s, r)
            correlations.append(corr if not np.isnan(corr) else 0)
        
        lags = list(range(-max_lag, max_lag + 1))
        
        # Znajdź optymalny lag
        max_idx = np.argmax(np.abs(correlations))
        optimal_lag = lags[max_idx]
        max_corr = correlations[max_idx]
        
        return {
            "region": region,
            "optimal_lag_hours": optimal_lag,
            "max_correlation": max_corr,
            "lags": lags,
            "correlations": correlations,
            "interpretation": (
                f"Sentiment z {region} {'wyprzedza' if optimal_lag < 0 else 'opóźniony względem'} "
                f"ceny o {abs(optimal_lag)}h (r={max_corr:.3f})"
            )
        }
    
    # === Wizualizacje ===
    
    def plot_lag_heatmap(
        self,
        lag_matrix: Dict[Tuple[str, str], LagResult],
        regions: List[str] = None,
        save_path: str = None
    ):
        """
        Rysuje heatmapę lag-ów między regionami.
        
        Args:
            lag_matrix: Macierz lag-ów
            regions: Lista regionów
            save_path: Ścieżka do zapisu (opcjonalnie)
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib niedostępny - pomijam wizualizację")
            return
        
        if regions is None:
            regions = sorted(list(set([k[0] for k in lag_matrix.keys()])))
        
        n = len(regions)
        matrix = np.zeros((n, n))
        
        for i, a in enumerate(regions):
            for j, b in enumerate(regions):
                if (a, b) in lag_matrix:
                    matrix[i, j] = lag_matrix[(a, b)].lag_hours
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        im = ax.imshow(matrix, cmap='RdBu_r', aspect='auto', vmin=-24, vmax=24)
        
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(regions)
        ax.set_yticklabels(regions)
        
        plt.colorbar(im, label='Lag (hours)')
        
        ax.set_title('Sentiment Propagation Lag Matrix\n(negative = row leads column)')
        ax.set_xlabel('Region B')
        ax.set_ylabel('Region A')
        
        # Dodaj wartości na heatmapie
        for i in range(n):
            for j in range(n):
                if i != j:
                    ax.text(j, i, f'{matrix[i, j]:.1f}', ha='center', va='center', fontsize=8)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Zapisano: {save_path}")
        
        return fig
    
    def plot_timeseries_comparison(
        self,
        df: pd.DataFrame,
        regions: List[str] = None,
        title: str = "Sentiment Timeseries by Region",
        save_path: str = None
    ):
        """
        Rysuje porównanie szeregów czasowych sentymentu.
        
        Args:
            df: DataFrame z kolumnami dla regionów
            regions: Lista regionów do wyświetlenia
            title: Tytuł wykresu
            save_path: Ścieżka do zapisu
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib niedostępny")
            return
        
        if regions is None:
            regions = list(df.columns)[:6]  # Max 6 dla czytelności
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        colors = plt.cm.tab10(np.linspace(0, 1, len(regions)))
        
        for region, color in zip(regions, colors):
            if region in df.columns:
                ax.plot(df.index, df[region], label=region, color=color, alpha=0.8)
        
        ax.set_xlabel('Time')
        ax.set_ylabel('Sentiment (tone)')
        ax.set_title(title)
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        # Format osi X
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        
        return fig
    
    def plot_wave_propagation(
        self,
        wave: PropagationWave,
        save_path: str = None
    ):
        """
        Wizualizuje propagację pojedynczej fali sentymentu.
        
        Args:
            wave: Obiekt PropagationWave
            save_path: Ścieżka do zapisu
        """
        if not MATPLOTLIB_AVAILABLE:
            return
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        regions = wave.affected_regions
        times = [wave.arrival_times[r] for r in regions]
        
        # Kolory na podstawie czasu
        colors = plt.cm.coolwarm(np.linspace(0, 1, len(regions)))
        
        bars = ax.barh(regions, times, color=colors)
        
        ax.axvline(x=0, color='black', linestyle='--', label='Origin')
        ax.set_xlabel('Time from origin (hours)')
        ax.set_title(f'Sentiment Wave Propagation\nOrigin: {wave.origin_region} at {wave.wave_time}')
        
        # Dodaj wartości na słupkach
        for bar, time in zip(bars, times):
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                   f'{time:+.1f}h', va='center', fontsize=9)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        
        return fig
    
    def generate_report(
        self,
        df: pd.DataFrame,
        price_df: pd.DataFrame = None
    ) -> str:
        """
        Generuje tekstowy raport z analizy propagacji.
        
        Args:
            df: DataFrame z sentymentem
            price_df: DataFrame z cenami (opcjonalnie)
            
        Returns:
            Raport jako string
        """
        regions = list(df.columns)
        
        report = []
        report.append("=" * 60)
        report.append("SENTIMENT PROPAGATION ANALYSIS REPORT")
        report.append("=" * 60)
        report.append(f"\nAnalyzed period: {df.index.min()} to {df.index.max()}")
        report.append(f"Regions: {', '.join(regions)}")
        report.append(f"Data points: {len(df)}")
        
        # Statystyki sentymentu
        report.append("\n" + "-" * 40)
        report.append("SENTIMENT STATISTICS BY REGION")
        report.append("-" * 40)
        
        for region in regions:
            mean_val = df[region].mean()
            std_val = df[region].std()
            report.append(f"  {region}: mean={mean_val:+.2f}, std={std_val:.2f}")
        
        # Lag matrix
        report.append("\n" + "-" * 40)
        report.append("LAG ANALYSIS")
        report.append("-" * 40)
        
        lag_matrix = self.compute_lag_matrix(df, regions)
        
        significant_lags = [
            result for result in lag_matrix.values()
            if result.direction != PropagationDirection.SYNCHRONOUS
            and result.confidence > 0.5
        ]
        
        if significant_lags:
            for result in sorted(significant_lags, key=lambda x: -x.confidence)[:10]:
                report.append(f"  {result}")
        else:
            report.append("  No significant lags detected")
        
        # Leader
        leader, avg_lead = self.find_leader_region(lag_matrix, regions)
        report.append(f"\n  LEADER REGION: {leader} (avg lead: {avg_lead:.1f}h)")
        
        # Fale
        report.append("\n" + "-" * 40)
        report.append("DETECTED SENTIMENT WAVES")
        report.append("-" * 40)
        
        waves = self.detect_sentiment_waves(df)
        
        if waves:
            for i, wave in enumerate(waves[:5], 1):
                report.append(f"\n  Wave {i}:")
                report.append(f"    Origin: {wave.origin_region} at {wave.wave_time}")
                report.append(f"    Affected: {' -> '.join(wave.affected_regions)}")
                report.append(f"    Sentiment change: {wave.sentiment_change:+.2f}")
        else:
            report.append("  No significant waves detected")
        
        # Korelacja z ceną
        if price_df is not None and not price_df.empty:
            report.append("\n" + "-" * 40)
            report.append("PRICE CORRELATION")
            report.append("-" * 40)
            
            for region in regions[:3]:  # Top 3
                result = self.correlate_with_price(df, price_df, region)
                if result:
                    report.append(f"  {result['interpretation']}")
        
        report.append("\n" + "=" * 60)
        report.append("END OF REPORT")
        report.append("=" * 60)
        
        return "\n".join(report)


# === Przykład użycia ===
if __name__ == "__main__":
    import sys
    
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    print("\n" + "="*60)
    print("🌊 SENTIMENT PROPAGATION ANALYZER - DEMO")
    print("="*60)
    
    # Generuj syntetyczne dane do demonstracji
    print("\n📊 Generuję syntetyczne dane do demonstracji...")
    
    np.random.seed(42)
    
    # Symulacja: US prowadzi, CN opóźnione o 6h, JP opóźnione o 3h
    hours = 168  # 7 dni
    timestamps = pd.date_range(start="2024-01-01", periods=hours, freq="H")
    
    # Bazowy sygnał (np. reakcja na news)
    base_signal = np.cumsum(np.random.randn(hours) * 0.5)
    
    # Dodaj "event" w połowie
    base_signal[84:90] += 5  # Pozytywny event
    
    # Regiony z różnymi opóźnieniami
    data = {
        "US": base_signal + np.random.randn(hours) * 0.3,
        "CN": np.roll(base_signal, 6) + np.random.randn(hours) * 0.4,  # 6h lag
        "JP": np.roll(base_signal, 3) + np.random.randn(hours) * 0.35,  # 3h lag
        "DE": np.roll(base_signal, 2) + np.random.randn(hours) * 0.3,   # 2h lag
        "KR": np.roll(base_signal, 4) + np.random.randn(hours) * 0.35,  # 4h lag
    }
    
    df = pd.DataFrame(data, index=timestamps)
    
    print(f"   Wygenerowano dane dla {len(df.columns)} regionów, {len(df)} godzin")
    
    # Inicjalizacja analizatora
    analyzer = SentimentPropagationAnalyzer(
        time_resolution_hours=1.0,
        max_lag_hours=24
    )
    
    # Test 1: Pojedynczy lag
    print("\n🔍 Test 1: Wykrywanie lag-u US -> CN")
    lag_result = analyzer.detect_lag(df, "US", "CN")
    if lag_result:
        print(f"   {lag_result}")
        print(f"   Oczekiwany lag: ~6h, wykryty: {lag_result.lag_hours:.1f}h")
    
    # Test 2: Pełna macierz
    print("\n🔢 Test 2: Macierz lag-ów")
    lag_matrix = analyzer.compute_lag_matrix(df)
    
    print("   Top 5 par z największym lag-iem:")
    sorted_pairs = sorted(
        [(k, v) for k, v in lag_matrix.items() if v.direction == PropagationDirection.LEADS],
        key=lambda x: -abs(x[1].lag_hours)
    )
    for (a, b), result in sorted_pairs[:5]:
        print(f"   {a} leads {b} by {result.lag_hours:.1f}h (r={result.correlation:.3f})")
    
    # Test 3: Leader region
    print("\n👑 Test 3: Region lider")
    leader, avg_lead = analyzer.find_leader_region(lag_matrix)
    print(f"   Leader: {leader} (średnio wyprzedza o {avg_lead:.1f}h)")
    
    # Test 4: Fale
    print("\n🌊 Test 4: Wykrywanie fal sentymentu")
    waves = analyzer.detect_sentiment_waves(df, threshold_std=1.5)
    print(f"   Wykryto {len(waves)} fal")
    
    if waves:
        wave = waves[0]
        print(f"   Pierwsza fala:")
        print(f"     Origin: {wave.origin_region} at {wave.wave_time}")
        print(f"     Propagacja: {' -> '.join(wave.affected_regions)}")
    
    # Test 5: Raport
    print("\n📄 Test 5: Generowanie raportu")
    report = analyzer.generate_report(df)
    print("\n" + report)
    
    # Wizualizacje (jeśli matplotlib dostępny)
    if MATPLOTLIB_AVAILABLE:
        print("\n📈 Generuję wizualizacje...")
        
        # Timeseries
        fig1 = analyzer.plot_timeseries_comparison(df, title="Synthetic Sentiment Data")
        fig1.savefig("/tmp/sentiment_timeseries.png", dpi=150)
        print("   Zapisano: /tmp/sentiment_timeseries.png")
        
        # Heatmap
        fig2 = analyzer.plot_lag_heatmap(lag_matrix)
        fig2.savefig("/tmp/lag_heatmap.png", dpi=150)
        print("   Zapisano: /tmp/lag_heatmap.png")
        
        if waves:
            fig3 = analyzer.plot_wave_propagation(waves[0])
            fig3.savefig("/tmp/wave_propagation.png", dpi=150)
            print("   Zapisano: /tmp/wave_propagation.png")
    
    print("\n" + "="*60)
    print("✅ Demo zakończone!")
    print("="*60)
