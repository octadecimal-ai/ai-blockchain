#!/usr/bin/env python3
"""
Backend API dla aplikacji wizualizacji sentymentu
==================================================
Flask REST API do pobierania danych sentymentu z bazy danych PostgreSQL.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import json

# Dodaj ścieżkę projektu
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from loguru import logger
from dotenv import load_dotenv

# Załaduj zmienne środowiskowe
load_dotenv(project_root / '.env')

from src.database.manager import DatabaseManager
import pandas as pd
import numpy as np

app = Flask(__name__)
CORS(app)  # Włącz CORS dla frontendu

# Inicjalizuj DatabaseManager
db = DatabaseManager(database_url=os.getenv('DATABASE_URL'))

# Mapowanie regionów na współrzędne geograficzne (centrum kraju)
REGION_COORDINATES = {
    "US": {"lat": 39.8283, "lng": -98.5795, "name": "United States"},
    "GB": {"lat": 55.3781, "lng": -3.4360, "name": "United Kingdom"},
    "CN": {"lat": 35.8617, "lng": 104.1954, "name": "China"},
    "JP": {"lat": 36.2048, "lng": 138.2529, "name": "Japan"},
    "KR": {"lat": 35.9078, "lng": 127.7669, "name": "South Korea"},
    "DE": {"lat": 51.1657, "lng": 10.4515, "name": "Germany"},
    "RU": {"lat": 61.5240, "lng": 105.3188, "name": "Russia"},
    "SG": {"lat": 1.3521, "lng": 103.8198, "name": "Singapore"},
    "AU": {"lat": -25.2744, "lng": 133.7751, "name": "Australia"},
    "FR": {"lat": 46.2276, "lng": 2.2137, "name": "France"},
    "ES": {"lat": 40.4637, "lng": -3.7492, "name": "Spain"},
    "IT": {"lat": 41.8719, "lng": 12.5674, "name": "Italy"},
    "NL": {"lat": 52.1326, "lng": 5.2913, "name": "Netherlands"},
    "CA": {"lat": 56.1304, "lng": -106.3468, "name": "Canada"},
    "BR": {"lat": -14.2350, "lng": -51.9253, "name": "Brazil"},
    "IN": {"lat": 20.5937, "lng": 78.9629, "name": "India"},
    "HK": {"lat": 22.3193, "lng": 114.1694, "name": "Hong Kong"},
    "CH": {"lat": 46.8182, "lng": 8.2275, "name": "Switzerland"},
    "AE": {"lat": 23.4241, "lng": 53.8478, "name": "United Arab Emirates"},
    "PL": {"lat": 51.9194, "lng": 19.1451, "name": "Poland"},
}


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})


@app.route('/api/sentiment/timeseries', methods=['GET'])
def get_sentiment_timeseries():
    """
    Pobiera dane sentymentu jako time series.
    
    Query params:
        symbol: Symbol kryptowaluty (domyślnie: BTC/USDC)
        regions: Lista regionów oddzielona przecinkami (domyślnie: wszystkie)
        days_back: Dni wstecz (domyślnie: 7)
        resolution_hours: Rozdzielczość w godzinach (domyślnie: 1.0)
        source: Źródło danych - 'llm' lub 'gdelt' (domyślnie: 'llm')
    """
    try:
        symbol = request.args.get('symbol', 'BTC/USDC')
        regions_str = request.args.get('regions', None)
        days_back = int(request.args.get('days_back', 7))
        resolution_hours = float(request.args.get('resolution_hours', 1.0))
        source = request.args.get('source', 'llm')  # 'llm' lub 'gdelt'
        
        regions = None
        if regions_str:
            regions = [r.strip().upper() for r in regions_str.split(',')]
        
        # Pobierz dane z bazy
        if source == 'llm':
            df = db.get_llm_sentiment_timeseries(
                symbol=symbol,
                regions=regions,
                days_back=days_back,
                resolution_hours=resolution_hours
            )
            
            # Pobierz dodatkowe wartości z attrs DataFrame
            confidence_df = df.attrs.get('confidence', pd.DataFrame()) if hasattr(df, 'attrs') else pd.DataFrame()
            fud_level_df = df.attrs.get('fud_level', pd.DataFrame()) if hasattr(df, 'attrs') else pd.DataFrame()
            fomo_level_df = df.attrs.get('fomo_level', pd.DataFrame()) if hasattr(df, 'attrs') else pd.DataFrame()
            market_impact_df = df.attrs.get('market_impact', pd.DataFrame()) if hasattr(df, 'attrs') else pd.DataFrame()
        else:  # gdelt
            # Dla GDELT używamy innej metody
            start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            end_date = datetime.now(timezone.utc)
            df = db.get_gdelt_sentiment(
                query="bitcoin OR BTC OR cryptocurrency",
                regions=regions,
                start_date=start_date,
                end_date=end_date
            )
            
            if not df.empty and 'tone' in df.columns:
                # Konwertuj tone (-100 do +100) na score (-1.0 do 1.0)
                df['score'] = df['tone'] / 100.0
                # Pivot na time series
                df = df.pivot_table(
                    values='score',
                    index='timestamp',
                    columns='region',
                    aggfunc='mean'
                )
        
        if df.empty:
            return jsonify({
                "error": "Brak danych dla podanych parametrów",
                "data": {},
                "timestamps": [],
                "regions": []
            }), 404
        
        # Konwertuj DataFrame na format JSON
        timestamps = [ts.isoformat() for ts in df.index]
        regions_list = df.columns.tolist()
        
        # Dane dla każdego regionu
        data = {}
        for region in regions_list:
            region_data = {
                "scores": df[region].fillna(0).tolist(),
                "coordinates": REGION_COORDINATES.get(region, {"lat": 0, "lng": 0, "name": region})
            }
            
            # Dodaj dodatkowe wartości jeśli są dostępne (tylko dla LLM)
            if source == 'llm':
                if not confidence_df.empty and region in confidence_df.columns:
                    region_data["confidence"] = confidence_df[region].fillna(0.5).tolist()
                if not fud_level_df.empty and region in fud_level_df.columns:
                    region_data["fud_level"] = fud_level_df[region].fillna(0).tolist()
                if not fomo_level_df.empty and region in fomo_level_df.columns:
                    region_data["fomo_level"] = fomo_level_df[region].fillna(0).tolist()
                if not market_impact_df.empty and region in market_impact_df.columns:
                    # Konwertuj market_impact na liczby (high=3, medium=2, low=1)
                    impact_values = market_impact_df[region].fillna('medium').tolist()
                    region_data["market_impact"] = [
                        3 if v == 'high' else (2 if v == 'medium' else 1) 
                        for v in impact_values
                    ]
            
            data[region] = region_data
        
        return jsonify({
            "timestamps": timestamps,
            "regions": regions_list,
            "data": data,
            "metadata": {
                "symbol": symbol,
                "source": source,
                "days_back": days_back,
                "resolution_hours": resolution_hours,
                "total_points": len(timestamps)
            }
        })
    
    except Exception as e:
        logger.error(f"Błąd pobierania danych sentymentu: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sentiment/range', methods=['GET'])
def get_sentiment_range():
    """
    Pobiera zakres dostępnych danych (min/max timestamp).
    
    Query params:
        symbol: Symbol kryptowaluty (domyślnie: BTC/USDC)
        source: Źródło danych - 'llm' lub 'gdelt' (domyślnie: 'llm')
    """
    try:
        symbol = request.args.get('symbol', 'BTC/USDC')
        source = request.args.get('source', 'llm')
        
        # Pobierz zakres danych
        if source == 'llm':
            df = db.get_llm_sentiment_analysis(symbol=symbol)
        else:  # gdelt
            df = db.get_gdelt_sentiment(query="bitcoin OR BTC OR cryptocurrency")
        
        if df.empty:
            return jsonify({
                "min_timestamp": None,
                "max_timestamp": None,
                "total_records": 0
            })
        
        timestamps = df.index if hasattr(df.index, 'min') else df['timestamp']
        min_ts = timestamps.min()
        max_ts = timestamps.max()
        
        return jsonify({
            "min_timestamp": min_ts.isoformat() if hasattr(min_ts, 'isoformat') else str(min_ts),
            "max_timestamp": max_ts.isoformat() if hasattr(max_ts, 'isoformat') else str(max_ts),
            "total_records": len(df)
        })
    
    except Exception as e:
        logger.error(f"Błąd pobierania zakresu danych: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/regions', methods=['GET'])
def get_regions():
    """Zwraca listę dostępnych regionów z ich współrzędnymi."""
    return jsonify({
        "regions": REGION_COORDINATES
    })


def resample_ohlcv(df: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
    """
    Agreguje dane OHLCV do wyższego timeframe.
    
    Args:
        df: DataFrame z danymi OHLCV (index: timestamp, kolumny: open, high, low, close, volume)
        target_timeframe: Docelowy timeframe (np. '1h', '4h', '1d')
        
    Returns:
        DataFrame z zagregowanymi danymi
    """
    if df.empty:
        return df
    
    # Upewnij się, że index jest timezone-aware (UTC)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    elif df.index.tz != timezone.utc:
        df.index = df.index.tz_convert('UTC')
    
    # Mapowanie timeframe na pandas resample rule
    timeframe_map = {
        '1m': '1T',
        '5m': '5T',
        '15m': '15T',
        '30m': '30T',
        '1h': '1H',
        '2h': '2H',
        '4h': '4H',
        '6h': '6H',
        '8h': '8H',
        '12h': '12H',
        '1d': '1D',
        '3d': '3D',
        '1w': '1W',
        '1M': '1M'
    }
    
    resample_rule = timeframe_map.get(target_timeframe)
    if not resample_rule:
        logger.warning(f"Nieznany timeframe: {target_timeframe}, używam 1H")
        resample_rule = '1H'
    
    # Agreguj OHLCV
    resampled = df.resample(resample_rule).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    return resampled


def calculate_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Oblicza wskaźniki techniczne dla danych OHLCV.
    
    Args:
        df: DataFrame z danymi OHLCV (kolumny: open, high, low, close, volume)
        
    Returns:
        Dict ze wskaźnikami
    """
    if df.empty or len(df) < 2:
        return {}
    
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    
    indicators = {}
    
    # SMA (Simple Moving Average) - 20, 50, 200
    for period in [20, 50, 200]:
        if len(close) >= period:
            indicators[f'sma_{period}'] = close.rolling(window=period).mean().iloc[-1]
    
    # EMA (Exponential Moving Average) - 12, 26
    for period in [12, 26]:
        if len(close) >= period:
            indicators[f'ema_{period}'] = close.ewm(span=period, adjust=False).mean().iloc[-1]
    
    # RSI (Relative Strength Index) - 14
    if len(close) >= 14:
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        indicators['rsi'] = 100 - (100 / (1 + rs.iloc[-1]))
    
    # MACD
    if len(close) >= 26:
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        indicators['macd'] = macd_line.iloc[-1]
        indicators['macd_signal'] = signal_line.iloc[-1]
        indicators['macd_histogram'] = (macd_line - signal_line).iloc[-1]
    
    # Bollinger Bands
    if len(close) >= 20:
        sma_20 = close.rolling(window=20).mean()
        std_20 = close.rolling(window=20).std()
        indicators['bb_upper'] = (sma_20 + (std_20 * 2)).iloc[-1]
        indicators['bb_middle'] = sma_20.iloc[-1]
        indicators['bb_lower'] = (sma_20 - (std_20 * 2)).iloc[-1]
        indicators['bb_width'] = ((indicators['bb_upper'] - indicators['bb_lower']) / indicators['bb_middle']) * 100
    
    # ATR (Average True Range) - 14
    if len(close) >= 14:
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        indicators['atr'] = tr.rolling(window=14).mean().iloc[-1]
        indicators['atr_percent'] = (indicators['atr'] / close.iloc[-1]) * 100
    
    # Volume indicators
    if len(volume) >= 20:
        indicators['volume_sma_20'] = volume.rolling(window=20).mean().iloc[-1]
        indicators['volume_ratio'] = volume.iloc[-1] / indicators['volume_sma_20'] if indicators['volume_sma_20'] > 0 else 1.0
    
    # Price change
    if len(close) >= 2:
        indicators['price_change'] = close.iloc[-1] - close.iloc[-2]
        indicators['price_change_percent'] = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]) * 100
    
    # 24h change
    if len(close) >= 24:
        indicators['price_change_24h'] = close.iloc[-1] - close.iloc[-24]
        indicators['price_change_24h_percent'] = ((close.iloc[-1] - close.iloc[-24]) / close.iloc[-24]) * 100
    
    return indicators


@app.route('/api/btc/price', methods=['GET'])
def get_btc_price():
    """
    Pobiera kurs BTC dla danego timestampu wraz ze wskaźnikami technicznymi.
    
    Query params:
        timestamp: Timestamp ISO format (domyślnie: najnowszy)
        exchange: Giełda (domyślnie: binance)
        symbol: Symbol (domyślnie: BTC/USDC)
        timeframe: Interwał (domyślnie: 1h)
        resolution_hours: Rozdzielczość w godzinach (np. 1/60 = 1 min, 1/12 = 5 min) - używane do agregacji
        lookback_hours: Ile godzin wstecz pobrać dla wskaźników (domyślnie: 200)
    """
    try:
        timestamp_str = request.args.get('timestamp', None)
        exchange = request.args.get('exchange', 'binance')
        symbol = request.args.get('symbol', 'BTC/USDC')
        timeframe = request.args.get('timeframe', '1h')
        resolution_hours = request.args.get('resolution_hours', None)
        if resolution_hours:
            resolution_hours = float(resolution_hours)
        lookback_hours = int(request.args.get('lookback_hours', 200))
        
        # Jeśli podano timestamp, znajdź najbliższą świecę
        if timestamp_str:
            target_timestamp = pd.to_datetime(timestamp_str)
            if target_timestamp.tzinfo is None:
                target_timestamp = target_timestamp.tz_localize('UTC')
            elif target_timestamp.tzinfo != timezone.utc:
                target_timestamp = target_timestamp.tz_convert('UTC')
            start_date = target_timestamp - pd.Timedelta(hours=lookback_hours)
            end_date = target_timestamp + pd.Timedelta(hours=1)
        else:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - pd.Timedelta(hours=lookback_hours)
            target_timestamp = end_date
        
        # Upewnij się, że start_date i end_date są timezone-aware (UTC)
        if start_date.tzinfo is None:
            start_date = start_date.tz_localize('UTC')
        elif start_date.tzinfo != timezone.utc:
            start_date = start_date.tz_convert('UTC')
        
        if end_date.tzinfo is None:
            end_date = end_date.tz_localize('UTC')
        elif end_date.tzinfo != timezone.utc:
            end_date = end_date.tz_convert('UTC')
        
        # Jeśli podano resolution_hours i jest większe niż 1 min, pobierz 1m i zagreguj używając średniej
        use_aggregation = resolution_hours and resolution_hours > (1/60 + 0.0001)  # Dodałem małą tolerancję dla float
        if use_aggregation:
            logger.info(f"Używam agregacji dla resolution_hours={resolution_hours}, pobieram dane 1m i agreguję...")
            # Pobierz dane 1m z przedziału [target_timestamp - resolution_hours, target_timestamp]
            resolution_td = pd.Timedelta(hours=resolution_hours)
            aggregation_start = target_timestamp - resolution_td
            aggregation_end = target_timestamp + pd.Timedelta(minutes=1)
            
            # Upewnij się, że aggregation_start i aggregation_end są timezone-aware (UTC)
            if aggregation_start.tzinfo is None:
                aggregation_start = aggregation_start.tz_localize('UTC')
            elif aggregation_start.tzinfo != timezone.utc:
                aggregation_start = aggregation_start.tz_convert('UTC')
            
            if aggregation_end.tzinfo is None:
                aggregation_end = aggregation_end.tz_localize('UTC')
            elif aggregation_end.tzinfo != timezone.utc:
                aggregation_end = aggregation_end.tz_convert('UTC')
            
            # Pobierz dane 1m
            df_1m = db.get_ohlcv(
                exchange=exchange,
                symbol=symbol,
                timeframe='1m',
                start_date=aggregation_start,
                end_date=aggregation_end,
                limit=1000  # Limit dla bezpieczeństwa
            )
            
            if not df_1m.empty:
                # Upewnij się, że index jest timezone-aware (UTC) - usuń timezone jeśli istnieje, potem dodaj UTC
                if df_1m.index.tz is not None:
                    # Jeśli ma timezone, usuń go i dodaj UTC
                    df_1m.index = df_1m.index.tz_localize(None).tz_localize('UTC')
                else:
                    # Jeśli nie ma timezone, dodaj UTC
                    df_1m.index = df_1m.index.tz_localize('UTC')
                
                # Filtruj dane do przedziału [aggregation_start, target_timestamp]
                # Użyj unix timestamp dla porównań, żeby uniknąć problemów z timezone
                aggregation_start_unix = pd.Timestamp(aggregation_start).value
                target_timestamp_unix = pd.Timestamp(target_timestamp).value
                # Konwertuj index do unix timestamp (nanoseconds) - użyj .values.view('int64')
                # Najpierw usuń timezone z values jeśli istnieje
                index_values = df_1m.index.values
                # Jeśli values mają timezone, usuń go najpierw
                if hasattr(index_values, 'dtype') and 'UTC' in str(index_values.dtype):
                    # Index ma timezone - usuń go najpierw przez konwersję do datetime64[ns]
                    index_values = index_values.astype('datetime64[ns]')
                try:
                    df_1m_index_unix = index_values.view('int64')
                except (TypeError, ValueError):
                    # Jeśli .view() nie działa, użyj .astype('int64')
                    df_1m_index_unix = index_values.astype('int64')
                mask = (df_1m_index_unix >= aggregation_start_unix) & (df_1m_index_unix <= target_timestamp_unix)
                df_1m_filtered = df_1m[mask]
                
                if not df_1m_filtered.empty:
                    # Utwórz zagregowaną świecę używając średniej
                    aggregated_candle = {
                        'open': float(df_1m_filtered['open'].iloc[0]),  # Pierwsza wartość open
                        'high': float(df_1m_filtered['high'].max()),     # Max high
                        'low': float(df_1m_filtered['low'].min()),       # Min low
                        'close': float(df_1m_filtered['close'].mean()),   # Średnia close
                        'volume': float(df_1m_filtered['volume'].sum())   # Suma volume
                    }
                    # Utwórz DataFrame z jedną świecą
                    # Upewnij się, że index jest timezone-aware (UTC)
                    df = pd.DataFrame([aggregated_candle], index=[target_timestamp])
                    if df.index.tz is None:
                        df.index = df.index.tz_localize('UTC')
                    elif df.index.tz != timezone.utc:
                        df.index = df.index.tz_convert('UTC')
                    logger.info(f"Zagregowano {len(df_1m_filtered)} świec 1m do 1 świecy używając średniej")
                else:
                    # Jeśli brak danych w przedziale, użyj standardowej logiki
                    use_aggregation = False
            else:
                # Jeśli brak danych 1m, użyj standardowej logiki
                use_aggregation = False
        
        # Pobierz dane OHLCV (tylko jeśli nie używamy agregacji)
        if not use_aggregation:
            df = db.get_ohlcv(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
        # Jeśli use_aggregation jest True, df już został utworzony przez agregację w linii 437
        
        # Jeśli brak danych dla żądanego timeframe, spróbuj pobrać 1m i zagregować
        if df.empty and timeframe != '1m':
            logger.info(f"Brak danych dla {exchange}:{symbol} {timeframe}, próbuję pobrać 1m i zagregować...")
            # Ogranicz lookback_hours dla 1m, żeby nie pobierać zbyt dużo danych
            # Dla 1h potrzebujemy max 200h * 60 = 12,000 świec 1m, ale to za dużo
            # Ograniczmy do max 5000 świec 1m (ok. 83h) - wystarczy dla większości wskaźników
            max_1m_candles = 5000
            # Przelicz lookback_hours na liczbę świec 1m
            estimated_1m_candles = lookback_hours * 60
            if estimated_1m_candles > max_1m_candles:
                # Ogranicz start_date, żeby nie pobierać zbyt dużo
                limited_start_date = end_date - pd.Timedelta(minutes=max_1m_candles)
                logger.info(f"Ograniczam zakres 1m do {max_1m_candles} świec (zamiast {estimated_1m_candles})")
            else:
                limited_start_date = start_date
            
            df_1m = db.get_ohlcv(
                exchange=exchange,
                symbol=symbol,
                timeframe='1m',
                start_date=limited_start_date,
                end_date=end_date,
                limit=max_1m_candles  # Dodaj limit jako zabezpieczenie
            )
            if not df_1m.empty:
                df = resample_ohlcv(df_1m, timeframe)
                logger.info(f"Zagregowano {len(df_1m)} świec 1m do {len(df)} świec {timeframe}")
        
        # Jeśli nadal brak danych, spróbuj alternatywnych symboli/exchange
        if df.empty:
            # Spróbuj dydx zamiast binance
            if exchange == 'binance':
                df = db.get_ohlcv(
                    exchange='dydx',
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date
                )
                # Jeśli brak danych dla żądanego timeframe, spróbuj 1m i zagreguj
                if df.empty and timeframe != '1m':
                    df_1m = db.get_ohlcv(
                        exchange='dydx',
                        symbol=symbol,
                        timeframe='1m',
                        start_date=start_date,
                        end_date=end_date
                    )
                    if not df_1m.empty:
                        df = resample_ohlcv(df_1m, timeframe)
                        logger.info(f"Zagregowano dydx {len(df_1m)} świec 1m do {len(df)} świec {timeframe}")
            # Spróbuj BTC-USD zamiast BTC/USDC
            if df.empty and symbol == 'BTC/USDC':
                df = db.get_ohlcv(
                    exchange=exchange,
                    symbol='BTC-USD',
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date
                )
                # Jeśli brak danych dla żądanego timeframe, spróbuj 1m i zagreguj
                if df.empty and timeframe != '1m':
                    df_1m = db.get_ohlcv(
                        exchange=exchange,
                        symbol='BTC-USD',
                        timeframe='1m',
                        start_date=start_date,
                        end_date=end_date
                    )
                    if not df_1m.empty:
                        df = resample_ohlcv(df_1m, timeframe)
                        logger.info(f"Zagregowano BTC-USD {len(df_1m)} świec 1m do {len(df)} świec {timeframe}")
            # Spróbuj dydx + BTC-USD
            if df.empty and exchange == 'binance' and symbol == 'BTC/USDC':
                df = db.get_ohlcv(
                    exchange='dydx',
                    symbol='BTC-USD',
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date
                )
                # Jeśli brak danych dla żądanego timeframe, spróbuj 1m i zagreguj
                if df.empty and timeframe != '1m':
                    df_1m = db.get_ohlcv(
                        exchange='dydx',
                        symbol='BTC-USD',
                        timeframe='1m',
                        start_date=start_date,
                        end_date=end_date
                    )
                    if not df_1m.empty:
                        df = resample_ohlcv(df_1m, timeframe)
                        logger.info(f"Zagregowano dydx BTC-USD {len(df_1m)} świec 1m do {len(df)} świec {timeframe}")
        
        # Sprawdź czy mamy dane
        if df.empty:
            # Zwróć 200 OK zamiast 404, żeby frontend mógł wyświetlić komunikat
            return jsonify({
                "error": "Brak danych OHLCV dla podanych parametrów",
                "timestamp": timestamp_str,
                "price": None,
                "indicators": {},
                "debug": {
                    "tried_exchange": exchange,
                    "tried_symbol": symbol,
                    "timeframe": timeframe,
                    "resolution_hours": resolution_hours,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            }), 200
        
        # Znajdź najbliższą świecę do target_timestamp
        df_sorted = df.sort_index()
        
        # Upewnij się, że index jest timezone-aware (UTC) - konwertuj do UTC jeśli potrzeba
        # Najpierw usuń timezone jeśli istnieje, potem dodaj UTC
        if df_sorted.index.tz is not None:
            # Jeśli ma timezone, usuń go i dodaj UTC
            df_sorted.index = df_sorted.index.tz_localize(None).tz_localize('UTC')
        else:
            # Jeśli nie ma timezone, dodaj UTC
            df_sorted.index = df_sorted.index.tz_localize('UTC')
        
        # Upewnij się, że target_timestamp jest timezone-aware (UTC)
        if isinstance(target_timestamp, pd.Timestamp):
            if target_timestamp.tz is None:
                target_timestamp = target_timestamp.tz_localize('UTC')
            elif target_timestamp.tz != timezone.utc:
                target_timestamp = target_timestamp.tz_convert('UTC')
        else:
            # Jeśli to datetime, konwertuj do pd.Timestamp
            target_timestamp = pd.Timestamp(target_timestamp)
            if target_timestamp.tz is None:
                target_timestamp = target_timestamp.tz_localize('UTC')
            elif target_timestamp.tz != timezone.utc:
                target_timestamp = target_timestamp.tz_convert('UTC')
        
        if use_aggregation:
            # Jeśli używamy agregacji, df już zawiera jedną świecę dla target_timestamp
            closest_timestamp = target_timestamp
            closest_candle = df_sorted.iloc[0]
            # Dla wskaźników potrzebujemy więcej danych - pobierz dane 1m dla lookback_hours
            df_for_indicators = db.get_ohlcv(
                exchange=exchange,
                symbol=symbol,
                timeframe='1m',
                start_date=start_date,
                end_date=target_timestamp + pd.Timedelta(minutes=1),
                limit=5000
            )
            if not df_for_indicators.empty:
                # Agreguj do timeframe dla wskaźników
                df_for_indicators = resample_ohlcv(df_for_indicators, timeframe)
        else:
            # Użyj argmin z unix timestamp, żeby uniknąć problemów z timezone
            # Konwertuj index do unix timestamp (nanoseconds) - użyj .view('int64') dla szybkiej konwersji
            try:
                # Spróbuj użyć .view() dla szybkiej konwersji
                index_unix = df_sorted.index.values.view('int64')
            except (TypeError, ValueError):
                # Jeśli .view() nie działa, użyj .to_numpy() i konwertuj
                index_np = df_sorted.index.to_numpy()
                # Konwertuj datetime64 do int64 (nanoseconds) - usuń timezone jeśli istnieje
                if index_np.dtype.name.startswith('datetime64'):
                    index_unix = index_np.astype('int64')
                else:
                    # Jeśli już jest int64, użyj bezpośrednio
                    index_unix = index_np
            
            # Konwertuj target_timestamp do unix timestamp
            target_ts = pd.Timestamp(target_timestamp)
            if target_ts.tz is None:
                target_ts = target_ts.tz_localize('UTC')
            elif target_ts.tz != timezone.utc:
                target_ts = target_ts.tz_convert('UTC')
            target_unix = target_ts.value  # value to nanoseconds since epoch
            # Oblicz różnice czasowe
            time_diffs = np.abs(index_unix - target_unix)
            closest_idx = time_diffs.argmin()
            
            closest_timestamp = df_sorted.index[closest_idx]
            closest_candle = df_sorted.iloc[closest_idx]
            # Oblicz wskaźniki na podstawie danych do tego momentu
            # Użyj indeksu zamiast timestampu, żeby uniknąć problemów z timezone
            df_for_indicators = df_sorted.iloc[:closest_idx+1]
        
        indicators = calculate_indicators(df_for_indicators)
        
        return jsonify({
            "timestamp": closest_timestamp.isoformat(),
            "price": float(closest_candle['close']),
            "open": float(closest_candle['open']),
            "high": float(closest_candle['high']),
            "low": float(closest_candle['low']),
            "close": float(closest_candle['close']),
            "volume": float(closest_candle['volume']),
            "indicators": {k: float(v) if not np.isnan(v) else None for k, v in indicators.items()}
        })
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Błąd pobierania kursu BTC: {e}\n{error_trace}")
        return jsonify({
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": error_trace.split('\n')[-5:] if len(error_trace) > 100 else error_trace
        }), 500


if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5001))  # Zmieniono na 5001 (5000 zajęty przez AirPlay)
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Uruchamiam Flask API na porcie {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

