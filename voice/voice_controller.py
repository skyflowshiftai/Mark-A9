from typing import Dict, Any, Optional, Union
from vision.tracker import TrackedEntity
from intelligence.silence_manager import SilenceManager

class VoiceController:
    """
    MARK 2.0 Dedicated Voice Instruction Layer.
    Translates machine visual telemetry into concise (<= 5 words), actionable spoken directives.
    Core Principle: SEE -> UNDERSTAND -> PRIORITIZE -> INSTRUCT -> SILENCE.
    """
    def __init__(self):
        self.silence_manager = SilenceManager()

    def generate_spoken_cue(self, track_or_dict: Union[TrackedEntity, Dict[str, Any]]) -> str:
        """
        Synthesizes concise, direct human instructions (maximum 5 words always).
        Never speaks confidence scores, bounding boxes, or technical jargon.
        """
        if isinstance(track_or_dict, TrackedEntity):
            t = track_or_dict
            sector = t.spatial_sector
            motion = t.motion_info.get("motion_state", "STATIONARY")
            approach = t.motion_info.get("approach_tendency", "STATIONARY")
            risk = t.risk_level
            recog_status = getattr(t, "recognition_status", "KNOWN")
            name = getattr(t, "voice_name", t.display_name).capitalize()
            path_rel = getattr(t, "path_relevance", "MEDIUM")
            prox = getattr(t, "proximity", "MEDIUM")
        else:
            d = track_or_dict
            sector = d.get("spatial_sector") or d.get("direction") or "CENTER"
            pos = d.get("position", {})
            if isinstance(pos, dict) and "horizontal" in pos:
                sector = pos["horizontal"]
            motion = d.get("motion_state") or (d.get("motion", {}).get("state") if isinstance(d.get("motion"), dict) else "STATIONARY")
            approach = d.get("approach_tendency") or "STATIONARY"
            risk = d.get("risk_level") or d.get("threat") or "LOW"
            recog_status = d.get("recognition_status") or d.get("recognition_state") or "KNOWN"
            name = (d.get("recognized_name") or d.get("class_name") or d.get("name") or "Object").capitalize()
            path_rel = d.get("path_relevance") or "MEDIUM"
            prox = d.get("proximity") or d.get("proximity_zone") or "MEDIUM"

        # 1. Handle Uncertain / Unverified Object
        if recog_status == "UNCERTAIN" or "unknown" in name.lower():
            if risk in ("URGENT", "CAUTION") or path_rel == "HIGH":
                if sector == "CENTER":
                    return "Obstacle ahead. Stop." if risk == "URGENT" else "Obstacle ahead. Careful."
                return f"Obstacle on your {sector.lower()}."
            elif prox == "NEAR":
                return f"Object on your {sector.lower()}."
            return ""

        # 2. Vehicles / High-Speed Moving Threats
        if name.lower() in ("car", "truck", "bus", "motorcycle", "vehicle"):
            if risk in ("URGENT", "CAUTION") or approach == "CLOSING_IN" or motion == "APPROACHING":
                return f"{name} approaching. Stop."
            elif sector == "CENTER":
                return f"{name} ahead. Careful."
            return f"{name} on your {sector.lower()}."

        # 3. Stairs, Steps & Drop-offs
        if any(s in name.lower() for s in ("stair", "step", "curb", "ledge")):
            if prox == "NEAR" or risk in ("URGENT", "CAUTION"):
                return "Step down. Stop."
            return "Stairs ahead. Careful."

        # 4. Animals (Dogs, etc.)
        if name.lower() in ("dog", "cat", "animal"):
            if approach == "CLOSING_IN" or motion == "APPROACHING":
                return f"{name} approaching. Careful."
            if sector == "CENTER":
                return f"{name} ahead."
            return f"{name} on your {sector.lower()}."

        # 5. Pedestrians
        if name.lower() == "person":
            if risk == "URGENT" or (prox == "NEAR" and sector == "CENTER"):
                return "Person close ahead. Stop."
            elif approach == "CLOSING_IN":
                return "Person approaching."
            elif sector == "CENTER":
                return "Person ahead."
            return f"Person on your {sector.lower()}."

        # 6. Low Obstacles, Packages, Doors & Furniture
        if name.lower() in ("chair", "bench", "table", "dining table", "couch", "bed", "door", "bottle", "container", "packet", "box"):
            if name.lower() == "door" and sector == "CENTER":
                return "Door ahead."
            if sector == "CENTER":
                if risk in ("URGENT", "CAUTION") or path_rel == "HIGH":
                    return f"{name} ahead. Stop." if risk == "URGENT" else f"{name} ahead. Careful."
                return f"{name} ahead."
            return f"{name} on your {sector.lower()}."

        # Default short phrase (<= 5 words)
        if sector == "CENTER":
            return f"{name} ahead."
        return f"{name} on your {sector.lower()}."

    def evaluate_voice_instruction(self, primary_track: Optional[Union[TrackedEntity, Dict[str, Any]]], timestamp: Optional[float] = None) -> Dict[str, Any]:
        """
        Synthesizes cue and evaluates against silence & cooldown policy.
        """
        if primary_track is None:
            return {
                "should_speak": False,
                "spoken_phrase": "",
                "reason": "SILENCE_PATH_CLEAR",
                "risk_level": "LOW"
            }

        phrase = self.generate_spoken_cue(primary_track)
        if not phrase:
            return {
                "should_speak": False,
                "spoken_phrase": "",
                "reason": "SILENCE_IRRELEVANT",
                "risk_level": "LOW"
            }

        # Evaluate against silence manager
        if isinstance(primary_track, TrackedEntity):
            decision = self.silence_manager.evaluate_speech_decision(primary_track, phrase, timestamp)
        else:
            # Standalone dict fallback
            decision = {
                "should_speak": True,
                "phrase": phrase,
                "reason": "STANDALONE_EVAL",
                "risk_level": primary_track.get("risk_level", "LOW")
            }
        
        return {
            "should_speak": decision["should_speak"],
            "spoken_phrase": decision["phrase"],
            "active_phrase": phrase,
            "reason": decision["reason"],
            "risk_level": decision.get("risk_level", "LOW")
        }
