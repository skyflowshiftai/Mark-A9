import re
from typing import Dict, Any, List
from ..vision.tracker import ObjectState

class CommandEngine:
    def __init__(self):
        self.intent_patterns = {
            "EMERGENCY": [
                r"\bhelp\b", r"\bemergency\b", r"\bdanger\b", r"\bsos\b", r"\bcall (for )?help\b", r"\bmark help\b"
            ],
            "OCR": [
                r"\bread( this)?\b", r"\bread text\b", r"\bwhat does (this|it) say\b", r"\bread sign\b", r"\bocr\b"
            ],
            "CURRENCY": [
                r"\b(what|which) note\b", r"\bcurrency\b", r"\bmoney\b", r"\bhow much is this\b", r"\bwhat bill\b", r"\bwhat rupee\b"
            ],
            "SAFETY": [
                r"\bam i safe\b", r"\bis it safe\b", r"\bcan i walk\b", r"\bis path clear\b", r"\bany danger\b"
            ],
            "SCENE": [
                r"\bwhat('s| is) ahead\b", r"\bwhat do you see\b", r"\bdescribe( the)? scene\b", r"\bwhat is in front\b", r"\blook around\b"
            ]
        }

    def process_command(
        self,
        command_text: str,
        tracks: List[ObjectState],
        scene_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Interprets natural language query and generates conversational answer.
        """
        text = command_text.strip().lower()
        matched_intent = "UNKNOWN"

        for intent, patterns in self.intent_patterns.items():
            for pat in patterns:
                if re.search(pat, text):
                    matched_intent = intent
                    break
            if matched_intent != "UNKNOWN":
                break

        # Generate contextual response based on intent
        if matched_intent == "EMERGENCY":
            return {
                "intent": "EMERGENCY",
                "response": "Emergency mode activated. High priority alert triggered.",
                "action": "TRIGGER_EMERGENCY",
                "is_priority": True
            }

        elif matched_intent == "OCR":
            return {
                "intent": "OCR",
                "response": "Scanning text in view.",
                "action": "TRIGGER_OCR",
                "is_priority": False
            }

        elif matched_intent == "CURRENCY":
            return {
                "intent": "CURRENCY",
                "response": "Analyzing banknote in view.",
                "action": "TRIGGER_CURRENCY",
                "is_priority": False
            }

        elif matched_intent == "SAFETY":
            forward_clear = scene_summary.get("forward_clear", True)
            if forward_clear:
                resp = "Path clear. Safe to walk."
            else:
                resp = f"Caution. {scene_summary.get('path_message', 'Obstacle in path.')}"
            return {
                "intent": "SAFETY",
                "response": resp,
                "action": "NONE",
                "is_priority": not forward_clear
            }

        elif matched_intent == "SCENE":
            if not tracks:
                resp = "Open space ahead. No obstacles detected in view."
            else:
                parts = []
                for t in tracks[:3]:
                    parts.append(f"{t.class_name} at {t.distance_m} meters on your {t.sector.lower()}")
                resp = f"I see: {', '.join(parts)}."
            return {
                "intent": "SCENE",
                "response": resp,
                "action": "NONE",
                "is_priority": False
            }

        else:
            # Fallback natural explanation
            if not tracks:
                resp = "The path ahead is clear. Let me know if you need to read text or check currency."
            else:
                resp = f"There are {len(tracks)} objects tracked. Forward path is {'clear' if scene_summary.get('forward_clear') else 'obstructed'}."
            return {
                "intent": "GENERAL",
                "response": resp,
                "action": "NONE",
                "is_priority": False
            }
