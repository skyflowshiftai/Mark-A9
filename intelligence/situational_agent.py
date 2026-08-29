"""
MARK 2.0 — REAL-WORLD SITUATIONAL VOICE ASSISTANT ENGINE
Observes -> Tracks -> Understands -> Decides -> Informs -> Reassesses -> Updates.

Key Invariants:
1. Closed Information Loops: (APPEARS -> TRACK/SILENCE -> RESOLVED)
2. Silence between states, NOT silence instead of states.
3. Natural, respectful Telugu phrasing ("సర్, ...").
4. Fast safety override for approaching danger.
"""

import time
from typing import Dict, Any, List, Optional

class SituationalVoiceAgent:
    def __init__(self, reassess_cooldown_sec: float = 3.0):
        self.reassess_cooldown = reassess_cooldown_sec
        self.tracked_entities: Dict[str, Dict[str, Any]] = {}
        self.active_hazard_id: Optional[str] = None
        self.active_hazard_type: Optional[str] = None
        self.path_clear_confirmations: int = 0
        self.last_speech_time: float = 0.0

    def process_state(
        self,
        active_tracks: List[Dict[str, Any]],
        timestamp: Optional[float] = None,
        language: str = "te-IN"
    ) -> Dict[str, Any]:
        """
        Receives persistent tracked objects, updates entity lifecycle states,
        and generates stateful spoken voice guidance.
        """
        t_now = timestamp if timestamp is not None else time.time()
        should_speak = False
        speech_text = None
        highest_priority = "LOW"
        highest_event = None
        interrupt_audio = False

        current_entity_ids = set()

        # 1. Process Active Tracks
        for track in active_tracks:
            d = track.to_dict() if hasattr(track, "to_dict") else track
            eid = str(d.get("track_id") or d.get("id") or d.get("entity_id") or "1")
            current_entity_ids.add(eid)
            raw_class = str(d.get("detector_class") or d.get("raw_class_name") or d.get("name") or "object").lower()
            dist = float(d.get("distance_m") or d.get("distance") or 2.0)
            motion = str(d.get("motion_state") or d.get("movement") or "STATIONARY").upper()

            if eid not in self.tracked_entities:
                # ── NEW ENTITY DETECTED ──
                entity_record = {
                    "entity_id": eid,
                    "raw_class": raw_class,
                    "first_seen": t_now,
                    "last_seen": t_now,
                    "distance": dist,
                    "previous_distance": dist,
                    "movement": motion,
                    "warned": False,
                    "warn_time": 0.0,
                    "consecutive_frames": 1,
                    "status": "NEW"
                }
                self.tracked_entities[eid] = entity_record

                # Initial Courteous Directive if within relevant distance (<= 3.5m)
                if dist <= 3.5:
                    entity_record["warned"] = True
                    entity_record["warn_time"] = t_now
                    entity_record["status"] = "CONFIRMED"
                    self.active_hazard_id = eid
                    self.active_hazard_type = raw_class
                    self.path_clear_confirmations = 0

                    if "person" in raw_class:
                        speech_text = "సర్, మీ ముందు ఒక వ్యక్తి ఉన్నారు... ఆగండి ఒకసారి." if language.startswith("te") else "Sir, a person is ahead. Please stop a moment."
                    elif "car" in raw_class or "vehicle" in raw_class or "motorcycle" in raw_class:
                        speech_text = "సర్, వాహనం దగ్గరగా వస్తోంది... ఆగండి." if language.startswith("te") else "Sir, vehicle approaching. Stop."
                        interrupt_audio = True
                    elif "chair" in raw_class or "obstacle" in raw_class:
                        speech_text = "సర్, మీ ముందు కుర్చీ ఉంది... ఆగండి." if language.startswith("te") else "Sir, chair ahead. Stop."
                    else:
                        speech_text = "సర్, మీ ముందు అడ్డంకి ఉంది... ఆగండి." if language.startswith("te") else "Sir, obstacle ahead. Stop."

                    should_speak = True
                    highest_priority = "HIGH" if ("car" in raw_class or "vehicle" in raw_class) else "MEDIUM"
                    highest_event = {
                        "event": "object_appeared",
                        "entity_id": eid,
                        "object": raw_class,
                        "distance": dist,
                        "status": "CONFIRMED"
                    }
            else:
                # ── EXISTING TRACKED ENTITY ──
                ent = self.tracked_entities[eid]
                ent["consecutive_frames"] += 1
                ent["last_seen"] = t_now
                prev_dist = ent["distance"]
                ent["previous_distance"] = prev_dist
                ent["distance"] = dist
                ent["movement"] = motion

                # Check for approaching danger escalation
                is_approaching = (dist < prev_dist - 0.25) or (motion == "APPROACHING")
                time_since_warn = t_now - ent.get("warn_time", 0.0)

                if is_approaching and dist <= 2.0:
                    # ── DANGER ESCALATION ──
                    if dist <= 1.2 and ("car" in raw_class or "vehicle" in raw_class):
                        speech_text = "సర్, ఆగండి. వాహనం చాలా దగ్గరగా ఉంది." if language.startswith("te") else "Sir, stop. Vehicle is very close."
                        interrupt_audio = True
                        highest_priority = "CRITICAL"
                    elif "person" in raw_class:
                        speech_text = "సర్, ఒక వ్యక్తి మీ వైపు వస్తున్నారు... ఆగండి." if language.startswith("te") else "Sir, a person is approaching your path. Stop."
                        highest_priority = "HIGH"
                    else:
                        speech_text = "సర్, అడ్డంకి చాలా దగ్గరగా వస్తోంది... ఆగండి." if language.startswith("te") else "Sir, obstacle very close. Stop."
                        highest_priority = "HIGH"

                    ent["warn_time"] = t_now
                    ent["status"] = "CHANGED"
                    should_speak = True
                    highest_event = {
                        "event": "hazard_escalated",
                        "entity_id": eid,
                        "object": raw_class,
                        "distance": dist,
                        "status": "CHANGED"
                    }
                elif time_since_warn < self.reassess_cooldown:
                    # ── 3-SECOND MONITORING SILENCE (Silence between states) ──
                    ent["status"] = "TRACKED"
                    # Remain silent

        # 2. Check for Disappeared / Resolved Hazards (Closing the Information Loop)
        if not active_tracks and self.active_hazard_id:
            self.path_clear_confirmations += 1
            if self.path_clear_confirmations >= 2:
                hz_type = (self.active_hazard_type or "person").lower()
                if "person" in hz_type:
                    speech_text = "సర్, మీ ముందు ఇప్పుడు ఎవరూ లేరు. ఇప్పుడు మీరు ముందుకు వెళ్లవచ్చు." if language.startswith("te") else "Sir, no one is ahead now. You can move forward."
                elif "car" in hz_type or "vehicle" in hz_type:
                    speech_text = "సర్, వాహనం వెళ్లిపోయింది. ఇప్పుడు దారి క్లియర్గా ఉంది." if language.startswith("te") else "Sir, vehicle has passed. Path is now clear."
                elif "chair" in hz_type:
                    speech_text = "సర్, కుర్చీ దాటారు. ఇప్పుడు దారి క్లియర్గా ఉంది." if language.startswith("te") else "Sir, chair passed. Path is now clear."
                else:
                    speech_text = "సర్, ఇప్పుడు మీ ముందు దారి క్లియర్గా ఉంది. ముందుకు వెళ్లవచ్చు." if language.startswith("te") else "Sir, path is now clear. You can move forward."

                should_speak = True
                highest_priority = "NORMAL"
                highest_event = {
                    "event": "hazard_resolved",
                    "entity_id": self.active_hazard_id,
                    "previous_state": "blocking",
                    "current_state": "clear",
                    "status": "RESOLVED"
                }
                self.tracked_entities.clear()
                self.active_hazard_id = None
                self.active_hazard_type = None
                self.path_clear_confirmations = 0

        # Return structured situational voice directive
        return {
            "should_speak": should_speak,
            "speech": speech_text or "",
            "priority": highest_priority,
            "interrupt_audio": interrupt_audio,
            "event": highest_event or {"event": "monitoring_silence", "status": "TRACKED"},
            "active_entities_count": len(self.tracked_entities)
        }

    def answer_situational_query(self, intent: str, world_state: Dict[str, Any], language: str = "te-IN") -> str:
        """
        Handles explicit user conversational queries grounded in the latest situational world state.
        """
        active_tracks = world_state.get("active_tracks", [])
        is_uncertain = world_state.get("is_uncertain", False)

        if intent == "IS_SAFE" or intent == "WHAT_AHEAD":
            if is_uncertain:
                return "సర్, ముందు పరిస్థితి స్పష్టంగా లేదు... ఆగండి." if language.startswith("te") else "Sir, the situation ahead is unclear. Please wait."
            if not active_tracks:
                return "సర్, మీ ముందు దారి క్లియర్గా ఉంది." if language.startswith("te") else "Sir, path ahead is clear."
            
            # Find closest obstacle
            closest = min(active_tracks, key=lambda x: float((x.to_dict() if hasattr(x, "to_dict") else x).get("distance_m", 3.0)))
            d = closest.to_dict() if hasattr(closest, "to_dict") else closest
            raw_class = str(d.get("raw_class_name") or d.get("name") or "obstacle").lower()
            dist = float(d.get("distance_m") or 2.0)

            if "car" in raw_class or "vehicle" in raw_class:
                return "సర్, మీ ముందు వాహనం ఉంది." if language.startswith("te") else "Sir, there is a vehicle ahead."
            elif "person" in raw_class:
                return "సర్, మీ ముందు ఒక వ్యక్తి ఉన్నారు." if language.startswith("te") else "Sir, a person is ahead."
            elif "chair" in raw_class:
                return "సర్, మీ ముందు కుర్చీ ఉంది." if language.startswith("te") else "Sir, a chair is ahead."
            return "సర్, మీ ముందు అడ్డంకి ఉంది... ఆగండి." if language.startswith("te") else "Sir, an obstacle is ahead. Please stop."

        elif intent == "READ_TEXT":
            ocr_text = world_state.get("last_ocr_text", "")
            if not ocr_text:
                return "సర్, అక్షరాలు స్పష్టంగా కనిపించడం లేదు." if language.startswith("te") else "Sir, no clear text visible."
            if "construction" in ocr_text.lower() or "danger" in ocr_text.lower():
                return "సర్, డేంజర్. ముందు నిర్మాణ పనులు ఉన్నాయి." if language.startswith("te") else f"Sir, danger: {ocr_text}"
            return f"సర్, బోర్డు మీద '{ocr_text}' అని రాసి ఉంది." if language.startswith("te") else f"Sir, text reads: {ocr_text}"

        elif intent == "IDENTIFY_CURRENCY":
            curr = world_state.get("last_currency_text", "")
            if not curr:
                return "సర్, నోటు స్పష్టంగా కనిపించడం లేదు." if language.startswith("te") else "Sir, banknote is not clear."
            if "500" in curr:
                return "సర్, ఇది ఐదు వందల రూపాయల నోటు." if language.startswith("te") else "Sir, this is a 500 Rupee note."
            return f"సర్, ఇది {curr} నోటు." if language.startswith("te") else f"Sir, this is a {curr} note."

        elif intent == "HELP" or intent == "EMERGENCY":
            return "సర్, సహాయం కోసం అలర్ట్ పంపుతున్నాను." if language.startswith("te") else "Sir, sending emergency alert."

        return "సర్, మీ ముందు దారి క్లియర్గా ఉంది." if language.startswith("te") else "Sir, path ahead is clear."
