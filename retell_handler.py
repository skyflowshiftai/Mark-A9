import os
import time
import re
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

class RetellHandler:
    def __init__(self, cooldown_sec: float = 2.0):
        self.api_key = os.getenv("RETELL_API_KEY", "")
        self.cooldown_sec = cooldown_sec
        
        # State tracking for speech policy
        self.last_threat_level = "SILENT"
        self.last_spoken_message = ""
        self.last_spoken_time = 0.0
        self.repeat_count = 0
        self.is_emergency = False

    def evaluate_voice_output(self, mark_message: str, threat_level: str) -> Dict[str, Any]:
        """
        Applies MARK Voice Rules:
        - Speak only RED or YELLOW threats
        - Maximum 5 words always
        - Speak once -> wait 2 sec -> speak again if same threat persists -> silence after 2nd time
        - 90% of time -> complete silence
        """
        now = time.time()
        
        # Green / Silent -> Intentional complete silence
        if threat_level not in ("RED", "YELLOW"):
            self.last_threat_level = threat_level
            self.repeat_count = 0
            return {
                "should_speak": False,
                "spoken_message": "",
                "threat_level": threat_level,
                "reason": "SILENCE_POLICY_ACTIVE"
            }

        # Check if threat is the same as previous
        is_same_threat = (threat_level == self.last_threat_level) and (mark_message == self.last_spoken_message)

        if is_same_threat:
            # Check cooldown
            if (now - self.last_spoken_time) >= self.cooldown_sec:
                if self.repeat_count < 2:
                    # Allow 2nd repetition
                    self.repeat_count += 1
                    self.last_spoken_time = now
                    return {
                        "should_speak": True,
                        "spoken_message": mark_message,
                        "threat_level": threat_level,
                        "repeat_count": self.repeat_count
                    }
                else:
                    # Silence after second time to avoid spamming
                    return {
                        "should_speak": False,
                        "spoken_message": mark_message,
                        "threat_level": threat_level,
                        "reason": "MAX_REPEATS_REACHED"
                    }
            else:
                # Within cooldown window
                return {
                    "should_speak": False,
                    "spoken_message": mark_message,
                    "threat_level": threat_level,
                    "reason": "COOLDOWN_ACTIVE"
                }
        else:
            # New threat -> Speak immediately
            self.last_threat_level = threat_level
            self.last_spoken_message = mark_message
            self.last_spoken_time = now
            self.repeat_count = 1

            return {
                "should_speak": True,
                "spoken_message": mark_message,
                "threat_level": threat_level,
                "repeat_count": 1
            }

    def process_voice_command(self, transcript: str, current_objects: list, highest_threat: str) -> Dict[str, Any]:
        """
        Listens for wake words:
        - "Hey Mark what's ahead"
        - "Hey Mark am I safe"
        - "Hey Mark read this"
        - "Hey Mark what note is this"
        - "Hey Mark help"
        """
        clean = transcript.lower().strip()
        
        # 1. Emergency
        if any(w in clean for w in ["help", "emergency", "danger", "sos"]):
            self.is_emergency = True
            return {
                "action": "EMERGENCY",
                "speech": "Emergency alert activated. Calling assistance.",
                "is_priority": True
            }

        # 2. Text Reading
        if any(w in clean for w in ["read", "sign", "label", "text"]):
            return {
                "action": "READ_TEXT",
                "speech": "Scanning text.",
                "is_priority": False
            }

        # 3. Currency Detection
        if any(w in clean for w in ["note", "currency", "money", "rupee", "dollar"]):
            return {
                "action": "CURRENCY",
                "speech": "Identifying banknote.",
                "is_priority": False
            }

        # 4. Safe Query
        if any(w in clean for w in ["safe", "can i walk", "clear"]):
            if highest_threat in ("RED", "YELLOW"):
                return {
                    "action": "ANSWER",
                    "speech": f"Obstacle nearby. {current_objects[0]['name'] if current_objects else 'Caution.'}",
                    "is_priority": True
                }
            else:
                return {
                    "action": "ANSWER",
                    "speech": "Path clear. Safe to walk.",
                    "is_priority": False
                }

        # 5. Scene Query
        if any(w in clean for w in ["ahead", "what do you see", "describe"]):
            if not current_objects:
                return {
                    "action": "ANSWER",
                    "speech": "Path clear. No obstacles.",
                    "is_priority": False
                }
            else:
                closest = current_objects[0]
                return {
                    "action": "ANSWER",
                    "speech": f"{closest['name']} {closest['distance']} meters {closest['direction'].lower()}.",
                    "is_priority": False
                }

        # Default conversational acknowledgment
        return {
            "action": "ANSWER",
            "speech": "Mark online. How can I help?",
            "is_priority": False
        }
