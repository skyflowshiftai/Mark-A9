from typing import Dict, Any

class TTSEngine:
    def __init__(self, default_rate: int = 175, default_volume: float = 1.0):
        self.rate = default_rate
        self.volume = default_volume

    def format_speech_payload(self, text: str, is_priority: bool = False, level: str = "INFO") -> Dict[str, Any]:
        """
        Formats speech instruction for client-side or server-side speech synthesis.
        """
        return {
            "should_speak": bool(text.strip()),
            "message": text.strip(),
            "is_priority": is_priority,
            "level": level,
            "rate": self.rate,
            "volume": self.volume
        }
