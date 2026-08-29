import time
from typing import Dict, Any, List, Optional, Tuple

SAFETY_THRESHOLDS = {
    "critical_distance_m": 1.5,
    "high_distance_m": 3.0,
    "medium_distance_m": 6.0
}

class ObstaclePriorityEngine:
    """
    Fast, Deterministic, Zero-LLM Safety & Obstacle Priority Engine.
    Evaluates obstacles, computes priority levels, synthesizes short instruction templates,
    and manages cooldown with escalation-based audio interruption.
    """
    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        self.thresholds = thresholds or SAFETY_THRESHOLDS
        self.last_alerts: Dict[int, Dict[str, Any]] = {}
        self.global_last_alert_time = -100.0
        self.cooldown_sec = 2.0

    def evaluate_scene(self, tracks: List[Any], timestamp: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Evaluates all active tracks, selects the highest-priority obstacle,
        and generates a deterministic voice directive with interruption flags.
        """
        if timestamp is None:
            timestamp = time.perf_counter()

        if not tracks:
            return None

        # 1. Rank tracks by safety urgency
        scored_tracks = []
        for t in tracks:
            eval_res = self.evaluate_single_obstacle(t, timestamp)
            if eval_res["priority"] != "IGNORE":
                scored_tracks.append((eval_res["score"], eval_res))

        if not scored_tracks:
            return None

        # Sort highest safety score first
        scored_tracks.sort(key=lambda x: x[0], reverse=True)
        top_score, top_eval = scored_tracks[0]

        # 2. Check Deduplication & Cooldown with Escalation Bypass
        track_id = top_eval["track_id"]
        last = self.last_alerts.get(track_id)

        should_speak = False
        interrupt_audio = False
        reason = "NORMAL"

        priority_ranks = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "IGNORE": 0}
        curr_rank = priority_ranks.get(top_eval["priority"], 0)

        if last is None:
            should_speak = True
            interrupt_audio = (top_eval["priority"] == "CRITICAL")
            reason = "NEW_OBSTACLE"
        else:
            prev_rank = priority_ranks.get(last["priority"], 0)
            dt = timestamp - last["time"]

            # Escalation bypass: if threat level increased (e.g. MEDIUM -> CRITICAL)
            if curr_rank > prev_rank:
                should_speak = True
                interrupt_audio = (top_eval["priority"] == "CRITICAL")
                reason = "THREAT_ESCALATED"
            elif dt >= self.cooldown_sec:
                should_speak = True
                interrupt_audio = (top_eval["priority"] == "CRITICAL")
                reason = "COOLDOWN_EXPIRED"

        if should_speak:
            self.last_alerts[track_id] = {
                "priority": top_eval["priority"],
                "time": timestamp,
                "instruction": top_eval["instruction"]
            }
            self.global_last_alert_time = timestamp

            return {
                "should_speak": True,
                "priority": top_eval["priority"],
                "instruction": top_eval["instruction"],
                "interrupt_audio": interrupt_audio,
                "object": top_eval["object"],
                "distance": top_eval["distance"],
                "direction": top_eval["direction"],
                "reason": reason,
                "track_id": track_id
            }

        return None

    def evaluate_single_obstacle(self, track: Any, timestamp: float) -> Dict[str, Any]:
        """
        Classifies single obstacle into CRITICAL, HIGH, MEDIUM, LOW, or IGNORE,
        and formats human-directional instruction.
        """
        # Support both TrackedEntity object and dict
        if hasattr(track, "to_dict"):
            d = track.to_dict()
        else:
            d = track

        obj_name = d.get("recognized_name") or d.get("class_name") or d.get("name") or "Object"
        raw_class = d.get("raw_class_name") or d.get("detector_class") or obj_name.lower()
        recog_status = d.get("recognition_status") or d.get("recognition_state") or "KNOWN"

        dist_m = d.get("distance_m") or d.get("distance") or 2.5
        prox = d.get("proximity") or d.get("proximity_zone") or "MEDIUM"
        direction = d.get("spatial_sector") or d.get("direction") or "CENTER"
        zone = d.get("spatial_zone") or "CENTER-MIDDLE"
        path_rel = d.get("path_relevance") or "MEDIUM"
        motion = d.get("motion_state") or "STATIONARY"
        approach = d.get("approach_tendency") or "STATIONARY"
        track_id = d.get("track_id") or d.get("id") or 1

        human_dir = self._to_human_direction(direction, zone)
        is_vehicle = raw_class.lower() in ("car", "truck", "bus", "motorcycle", "vehicle")
        is_step = any(s in raw_class.lower() for s in ("stair", "step", "curb", "ledge"))
        is_approaching = (motion == "APPROACHING" or approach == "CLOSING_IN")

        # ── Priority Classification Rules ──
        # 1. CRITICAL: < 1.5m or rapidly approaching vehicle / drop-off
        if dist_m <= self.thresholds["critical_distance_m"] or (is_vehicle and is_approaching and dist_m <= 3.5) or (is_step and dist_m <= 2.0):
            priority = "CRITICAL"
            score = 10.0 + (10.0 - dist_m)
            if is_vehicle:
                instruction = f"Stop. {obj_name.capitalize()} approaching from your {human_dir}." if human_dir != "ahead" else f"Stop. {obj_name.capitalize()} approaching ahead."
            elif is_step:
                instruction = "Stop. Step down directly ahead."
            elif direction == "CENTER" or path_rel == "HIGH":
                instruction = f"Stop. {obj_name.capitalize()} directly ahead." if recog_status != "UNCERTAIN" else "Stop. Obstacle directly ahead."
            else:
                instruction = f"Stop. {obj_name.capitalize()} very close on your {human_dir}."

        # 2. HIGH: 1.5m - 3.0m or approaching obstacle in path
        elif dist_m <= self.thresholds["high_distance_m"] or (path_rel == "HIGH" and dist_m <= 4.0) or is_approaching:
            priority = "HIGH"
            score = 6.0 + (6.0 - dist_m)
            if is_vehicle or is_approaching:
                instruction = f"Warning. {obj_name.capitalize()} approaching on your {human_dir}." if human_dir != "ahead" else f"Warning. {obj_name.capitalize()} approaching ahead."
            elif direction == "CENTER" or path_rel == "HIGH":
                instruction = f"Warning. {obj_name.capitalize()} ahead." if recog_status != "UNCERTAIN" else "Warning. Obstacle ahead."
            else:
                instruction = f"Warning. {obj_name.capitalize()} on your {human_dir}."

        # 3. MEDIUM: 3.0m - 6.0m
        elif dist_m <= self.thresholds["medium_distance_m"]:
            priority = "MEDIUM"
            score = 3.0 + (6.0 - dist_m)
            if direction == "CENTER":
                instruction = f"{obj_name.capitalize()} ahead." if recog_status != "UNCERTAIN" else "Obstacle ahead."
            else:
                instruction = f"{obj_name.capitalize()} on your {human_dir}."

        # 4. LOW / IGNORE: > 6.0m
        else:
            priority = "IGNORE"
            score = 0.0
            instruction = ""

        return {
            "track_id": track_id,
            "object": obj_name,
            "priority": priority,
            "score": round(score, 2),
            "distance": dist_m,
            "direction": human_dir,
            "instruction": instruction
        }

    @staticmethod
    def _to_human_direction(sector: str, zone: str) -> str:
        """
        Converts technical zones into simple natural human directions.
        """
        s = sector.upper()
        if "LEFT" in s or "LEFT" in zone:
            return "left"
        elif "RIGHT" in s or "RIGHT" in zone:
            return "right"
        return "ahead"
