"""
Timezone-Aware Sentiment Analysis
=================================
Rozszerzenie analizatora o uwzględnienie:
- Stref czasowych każdego regionu
- "Aktywnych okien" (kiedy ludzie czytają/reagują na newsy)
- Rozróżnienie między "lag propagacji" a "lag aktywności"

Kluczowy insight:
- Wiadomość o 15:00 EST (USA) = 04:00 CST (Chiny) 
- Chińczycy śpią, więc reakcja będzie dopiero o 08:00-09:00 CST
- To nie jest "6h propagacji", tylko "lag spania"
- Rzeczywista propagacja może być natychmiastowa gdy ludzie się obudzą
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone, time
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import pytz
from loguru import logger


@dataclass
class RegionConfig:
    """Konfiguracja regionu z informacjami o strefie czasowej i aktywności."""
    code: str                    # Kod kraju (US, CN, JP, etc.)
    name: str                    # Pełna nazwa
    timezone: str                # Strefa czasowa (pytz)
    
    # Aktywne okna - godziny lokalne kiedy ludzie czytają newsy/tradują
    trading_hours_start: int     # Godzina rozpoczęcia (0-23)
    trading_hours_end: int       # Godzina zakończenia (0-23)
    
    # Peak activity - najbardziej aktywne godziny
    peak_start: int
    peak_end: int
    
    # Weekendy - czy region jest aktywny w weekendy (crypto = tak, ale mniej)
    weekend_activity: float      # 0.0-1.0 (1.0 = pełna aktywność)


# Predefiniowane konfiguracje regionów
REGION_CONFIGS = {
    "US": RegionConfig(
        code="US", name="United States",
        timezone="America/New_York",
        trading_hours_start=6, trading_hours_end=23,  # 6 AM - 11 PM EST
        peak_start=9, peak_end=17,  # 9 AM - 5 PM (trading hours)
        weekend_activity=0.6
    ),
    "GB": RegionConfig(
        code="GB", name="United Kingdom",
        timezone="Europe/London",
        trading_hours_start=7, trading_hours_end=23,
        peak_start=8, peak_end=17,
        weekend_activity=0.5
    ),
    "DE": RegionConfig(
        code="DE", name="Germany",
        timezone="Europe/Berlin",
        trading_hours_start=7, trading_hours_end=23,
        peak_start=9, peak_end=18,
        weekend_activity=0.5
    ),
    "JP": RegionConfig(
        code="JP", name="Japan",
        timezone="Asia/Tokyo",
        trading_hours_start=7, trading_hours_end=23,
        peak_start=9, peak_end=18,
        weekend_activity=0.7  # Japończycy aktywni w weekendy
    ),
    "KR": RegionConfig(
        code="KR", name="South Korea",
        timezone="Asia/Seoul",
        trading_hours_start=7, trading_hours_end=24,  # Koreańczycy tradują do późna
        peak_start=9, peak_end=22,
        weekend_activity=0.8  # Bardzo aktywni w weekendy
    ),
    "CN": RegionConfig(
        code="CN", name="China",
        timezone="Asia/Shanghai",
        trading_hours_start=7, trading_hours_end=23,
        peak_start=9, peak_end=18,
        weekend_activity=0.6
    ),
    "RU": RegionConfig(
        code="RU", name="Russia",
        timezone="Europe/Moscow",
        trading_hours_start=7, trading_hours_end=23,
        peak_start=10, peak_end=19,
        weekend_activity=0.5
    ),
    "SG": RegionConfig(
        code="SG", name="Singapore",
        timezone="Asia/Singapore",
        trading_hours_start=7, trading_hours_end=23,
        peak_start=9, peak_end=18,
        weekend_activity=0.6
    ),
    "AU": RegionConfig(
        code="AU", name="Australia",
        timezone="Australia/Sydney",
        trading_hours_start=6, trading_hours_end=22,
        peak_start=9, peak_end=17,
        weekend_activity=0.5
    ),
}


class ActivityType(Enum):
    """Typ aktywności w danym momencie."""
    SLEEPING = "sleeping"        # 0:00 - 6:00 (noc)
    LOW = "low"                  # Poza godzinami tradingu
    NORMAL = "normal"            # Godziny tradingu
    PEAK = "peak"                # Szczyt aktywności


@dataclass
class TimezoneAwareLag:
    """Wynik analizy lag-u z uwzględnieniem stref czasowych."""
    region_a: str
    region_b: str
    
    # Surowy lag (bez uwzględnienia stref czasowych)
    raw_lag_hours: float
    
    # Skorygowany lag (uwzględniający aktywne okna)
    adjusted_lag_hours: float
    
    # Czy lag wynika głównie z różnicy stref czasowych?
    timezone_driven: bool
    
    # Czas potrzebny na "przebudzenie" regionu B
    wakeup_delay_hours: float
    
    # Rzeczywista prędkość propagacji (po odjęciu wakeup delay)
    true_propagation_hours: float
    
    # Korelacja
    correlation: float
    
    def __repr__(self):
        if self.timezone_driven:
            return (f"<TZLag: {self.region_a}→{self.region_b} "
                   f"raw={self.raw_lag_hours:.1f}h, "
                   f"wakeup={self.wakeup_delay_hours:.1f}h, "
                   f"true={self.true_propagation_hours:.1f}h (TZ-driven)>")
        else:
            return (f"<TZLag: {self.region_a}→{self.region_b} "
                   f"lag={self.adjusted_lag_hours:.1f}h (real propagation)>")


class TimezoneAwareAnalyzer:
    """
    Analizator sentymentu uwzględniający strefy czasowe.
    
    Rozróżnia:
    1. LAG PROPAGACJI - czas potrzebny na dotarcie informacji
    2. LAG AKTYWNOŚCI - czas czekania aż ludzie się obudzą/będą online
    
    Przykład:
        News o 15:00 EST (US):
        - GB: 20:00 GMT - ludzie online, reakcja natychmiastowa
        - JP: 05:00 JST - ludzie śpią, reakcja za ~4h (o 09:00)
        - CN: 04:00 CST - ludzie śpią, reakcja za ~5h (o 09:00)
    """
    
    def __init__(self, region_configs: Dict[str, RegionConfig] = None):
        """
        Inicjalizuje analizator.
        
        Args:
            region_configs: Konfiguracje regionów (domyślnie REGION_CONFIGS)
        """
        self.configs = region_configs or REGION_CONFIGS
        logger.info(f"TimezoneAwareAnalyzer: {len(self.configs)} regionów")
    
    def get_local_time(self, utc_time: datetime, region: str) -> datetime:
        """Konwertuje czas UTC na czas lokalny regionu."""
        config = self.configs.get(region)
        if not config:
            return utc_time
        
        tz = pytz.timezone(config.timezone)
        if utc_time.tzinfo is None:
            utc_time = pytz.utc.localize(utc_time)
        return utc_time.astimezone(tz)
    
    def get_activity_type(self, utc_time: datetime, region: str) -> ActivityType:
        """
        Określa typ aktywności w danym regionie o danej godzinie.
        
        Args:
            utc_time: Czas UTC
            region: Kod regionu
            
        Returns:
            ActivityType
        """
        config = self.configs.get(region)
        if not config:
            return ActivityType.NORMAL
        
        local_time = self.get_local_time(utc_time, region)
        hour = local_time.hour
        
        # Noc (śpią)
        if hour < 6:
            return ActivityType.SLEEPING
        
        # Sprawdź weekend
        is_weekend = local_time.weekday() >= 5
        if is_weekend and config.weekend_activity < 0.5:
            return ActivityType.LOW
        
        # Peak hours
        if config.peak_start <= hour < config.peak_end:
            return ActivityType.PEAK
        
        # Trading hours
        if config.trading_hours_start <= hour < config.trading_hours_end:
            return ActivityType.NORMAL
        
        return ActivityType.LOW
    
    def get_activity_score(self, utc_time: datetime, region: str) -> float:
        """
        Zwraca score aktywności (0.0 - 1.0) dla danego regionu i czasu.
        
        Args:
            utc_time: Czas UTC
            region: Kod regionu
            
        Returns:
            Float 0.0-1.0
        """
        activity = self.get_activity_type(utc_time, region)
        
        scores = {
            ActivityType.SLEEPING: 0.1,
            ActivityType.LOW: 0.3,
            ActivityType.NORMAL: 0.7,
            ActivityType.PEAK: 1.0
        }
        
        return scores.get(activity, 0.5)
    
    def calculate_wakeup_delay(
        self,
        event_time_utc: datetime,
        region: str
    ) -> float:
        """
        Oblicza ile godzin musi minąć zanim region "się obudzi".
        
        Args:
            event_time_utc: Czas wydarzenia (UTC)
            region: Kod regionu
            
        Returns:
            Liczba godzin do osiągnięcia aktywności NORMAL/PEAK
        """
        config = self.configs.get(region)
        if not config:
            return 0.0
        
        local_time = self.get_local_time(event_time_utc, region)
        hour = local_time.hour
        
        # Jeśli już aktywni - brak opóźnienia
        if config.trading_hours_start <= hour < config.trading_hours_end:
            return 0.0
        
        # Oblicz ile godzin do początku trading hours
        if hour < config.trading_hours_start:
            return config.trading_hours_start - hour
        else:
            # Po trading hours - czekamy do następnego dnia
            return (24 - hour) + config.trading_hours_start
    
    def calculate_timezone_aware_lag(
        self,
        sentiment_df: pd.DataFrame,
        region_a: str,
        region_b: str,
        raw_lag_hours: float,
        correlation: float
    ) -> TimezoneAwareLag:
        """
        Oblicza lag z uwzględnieniem stref czasowych.
        
        Args:
            sentiment_df: DataFrame z danymi sentymentu
            region_a: Region źródłowy
            region_b: Region docelowy
            raw_lag_hours: Surowy lag zmierzony przez cross-correlation
            correlation: Korelacja
            
        Returns:
            TimezoneAwareLag
        """
        # Znajdź typowy czas eventów w region_a
        # (używamy środka danych jako reprezentatywnego przykładu)
        mid_idx = len(sentiment_df) // 2
        sample_time = sentiment_df.index[mid_idx]
        if sample_time.tzinfo is None:
            sample_time = pytz.utc.localize(sample_time)
        
        # Oblicz wakeup delay dla region_b
        wakeup_delay = self.calculate_wakeup_delay(sample_time, region_b)
        
        # Oblicz średni wakeup delay dla różnych godzin dnia
        delays = []
        for hour in range(24):
            test_time = sample_time.replace(hour=hour)
            delays.append(self.calculate_wakeup_delay(test_time, region_b))
        avg_wakeup_delay = np.mean(delays)
        
        # Rzeczywista propagacja = surowy lag - wakeup delay
        true_propagation = max(0, abs(raw_lag_hours) - avg_wakeup_delay)
        
        # Czy lag jest głównie timezone-driven?
        # Jeśli wakeup delay stanowi >50% surowego lagu, to tak
        timezone_driven = avg_wakeup_delay > abs(raw_lag_hours) * 0.5
        
        # Skorygowany lag
        adjusted_lag = true_propagation if raw_lag_hours >= 0 else -true_propagation
        
        return TimezoneAwareLag(
            region_a=region_a,
            region_b=region_b,
            raw_lag_hours=raw_lag_hours,
            adjusted_lag_hours=adjusted_lag,
            timezone_driven=timezone_driven,
            wakeup_delay_hours=avg_wakeup_delay,
            true_propagation_hours=true_propagation,
            correlation=correlation
        )
    
    def analyze_propagation_windows(
        self,
        event_time_utc: datetime,
        source_region: str = "US"
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analizuje okna propagacji dla wszystkich regionów.
        
        Dla danego wydarzenia w source_region, pokazuje:
        - Czas lokalny w każdym regionie
        - Czy ludzie są aktywni
        - Oczekiwane opóźnienie reakcji
        
        Args:
            event_time_utc: Czas wydarzenia (UTC)
            source_region: Region źródłowy
            
        Returns:
            Dict z analizą dla każdego regionu
        """
        if event_time_utc.tzinfo is None:
            event_time_utc = pytz.utc.localize(event_time_utc)
        
        analysis = {}
        
        for region, config in self.configs.items():
            local_time = self.get_local_time(event_time_utc, region)
            activity = self.get_activity_type(event_time_utc, region)
            wakeup_delay = self.calculate_wakeup_delay(event_time_utc, region)
            
            analysis[region] = {
                "local_time": local_time.strftime("%Y-%m-%d %H:%M"),
                "local_hour": local_time.hour,
                "activity": activity.value,
                "activity_score": self.get_activity_score(event_time_utc, region),
                "wakeup_delay_hours": wakeup_delay,
                "expected_reaction_time": (
                    event_time_utc + timedelta(hours=wakeup_delay)
                ).strftime("%H:%M UTC"),
                "is_sleeping": activity == ActivityType.SLEEPING,
                "is_peak": activity == ActivityType.PEAK,
            }
        
        return analysis
    
    def get_best_propagation_times(
        self,
        source_region: str = "US",
        target_region: str = "CN"
    ) -> List[Dict[str, Any]]:
        """
        Znajduje najlepsze godziny na propagację między regionami.
        
        Szuka okien czasowych gdy OBA regiony są aktywne.
        
        Args:
            source_region: Region źródłowy
            target_region: Region docelowy
            
        Returns:
            Lista najlepszych okien czasowych
        """
        windows = []
        
        # Sprawdź każdą godzinę dnia
        base_date = datetime.now(pytz.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        for hour in range(24):
            test_time = base_date + timedelta(hours=hour)
            
            source_activity = self.get_activity_score(test_time, source_region)
            target_activity = self.get_activity_score(test_time, target_region)
            
            # Oba regiony aktywne?
            combined_score = source_activity * target_activity
            
            if combined_score >= 0.5:  # Oba co najmniej NORMAL
                source_local = self.get_local_time(test_time, source_region)
                target_local = self.get_local_time(test_time, target_region)
                
                windows.append({
                    "utc_hour": hour,
                    f"{source_region}_local": source_local.strftime("%H:%M"),
                    f"{target_region}_local": target_local.strftime("%H:%M"),
                    "combined_score": combined_score,
                    "source_activity": self.get_activity_type(test_time, source_region).value,
                    "target_activity": self.get_activity_type(test_time, target_region).value,
                })
        
        # Sortuj po combined_score
        windows.sort(key=lambda x: -x["combined_score"])
        
        return windows
    
    def add_activity_features(
        self,
        df: pd.DataFrame,
        regions: List[str] = None
    ) -> pd.DataFrame:
        """
        Dodaje kolumny z informacjami o aktywności do DataFrame.
        
        Args:
            df: DataFrame z timestampem jako index
            regions: Lista regionów
            
        Returns:
            DataFrame z dodatkowymi kolumnami
        """
        if regions is None:
            regions = list(self.configs.keys())
        
        df = df.copy()
        
        for region in regions:
            if region not in self.configs:
                continue
            
            # Dodaj kolumny
            activity_scores = []
            is_sleeping = []
            is_peak = []
            
            for ts in df.index:
                if ts.tzinfo is None:
                    ts = pytz.utc.localize(ts)
                
                activity_scores.append(self.get_activity_score(ts, region))
                activity_type = self.get_activity_type(ts, region)
                is_sleeping.append(activity_type == ActivityType.SLEEPING)
                is_peak.append(activity_type == ActivityType.PEAK)
            
            df[f"{region}_activity"] = activity_scores
            df[f"{region}_sleeping"] = is_sleeping
            df[f"{region}_peak"] = is_peak
        
        return df
    
    def calculate_weighted_sentiment(
        self,
        df: pd.DataFrame,
        region: str,
        weight_by_activity: bool = True
    ) -> pd.Series:
        """
        Oblicza ważony sentyment, dając większą wagę okresom wysokiej aktywności.
        
        Args:
            df: DataFrame z sentymentem i activity features
            region: Region
            weight_by_activity: Czy ważyć przez aktywność
            
        Returns:
            Series z ważonym sentymentem
        """
        if region not in df.columns:
            return pd.Series()
        
        sentiment = df[region]
        
        if weight_by_activity and f"{region}_activity" in df.columns:
            weights = df[f"{region}_activity"]
            # Normalizuj wagi
            weights = weights / weights.sum()
            return sentiment * weights
        
        return sentiment


def print_propagation_analysis(
    event_time_utc: datetime,
    source_region: str = "US"
):
    """Drukuje czytelną analizę propagacji."""
    
    analyzer = TimezoneAwareAnalyzer()
    analysis = analyzer.analyze_propagation_windows(event_time_utc, source_region)
    
    print("\n" + "="*70)
    print(f"🌍 ANALIZA PROPAGACJI - Event @ {event_time_utc.strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"   Źródło: {source_region}")
    print("="*70)
    
    # Sortuj po expected reaction time
    sorted_regions = sorted(
        analysis.items(),
        key=lambda x: x[1]["wakeup_delay_hours"]
    )
    
    for region, info in sorted_regions:
        status = ""
        if info["is_sleeping"]:
            status = "😴 ŚPIĄ"
        elif info["is_peak"]:
            status = "🔥 PEAK"
        else:
            status = "👁️ ONLINE"
        
        delay = info["wakeup_delay_hours"]
        delay_str = f"+{delay:.0f}h" if delay > 0 else "TERAZ"
        
        bar = "█" * int(info["activity_score"] * 10)
        
        print(f"   {region}: {info['local_time']} | {status:10} | Reakcja: {delay_str:6} | [{bar:10}]")
    
    print("\n" + "-"*70)
    print("💡 WNIOSKI:")
    
    sleeping_regions = [r for r, i in analysis.items() if i["is_sleeping"]]
    active_regions = [r for r, i in analysis.items() if not i["is_sleeping"]]
    
    if sleeping_regions:
        print(f"   ⏰ Regiony śpiące: {', '.join(sleeping_regions)}")
        print(f"   → Reakcja z tych regionów będzie OPÓŹNIONA o czas 'przebudzenia'")
    
    if active_regions:
        print(f"   ✅ Regiony aktywne: {', '.join(active_regions)}")
        print(f"   → Reakcja natychmiastowa lub z minimalnym opóźnieniem")


# === Demo ===
if __name__ == "__main__":
    import sys
    from loguru import logger
    
    logger.remove()
    logger.add(sys.stderr, level='INFO', format='{time:HH:mm:ss} | {level} | {message}')
    
    print("="*70)
    print("🌍 TIMEZONE-AWARE SENTIMENT ANALYSIS - DEMO")
    print("="*70)
    
    analyzer = TimezoneAwareAnalyzer()
    
    # Scenariusz 1: Wiadomość w USA o 15:00 EST (20:00 UTC)
    print("\n📰 SCENARIUSZ 1: News w USA o 15:00 EST (20:00 UTC)")
    event1 = datetime(2024, 6, 15, 20, 0, 0, tzinfo=pytz.utc)
    print_propagation_analysis(event1, "US")
    
    # Scenariusz 2: Wiadomość w USA o 3:00 EST (08:00 UTC)
    print("\n📰 SCENARIUSZ 2: News w USA o 03:00 EST (08:00 UTC) - noc w USA")
    event2 = datetime(2024, 6, 15, 8, 0, 0, tzinfo=pytz.utc)
    print_propagation_analysis(event2, "US")
    
    # Scenariusz 3: Wiadomość z Chin
    print("\n📰 SCENARIUSZ 3: News z CHIN o 10:00 CST (02:00 UTC)")
    event3 = datetime(2024, 6, 15, 2, 0, 0, tzinfo=pytz.utc)
    print_propagation_analysis(event3, "CN")
    
    # Najlepsze okna propagacji
    print("\n" + "="*70)
    print("🕐 NAJLEPSZE OKNA PROPAGACJI US → CN")
    print("="*70)
    
    windows = analyzer.get_best_propagation_times("US", "CN")
    print("\n   Godziny gdy OBA regiony są aktywne:")
    for w in windows[:5]:
        print(f"   {w['utc_hour']:02d}:00 UTC | US: {w['US_local']} | CN: {w['CN_local']} | Score: {w['combined_score']:.2f}")
    
    print("\n" + "="*70)
    print("✅ Demo zakończone!")
    print("="*70)
