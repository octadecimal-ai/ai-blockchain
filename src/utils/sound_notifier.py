"""
Sound Notifier
==============
Moduł do odtwarzania dźwięków powiadomień dla tradingu.
Używa systemowych dźwięków macOS.
"""

import os
import platform
import subprocess
from typing import Optional
from loguru import logger


class SoundNotifier:
    """
    Klasa do odtwarzania dźwięków powiadomień.
    
    Obsługuje:
    - macOS: systemowe dźwięki i text-to-speech
    - Linux: możliwość użycia beep lub innych narzędzi
    - Windows: możliwość użycia winsound
    """
    
    def __init__(self, enabled: bool = True, use_tts: bool = False):
        """
        Inicjalizacja notyfikatora dźwiękowego.
        
        Args:
            enabled: Czy dźwięki są włączone
            use_tts: Czy używać text-to-speech zamiast dźwięków systemowych
        """
        self.enabled = enabled
        self.use_tts = use_tts
        self.system = platform.system()
        
        if not enabled:
            logger.debug("🔇 Dźwięki wyłączone")
        else:
            logger.debug(f"🔊 Dźwięki włączone (system: {self.system}, TTS: {use_tts})")
    
    def _play_sound_macos(self, sound_name: str, message: Optional[str] = None):
        """Odtwarza dźwięk na macOS."""
        if not self.enabled:
            return
        
        try:
            if self.use_tts and message:
                # Użyj text-to-speech
                subprocess.run(
                    ['say', message],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Użyj systemowego dźwięku
                # macOS ma wbudowane dźwięki: Glass, Basso, Blow, Bottle, Frog, Funk, etc.
                subprocess.run(
                    ['afplay', f'/System/Library/Sounds/{sound_name}.aiff'],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        except Exception as e:
            logger.debug(f"Nie udało się odtworzyć dźwięku: {e}")
    
    def _play_sound_linux(self, sound_name: str, message: Optional[str] = None):
        """Odtwarza dźwięk na Linux."""
        if not self.enabled:
            return
        
        try:
            # Spróbuj użyć beep lub paplay
            if message and self.use_tts:
                subprocess.run(
                    ['espeak', message],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Spróbuj beep
                subprocess.run(
                    ['beep'],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        except Exception as e:
            logger.debug(f"Nie udało się odtworzyć dźwięku: {e}")
    
    def _play_sound_windows(self, sound_name: str, message: Optional[str] = None):
        """Odtwarza dźwięk na Windows."""
        if not self.enabled:
            return
        
        try:
            import winsound
            # Windows system sounds
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
        except Exception as e:
            logger.debug(f"Nie udało się odtworzyć dźwięku: {e}")
    
    def play_sound(self, sound_name: str, message: Optional[str] = None):
        """
        Odtwarza dźwięk w zależności od systemu operacyjnego.
        
        Args:
            sound_name: Nazwa dźwięku (dla macOS: Glass, Basso, Blow, etc.)
            message: Opcjonalna wiadomość dla TTS
        """
        if not self.enabled:
            return
        
        if self.system == "Darwin":  # macOS
            self._play_sound_macos(sound_name, message)
        elif self.system == "Linux":
            self._play_sound_linux(sound_name, message)
        elif self.system == "Windows":
            self._play_sound_windows(sound_name, message)
        else:
            logger.debug(f"System {self.system} nie jest obsługiwany dla dźwięków")
    
    def notify_position_opened(self, symbol: str, side: str):
        """Powiadamia o otwarciu pozycji."""
        if self.use_tts:
            self.play_sound("Glass", f"Nastąpiła inwestycja {side} na {symbol}")
        else:
            self.play_sound("Glass")  # Pozytywny dźwięk dla otwarcia
            logger.debug(f"🔊 Dźwięk: Otwarcie pozycji {symbol} {side}")
    
    def notify_position_closed_profit(self, symbol: str, pnl: float):
        """Powiadamia o zamknięciu pozycji ze zyskiem."""
        if self.use_tts:
            self.play_sound("Glass", f"Rozliczona inwestycja przyniosła zysk {pnl:.2f} dolarów")
        else:
            self.play_sound("Glass")  # Pozytywny dźwięk
            logger.debug(f"🔊 Dźwięk: Zysk {symbol} ${pnl:.2f}")
    
    def notify_position_closed_loss(self, symbol: str, pnl: float):
        """Powiadamia o zamknięciu pozycji ze stratą."""
        if self.use_tts:
            self.play_sound("Basso", f"Rozliczona inwestycja przyniosła stratę {abs(pnl):.2f} dolarów")
        else:
            self.play_sound("Basso")  # Negatywny dźwięk
            logger.debug(f"🔊 Dźwięk: Strata {symbol} ${pnl:.2f}")


# Globalna instancja (można wyłączyć przez zmienną środowiskową)
_sound_notifier: Optional[SoundNotifier] = None


def get_sound_notifier() -> SoundNotifier:
    """Zwraca globalną instancję SoundNotifier."""
    global _sound_notifier
    
    if _sound_notifier is None:
        enabled = os.getenv('TRADING_SOUNDS_ENABLED', 'true').lower() == 'true'
        use_tts = os.getenv('TRADING_SOUNDS_TTS', 'false').lower() == 'true'
        _sound_notifier = SoundNotifier(enabled=enabled, use_tts=use_tts)
    
    return _sound_notifier

