from typing import Dict, Any, Optional
from ..vision.tracker import ObjectState

class TrajectoryPredictor:
    def __init__(self, warning_horizon_sec: float = 3.0):
        self.warning_horizon_sec = warning_horizon_sec

    def predict_collision(self, track: ObjectState) -> Dict[str, Any]:
        """
        Estimates time-to-danger (TTD) based on kinematic approach velocity.
        """
        velocity = track.approach_velocity_mps
        distance = track.distance_m
        
        ttd_seconds: Optional[float] = None
        predicted_danger = False
        urgency = "NONE"

        if velocity > 0.3 and distance > 0.5:
            ttd_seconds = round(distance / velocity, 1)
            
            if ttd_seconds <= self.warning_horizon_sec:
                predicted_danger = True
                if ttd_seconds <= 1.5:
                    urgency = "IMMINENT"
                else:
                    urgency = "APPROACHING"

        return {
            "predicted_danger": predicted_danger,
            "time_to_danger_sec": ttd_seconds,
            "urgency": urgency,
            "approach_velocity_mps": velocity,
            "is_fast_approaching": velocity >= 1.8
        }
