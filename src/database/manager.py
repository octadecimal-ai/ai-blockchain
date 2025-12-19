"""
Database Manager
================
Zarządzanie połączeniem z bazą danych i operacjami CRUD.

Obsługuje:
- SQLite (development)
- PostgreSQL + TimescaleDB (produkcja)
- Automatyczne tworzenie tabel
- Bulk insert dla dużych zbiorów danych
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from loguru import logger

from .models import (
    Base, OHLCV, Ticker, Trade, 
    TechnicalIndicator, SentimentScore, Signal,
    LLMSentimentAnalysis, GDELTSentiment,
    create_timescale_hypertables
)


class DatabaseManager:
    """
    Manager do zarządzania bazą danych.
    
    Przykłady użycia:
    
    # SQLite (development)
    db = DatabaseManager()
    
    # PostgreSQL (produkcja)
    db = DatabaseManager("postgresql://user:pass@localhost:5432/ai_blockchain")
    
    # TimescaleDB
    db = DatabaseManager("postgresql://...", use_timescale=True)
    """
    
    def __init__(
        self,
        database_url: str = None,
        use_timescale: bool = False,
        echo: bool = False
    ):
        """
        Inicjalizacja managera bazy danych.
        
        Args:
            database_url: URL do bazy (domyślnie SQLite w data/)
            use_timescale: Czy użyć TimescaleDB (wymaga PostgreSQL)
            echo: Czy logować zapytania SQL
        """
        if database_url is None:
            # Domyślnie SQLite
            db_path = os.path.join(
                os.path.dirname(__file__), 
                '..', '..', 'data', 'ai_blockchain.db'
            )
            database_url = f"sqlite:///{os.path.abspath(db_path)}"
        
        self.database_url = database_url
        self.use_timescale = use_timescale
        
        # Konfiguracja connection pool
        pool_config = {}
        if 'postgresql' in database_url:
            pool_config = {
                'poolclass': QueuePool,
                'pool_size': 5,
                'max_overflow': 10,
                'pool_timeout': 30
            }
        
        self.engine = create_engine(
            database_url,
            echo=echo,
            **pool_config
        )
        
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
            expire_on_commit=False  # Pozwala na dostęp do atrybutów po zamknięciu sesji
        )
        
        logger.info(f"DatabaseManager zainicjalizowany: {self._safe_url()}")
    
    def _safe_url(self) -> str:
        """Zwraca URL bez hasła."""
        url = self.database_url
        if '@' in url:
            parts = url.split('@')
            creds = parts[0].split('://')
            return f"{creds[0]}://***@{parts[1]}"
        return url
    
    def create_tables(self):
        """Tworzy wszystkie tabele."""
        try:
            Base.metadata.create_all(bind=self.engine, checkfirst=True)
            logger.success("Tabele utworzone")
        except Exception as e:
            # Jeśli tabele już istnieją, to nie jest błąd
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                logger.debug("Tabele już istnieją w bazie danych")
            else:
                logger.warning(f"Ostrzeżenie przy tworzeniu tabel: {e}")
        
        if self.use_timescale and 'postgresql' in self.database_url:
            try:
                create_timescale_hypertables(self.engine)
            except Exception as e:
                logger.debug(f"Hypertables mogą już istnieć: {e}")
    
    def drop_tables(self):
        """Usuwa wszystkie tabele (UWAGA!)."""
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("Tabele usunięte")
    
    @contextmanager
    def get_session(self) -> Session:
        """Context manager dla sesji."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    # === OHLCV Operations ===
    
    def save_ohlcv(
        self,
        df: pd.DataFrame,
        exchange: str,
        symbol: str,
        timeframe: str
    ) -> int:
        """
        Zapisuje DataFrame OHLCV do bazy (bulk insert z obsługą duplikatów).
        
        Args:
            df: DataFrame z kolumnami open, high, low, close, volume
            exchange: Nazwa giełdy
            symbol: Symbol pary
            timeframe: Interwał czasowy
            
        Returns:
            Liczba zapisanych rekordów
        """
        if df.empty:
            return 0
        
        records = []
        for timestamp, row in df.iterrows():
            records.append({
                'timestamp': timestamp,
                'exchange': exchange,
                'symbol': symbol,
                'timeframe': timeframe,
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume'],
                'trades_count': row.get('trades', None),
            })
        
        inserted_count = 0
        
        # Bulk insert z obsługą duplikatów
        if 'postgresql' in self.database_url.lower() or 'postgres' in self.database_url.lower():
            # PostgreSQL: użyj ON CONFLICT DO NOTHING
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from sqlalchemy import func
            
            with self.get_session() as session:
                # Sprawdź ile rekordów już istnieje przed zapisem
                timestamps = [r['timestamp'] for r in records]
                if timestamps:
                    min_ts = min(timestamps)
                    max_ts = max(timestamps)
                    
                    existing_count = session.query(func.count(OHLCV.id)).filter(
                        OHLCV.exchange == exchange,
                        OHLCV.symbol == symbol,
                        OHLCV.timeframe == timeframe,
                        OHLCV.timestamp >= min_ts,
                        OHLCV.timestamp <= max_ts
                    ).scalar() or 0
                else:
                    existing_count = 0
                
                # Wykonaj insert
                stmt = pg_insert(OHLCV).values(records)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=['timestamp', 'exchange', 'symbol', 'timeframe']
                )
                session.execute(stmt)
                session.commit()
                
                # Sprawdź ile rekordów jest teraz w bazie
                if timestamps:
                    new_count = session.query(func.count(OHLCV.id)).filter(
                        OHLCV.exchange == exchange,
                        OHLCV.symbol == symbol,
                        OHLCV.timeframe == timeframe,
                        OHLCV.timestamp >= min_ts,
                        OHLCV.timestamp <= max_ts
                    ).scalar() or 0
                    
                    # Różnica to liczba zapisanych rekordów
                    inserted_count = new_count - existing_count
                else:
                    inserted_count = 0
        else:
            # SQLite/inne: batch insert z ignorowaniem błędów
            with self.get_session() as session:
                for record in records:
                    try:
                        # Sprawdź czy istnieje (optymalizacja: można użyć INSERT OR IGNORE)
                        existing = session.query(OHLCV).filter(
                            OHLCV.timestamp == record['timestamp'],
                            OHLCV.exchange == record['exchange'],
                            OHLCV.symbol == record['symbol'],
                            OHLCV.timeframe == record['timeframe']
                        ).first()
                        
                        if not existing:
                            session.add(OHLCV(**record))
                            inserted_count += 1
                    except Exception:
                        continue
        
        logger.info(f"Zapisano {inserted_count}/{len(records)} świec {exchange}:{symbol} {timeframe}")
        return inserted_count
    
    def get_ohlcv(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = None
    ) -> pd.DataFrame:
        """
        Pobiera dane OHLCV z bazy.
        
        Args:
            exchange: Nazwa giełdy
            symbol: Symbol pary
            timeframe: Interwał czasowy
            start_date: Data początkowa
            end_date: Data końcowa
            limit: Limit rekordów
            
        Returns:
            DataFrame z danymi OHLCV
        """
        with self.get_session() as session:
            query = session.query(OHLCV).filter(
                OHLCV.exchange == exchange,
                OHLCV.symbol == symbol,
                OHLCV.timeframe == timeframe
            )
            
            if start_date:
                query = query.filter(OHLCV.timestamp >= start_date)
            if end_date:
                query = query.filter(OHLCV.timestamp <= end_date)
            
            # Jeśli jest limit, sortuj od najstarszych (żeby pobrać ciągły zakres)
            # Jeśli nie ma limitu, sortuj od najnowszych (dla kompatybilności)
            if limit:
                query = query.order_by(OHLCV.timestamp.asc())
                query = query.limit(limit)
            else:
                query = query.order_by(OHLCV.timestamp.desc())
            
            results = query.all()
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame([{
            'timestamp': r.timestamp,
            'open': r.open,
            'high': r.high,
            'low': r.low,
            'close': r.close,
            'volume': r.volume,
        } for r in results])
        
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        return df
    
    # === Funding Rates ===
    
    def save_funding_rates(
        self,
        df: pd.DataFrame,
        exchange: str,
        symbol: str
    ) -> int:
        """
        Zapisuje funding rates do bazy (jako Ticker records).
        
        Args:
            df: DataFrame z kolumną funding_rate i indexem timestamp
            exchange: Nazwa giełdy
            symbol: Symbol pary
            
        Returns:
            Liczba zapisanych rekordów
        """
        if df.empty or 'funding_rate' not in df.columns:
            return 0
        
        saved = 0
        skipped = 0
        
        with self.get_session() as session:
            for timestamp, row in df.iterrows():
                # Sprawdź czy już istnieje ticker dla tego timestamp
                existing = session.query(Ticker).filter(
                    Ticker.timestamp == timestamp,
                    Ticker.exchange == exchange,
                    Ticker.symbol == symbol
                ).first()
                
                if existing:
                    # Aktualizuj funding_rate
                    existing.funding_rate = row['funding_rate']
                    # Jeśli mamy price, zaktualizuj też price
                    if 'price' in row and pd.notna(row.get('price')):
                        existing.price = row['price']
                    saved += 1
                else:
                    # Utwórz nowy ticker
                    price = row.get('price', row.get('close', 0))
                    session.add(Ticker(
                        timestamp=timestamp,
                        exchange=exchange,
                        symbol=symbol,
                        price=price,
                        funding_rate=row['funding_rate']
                    ))
                    saved += 1
                
                # Commit co 100 rekordów dla lepszej wydajności
                if saved % 100 == 0:
                    session.commit()
            
            session.commit()
        
        logger.info(f"Zapisano {saved} funding rates {exchange}:{symbol} (pominięto {skipped} duplikatów)")
        return saved
    
    def get_funding_rates(
        self,
        exchange: str,
        symbol: str,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = None
    ) -> pd.DataFrame:
        """
        Pobiera funding rates z bazy (z tabeli Ticker).
        
        Args:
            exchange: Nazwa giełdy
            symbol: Symbol pary
            start_date: Data początkowa
            end_date: Data końcowa
            limit: Limit rekordów
            
        Returns:
            DataFrame z funding rates (index: timestamp, kolumna: funding_rate)
        """
        with self.get_session() as session:
            query = session.query(Ticker).filter(
                Ticker.exchange == exchange,
                Ticker.symbol == symbol,
                Ticker.funding_rate.isnot(None)
            )
            
            if start_date:
                query = query.filter(Ticker.timestamp >= start_date)
            if end_date:
                query = query.filter(Ticker.timestamp <= end_date)
            
            query = query.order_by(Ticker.timestamp.asc())
            
            if limit:
                query = query.limit(limit)
            
            results = query.all()
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame([{
            'timestamp': r.timestamp,
            'funding_rate': r.funding_rate,
        } for r in results])
        
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        return df
    
    def save_tickers(
        self,
        df: pd.DataFrame,
        exchange: str,
        symbol: str
    ) -> int:
        """
        Zapisuje pełne tickery do bazy.
        
        Args:
            df: DataFrame z kolumnami tickera i indexem timestamp
            exchange: Nazwa giełdy
            symbol: Symbol pary
            
        Returns:
            Liczba zapisanych rekordów
        """
        if df.empty or 'price' not in df.columns:
            return 0
        
        saved = 0
        skipped = 0
        
        with self.get_session() as session:
            for timestamp, row in df.iterrows():
                # Sprawdź czy już istnieje ticker dla tego timestamp
                existing = session.query(Ticker).filter(
                    Ticker.timestamp == timestamp,
                    Ticker.exchange == exchange,
                    Ticker.symbol == symbol
                ).first()
                
                if existing:
                    # Aktualizuj wszystkie pola
                    # Konwertuj NaN na None (zgodnie z zasadą projektu)
                    def clean_value(val):
                        import math
                        if val is None:
                            return None
                        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                            return None
                        return val
                    
                    existing.price = clean_value(row.get('price', existing.price))
                    existing.bid = clean_value(row.get('bid', existing.bid))
                    existing.ask = clean_value(row.get('ask', existing.ask))
                    existing.spread = clean_value(row.get('spread', existing.spread))
                    existing.volume_24h = clean_value(row.get('volume_24h', existing.volume_24h))
                    existing.change_24h = clean_value(row.get('change_24h', existing.change_24h))
                    existing.high_24h = clean_value(row.get('high_24h', existing.high_24h))
                    existing.low_24h = clean_value(row.get('low_24h', existing.low_24h))
                    existing.funding_rate = clean_value(row.get('funding_rate', existing.funding_rate))
                    existing.open_interest = clean_value(row.get('open_interest', existing.open_interest))
                    saved += 1
                else:
                    # Utwórz nowy ticker
                    # Konwertuj NaN na None (zgodnie z zasadą projektu)
                    def clean_value(val):
                        import math
                        if val is None:
                            return None
                        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                            return None
                        return val
                    
                    session.add(Ticker(
                        timestamp=timestamp,
                        exchange=exchange,
                        symbol=symbol,
                        price=clean_value(row.get('price', 0)),
                        bid=clean_value(row.get('bid', None)),
                        ask=clean_value(row.get('ask', None)),
                        spread=clean_value(row.get('spread', None)),
                        volume_24h=clean_value(row.get('volume_24h', None)),
                        change_24h=clean_value(row.get('change_24h', None)),
                        high_24h=clean_value(row.get('high_24h', None)),
                        low_24h=clean_value(row.get('low_24h', None)),
                        funding_rate=clean_value(row.get('funding_rate', None)),
                        open_interest=clean_value(row.get('open_interest', None))
                    ))
                    saved += 1
                
                # Commit co 100 rekordów dla lepszej wydajności
                if saved % 100 == 0:
                    session.commit()
            
            session.commit()
        
        logger.info(f"Zapisano {saved} tickerów {exchange}:{symbol} (pominięto {skipped} duplikatów)")
        return saved
    
    def save_open_interest(
        self,
        df: pd.DataFrame,
        exchange: str,
        symbol: str
    ) -> int:
        """
        Zapisuje open interest do bazy (jako Ticker records).
        
        Args:
            df: DataFrame z kolumną open_interest i indexem timestamp
            exchange: Nazwa giełdy
            symbol: Symbol pary
            
        Returns:
            Liczba zapisanych rekordów
        """
        if df.empty or 'open_interest' not in df.columns:
            return 0
        
        saved = 0
        with self.get_session() as session:
            for timestamp, row in df.iterrows():
                # Sprawdź czy już istnieje ticker dla tego timestamp
                existing = session.query(Ticker).filter(
                    Ticker.timestamp == timestamp,
                    Ticker.exchange == exchange,
                    Ticker.symbol == symbol
                ).first()
                
                if existing:
                    # Aktualizuj open_interest
                    existing.open_interest = row['open_interest']
                else:
                    # Utwórz nowy ticker
                    price = row.get('close', row.get('price', 0))
                    session.add(Ticker(
                        timestamp=timestamp,
                        exchange=exchange,
                        symbol=symbol,
                        price=price,
                        open_interest=row['open_interest']
                    ))
                saved += 1
                
                # Commit co 100 rekordów dla lepszej wydajności
                if saved % 100 == 0:
                    session.commit()
            
            session.commit()
        
        logger.info(f"Zapisano {saved} rekordów open interest {exchange}:{symbol}")
        return saved
    
    def get_open_interest(
        self,
        exchange: str,
        symbol: str,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = None
    ) -> pd.DataFrame:
        """
        Pobiera open interest z bazy (z tabeli Ticker).
        
        Args:
            exchange: Nazwa giełdy
            symbol: Symbol pary
            start_date: Data początkowa
            end_date: Data końcowa
            limit: Limit rekordów
            
        Returns:
            DataFrame z open interest (index: timestamp, kolumna: open_interest)
        """
        with self.get_session() as session:
            query = session.query(Ticker).filter(
                Ticker.exchange == exchange,
                Ticker.symbol == symbol,
                Ticker.open_interest.isnot(None)
            )
            
            if start_date:
                query = query.filter(Ticker.timestamp >= start_date)
            if end_date:
                query = query.filter(Ticker.timestamp <= end_date)
            
            query = query.order_by(Ticker.timestamp.asc())
            
            if limit:
                query = query.limit(limit)
            
            results = query.all()
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame([{
            'timestamp': r.timestamp,
            'open_interest': r.open_interest,
        } for r in results])
        
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        return df
    
    # === Sygnały ===
    
    def save_signal(
        self,
        exchange: str,
        symbol: str,
        signal_type: str,
        strategy: str,
        price: float,
        **kwargs
    ):
        """Zapisuje sygnał handlowy."""
        with self.get_session() as session:
            signal = Signal(
                timestamp=datetime.now(timezone.utc),
                exchange=exchange,
                symbol=symbol,
                signal_type=signal_type,
                strategy=strategy,
                price_at_signal=price,
                **kwargs
            )
            session.add(signal)
        
        logger.info(f"📢 Sygnał: {signal_type.upper()} {symbol} @ ${price:,.2f} ({strategy})")
    
    def get_recent_signals(
        self,
        symbol: str = None,
        hours: int = 24,
        limit: int = 50
    ) -> List[Signal]:
        """Pobiera ostatnie sygnały."""
        with self.get_session() as session:
            query = session.query(Signal).filter(
                Signal.timestamp >= datetime.now(timezone.utc) - timedelta(hours=hours)
            )
            
            if symbol:
                query = query.filter(Signal.symbol == symbol)
            
            return query.order_by(Signal.timestamp.desc()).limit(limit).all()
    
    # === Statystyki ===
    
    def get_stats(self) -> dict:
        """Zwraca statystyki bazy danych."""
        with self.get_session() as session:
            stats = {
                'ohlcv_count': session.query(OHLCV).count(),
                'tickers_count': session.query(Ticker).count(),
                'funding_rates_count': session.query(Ticker).filter(Ticker.funding_rate.isnot(None)).count(),
                'trades_count': session.query(Trade).count(),
                'signals_count': session.query(Signal).count(),
            }
            
            # Ostatni timestamp
            latest_ohlcv = session.query(OHLCV).order_by(OHLCV.timestamp.desc()).first()
            if latest_ohlcv:
                stats['latest_ohlcv'] = latest_ohlcv.timestamp.isoformat()
                stats['latest_symbol'] = f"{latest_ohlcv.exchange}:{latest_ohlcv.symbol}"
        
        return stats
    
    def get_available_data(self) -> pd.DataFrame:
        """Zwraca podsumowanie dostępnych danych."""
        query = """
            SELECT 
                exchange,
                symbol,
                timeframe,
                MIN(timestamp) as first_date,
                MAX(timestamp) as last_date,
                COUNT(*) as candle_count
            FROM ohlcv
            GROUP BY exchange, symbol, timeframe
            ORDER BY exchange, symbol, timeframe
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
        
        if not rows:
            return pd.DataFrame()
        
        return pd.DataFrame(rows, columns=[
            'exchange', 'symbol', 'timeframe', 
            'first_date', 'last_date', 'candle_count'
        ])
    
    # === LLM Sentiment Analysis Operations ===
    
    def get_llm_sentiment_analysis(
        self,
        symbol: str = None,
        regions: List[str] = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = None
    ) -> pd.DataFrame:
        """
        Pobiera dane analizy sentymentu LLM z bazy.
        
        Args:
            symbol: Symbol kryptowaluty (np. BTC/USDC, BTC-USD)
            regions: Lista kodów regionów (np. ["US", "CN", "JP"])
            start_date: Data początkowa
            end_date: Data końcowa
            limit: Maksymalna liczba rekordów
            
        Returns:
            DataFrame z kolumnami: timestamp, symbol, region, language, sentiment, score, confidence, etc.
            Index: timestamp
        """
        with self.get_session() as session:
            query = session.query(LLMSentimentAnalysis)
            
            if symbol:
                query = query.filter(LLMSentimentAnalysis.symbol == symbol)
            
            if regions:
                query = query.filter(LLMSentimentAnalysis.region.in_(regions))
            
            if start_date:
                query = query.filter(LLMSentimentAnalysis.timestamp >= start_date)
            
            if end_date:
                query = query.filter(LLMSentimentAnalysis.timestamp <= end_date)
            
            query = query.order_by(LLMSentimentAnalysis.timestamp.asc())
            
            if limit:
                query = query.limit(limit)
            
            results = query.all()
        
        if not results:
            return pd.DataFrame()
        
        # Konwertuj do DataFrame
        data = []
        for r in results:
            data.append({
                'timestamp': r.timestamp,
                'symbol': r.symbol,
                'region': r.region,
                'language': r.language,
                'sentiment': r.sentiment,
                'score': r.score,
                'confidence': r.confidence,
                'fud_level': r.fud_level,
                'fomo_level': r.fomo_level,
                'market_impact': r.market_impact,
                'key_topics': r.key_topics,
                'reasoning': r.reasoning,
                'llm_model': r.llm_model,
                'input_tokens': r.input_tokens,
                'output_tokens': r.output_tokens,
                'cost_pln': r.cost_pln,
                'texts_count': r.texts_count,
                'prompt': r.prompt,
                'response': r.response,
                'web_search_query': r.web_search_query,
                'web_search_response': r.web_search_response,
                'web_search_answer': r.web_search_answer,
                'web_search_results_count': r.web_search_results_count,
            })
        
        df = pd.DataFrame(data)
        
        if not df.empty:
            # Ustaw timestamp jako index
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            df = df.sort_index()
        
        return df
    
    def get_llm_sentiment_timeseries(
        self,
        symbol: str,
        regions: List[str] = None,
        days_back: int = 7,
        resolution_hours: float = 1.0
    ) -> pd.DataFrame:
        """
        Pobiera dane sentymentu LLM jako time series (pogrupowane po regionach).
        
        Args:
            symbol: Symbol kryptowaluty
            regions: Lista kodów regionów (jeśli None, pobiera wszystkie)
            days_back: Dni wstecz
            resolution_hours: Rozdzielczość czasowa w godzinach (domyślnie 1h)
            
        Returns:
            DataFrame z kolumnami dla każdego regionu (wartości = score)
            Index: timestamp (pogrupowane według resolution_hours)
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        end_date = datetime.now(timezone.utc)
        
        df = self.get_llm_sentiment_analysis(
            symbol=symbol,
            regions=regions,
            start_date=start_date,
            end_date=end_date
        )
        
        if df.empty:
            logger.warning(f"Brak danych LLM sentymentu dla {symbol}")
            return pd.DataFrame()
        
        # Jeśli nie podano regionów, pobierz wszystkie dostępne
        if regions is None:
            regions = df['region'].unique().tolist()
        
        # Grupuj po regionach i agreguj wszystkie wartości według resolution_hours
        all_series = {}
        all_confidence = {}
        all_fud_level = {}
        all_fomo_level = {}
        all_market_impact = {}
        
        for region in regions:
            region_df = df[df['region'] == region].copy()
            
            if region_df.empty:
                continue
            
            # Resample do resolution_hours i uśrednij wszystkie wartości
            resample_rule = f'{int(resolution_hours * 60)}T'  # Konwertuj godziny na minuty
            
            # Agreguj score (średnia)
            region_df_resampled = region_df['score'].resample(resample_rule).mean()
            all_series[region] = region_df_resampled
            
            # Agreguj confidence (średnia)
            if 'confidence' in region_df.columns:
                confidence_resampled = region_df['confidence'].resample(resample_rule).mean()
                all_confidence[region] = confidence_resampled
            
            # Agreguj fud_level (średnia)
            if 'fud_level' in region_df.columns:
                fud_resampled = region_df['fud_level'].resample(resample_rule).mean()
                all_fud_level[region] = fud_resampled
            
            # Agreguj fomo_level (średnia)
            if 'fomo_level' in region_df.columns:
                fomo_resampled = region_df['fomo_level'].resample(resample_rule).mean()
                all_fomo_level[region] = fomo_resampled
            
            # Agreguj market_impact (ostatnia wartość - string)
            if 'market_impact' in region_df.columns:
                impact_resampled = region_df['market_impact'].resample(resample_rule).last()
                all_market_impact[region] = impact_resampled
        
        if not all_series:
            return pd.DataFrame()
        
        # Połącz wszystkie serie w jeden DataFrame
        combined = pd.DataFrame(all_series)
        combined = combined.sort_index()
        
        # Wypełnij brakujące wartości interpolacją (tylko dla score)
        combined = combined.interpolate(method="time", limit=3)
        
        # Dodaj dodatkowe wartości jako atrybuty DataFrame (dla łatwego dostępu)
        combined.attrs = {
            'confidence': pd.DataFrame(all_confidence) if all_confidence else pd.DataFrame(),
            'fud_level': pd.DataFrame(all_fud_level) if all_fud_level else pd.DataFrame(),
            'fomo_level': pd.DataFrame(all_fomo_level) if all_fomo_level else pd.DataFrame(),
            'market_impact': pd.DataFrame(all_market_impact) if all_market_impact else pd.DataFrame()
        }
        
        logger.success(f"Pobrano LLM sentiment timeseries dla {len(all_series)} regionów")
        return combined
    
    # === GDELT Sentiment Operations ===
    
    def save_gdelt_sentiment(
        self,
        df: pd.DataFrame,
        query: str,
        region: str,
        language: Optional[str] = None,
        resolution: str = "hour"
    ) -> int:
        """
        Zapisuje dane sentymentu GDELT do bazy.
        
        Args:
            df: DataFrame z kolumnami: timestamp (index), tone, volume
            query: Zapytanie użyte do wyszukiwania
            region: Kod regionu/kraju
            language: Kod języka (opcjonalnie)
            resolution: Rozdzielczość czasowa (hour, day)
            
        Returns:
            Liczba zapisanych rekordów
        """
        if df.empty:
            return 0
        
        try:
            records = []
            for timestamp, row in df.iterrows():
                tone = row.get('tone')
                volume = row.get('volume', 0)
                
                # Oblicz statystyki (jeśli dostępne)
                tone_std = None
                positive_count = None
                negative_count = None
                neutral_count = None
                
                # Jeśli tone jest dostępny, możemy oszacować pozytywne/negatywne
                if tone is not None:
                    if tone > 0:
                        positive_count = int(volume * (tone / 100)) if volume else None
                        negative_count = int(volume * (1 - tone / 100)) if volume else None
                    elif tone < 0:
                        positive_count = int(volume * (1 + tone / 100)) if volume else None
                        negative_count = int(volume * (-tone / 100)) if volume else None
                    else:
                        neutral_count = volume if volume else None
                
                records.append({
                    'timestamp': timestamp if isinstance(timestamp, datetime) else pd.to_datetime(timestamp),
                    'region': region,
                    'language': language,
                    'query': query,
                    'tone': tone,
                    'tone_std': tone_std,
                    'volume': int(volume) if volume else None,
                    'positive_count': positive_count,
                    'negative_count': negative_count,
                    'neutral_count': neutral_count,
                    'resolution': resolution
                })
            
            with self.get_session() as session:
                for record in records:
                    gdelt_sentiment = GDELTSentiment(**record)
                    session.add(gdelt_sentiment)
                session.commit()
            
            logger.debug(f"Zapisano {len(records)} rekordów GDELT sentymentu dla {region}")
            return len(records)
            
        except Exception as e:
            logger.error(f"Błąd zapisu GDELT sentymentu do bazy: {e}")
            raise
    
    def get_gdelt_sentiment(
        self,
        query: str = None,
        regions: List[str] = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = None
    ) -> pd.DataFrame:
        """
        Pobiera dane sentymentu GDELT z bazy.
        
        Args:
            query: Zapytanie (opcjonalnie)
            regions: Lista kodów regionów (opcjonalnie)
            start_date: Data początkowa
            end_date: Data końcowa
            limit: Maksymalna liczba rekordów
            
        Returns:
            DataFrame z kolumnami: timestamp, region, query, tone, volume, etc.
            Index: timestamp
        """
        with self.get_session() as session:
            db_query = session.query(GDELTSentiment)
            
            if query:
                db_query = db_query.filter(GDELTSentiment.query == query)
            
            if regions:
                db_query = db_query.filter(GDELTSentiment.region.in_(regions))
            
            if start_date:
                db_query = db_query.filter(GDELTSentiment.timestamp >= start_date)
            
            if end_date:
                db_query = db_query.filter(GDELTSentiment.timestamp <= end_date)
            
            db_query = db_query.order_by(GDELTSentiment.timestamp.asc())
            
            if limit:
                db_query = db_query.limit(limit)
            
            results = db_query.all()
        
        if not results:
            return pd.DataFrame()
        
        # Konwertuj do DataFrame
        data = []
        for r in results:
            data.append({
                'timestamp': r.timestamp,
                'region': r.region,
                'language': r.language,
                'query': r.query,
                'tone': r.tone,
                'tone_std': r.tone_std,
                'volume': r.volume,
                'positive_count': r.positive_count,
                'negative_count': r.negative_count,
                'neutral_count': r.neutral_count,
                'resolution': r.resolution,
            })
        
        df = pd.DataFrame(data)
        
        if not df.empty:
            # Ustaw timestamp jako index
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            df = df.sort_index()
        
        return df


# === Przykład użycia ===
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Dodaj ścieżkę projektu
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    from src.collectors.exchange.binance_collector import BinanceCollector
    
    # Inicjalizacja bazy
    db = DatabaseManager()
    db.create_tables()
    
    print("\n📊 DATABASE STATS:")
    print(db.get_stats())
    
    # Pobierz i zapisz dane
    print("\n⬇️ Pobieram dane z Binance...")
    collector = BinanceCollector()
    df = collector.fetch_ohlcv("BTC/USDT", "1h", limit=100)
    
    print(f"Pobrano {len(df)} świec")
    
    # Zapisz do bazy
    saved = db.save_ohlcv(df, "binance", "BTC/USDT", "1h")
    print(f"Zapisano {saved} świec do bazy")
    
    # Odczytaj z bazy
    print("\n⬆️ Odczytuję z bazy...")
    df_from_db = db.get_ohlcv("binance", "BTC/USDT", "1h", limit=5)
    print(df_from_db)
    
    # Statystyki
    print("\n📈 Dostępne dane:")
    print(db.get_available_data())

