"""
Telegram Collector
==================
Kolektor danych z Telegram Bot API do wysyłania/odbierania wiadomości.

Uwaga: Telegram nie ma sandbox/testnet, ale można użyć testowego bota.
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.error("requests nie jest zainstalowany. Użyj: pip install requests")


class TelegramCollector:
    """
    Kolektor do komunikacji z Telegram Bot API.
    
    Wymaga: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    """
    
    BASE_URL = "https://api.telegram.org/bot"
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Inicjalizacja kolektora Telegram.
        
        Args:
            bot_token: Bot token (lub z TELEGRAM_BOT_TOKEN)
            chat_id: Chat ID (lub z TELEGRAM_CHAT_ID)
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError("Zainstaluj requests: pip install requests")
        
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.bot_token:
            logger.warning("Brak TELEGRAM_BOT_TOKEN - niektóre funkcje mogą nie działać")
        
        self.api_url = f"{self.BASE_URL}{self.bot_token}" if self.bot_token else None
        logger.info("Telegram Collector zainicjalizowany")
    
    def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = 'HTML',
        disable_notification: bool = False
    ) -> Optional[Dict]:
        """
        Wysyła wiadomość przez Telegram.
        
        Args:
            text: Tekst wiadomości
            chat_id: Chat ID (lub używa domyślnego)
            parse_mode: 'HTML', 'Markdown', 'MarkdownV2'
            disable_notification: Wyłącz powiadomienia
            
        Returns:
            Odpowiedź API
        """
        if not self.api_url:
            raise ValueError("TELEGRAM_BOT_TOKEN jest wymagany")
        
        target_chat_id = chat_id or self.chat_id
        if not target_chat_id:
            raise ValueError("chat_id jest wymagany (jako parametr lub TELEGRAM_CHAT_ID)")
        
        url = f"{self.api_url}/sendMessage"
        data = {
            'chat_id': target_chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_notification': disable_notification
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Błąd wysyłania wiadomości Telegram: {e}")
            return None
    
    def send_signal_alert(
        self,
        symbol: str,
        signal_type: str,
        price: float,
        strategy: str,
        additional_info: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Wysyła alert o sygnale tradingowym.
        
        Args:
            symbol: Symbol pary (np. "BTC/USDT")
            signal_type: Typ sygnału ("buy", "sell")
            price: Cena
            strategy: Nazwa strategii
            additional_info: Dodatkowe informacje
            
        Returns:
            Odpowiedź API
        """
        emoji = "🟢" if signal_type.lower() == "buy" else "🔴"
        
        message = f"""
{emoji} <b>SYGNAŁ TRADINGOWY</b>

<b>Symbol:</b> {symbol}
<b>Typ:</b> {signal_type.upper()}
<b>Cena:</b> ${price:,.2f}
<b>Strategia:</b> {strategy}
"""
        
        if additional_info:
            message += f"\n<b>Info:</b> {additional_info}"
        
        message += f"\n\n<i>Czas: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        
        return self.send_message(message)
    
    def send_market_report(
        self,
        report: str,
        title: str = "📊 Raport Rynkowy"
    ) -> Optional[Dict]:
        """
        Wysyła raport rynkowy.
        
        Args:
            report: Treść raportu
            title: Tytuł raportu
            
        Returns:
            Odpowiedź API
        """
        # Telegram ma limit 4096 znaków na wiadomość
        if len(report) > 4000:
            report = report[:4000] + "\n\n... (raport został obcięty)"
        
        message = f"<b>{title}</b>\n\n{report}"
        return self.send_message(message)
    
    def get_updates(self, offset: Optional[int] = None, limit: int = 100) -> List[Dict]:
        """
        Pobiera nowe wiadomości (webhook polling).
        
        Args:
            offset: Offset dla paginacji
            limit: Maksymalna liczba wiadomości
            
        Returns:
            Lista wiadomości
        """
        if not self.api_url:
            raise ValueError("TELEGRAM_BOT_TOKEN jest wymagany")
        
        url = f"{self.api_url}/getUpdates"
        params = {'limit': limit}
        if offset:
            params['offset'] = offset
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('result', [])
        except Exception as e:
            logger.error(f"Błąd pobierania wiadomości Telegram: {e}")
            return []
    
    def get_me(self) -> Optional[Dict]:
        """
        Sprawdza informacje o bocie.
        
        Returns:
            Informacje o bocie
        """
        if not self.api_url:
            raise ValueError("TELEGRAM_BOT_TOKEN jest wymagany")
        
        url = f"{self.api_url}/getMe"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json().get('result')
        except Exception as e:
            logger.error(f"Błąd pobierania informacji o bocie: {e}")
            return None

