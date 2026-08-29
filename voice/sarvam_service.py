import os
import time
import json
import base64
import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict, Any

class SarvamService:
    """
    Sarvam AI Bulbul v3 Telugu Text-to-Speech Service.
    Configured for natural, ultra-clear Telugu safety instructions (22050 Hz).
    """
    def __init__(self):
        self.api_key = os.getenv("SARVAM_API_KEY", "")
        self.model = "bulbul:v3"
        self.language_code = "te-IN"
        self.speaker = "ritu"
        self.sample_rate = 22050  # 22.05 kHz for high-quality browser playback
        self.pace = 1.0

    def synthesize_telugu_speech(
        self,
        text: str,
        speaker: str = "ritu",
        pace: float = 1.0,
        priority: str = "normal"
    ) -> Tuple[Optional[bytes], str, float]:
        """
        Synthesizes Telugu text into WAV audio using Sarvam Bulbul v3.
        Returns: (audio_bytes, mime_type, latency_ms)
        """
        if not text or not text.strip():
            return None, "", 0.0

        t_start = time.perf_counter()

        # Adjust pace for urgent safety alerts (slightly faster, crisp)
        actual_pace = 1.05 if priority.lower() in ("critical", "urgent", "high") else pace

        if self.api_key:
            try:
                audio_bytes = self._call_sarvam_tts(text, speaker, actual_pace)
                latency_ms = round((time.perf_counter() - t_start) * 1000, 1)
                return audio_bytes, "audio/wav", latency_ms
            except Exception as e:
                pass

        # Fallback to client-side natural Telugu TTS
        latency_ms = round((time.perf_counter() - t_start) * 1000, 1)
        return None, "client/telugu_speech", max(0.5, latency_ms)

    def _call_sarvam_tts(self, text: str, speaker: str, pace: float) -> bytes:
        """
        Direct REST call to Sarvam AI TTS endpoint.
        """
        url = "https://api.sarvam.ai/text-to-speech"
        payload = {
            "inputs": [text],
            "target_language_code": self.language_code,
            "speaker": speaker or self.speaker,
            "pitch": 0,
            "pace": pace,
            "loudness": 1.5,
            "speech_sample_rate": self.sample_rate,
            "enable_preprocessing": True,
            "model": self.model
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "api-subscription-key": self.api_key
            }
        )

        with urllib.request.urlopen(req, timeout=3.5) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            # Sarvam returns base64 encoded audio in audios list
            if "audios" in res_json and len(res_json["audios"]) > 0:
                b64_audio = res_json["audios"][0]
                return base64.b64decode(b64_audio)
            raise ValueError("No audio returned from Sarvam API")
