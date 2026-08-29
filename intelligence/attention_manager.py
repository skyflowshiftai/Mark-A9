"""
MARK 2.0 — ATTENTION & SITUATION ENGINE
Central authority for deterministic autonomous voice decisions.

Key Principles:
1. VISION IS CONTINUOUS. VOICE IS EVENT-DRIVEN.
2. The detector & tracker update at full frame rate (10 FPS).
3. The Attention Manager filters 99.9% of frame noise into ABSOLUTE SILENCE.
4. Autonomous speech is generated ONLY upon meaningful semantic state transitions:
   - NEW_CRITICAL_OBSTACLE (temporally confirmed)
   - DANGER_ESCALATED (semantic zone transition)
   - CONFIRMED_DEPARTURE (sustained disappearance)
   - EMERGENCY / IMMEDIATE_HAZARD
5. Once an object is warned, SILENCE while situation is unchanged.
6. User-initiated conversations (/api/conversation) are completely separate and never muted.
"""

import time
from typing import Dict, Any, List, Optional, Tuple


class AttentionManager:
    """
    Evaluates continuous tracked objects and determines if a meaningful,
    user-worthy event has occurred requiring autonomous speech.
    """

    def __init__(
        self,
        min_confirm_frames: int = 3,       # ~300ms dwell gate
        departure_confirm_frames: int = 6, # ~600ms disappearance gate
        normal_cooldown_sec: float = 4.0   # Backstop cooldown between non-critical alerts
    ):
        self.min_confirm_frames = min_confirm_frames
        self.departure_confirm_frames = departure_confirm_frames
        self.normal_cooldown_sec = normal_cooldown_sec

        # Persistent tracked entity state: eid -> dict
        self.entities: Dict[str, Dict[str, Any]] = {}
        
        # System state tracking
        self.active_primary_hazard_id: Optional[str] = None
        self.last_speech_time: float = -999.0
        self.last_spoken_text: str = ""

    def get_semantic_zone(self, distance_m: float, prev_zone: Optional[str] = None) -> str:
        """
        Maps continuous distance to semantic zones with hysteresis.
        """
        if prev_zone == "CRITICAL":
            return "CRITICAL" if distance_m < 1.15 else ("DANGER" if distance_m < 1.55 else "CAUTION")
        elif prev_zone == "DANGER":
            if distance_m < 0.9:
                return "CRITICAL"
            return "DANGER" if distance_m < 1.55 else "CAUTION"
        elif prev_zone == "CAUTION":
            if distance_m < 0.9:
                return "CRITICAL"
            elif distance_m < 1.3:
                return "DANGER"
            return "CAUTION" if distance_m < 3.2 else "AWARENESS"
        else:
            if distance_m < 0.9:
                return "CRITICAL"
            elif distance_m < 1.3:
                return "DANGER"
            elif distance_m <= 2.8:
                return "CAUTION"
            elif distance_m <= 4.0:
                return "AWARENESS"
            else:
                return "FAR"

    def evaluate_scene(
        self,
        active_tracks: List[Any],
        timestamp: Optional[float] = None,
        language: str = "te-IN"
    ) -> Dict[str, Any]:
        """
        Main attention evaluation loop.
        Returns a structured decision for autonomous speech.
        """
        t_now = timestamp if timestamp is not None else time.time()
        current_seen_ids = set()
        candidates: List[Dict[str, Any]] = []

        # 1. Update Lifecycle of Visible Tracks
        for track in active_tracks:
            d = track.to_dict() if hasattr(track, "to_dict") else track
            eid = str(d.get("track_id") or d.get("id") or d.get("entity_id") or "1")
            current_seen_ids.add(eid)

            raw_class = str(d.get("detector_class") or d.get("raw_class_name") or d.get("name") or "object").lower()
            dist = float(d.get("distance_m") or d.get("distance") or 3.0)
            motion = str(d.get("motion_state") or d.get("movement") or "STATIONARY").upper()
            sector = str(d.get("spatial_sector") or d.get("direction") or "CENTER").upper()

            if eid not in self.entities:
                # ── NEW ENTITY DETECTED ──
                zone = self.get_semantic_zone(dist)
                init_state = "CONFIRMED" if self.min_confirm_frames <= 1 else "NEW"
                self.entities[eid] = {
                    "eid": eid,
                    "class_name": raw_class,
                    "first_seen": t_now,
                    "last_seen": t_now,
                    "consecutive_frames": 1,
                    "missing_frames": 0,
                    "distance": dist,
                    "zone": zone,
                    "last_warned_zone": None,
                    "warned": False,
                    "warn_time": 0.0,
                    "motion": motion,
                    "sector": sector,
                    "state": init_state
                }
            else:
                # ── EXISTING TRACK ──
                ent = self.entities[eid]
                ent["last_seen"] = t_now
                ent["consecutive_frames"] += 1
                ent["missing_frames"] = 0
                ent["distance"] = dist
                ent["motion"] = motion
                ent["sector"] = sector
                prev_zone = ent["zone"]
                ent["zone"] = self.get_semantic_zone(dist, prev_zone)

                # Dwell Gate: Move from NEW to CONFIRMED after min_confirm_frames
                if ent["state"] == "NEW" and ent["consecutive_frames"] >= self.min_confirm_frames:
                    ent["state"] = "CONFIRMED"

            # 2. Check Candidate for Autonomous Speech
            ent = self.entities[eid]
            candidate_decision = self._test_entity_significance(ent, t_now, language)
            if candidate_decision["should_speak"]:
                candidates.append(candidate_decision)

        # 3. Handle Missing / Departed Tracks
        departure_candidates: List[Dict[str, Any]] = []
        for eid, ent in list(self.entities.items()):
            if eid not in current_seen_ids:
                ent["missing_frames"] += 1
                if ent["warned"] and ent["state"] != "DEPARTED" and ent["missing_frames"] >= self.departure_confirm_frames:
                    ent["state"] = "DEPARTED"
                    # Check if corridor is now clear
                    remaining_obstacles = any(
                        (e["eid"] != eid and e["state"] in ("CONFIRMED", "WARNED", "DANGER_ESCALATED") and e["distance"] <= 2.8)
                        for e in self.entities.values()
                    )
                    
                    if not remaining_obstacles:
                        dep_speech = "సర్, ఇప్పుడు మీ ముందు ఎవరూ లేరు. దారి క్లియర్గా ఉంది. మీరు ముందుకు వెళ్లవచ్చు." if language.startswith("te") else "Sir, path is clear now. You can walk ahead."
                    else:
                        dep_speech = "సర్, ఆ వ్యక్తి వెళ్లారు. ఇంకా ముందు అడ్డంకి ఉంది." if language.startswith("te") else "Sir, person has left. Obstacle still ahead."

                    departure_candidates.append({
                        "should_speak": True,
                        "speech": dep_speech,
                        "priority": "HIGH",
                        "interrupt": False,
                        "eid": eid,
                        "event_type": "CONFIRMED_DEPARTURE",
                        "debug_reason": f"entity_{eid}_confirmed_departure"
                    })
                elif ent["missing_frames"] > 30:
                    # Garbage collect old departed entities
                    self.entities.pop(eid, None)

        candidates.extend(departure_candidates)

        # 4. Select Single Highest-Priority Event (Zero Stacking)
        if candidates:
            # Sort by Priority: CRITICAL > HIGH > MEDIUM > LOW
            prio_map = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
            candidates.sort(key=lambda c: prio_map.get(c.get("priority", "LOW"), 0), reverse=True)
            chosen = candidates[0]

            # Cooldown backstop (CRITICAL, DANGER escalation, and CONFIRMED_DEPARTURE bypass normal cooldown)
            time_since_speech = t_now - self.last_speech_time
            is_urgent_event = (chosen["priority"] == "CRITICAL") or (chosen.get("event_type") in ("CONFIRMED_DEPARTURE", "DANGER_ESCALATED"))
            if not is_urgent_event and time_since_speech < self.normal_cooldown_sec:
                return {
                    "should_speak": False,
                    "speech": "",
                    "priority": "LOW",
                    "interrupt_audio": False,
                    "event": {"event": chosen.get("event_type", "SILENCE")},
                    "debug_reason": f"suppressed_by_cooldown_{time_since_speech:.1f}s"
                }

            # Update Speech State
            self.last_speech_time = t_now
            self.last_spoken_text = chosen["speech"]
            self.active_primary_hazard_id = chosen.get("eid")

            return {
                "should_speak": True,
                "speech": chosen["speech"],
                "priority": chosen["priority"],
                "interrupt_audio": chosen.get("interrupt", False),
                "event": {
                    "event": chosen.get("event_type", "ATTENTION_EVENT"),
                    "entity_id": chosen.get("eid"),
                    "debug_reason": chosen.get("debug_reason")
                },
                "debug_reason": chosen.get("debug_reason")
            }

        # 5. Default: SILENCE BY DESIGN
        return {
            "should_speak": False,
            "speech": "",
            "priority": "LOW",
            "interrupt_audio": False,
            "event": {"event": "SILENCE_BY_DESIGN"},
            "debug_reason": "same_track_same_zone_silent" if current_seen_ids else "same_situation_or_no_threat"
        }

    def _test_entity_significance(
        self,
        ent: Dict[str, Any],
        t_now: float,
        language: str
    ) -> Dict[str, Any]:
        """
        Tests whether an entity warrants autonomous speech.
        """
        eid = ent["eid"]
        raw_class = ent["class_name"]
        dist = ent["distance"]
        zone = ent["zone"]
        state = ent["state"]
        warned = ent["warned"]
        last_warned_zone = ent["last_warned_zone"]
        is_te = language.startswith("te")

        # ── Ignored Background (Distant or Irrelevant) ──
        if zone in ("FAR", "AWARENESS") and ("car" not in raw_class and "vehicle" not in raw_class):
            return {"should_speak": False, "debug_reason": "far_awareness_silent"}

        # ── Case 1: Initial Warning (Requires Dwell Confirmation) ──
        if not warned and state == "CONFIRMED" and zone in ("CAUTION", "DANGER", "CRITICAL"):
            ent["warned"] = True
            ent["warn_time"] = t_now
            ent["last_warned_zone"] = zone
            ent["state"] = "WARNED"

            if "traffic light" in raw_class or "traffic signal" in raw_class or "signal" in raw_class:
                if "green" in raw_class:
                    speech = "సర్, గ్రీన్ ట్రాఫిక్ సిగ్నల్ ఉంది. మీరు ముందుకు వెళ్లవచ్చు." if is_te else "Sir, green traffic signal. Safe to walk."
                    priority = "MEDIUM"
                    interrupt = False
                elif "yellow" in raw_class:
                    speech = "సర్, ఎల్లో ట్రాఫిక్ సిగ్నల్ ఉంది. సిద్ధంగా ఉండండి." if is_te else "Sir, yellow traffic signal. Get ready."
                    priority = "HIGH"
                    interrupt = False
                else:
                    speech = "సర్, ట్రాఫిక్ సిగ్నల్ రెడ్ కలర్లో ఉంది. ఒకసారి ఆగండి." if is_te else "Sir, red traffic signal. Please stop."
                    priority = "HIGH"
                    interrupt = True
            elif "stop sign" in raw_class or "stop board" in raw_class:
                speech = "సర్, స్టాప్ రోడ్ సైన్ బోర్డు ఉంది. ఒకసారి ఆగండి." if is_te else "Sir, Stop road sign board ahead. Please stop."
                priority = "HIGH"
                interrupt = False
            elif "sign" in raw_class or "board" in raw_class:
                if "no entry" in raw_class:
                    speech = "సర్, నో ఎంట్రీ బోర్డు ఉంది. అటు వెళ్లవద్దు." if is_te else "Sir, No Entry sign board ahead. Do not enter."
                    priority = "HIGH"
                    interrupt = True
                elif "zebra" in raw_class or "pedestrian" in raw_class:
                    speech = "సర్, జీబ్రా క్రాసింగ్ లేదా పాదచారుల దారి ఉంది." if is_te else "Sir, pedestrian crossing ahead."
                    priority = "MEDIUM"
                    interrupt = False
                elif "school" in raw_class:
                    speech = "సర్, స్కూల్ జోన్ సైన్ బోర్డు ఉంది." if is_te else "Sir, School Ahead sign board."
                    priority = "MEDIUM"
                    interrupt = False
                else:
                    speech = "సర్, ముందు రోడ్ సైన్ బోర్డు ఉంది." if is_te else "Sir, road sign board ahead."
                    priority = "MEDIUM"
                    interrupt = False
            elif "currency" in raw_class or "note" in raw_class or "rupee" in raw_class:
                speech = f"సర్, ఇది {raw_class}." if is_te else f"Sir, this is a {raw_class}."
                priority = "MEDIUM"
                interrupt = False
            elif "car" in raw_class or "vehicle" in raw_class or "motorcycle" in raw_class:
                speech = "సర్, వాహనం దగ్గరగా ఉంది. ఆగండి." if is_te else "Sir, vehicle close ahead. Please stop."
                priority = "CRITICAL"
                interrupt = True
            elif "person" in raw_class:
                speech = "సర్, మీ ముందు ఒక వ్యక్తి ఉన్నారు. ఒకసారి ఆగండి." if is_te else "Sir, a person is ahead. Please stop a moment."
                priority = "HIGH"
                interrupt = False
            elif "chair" in raw_class or "obstacle" in raw_class:
                speech = "సర్, మీ ముందు కుర్చీ ఉంది. ఒకసారి ఆగండి." if is_te else "Sir, chair ahead. Please stop."
                priority = "MEDIUM"
                interrupt = False
            else:
                speech = "సర్, మీ ముందు అడ్డంకి ఉంది. ఒకసారి ఆగండి." if is_te else "Sir, obstacle ahead. Please stop."
                priority = "MEDIUM"
                interrupt = False

            return {
                "should_speak": True,
                "speech": speech,
                "priority": priority,
                "interrupt": interrupt,
                "eid": eid,
                "event_type": "NEW_CRITICAL_OBSTACLE",
                "debug_reason": f"new_confirmed_{raw_class}_{zone}"
            }

        # ── Case 2: Danger Escalation (Semantic Zone Jump) ──
        if warned and state in ("WARNED", "DANGER_ESCALATED"):
            # If was warned in CAUTION and now enters DANGER (<1.3m) or CRITICAL (<0.9m)
            if (last_warned_zone == "CAUTION" and zone in ("DANGER", "CRITICAL")) or \
               (last_warned_zone == "DANGER" and zone == "CRITICAL"):
                ent["last_warned_zone"] = zone
                ent["state"] = "DANGER_ESCALATED"

                if zone == "CRITICAL":
                    speech = "సర్, ప్రమాదం! చాలా దగ్గరగా ఉంది. వెంటనే ఆగండి." if is_te else "Sir, immediate danger! Stop now."
                    priority = "CRITICAL"
                    interrupt = True
                else:
                    speech = "సర్, చాలా దగ్గరగా వస్తున్నారు. ఆగండి." if is_te else "Sir, getting very close. Please stop."
                    priority = "HIGH"
                    interrupt = True

                return {
                    "should_speak": True,
                    "speech": speech,
                    "priority": priority,
                    "interrupt": interrupt,
                    "eid": eid,
                    "event_type": "DANGER_ESCALATED",
                    "debug_reason": f"escalation_{last_warned_zone}_to_{zone}"
                }

        # ── Case 3: Same State / Minor Movement Jitter ──
        return {
            "should_speak": False,
            "debug_reason": "same_track_same_zone_silent"
        }

    def reset(self):
        """Resets attention manager state."""
        self.entities.clear()
        self.active_primary_hazard_id = None
        self.last_speech_time = 0.0
        self.last_spoken_text = ""
