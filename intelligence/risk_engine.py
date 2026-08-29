import config
from vision.tracker import TrackedEntity

class RiskEngine:
    def __init__(self):
        self.w_prox = config.WEIGHT_PROXIMITY
        self.w_mot = config.WEIGHT_MOTION
        self.w_type = config.WEIGHT_HAZARD_TYPE
        self.w_corr = config.WEIGHT_CORRIDOR
        self.w_pers = config.WEIGHT_PERSISTENCE

    def evaluate_track_risk(self, track: TrackedEntity) -> float:
        """
        Calculates multi-signal normalized risk score [0.0 .. 1.0].
        Signals:
        1. Object Class (Car > Pedestrian > Obstacle > Small item)
        2. Estimated Proximity (Close > Medium > Far)
        3. Corridor Alignment (Center path > Left/Right shoulder)
        4. Motion Tendency (Approaching > Stationary > Moving away)
        5. Persistence (Hit count confirmation)
        """
        # 1. Object Class Risk (0.0 to 1.0)
        cls_weight = config.HAZARD_CLASS_WEIGHTS.get(track.class_name.lower(), config.DEFAULT_HAZARD_WEIGHT)

        # 2. Proximity Risk (0.0 to 1.0)
        dist_m = track.distance_info.get("distance_m")
        if dist_m is not None:
            prox_factor = max(0.0, 1.0 - (dist_m / 8.0))
        else:
            prox_factor = 0.3 # Fallback if distance unknown

        # 3. Corridor Risk (0.0 to 1.0)
        if track.spatial_sector == "CENTER":
            corr_factor = 1.0
        else:
            corr_factor = 0.4

        # 4. Motion Risk (0.0 to 1.0)
        motion_state = track.motion_info.get("motion_state", "UNKNOWN")
        if motion_state == "APPROACHING":
            mot_factor = 1.0 if track.motion_info.get("is_rapid_approach") else 0.8
        elif motion_state == "LATERAL_CROSSING":
            mot_factor = 0.5
        elif motion_state == "STATIONARY":
            mot_factor = 0.3
        else: # MOVING_AWAY or UNKNOWN
            mot_factor = 0.1

        # 5. Persistence Factor (0.0 to 1.0)
        pers_factor = 1.0 if track.frames_seen >= config.CONFIRMATION_FRAMES else 0.4

        # Combined Weighted Risk Score [0.0 to 1.0]
        raw_score = (
            (self.w_type * cls_weight) +
            (self.w_prox * prox_factor) +
            (self.w_corr * corr_factor) +
            (self.w_mot * mot_factor) +
            (self.w_pers * pers_factor)
        )

        risk_score = round(max(0.0, min(1.0, raw_score)), 3)
        track.risk_score = risk_score

        # Classification into Discrete Risk Levels
        if risk_score >= config.RISK_THRESHOLD_URGENT:
            track.risk_level = "URGENT"
        elif risk_score >= config.RISK_THRESHOLD_CAUTION:
            track.risk_level = "CAUTION"
        elif risk_score >= config.RISK_THRESHOLD_AWARENESS:
            track.risk_level = "AWARENESS"
        else:
            track.risk_level = "SILENT"

        return risk_score
