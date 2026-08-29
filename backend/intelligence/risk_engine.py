from typing import Dict, Any
from ..vision.tracker import ObjectState

# Hazard weight mapping (out of 20 points)
OBJECT_HAZARD_WEIGHTS = {
    "car": 20.0,
    "truck": 20.0,
    "bus": 20.0,
    "motorcycle": 18.0,
    "train": 20.0,
    "bicycle": 16.0,
    "person": 16.0,
    "dog": 14.0,
    "stairs": 18.0,
    "chair": 12.0,
    "bench": 12.0,
    "fire hydrant": 12.0,
    "stop sign": 10.0,
    "couch": 10.0,
    "potted plant": 8.0,
    "dining table": 10.0,
    "suitcase": 10.0,
    "backpack": 6.0,
    "umbrella": 6.0,
    "bottle": 4.0,
}
DEFAULT_HAZARD_WEIGHT = 10.0

class RiskEngine:
    def __init__(
        self,
        weight_distance: float = 0.40,
        weight_movement: float = 0.25,
        weight_type: float = 0.20,
        weight_position: float = 0.10,
        weight_persistence: float = 0.05
    ):
        self.w_dist = weight_distance
        self.w_move = weight_movement
        self.w_type = weight_type
        self.w_pos = weight_position
        self.w_pers = weight_persistence

    def compute_risk(self, track: ObjectState) -> int:
        """
        Calculates multi-factor risk score [0..100]:
        - Distance (40 pts)
        - Movement / Trajectory (25 pts)
        - Object Class Hazard (20 pts)
        - Lateral Position (10 pts)
        - Temporal Persistence (5 pts)
        """
        # 1. Distance score (0 to 40)
        # Closer objects get higher points: 1.0m -> ~36 pts, 5.0m -> ~20 pts, 10.0m -> 0 pts
        dist_factor = max(0.0, 1.0 - (track.distance_m / 10.0))
        dist_score = (dist_factor ** 1.3) * 40.0

        # 2. Movement score (0 to 25)
        move_score = 0.0
        if track.movement_direction == "APPROACHING":
            if track.movement_speed == "HIGH":
                move_score = 25.0
            elif track.movement_speed == "MEDIUM":
                move_score = 18.0
            else:
                move_score = 10.0
        elif track.movement_direction in ("LATERAL_LEFT", "LATERAL_RIGHT"):
            move_score = 8.0
        elif track.movement_direction == "STATIONARY":
            move_score = 4.0
        else: # RECEDING
            move_score = 0.0

        # 3. Object Type Hazard (0 to 20)
        obj_weight = OBJECT_HAZARD_WEIGHTS.get(track.class_name.lower(), DEFAULT_HAZARD_WEIGHT)
        type_score = obj_weight  # directly scaled to 20

        # 4. Position / Corridor score (0 to 10)
        pos_score = 0.0
        if track.sector == "FORWARD":
            pos_score = 10.0
        elif track.sector in ("LEFT", "RIGHT"):
            if track.movement_direction in ("LATERAL_LEFT", "LATERAL_RIGHT", "APPROACHING"):
                pos_score = 6.0
            else:
                pos_score = 2.0

        # 5. Temporal Persistence (0 to 5)
        # N >= 3 frames confirms it is not a 1-frame visual artifact
        pers_score = 5.0 if track.hit_count >= 3 else 1.5

        # Total weighted score
        raw_total = dist_score + move_score + type_score + pos_score + pers_score
        total_risk = int(round(max(0.0, min(100.0, raw_total))))

        # Update track state directly
        track.risk_score = total_risk
        if total_risk >= 80:
            track.risk_level = "CRITICAL"
        elif total_risk >= 60:
            track.risk_level = "HIGH"
        elif total_risk >= 35:
            track.risk_level = "MEDIUM"
        else:
            track.risk_level = "LOW"

        return total_risk
