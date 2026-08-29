import re
from typing import List, Dict, Any
from vision.tracker import TrackedEntity

class VoiceCommandParser:
    def __init__(self):
        self.command_intents = {
            "EMERGENCY": [r"\bhelp\b", r"\bemergency\b", r"\bdanger\b", r"\bsos\b", r"\bmark help\b"],
            "OCR": [r"\bread\b", r"\bwhat does (this|it) say\b", r"\bread sign\b", r"\btext\b"],
            "CURRENCY": [r"\bnote\b", r"\bcurrency\b", r"\bmoney\b", r"\bhow much\b", r"\brupee\b", r"\bdollar\b"],
            "IDENTIFY": [r"\bwhat (is|am) (this|i holding)\b", r"\bwhat is in front\b", r"\bidentify\b", r"\bwhat item\b", r"\bwhat object\b"],
            "SAFETY": [r"\bam i safe\b", r"\bis it safe\b", r"\bcan i walk\b", r"\bclear\b"],
            "SCENE": [r"\bwhat('s| is) ahead\b", r"\bwhat do you see\b", r"\bdescribe\b", r"\blook\b"]
        }

    def parse(self, text: str, tracks: List[TrackedEntity]) -> Dict[str, Any]:
        clean = text.lower().strip()
        matched = "GENERAL"

        for intent, patterns in self.command_intents.items():
            for pat in patterns:
                if re.search(pat, clean):
                    matched = intent
                    break
            if matched != "GENERAL":
                break

        # Generate Contextual Answer
        if matched == "EMERGENCY":
            return {
                "intent": "EMERGENCY",
                "speech": "Emergency alert activated. Calling for assistance.",
                "is_priority": True,
                "action": "TRIGGER_EMERGENCY"
            }
        elif matched == "IDENTIFY":
            return {
                "intent": "IDENTIFY",
                "speech": "Analyzing object in front of camera.",
                "is_priority": True,
                "action": "TRIGGER_IDENTIFY"
            }
        elif matched == "OCR":
            return {
                "intent": "OCR",
                "speech": "Scanning visible text.",
                "is_priority": False,
                "action": "TRIGGER_OCR"
            }
        elif matched == "CURRENCY":
            return {
                "intent": "CURRENCY",
                "speech": "Analyzing banknote.",
                "is_priority": False,
                "action": "TRIGGER_CURRENCY"
            }
        elif matched == "SAFETY":
            urgent_tracks = [t for t in tracks if t.risk_level in ("URGENT", "CAUTION")]
            if urgent_tracks:
                h = urgent_tracks[0]
                resp = f"Caution. {h.display_name} {h.distance_info.get('display_str', 'nearby')}."
            else:
                resp = "Path clear. Safe to walk."
            return {
                "intent": "SAFETY",
                "speech": resp,
                "is_priority": bool(urgent_tracks),
                "action": "NONE"
            }
        elif matched == "SCENE":
            if not tracks:
                resp = "Path clear. No obstacles in view."
            else:
                parts = [f"{t.display_name} on {t.spatial_sector.lower()}" for t in tracks[:3]]
                resp = f"I see {', '.join(parts)}."
            return {
                "intent": "SCENE",
                "speech": resp,
                "is_priority": False,
                "action": "NONE"
            }
        else:
            return {
                "intent": "GENERAL",
                "speech": "Mark online. How can I help?",
                "is_priority": False,
                "action": "NONE"
            }
