"""
Arbitrage Strategies
====================
Strategie arbitrażowe między giełdami.

Główne typy arbitrażu w krypto:
1. Spot Arbitrage - różnice cen spot między giełdami
2. Funding Rate Arbitrage - wykorzystanie funding rate na perpetualach
3. Triangular Arbitrage - wykorzystanie par walutowych
4. Cross-Exchange Arbitrage - CEX vs DEX

WAŻNE: Arbitraż wymaga:
- Niskich opłat transakcyjnych
- Szybkiego wykonania
- Kapitału na obu giełdach
- Uwzględnienia slippage i spreadów
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
from loguru import logger


class ArbitrageType(Enum):
    """Typy arbitrażu."""
    SPOT = "spot"  # Różnica cen spot
    FUNDING = "funding"  # Funding rate
    TRIANGULAR = "triangular"  # Trójkątny
    CROSS_EXCHANGE = "cross_exchange"  # Między giełdami


@dataclass
class ArbitrageOpportunity:
    """Reprezentuje okazję arbitrażową."""
    timestamp: datetime
    arb_type: ArbitrageType
    symbol: str
    
    # Giełdy
    exchange_buy: str
    exchange_sell: str
    
    # Ceny
    price_buy: float
    price_sell: float
    spread_percent: float
    spread_usd: float
    
    # Koszty
    fees_buy: float = 0.001  # 0.1%
    fees_sell: float = 0.001
    slippage_estimate: float = 0.0005  # 0.05%
    
    # Szacowany zysk
    net_profit_percent: float = 0.0
    
    # Dodatkowe dane
    funding_rate: Optional[float] = None
    volume_24h_buy: Optional[float] = None
    volume_24h_sell: Optional[float] = None
    
    def __post_init__(self):
        """Oblicz net profit po opłatach."""
        total_fees = self.fees_buy + self.fees_sell + self.slippage_estimate
        self.net_profit_percent = self.spread_percent - (total_fees * 100)
    
    def is_profitable(self, min_profit: float = 0.1) -> bool:
        """Czy okazja jest opłacalna (domyślnie min 0.1% zysku)."""
        return self.net_profit_percent >= min_profit
    
    def summary(self) -> str:
        """Podsumowanie okazji."""
        profitable = "✅ PROFITABLE" if self.is_profitable() else "❌ NOT PROFITABLE"
        return f"""
{'='*50}
{profitable}
{'='*50}
Symbol: {self.symbol}
Typ: {self.arb_type.value}

📈 KUP na {self.exchange_buy}: ${self.price_buy:,.2f}
📉 SPRZEDAJ na {self.exchange_sell}: ${self.price_sell:,.2f}

Spread: {self.spread_percent:.3f}% (${self.spread_usd:.2f})
Opłaty: ~{(self.fees_buy + self.fees_sell) * 100:.2f}%
Slippage: ~{self.slippage_estimate * 100:.3f}%

💰 Net Profit: {self.net_profit_percent:.3f}%
{'='*50}
"""


class ArbitrageScanner:
    """
    Skaner okazji arbitrażowych między Binance a dYdX.
    
    Strategia:
    1. Pobiera ceny z obu giełd
    2. Oblicza spread
    3. Uwzględnia opłaty i slippage
    4. Raportuje opłacalne okazje
    
    Przykład użycia:
    ```python
    scanner = ArbitrageScanner()
    opportunities = scanner.scan_all()
    for opp in opportunities:
        if opp.is_profitable():
            print(opp.summary())
    ```
    """
    
    # Mapowanie symboli między giełdami
    SYMBOL_MAPPING = {
        'BTC': {'binance': 'BTC/USDT', 'dydx': 'BTC-USD'},
        'ETH': {'binance': 'ETH/USDT', 'dydx': 'ETH-USD'},
        'SOL': {'binance': 'SOL/USDT', 'dydx': 'SOL-USD'},
        'AVAX': {'binance': 'AVAX/USDT', 'dydx': 'AVAX-USD'},
        'LINK': {'binance': 'LINK/USDT', 'dydx': 'LINK-USD'},
        'DOGE': {'binance': 'DOGE/USDT', 'dydx': 'DOGE-USD'},
    }
    
    # Opłaty na giełdach
    FEES = {
        'binance': {'maker': 0.001, 'taker': 0.001},  # 0.1%
        'dydx': {'maker': 0.0002, 'taker': 0.0005},   # 0.02% / 0.05%
    }
    
    def __init__(self):
        """Inicjalizacja skanera."""
        # Lazy import - tylko gdy potrzebne
        self._binance = None
        self._dydx = None
    
    @property
    def binance(self):
        """Lazy loading Binance collector."""
        if self._binance is None:
            from src.collectors.exchange.binance_collector import BinanceCollector
            self._binance = BinanceCollector()
        return self._binance
    
    @property
    def dydx(self):
        """Lazy loading dYdX collector."""
        if self._dydx is None:
            from src.collectors.exchange.dydx_collector import DydxCollector
            self._dydx = DydxCollector(testnet=False)
        return self._dydx
    
    def _fetch_binance_price(self, asset: str, symbol: str) -> Tuple[str, Optional[float]]:
        """Pobiera cenę z Binance (helper do równoległego wykonania)."""
        try:
            ticker = self.binance.get_ticker(symbol)
            return ('binance', ticker['last'])
        except Exception as e:
            logger.error(f"Błąd Binance dla {asset}: {e}")
            return ('binance', None)
    
    def _fetch_dydx_price(self, asset: str, symbol: str) -> Tuple[str, Optional[float]]:
        """Pobiera cenę z dYdX (helper do równoległego wykonania)."""
        try:
            ticker = self.dydx.get_ticker(symbol)
            return ('dydx', ticker['oracle_price'])
        except Exception as e:
            logger.error(f"Błąd dYdX dla {asset}: {e}")
            return ('dydx', None)
    
    def get_prices(self, asset: str) -> Dict[str, Optional[float]]:
        """
        Pobiera aktualne ceny z obu giełd równolegle.
        
        Args:
            asset: Symbol aktywa (np. "BTC")
            
        Returns:
            Słownik z cenami na każdej giełdzie
        """
        symbols = self.SYMBOL_MAPPING.get(asset)
        if not symbols:
            raise ValueError(f"Nieznany asset: {asset}")
        
        prices = {}
        
        # Równoległe pobieranie cen z obu giełd
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self._fetch_binance_price, asset, symbols['binance']),
                executor.submit(self._fetch_dydx_price, asset, symbols['dydx'])
            ]
            
            for future in as_completed(futures):
                exchange, price = future.result()
                prices[exchange] = price
        
        return prices
    
    def scan_single(self, asset: str) -> Optional[ArbitrageOpportunity]:
        """
        Skanuje pojedynczy asset pod kątem arbitrażu.
        
        Args:
            asset: Symbol aktywa
            
        Returns:
            ArbitrageOpportunity lub None
        """
        prices = self.get_prices(asset)
        
        binance_price = prices.get('binance')
        dydx_price = prices.get('dydx')
        
        if not binance_price or not dydx_price:
            return None
        
        # Oblicz spread
        spread_usd = dydx_price - binance_price
        spread_percent = (spread_usd / binance_price) * 100
        
        # Określ kierunek
        if binance_price < dydx_price:
            # Kup na Binance, sprzedaj na dYdX
            exchange_buy = 'binance'
            exchange_sell = 'dydx'
            price_buy = binance_price
            price_sell = dydx_price
        else:
            # Kup na dYdX, sprzedaj na Binance
            exchange_buy = 'dydx'
            exchange_sell = 'binance'
            price_buy = dydx_price
            price_sell = binance_price
            spread_usd = abs(spread_usd)
            spread_percent = abs(spread_percent)
        
        # Opłaty
        fees_buy = self.FEES[exchange_buy]['taker']
        fees_sell = self.FEES[exchange_sell]['taker']
        
        return ArbitrageOpportunity(
            timestamp=datetime.now(),
            arb_type=ArbitrageType.CROSS_EXCHANGE,
            symbol=asset,
            exchange_buy=exchange_buy,
            exchange_sell=exchange_sell,
            price_buy=price_buy,
            price_sell=price_sell,
            spread_percent=spread_percent,
            spread_usd=spread_usd,
            fees_buy=fees_buy,
            fees_sell=fees_sell,
        )
    
    def scan_all(self, min_profit: float = 0.1, parallel: bool = True) -> List[ArbitrageOpportunity]:
        """
        Skanuje wszystkie dostępne assety (opcjonalnie równolegle).
        
        Args:
            min_profit: Minimalny zysk % aby uznać za okazję
            parallel: Czy skanować równolegle (szybciej, ale więcej requestów)
            
        Returns:
            Lista okazji arbitrażowych
        """
        opportunities = []
        assets = list(self.SYMBOL_MAPPING.keys())
        
        if parallel:
            # Równoległe skanowanie (szybsze)
            with ThreadPoolExecutor(max_workers=len(assets)) as executor:
                future_to_asset = {
                    executor.submit(self.scan_single, asset): asset 
                    for asset in assets
                }
                
                for future in as_completed(future_to_asset):
                    asset = future_to_asset[future]
                    try:
                        opp = future.result()
                        if opp:
                            opportunities.append(opp)
                            
                            if opp.is_profitable(min_profit):
                                logger.success(f"🎯 Okazja: {asset} | Spread: {opp.spread_percent:.3f}%")
                            else:
                                logger.debug(f"❌ {asset}: {opp.spread_percent:.3f}% (za mały spread)")
                                
                    except Exception as e:
                        logger.error(f"Błąd skanowania {asset}: {e}")
        else:
            # Sekwencyjne skanowanie (mniej requestów)
            for asset in assets:
                try:
                    opp = self.scan_single(asset)
                    if opp:
                        opportunities.append(opp)
                        
                        if opp.is_profitable(min_profit):
                            logger.success(f"🎯 Okazja: {asset} | Spread: {opp.spread_percent:.3f}%")
                        else:
                            logger.debug(f"❌ {asset}: {opp.spread_percent:.3f}% (za mały spread)")
                            
                except Exception as e:
                    logger.error(f"Błąd skanowania {asset}: {e}")
        
        # Sortuj po potencjalnym zysku
        opportunities.sort(key=lambda x: x.net_profit_percent, reverse=True)
        return opportunities
    
    def scan_funding_arbitrage(self) -> List[Dict]:
        """
        Skanuje okazje funding rate arbitrage.
        
        Strategia:
        - Gdy funding > 0: longi płacą shortom → otwarcie SHORT na dYdX
        - Gdy funding < 0: shorty płacą longom → otwarcie LONG na dYdX
        - Hedge na Binance spot
        
        Returns:
            Lista okazji funding arbitrage
        """
        opportunities = []
        
        for asset, symbols in self.SYMBOL_MAPPING.items():
            try:
                # Pobierz funding rate z dYdX
                dydx_ticker = self.dydx.get_ticker(symbols['dydx'])
                funding_rate = dydx_ticker.get('next_funding_rate', 0)
                
                # Funding rate jest zazwyczaj w skali 8h
                # Annualizowany = funding_rate * 3 * 365
                annual_rate = funding_rate * 3 * 365 * 100
                
                if abs(annual_rate) > 10:  # Powyżej 10% rocznie
                    direction = "SHORT" if funding_rate > 0 else "LONG"
                    opportunities.append({
                        'asset': asset,
                        'funding_rate': funding_rate,
                        'annual_rate': annual_rate,
                        'direction': direction,
                        'exchange': 'dydx',
                        'strategy': f"{direction} on dYdX, hedge on Binance spot"
                    })
                    logger.info(f"💰 Funding arb: {asset} | {annual_rate:.1f}% annual | {direction}")
                    
            except Exception as e:
                logger.error(f"Błąd funding scan {asset}: {e}")
        
        return opportunities
    
    def generate_report(self) -> str:
        """Generuje raport z możliwości arbitrażu."""
        report = []
        report.append("=" * 60)
        report.append("📊 RAPORT ARBITRAŻU - Binance vs dYdX")
        report.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 60)
        
        # Spread arbitraż
        report.append("\n🔄 CROSS-EXCHANGE ARBITRAŻ:")
        opportunities = self.scan_all()
        
        if not opportunities:
            report.append("  Brak okazji")
        else:
            for opp in opportunities[:5]:  # Top 5
                status = "✅" if opp.is_profitable() else "❌"
                report.append(f"  {status} {opp.symbol}: {opp.spread_percent:.3f}% "
                             f"({opp.exchange_buy} → {opp.exchange_sell})")
        
        # Funding arbitraż
        report.append("\n💰 FUNDING RATE ARBITRAŻ:")
        funding_opps = self.scan_funding_arbitrage()
        
        if not funding_opps:
            report.append("  Brak znaczących okazji")
        else:
            for opp in funding_opps:
                report.append(f"  🎯 {opp['asset']}: {opp['annual_rate']:.1f}% annual "
                             f"→ {opp['direction']}")
        
        report.append("\n" + "=" * 60)
        report.append("⚠️  Uwaga: To analiza, NIE porada inwestycyjna!")
        report.append("=" * 60)
        
        return "\n".join(report)


# === Przykład użycia ===
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Dodaj ścieżkę projektu
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    scanner = ArbitrageScanner()
    
    print("\n" + scanner.generate_report())
    
    # Szczegóły najlepszej okazji
    print("\n📋 SZCZEGÓŁY NAJLEPSZEJ OKAZJI:")
    opportunities = scanner.scan_all()
    if opportunities:
        print(opportunities[0].summary())

