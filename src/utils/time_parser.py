"""
Time Parser
===========
Parser czasu dla parametrów CLI (10h, 20min, 30sek, 10h 20min 30sek).
"""

import re
from typing import Optional


class TimeParseError(Exception):
    """Błąd parsowania czasu."""
    pass


def parse_time_duration(time_str: str) -> int:
    """
    Parsuje czas w formacie czytelnym dla człowieka na sekundy.
    
    Obsługiwane formaty:
    - "10h" -> 36000 sekund
    - "30min" -> 1800 sekund
    - "45sek" -> 45 sekund
    - "45s" -> 45 sekund
    - "10h 30min" -> 37800 sekund
    - "2h 15min 30sek" -> 8130 sekund
    - "1d" -> 86400 sekund
    - "1w" -> 604800 sekund
    
    Args:
        time_str: String z czasem
        
    Returns:
        Liczba sekund
        
    Raises:
        TimeParseError: Jeśli format jest nieprawidłowy
    """
    if not time_str or not isinstance(time_str, str):
        raise TimeParseError(f"Nieprawidłowy format czasu: {time_str}")
    
    time_str = time_str.strip().lower()
    
    # Mapowanie jednostek na sekundy
    units = {
        's': 1,
        'sec': 1,
        'sek': 1,
        'second': 1,
        'seconds': 1,
        
        'm': 60,
        'min': 60,
        'minute': 60,
        'minutes': 60,
        
        'h': 3600,
        'hour': 3600,
        'hours': 3600,
        'godzina': 3600,
        'godzin': 3600,
        'godziny': 3600,
        
        'd': 86400,
        'day': 86400,
        'days': 86400,
        'dzien': 86400,
        'dni': 86400,
        
        'w': 604800,
        'week': 604800,
        'weeks': 604800,
        'tydzien': 604800,
        'tygodnie': 604800,
    }
    
    # Pattern: liczba + jednostka (np. "10h", "30min")
    pattern = r'(\d+(?:\.\d+)?)\s*([a-z]+)'
    
    matches = re.findall(pattern, time_str)
    
    if not matches:
        raise TimeParseError(
            f"Nie można sparsować czasu: '{time_str}'. "
            f"Użyj formatu: 10h, 30min, 45sek, lub kombinacji: 2h 30min 15sek"
        )
    
    total_seconds = 0
    
    for value_str, unit in matches:
        try:
            value = float(value_str)
        except ValueError:
            raise TimeParseError(f"Nieprawidłowa liczba: {value_str}")
        
        if unit not in units:
            raise TimeParseError(
                f"Nieznana jednostka czasu: '{unit}'. "
                f"Dostępne: {', '.join(sorted(set(units.keys())))}"
            )
        
        total_seconds += int(value * units[unit])
    
    if total_seconds <= 0:
        raise TimeParseError(f"Czas musi być większy od 0: {time_str}")
    
    return total_seconds


def format_duration(seconds: int) -> str:
    """
    Formatuje sekundy na czytelny format.
    
    Args:
        seconds: Liczba sekund
        
    Returns:
        Sformatowany czas (np. "2h 30min 15sek")
    """
    if seconds < 0:
        return "0s"
    
    units = [
        ('w', 604800),
        ('d', 86400),
        ('h', 3600),
        ('min', 60),
        ('sek', 1)
    ]
    
    parts = []
    remaining = seconds
    
    for unit_name, unit_seconds in units:
        if remaining >= unit_seconds:
            value = remaining // unit_seconds
            remaining = remaining % unit_seconds
            parts.append(f"{value}{unit_name}")
    
    if not parts:
        return "0sek"
    
    return " ".join(parts)


def validate_time_param(time_str: str, min_seconds: Optional[int] = None, 
                       max_seconds: Optional[int] = None) -> int:
    """
    Waliduje i parsuje parametr czasu.
    
    Args:
        time_str: String z czasem
        min_seconds: Minimalna liczba sekund (opcjonalnie)
        max_seconds: Maksymalna liczba sekund (opcjonalnie)
        
    Returns:
        Liczba sekund
        
    Raises:
        TimeParseError: Jeśli walidacja nie przejdzie
    """
    seconds = parse_time_duration(time_str)
    
    if min_seconds is not None and seconds < min_seconds:
        raise TimeParseError(
            f"Czas za krótki: {format_duration(seconds)} < {format_duration(min_seconds)}"
        )
    
    if max_seconds is not None and seconds > max_seconds:
        raise TimeParseError(
            f"Czas za długi: {format_duration(seconds)} > {format_duration(max_seconds)}"
        )
    
    return seconds


# Testy
if __name__ == "__main__":
    test_cases = [
        ("10h", 36000),
        ("30min", 1800),
        ("45sek", 45),
        ("45s", 45),
        ("10h 30min", 37800),
        ("2h 15min 30sek", 8130),
        ("1d", 86400),
        ("1w", 604800),
        ("2h 30min 45s", 9045),
    ]
    
    print("🧪 Testy parsera czasu:")
    for input_str, expected in test_cases:
        try:
            result = parse_time_duration(input_str)
            status = "✅" if result == expected else "❌"
            print(f"{status} '{input_str}' -> {result}s (oczekiwano: {expected}s)")
            if result == expected:
                print(f"   Format: {format_duration(result)}")
        except TimeParseError as e:
            print(f"❌ '{input_str}' -> ERROR: {e}")
    
    print("\n🧪 Testy walidacji:")
    try:
        validate_time_param("5min", min_seconds=600)  # 5min < 10min
    except TimeParseError as e:
        print(f"✅ Wykryto za krótki czas: {e}")
    
    try:
        validate_time_param("25h", max_seconds=86400)  # 25h > 24h
    except TimeParseError as e:
        print(f"✅ Wykryto za długi czas: {e}")

