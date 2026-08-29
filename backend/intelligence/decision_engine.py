import time
from typing import List, Dict, Any, Optional
from ..vision.tracker import ObjectState
from .risk_engine import RiskEngine
from .priority_engine import PriorityEngine
from .prediction import TrajectoryPredictor

class DecisionEngine:
    def __init__(self, alert_cooldown_sec: float = 3.0, green_silence: bool = True):
        self.alert_cooldown_sec = alert_cooldown_sec
        self.green_silence = green_silence
        self.risk_engine = RiskEngine()
        self.priority_engine = PriorityEngine()
        self.predictor = TrajectoryPredictor()
        
        self.last_global_alert_time = -100.0
        self.last_alert_message = ""
        self.last_alert_track_id: Optional[int] = None

    def evaluate(
        self,
        tracks: List[ObjectState],
        optical_quality: Dict[str, Any],
        timestamp: float = None
    ) -> Dict[str, Any]:
        """
        MARK DECISION ENGINE:
        SEE -> UNDERSTAND -> DECIDE -> SPEAK
        """
        if timestamp is None:
            timestamp = time.time()

        # Step 1: Compute risk for every tracked object
        for track in tracks:
            self.risk_engine.compute_risk(track)

        # Step 2: Evaluate Optical Degradation Fail-Safe
        if optical_quality.get("is_degraded", False):
            defect = optical_quality.get("defect", "UNCERTAIN")
            msg = "Visibility is reduced."
            should_speak = (timestamp - self.last_global_alert_time) > 8.0
            
            if should_speak:
                self.last_global_alert_time = timestamp
                self.last_alert_message = msg

            return {
                "decision_state": "WARNING",
                "should_speak": should_speak,
                "voice_message": msg if should_speak else "",
                "reason": f"Optical degradation ({defect})",
                "risk_level": "MEDIUM",
                "primary_object": None,
                "reasoning_chain": {
                    "perception": f"Optical defect detected: {defect}",
                    "context": "Sensor visibility below safety confidence threshold",
                    "risk": "Medium (Sensor uncertainty)",
                    "decision": "Signal reduced visibility — avoid false confidence",
                    "voice": msg
                }
            }

        # Step 3: Priority selection of primary hazard
        primary = self.priority_engine.select_primary_hazard(tracks)

        if not primary:
            # Green Silence: Path is clear, remain silent
            return {
                "decision_state": "SILENCE",
                "should_speak": False,
                "voice_message": "",
                "reason": "Forward walking path clear",
                "risk_level": "LOW",
                "primary_object": None,
                "reasoning_chain": {
                    "perception": "Zero actionable obstacles in corridor",
                    "context": "Forward walking path is open",
                    "risk": "Low (Safe)",
                    "decision": "Remain silent — avoid auditory clutter",
                    "voice": "— (Silent)"
                }
            }

        # Step 4: Trajectory & Collision prediction
        pred = self.predictor.predict_collision(primary)

        # Step 5: Formulate concise spoken cue
        voice_msg = self._generate_spoken_cue(primary, pred)
        
        # Step 6: Cooldown & Repeat Suppression Gate
        time_since_track_alert = timestamp - primary.last_alert_time
        time_since_global_alert = timestamp - self.last_global_alert_time
        
        is_critical_spike = primary.risk_level == "CRITICAL" and (primary.risk_score >= 85)
        cooldown_cleared = (time_since_track_alert >= self.alert_cooldown_sec) and (time_since_global_alert >= 1.8)

        should_speak = False
        if (cooldown_cleared or is_critical_spike) and primary.hit_count >= 2:
            should_speak = True
            primary.last_alert_time = timestamp
            primary.alert_count += 1
            self.last_global_alert_time = timestamp
            self.last_alert_message = voice_msg
            self.last_alert_track_id = primary.track_id

        # Determine Decision State
        if primary.risk_level in ("CRITICAL", "HIGH"):
            state = "WARNING" if primary.risk_level == "HIGH" else "EMERGENCY"
        else:
            state = "INFO"

        return {
            "decision_state": state,
            "should_speak": should_speak,
            "voice_message": voice_msg if should_speak else "",
            "active_message": voice_msg,
            "reason": f"Track #{primary.track_id} ({primary.class_name}) in {primary.sector} at {primary.distance_m}m",
            "risk_level": primary.risk_level,
            "risk_score": primary.risk_score,
            "primary_object": primary.to_dict(),
            "reasoning_chain": {
                "perception": f"{primary.class_name.capitalize()} detected at ~{primary.distance_m}m",
                "context": f"{primary.sector} sector, {primary.movement_direction.lower()}",
                "risk": f"{primary.risk_level.capitalize()} ({primary.risk_score}/100)",
                "decision": f"Alert user via voice cue ({state})" if should_speak else "Track visually, cooldown active",
                "voice": voice_msg
            }
        }

    def _generate_spoken_cue(self, track: ObjectState, prediction: Dict[str, Any]) -> str:
        name = track.class_name.lower()
        sector = track.sector
        direction = track.movement_direction

        # 1. Approaching vehicle / high-speed threat
        if name in ("car", "truck", "bus", "motorcycle"):
            if direction == "APPROACHING" or prediction.get("predicted_danger"):
                if track.distance_m <= 3.5:
                    return f"{name.capitalize()} approaching. Stop."
                elif sector == "RIGHT":
                    return "Vehicle entering path from your right."
                elif sector == "LEFT":
                    return "Vehicle entering path from your left."
                return "Vehicle approaching."
            else:
                return "Vehicle ahead."

        # 2. Pedestrian
        if name == "person":
            if sector == "FORWARD":
                if track.distance_m <= 2.5:
                    return "Person close ahead."
                return "Person ahead."
            elif sector == "LEFT" and direction in ("APPROACHING", "LATERAL_RIGHT"):
                return "Person crossing from your left."
            elif sector == "RIGHT" and direction in ("APPROACHING", "LATERAL_LEFT"):
                return "Person crossing from your right."
            return "Person ahead."

        # 3. Stairs or drop hazards
        if "stair" in name or "step" in name:
            return "Stairs ahead. Caution."

        # 4. Low barriers & Furniture (trip hazards)
        if name in ("chair", "bench", "couch", "table", "dining table", "suitcase", "trash can"):
            if sector == "FORWARD":
                return f"Obstacle ahead. {name.capitalize()}."
            return f"{name.capitalize()} on your {sector.lower()}."

        # 5. Default concise alert
        if sector == "FORWARD":
            return f"Obstacle ahead. {name.capitalize()}."
        return f"{name.capitalize()} on your {sector.lower()}."
