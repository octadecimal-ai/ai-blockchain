#!/usr/bin/env python3
"""
Generuje INSERT-y SQL z pliku CSV region_phase_dictionary.csv
"""

import csv
from pathlib import Path
from collections import defaultdict

def parse_csv_to_inserts(csv_path: Path):
    """Parsuje CSV i zwraca dane pogrupowane według kategorii."""
    
    regions = set()
    region_events = []
    global_events = []
    macro_events = []
    options_events = []
    algo_events = []
    special_events = []
    social_events = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Pomiń komentarze i puste wiersze
            if not row.get('phase_code') or row['phase_code'].startswith('#'):
                continue
            
            region_code = row.get('region_code', '').strip()
            category = row.get('category', '').strip()
            
            # Zbierz regiony
            if region_code and region_code != 'GLOBAL' and region_code not in ['MACRO', 'OPTIONS', 'ALGO', 'EVENT', 'SOCIAL']:
                regions.add(region_code)
            
            # Grupuj według kategorii i region_code
            event_data = {
                'phase_code': row.get('phase_code', '').strip(),
                'region_code': region_code,
                'label': row.get('label', '').strip(),
                'description': row.get('description', '').strip(),
                'utc_start': row.get('utc_start', '').strip(),
                'utc_end': row.get('utc_end', '').strip(),
                'wraps_midnight': row.get('wraps_midnight', 'FALSE').strip().upper() == 'TRUE',
                'priority': int(row.get('priority', 0)) if row.get('priority') else 0,
                'volatility_level': row.get('volatility_level', '').strip(),
                'volume_impact': row.get('volume_impact', '').strip(),
                'typical_duration_min': int(row.get('typical_duration_min', 0)) if row.get('typical_duration_min') else 0,
                'trading_pattern': row.get('trading_pattern', '').strip(),
                'dominant_actors': row.get('dominant_actors', '').strip(),
                'news_sensitivity': row.get('news_sensitivity', '').strip(),
                'category': category
            }
            
            # Najpierw sprawdź region_code dla specjalnych kategorii
            if region_code == 'OPTIONS':
                options_events.append(event_data)
            elif region_code == 'ALGO':
                algo_events.append(event_data)
            elif region_code == 'MACRO':
                macro_events.append(event_data)
            elif region_code == 'SOCIAL':
                social_events.append(event_data)
            elif region_code == 'EVENT':
                special_events.append(event_data)
            elif category == 'MACRO':
                macro_events.append(event_data)
            elif category == 'EVENT':
                # Sprawdź czy to opcje czy specjalne wydarzenie
                if 'OPTIONS' in event_data['phase_code'] or 'OPTION' in event_data['phase_code']:
                    options_events.append(event_data)
                else:
                    special_events.append(event_data)
            elif category == 'ALGO':
                algo_events.append(event_data)
            elif category == 'SESSION' or category == 'OVERLAP' or category == 'LIQUIDITY' or category == 'WEEKEND':
                if region_code == 'GLOBAL':
                    global_events.append(event_data)
                else:
                    region_events.append(event_data)
            else:
                # Domyślnie do region_events jeśli ma region_code
                if region_code and region_code != 'GLOBAL':
                    region_events.append(event_data)
                else:
                    global_events.append(event_data)
    
    return {
        'regions': sorted(regions),
        'region_events': region_events,
        'global_events': global_events,
        'macro_events': macro_events,
        'options_events': options_events,
        'algo_events': algo_events,
        'special_events': special_events,
        'social_events': social_events
    }


def escape_sql_string(s: str) -> str:
    """Escape string dla SQL."""
    if not s:
        return 'NULL'
    return "'" + s.replace("'", "''") + "'"


def generate_regions_inserts(regions: list) -> str:
    """Generuje INSERT-y dla tabeli Regions."""
    
    # Mapowanie regionów na pełne nazwy i opisy
    region_info = {
        'CN': {
            'short_name': 'Chiny',
            'full_name': 'Chińska Republika Ludowa',
            'description': 'Jeden z największych rynków kryptowalut z dużą aktywnością handlową. Wysoka adopcja retail, regulacje wpływają na globalny rynek.',
            'timezone': 'UTC+8',
            'market_share_pct': 15.0,
            'dominant_participant': 'RETAIL',
            'regulatory_status': 'RESTRICTIVE',
            'crypto_adoption_level': 'HIGH',
            'btc_volume_rank': 3
        },
        'RU': {
            'short_name': 'Rosja',
            'full_name': 'Federacja Rosyjska',
            'description': 'Rosnący rynek kryptowalut z aktywną społecznością inwestorów. Wysokie wykorzystanie BTC jako alternatywy dla tradycyjnych systemów finansowych.',
            'timezone': 'UTC+3',
            'market_share_pct': 2.5,
            'dominant_participant': 'RETAIL',
            'regulatory_status': 'UNCLEAR',
            'crypto_adoption_level': 'MEDIUM',
            'btc_volume_rank': 8
        },
        'SG': {
            'short_name': 'Singapur',
            'full_name': 'Republika Singapuru',
            'description': 'Kluczowe centrum finansowe Azji z rozwiniętym rynkiem kryptowalut. Wysoka koncentracja instytucji finansowych i funduszy krypto.',
            'timezone': 'UTC+8',
            'market_share_pct': 4.0,
            'dominant_participant': 'INSTITUTIONAL',
            'regulatory_status': 'FRIENDLY',
            'crypto_adoption_level': 'HIGH',
            'btc_volume_rank': 5
        },
        'US': {
            'short_name': 'USA',
            'full_name': 'Stany Zjednoczone Ameryki',
            'description': 'Największy rynek kryptowalut na świecie. Dominacja instytucji finansowych, ETF-ów i funduszy. Wysoka zmienność podczas sesji NYSE.',
            'timezone': 'UTC-5/UTC-4',
            'market_share_pct': 35.0,
            'dominant_participant': 'INSTITUTIONAL',
            'regulatory_status': 'REGULATED',
            'crypto_adoption_level': 'HIGH',
            'btc_volume_rank': 1
        },
        'KR': {
            'short_name': 'Korea Południowa',
            'full_name': 'Republika Korei',
            'description': 'Wysoka aktywność retail, znana z "Kimchi Premium" - premii cenowej BTC na lokalnych giełdach. Wysoka zmienność.',
            'timezone': 'UTC+9',
            'market_share_pct': 5.0,
            'dominant_participant': 'RETAIL',
            'regulatory_status': 'REGULATED',
            'crypto_adoption_level': 'HIGH',
            'btc_volume_rank': 4
        },
        'JP': {
            'short_name': 'Japonia',
            'full_name': 'Japonia',
            'description': 'Wczesny adopter BTC, regulowany rynek z licencjonowanymi giełdami. Mieszanka retail i instytucji.',
            'timezone': 'UTC+9',
            'market_share_pct': 6.0,
            'dominant_participant': 'MIXED',
            'regulatory_status': 'REGULATED',
            'crypto_adoption_level': 'HIGH',
            'btc_volume_rank': 2
        },
        'GB': {
            'short_name': 'Wielka Brytania',
            'full_name': 'Zjednoczone Królestwo Wielkiej Brytanii i Irlandii Północnej',
            'description': 'Główne centrum finansowe Europy. Wysoka aktywność instytucjonalna, wpływ na europejskie rynki.',
            'timezone': 'UTC+0/UTC+1',
            'market_share_pct': 8.0,
            'dominant_participant': 'INSTITUTIONAL',
            'regulatory_status': 'REGULATED',
            'crypto_adoption_level': 'MEDIUM',
            'btc_volume_rank': 6
        },
        'DE': {
            'short_name': 'Niemcy',
            'full_name': 'Republika Federalna Niemiec',
            'description': 'Największa gospodarka Europy. Wysoka aktywność instytucjonalna, wpływ na strefę euro.',
            'timezone': 'UTC+1/UTC+2',
            'market_share_pct': 7.0,
            'dominant_participant': 'INSTITUTIONAL',
            'regulatory_status': 'REGULATED',
            'crypto_adoption_level': 'MEDIUM',
            'btc_volume_rank': 7
        },
        'PL': {
            'short_name': 'Polska',
            'full_name': 'Rzeczpospolita Polska',
            'description': 'Rosnący rynek retail z wysoką adopcją kryptowalut. Aktywna społeczność inwestorów.',
            'timezone': 'UTC+1/UTC+2',
            'market_share_pct': 1.5,
            'dominant_participant': 'RETAIL',
            'regulatory_status': 'REGULATED',
            'crypto_adoption_level': 'MEDIUM',
            'btc_volume_rank': 12
        },
        'HK': {
            'short_name': 'Hongkong',
            'full_name': 'Specjalny Region Administracyjny Hongkong',
            'description': 'Ważny ośrodek handlu kryptowalutami w Azji. Most między Chinami a światem. Wysoka koncentracja instytucji.',
            'timezone': 'UTC+8',
            'market_share_pct': 3.5,
            'dominant_participant': 'INSTITUTIONAL',
            'regulatory_status': 'FRIENDLY',
            'crypto_adoption_level': 'HIGH',
            'btc_volume_rank': 9
        },
        'AE': {
            'short_name': 'ZEA',
            'full_name': 'Zjednoczone Emiraty Arabskie',
            'description': 'Dynamicznie rozwijający się rynek kryptowalut na Bliskim Wschodzie. Most między Azją a Europą. Przyjazne regulacje.',
            'timezone': 'UTC+4',
            'market_share_pct': 2.0,
            'dominant_participant': 'INSTITUTIONAL',
            'regulatory_status': 'FRIENDLY',
            'crypto_adoption_level': 'MEDIUM',
            'btc_volume_rank': 10
        },
        'AU': {
            'short_name': 'Australia',
            'full_name': 'Wspólnota Australii',
            'description': 'Aktywny rynek kryptowalut z rosnącym zainteresowaniem inwestorów. Wczesna sesja azjatycka.',
            'timezone': 'UTC+10/UTC+11',
            'market_share_pct': 2.5,
            'dominant_participant': 'MIXED',
            'regulatory_status': 'REGULATED',
            'crypto_adoption_level': 'MEDIUM',
            'btc_volume_rank': 11
        },
        'BR': {
            'short_name': 'Brazylia',
            'full_name': 'Federacyjna Republika Brazylii',
            'description': 'Największy rynek kryptowalut w Ameryce Południowej. Wysoka adopcja retail, wykorzystanie jako zabezpieczenie przed inflacją.',
            'timezone': 'UTC-3',
            'market_share_pct': 3.0,
            'dominant_participant': 'RETAIL',
            'regulatory_status': 'REGULATED',
            'crypto_adoption_level': 'HIGH',
            'btc_volume_rank': 13
        },
        'IN': {
            'short_name': 'Indie',
            'full_name': 'Republika Indii',
            'description': 'Szybko rozwijający się rynek kryptowalut z dużą liczbą inwestorów detalicznych. Potencjał wzrostu.',
            'timezone': 'UTC+5:30',
            'market_share_pct': 1.0,
            'dominant_participant': 'RETAIL',
            'regulatory_status': 'UNCLEAR',
            'crypto_adoption_level': 'LOW',
            'btc_volume_rank': 14
        },
        'TR': {
            'short_name': 'Turcja',
            'full_name': 'Republika Turcji',
            'description': 'Rosnące zainteresowanie kryptowalutami wśród inwestorów. Wysoka adopcja jako zabezpieczenie przed inflacją waluty.',
            'timezone': 'UTC+3',
            'market_share_pct': 1.5,
            'dominant_participant': 'RETAIL',
            'regulatory_status': 'RESTRICTIVE',
            'crypto_adoption_level': 'HIGH',
            'btc_volume_rank': 15
        },
        'CA': {
            'short_name': 'Kanada',
            'full_name': 'Kanada',
            'description': 'Stabilny rynek kryptowalut z aktywną społecznością inwestorów. Synchronizacja z rynkiem USA.',
            'timezone': 'UTC-5/UTC-4',
            'market_share_pct': 2.0,
            'dominant_participant': 'MIXED',
            'regulatory_status': 'REGULATED',
            'crypto_adoption_level': 'MEDIUM',
            'btc_volume_rank': 16
        }
    }
    
    inserts = []
    for region_code in sorted(regions):
        info = region_info.get(region_code, {
            'short_name': region_code,
            'full_name': region_code,
            'description': f'Region {region_code}',
            'timezone': 'UTC+0',
            'market_share_pct': 0.0,
            'dominant_participant': 'MIXED',
            'regulatory_status': 'UNKNOWN',
            'crypto_adoption_level': 'UNKNOWN',
            'btc_volume_rank': 99
        })
        
        inserts.append(
            f"('{region_code}', {escape_sql_string(info['short_name'])}, "
            f"{escape_sql_string(info['full_name'])}, {escape_sql_string(info['description'])}, "
            f"{escape_sql_string(info['timezone'])}, {info['market_share_pct']}, "
            f"{escape_sql_string(info['dominant_participant'])}, "
            f"{escape_sql_string(info['regulatory_status'])}, "
            f"{escape_sql_string(info['crypto_adoption_level'])}, {info['btc_volume_rank']})"
        )
    
    return ",\n    ".join(inserts)


def generate_events_inserts(events: list, table_name: str) -> str:
    """Generuje INSERT-y dla tabel wydarzeń."""
    
    inserts = []
    for event in events:
        phase_code = escape_sql_string(event['phase_code'])
        region_code = escape_sql_string(event['region_code']) if event['region_code'] else 'NULL'
        label = escape_sql_string(event['label'])
        description = escape_sql_string(event['description'])
        utc_start = escape_sql_string(event['utc_start'])
        utc_end = escape_sql_string(event['utc_end'])
        wraps_midnight = 'TRUE' if event['wraps_midnight'] else 'FALSE'
        priority = event['priority']
        volatility_level = escape_sql_string(event['volatility_level']) if event['volatility_level'] else 'NULL'
        volume_impact = escape_sql_string(event['volume_impact']) if event['volume_impact'] else 'NULL'
        typical_duration_min = event['typical_duration_min']
        trading_pattern = escape_sql_string(event['trading_pattern']) if event['trading_pattern'] else 'NULL'
        dominant_actors = escape_sql_string(event['dominant_actors']) if event['dominant_actors'] else 'NULL'
        news_sensitivity = escape_sql_string(event['news_sensitivity']) if event['news_sensitivity'] else 'NULL'
        category = escape_sql_string(event['category']) if event['category'] else 'NULL'
        
        inserts.append(
            f"({phase_code}, {region_code}, {label}, {description}, {utc_start}, {utc_end}, "
            f"{wraps_midnight}, {priority}, {volatility_level}, {volume_impact}, "
            f"{typical_duration_min}, {trading_pattern}, {dominant_actors}, "
            f"{news_sensitivity}, {category})"
        )
    
    return ",\n    ".join(inserts)


def main():
    project_root = Path(__file__).parent.parent
    csv_path = project_root / 'docs' / 'database' / 'region_phase_dictionary.csv'
    
    if not csv_path.exists():
        print(f"Błąd: Nie znaleziono pliku {csv_path}")
        return
    
    data = parse_csv_to_inserts(csv_path)
    
    # Wygeneruj INSERT-y dla Regions
    regions_inserts = generate_regions_inserts(data['regions'])
    
    # Wygeneruj INSERT-y dla wydarzeń
    region_events_inserts = generate_events_inserts(data['region_events'], 'dictionary_region_events')
    global_events_inserts = generate_events_inserts(data['global_events'], 'dictionary_global_events')
    macro_events_inserts = generate_events_inserts(data['macro_events'], 'dictionary_macro_events')
    options_events_inserts = generate_events_inserts(data['options_events'], 'dictionary_options_events')
    algo_events_inserts = generate_events_inserts(data['algo_events'], 'dictionary_algo_events')
    special_events_inserts = generate_events_inserts(data['special_events'], 'dictionary_special_events')
    social_events_inserts = generate_events_inserts(data['social_events'], 'dictionary_social_events')
    
    # Zapisz do plików
    output_dir = project_root / 'src' / 'database' / 'migrations' / 'generated'
    output_dir.mkdir(exist_ok=True)
    
    with open(output_dir / 'regions_inserts.sql', 'w', encoding='utf-8') as f:
        f.write(f"-- INSERT-y dla tabeli regions\n")
        f.write(f"INSERT INTO regions (region_code, short_name, full_name, description, timezone, market_share_pct, dominant_participant, regulatory_status, crypto_adoption_level, btc_volume_rank) VALUES\n")
        f.write(f"    {regions_inserts};\n")
    
    with open(output_dir / 'region_events_inserts.sql', 'w', encoding='utf-8') as f:
        f.write(f"-- INSERT-y dla tabeli dictionary_region_events\n")
        f.write(f"INSERT INTO dictionary_region_events (phase_code, region_code, label, description, utc_start, utc_end, wraps_midnight, priority, volatility_level, volume_impact, typical_duration_min, trading_pattern, dominant_actors, news_sensitivity, category) VALUES\n")
        f.write(f"    {region_events_inserts};\n")
    
    with open(output_dir / 'global_events_inserts.sql', 'w', encoding='utf-8') as f:
        f.write(f"-- INSERT-y dla tabeli dictionary_global_events\n")
        f.write(f"INSERT INTO dictionary_global_events (phase_code, region_code, label, description, utc_start, utc_end, wraps_midnight, priority, volatility_level, volume_impact, typical_duration_min, trading_pattern, dominant_actors, news_sensitivity, category) VALUES\n")
        f.write(f"    {global_events_inserts};\n")
    
    with open(output_dir / 'macro_events_inserts.sql', 'w', encoding='utf-8') as f:
        f.write(f"-- INSERT-y dla tabeli dictionary_macro_events\n")
        f.write(f"INSERT INTO dictionary_macro_events (phase_code, region_code, label, description, utc_start, utc_end, wraps_midnight, priority, volatility_level, volume_impact, typical_duration_min, trading_pattern, dominant_actors, news_sensitivity, category) VALUES\n")
        f.write(f"    {macro_events_inserts};\n")
    
    with open(output_dir / 'options_events_inserts.sql', 'w', encoding='utf-8') as f:
        f.write(f"-- INSERT-y dla tabeli dictionary_options_events\n")
        f.write(f"INSERT INTO dictionary_options_events (phase_code, region_code, label, description, utc_start, utc_end, wraps_midnight, priority, volatility_level, volume_impact, typical_duration_min, trading_pattern, dominant_actors, news_sensitivity, category) VALUES\n")
        f.write(f"    {options_events_inserts};\n")
    
    with open(output_dir / 'algo_events_inserts.sql', 'w', encoding='utf-8') as f:
        f.write(f"-- INSERT-y dla tabeli dictionary_algo_events\n")
        f.write(f"INSERT INTO dictionary_algo_events (phase_code, region_code, label, description, utc_start, utc_end, wraps_midnight, priority, volatility_level, volume_impact, typical_duration_min, trading_pattern, dominant_actors, news_sensitivity, category) VALUES\n")
        f.write(f"    {algo_events_inserts};\n")
    
    with open(output_dir / 'special_events_inserts.sql', 'w', encoding='utf-8') as f:
        f.write(f"-- INSERT-y dla tabeli dictionary_special_events\n")
        f.write(f"INSERT INTO dictionary_special_events (phase_code, region_code, label, description, utc_start, utc_end, wraps_midnight, priority, volatility_level, volume_impact, typical_duration_min, trading_pattern, dominant_actors, news_sensitivity, category) VALUES\n")
        f.write(f"    {special_events_inserts};\n")
    
    with open(output_dir / 'social_events_inserts.sql', 'w', encoding='utf-8') as f:
        f.write(f"-- INSERT-y dla tabeli dictionary_social_events\n")
        f.write(f"INSERT INTO dictionary_social_events (phase_code, region_code, label, description, utc_start, utc_end, wraps_midnight, priority, volatility_level, volume_impact, typical_duration_min, trading_pattern, dominant_actors, news_sensitivity, category) VALUES\n")
        f.write(f"    {social_events_inserts};\n")
    
    print(f"✓ Wygenerowano INSERT-y w katalogu {output_dir}")
    print(f"  - {len(data['regions'])} regionów")
    print(f"  - {len(data['region_events'])} wydarzeń regionalnych")
    print(f"  - {len(data['global_events'])} wydarzeń globalnych")
    print(f"  - {len(data['macro_events'])} wydarzeń makroekonomicznych")
    print(f"  - {len(data['options_events'])} wydarzeń opcji")
    print(f"  - {len(data['algo_events'])} wydarzeń algorytmicznych")
    print(f"  - {len(data['special_events'])} wydarzeń specjalnych")
    print(f"  - {len(data['social_events'])} wydarzeń social media")


if __name__ == '__main__':
    main()

