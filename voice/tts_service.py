import os
import time
import io
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple
from voice.sarvam_service import SarvamService

class TTSService:
    """
    Production-Quality Multi-Provider Text-to-Speech Service.
    Supports Sarvam Bulbul v3 (te-IN), ElevenLabs (en), and high-speed local fallback.
    Ensures zero fatal crashes and measures exact latency.
    """
    def __init__(self):
        self.provider = os.getenv("TTS_PROVIDER", "elevenlabs").lower()
        self.api_key = os.getenv("TTS_API_KEY", "")
        # Default ElevenLabs voice
        self.voice_id = os.getenv("TTS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        self.model_id = os.getenv("TTS_MODEL_ID", "eleven_turbo_v2")
        self.sarvam = SarvamService()

    def synthesize_speech(
        self,
        text: str,
        priority: str = "normal",
        language: str = "en"
    ) -> Tuple[Optional[bytes], str, float]:
        """
        Synthesizes text into playable audio bytes.
        Returns: (audio_bytes, mime_type, latency_ms)
        """
        if not text or not text.strip():
            return None, "", 0.0

        # 1. If Telugu requested, use Sarvam Bulbul v3
        if language.lower() in ("te", "te-in", "telugu") or any('\u0c00' <= char <= '\u0c7f' for char in text):
            return self.sarvam.synthesize_telugu_speech(text, priority=priority)

        t_start = time.perf_counter()

        # 2. Try ElevenLabs for English if API key is present
        if self.provider == "elevenlabs" and self.api_key:
            try:
                audio_bytes = self._call_elevenlabs(text, priority)
                latency_ms = round((time.perf_counter() - t_start) * 1000, 1)
                return audio_bytes, "audio/mpeg", latency_ms
            except Exception as e:
                pass

        # 3. Local Fallback Generator
        latency_ms = round((time.perf_counter() - t_start) * 1000, 1)
        return None, "client/natural_speech", max(0.5, latency_ms)

    def _call_elevenlabs(self, text: str, priority: str) -> bytes:
        """
        Direct REST call to ElevenLabs Ultra-Low Latency Turbo endpoint.
        """
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream"
        
        # Stability & clarity settings tailored for safety instructions
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.50 if priority.lower() in ("critical", "urgent") else 0.70,
                "similarity_boost": 0.80,
                "style": 0.20 if priority.lower() in ("critical", "urgent") else 0.0,
                "use_speaker_boost": True
            }
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "xi-api-key": self.api_key,
                "Accept": "audio/mpeg"
            }
        )

        with urllib.request.urlopen(req, timeout=3.5) as response:
            return response.read()
