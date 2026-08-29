import cv2
import numpy as np
from typing import List, Dict, Any
from .tracker import ObjectState

class SceneAnalyzer:
    def __init__(self, blur_threshold: float = 35.0, glare_threshold: float = 240.0, dark_threshold: float = 20.0):
        self.blur_threshold = blur_threshold
        self.glare_threshold = glare_threshold
        self.dark_threshold = dark_threshold

    def evaluate_optical_quality(self, frame_bgr: np.ndarray) -> Dict[str, Any]:
        """
        Evaluates optical degradation such as blur, glare, and extreme darkness.
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return {"is_degraded": True, "defect": "NO_FRAME", "blur_score": 0.0, "mean_intensity": 0.0}

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY) if len(frame_bgr.shape) == 3 else frame_bgr
        
        # Laplacian variance for sharpness/blur
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        mean_intensity = float(np.mean(gray))

        is_degraded = False
        defect = None

        if blur_score < self.blur_threshold:
            is_degraded = True
            defect = "BLUR"
        elif mean_intensity > self.glare_threshold:
            is_degraded = True
            defect = "GLARE"
        elif mean_intensity < self.dark_threshold:
            is_degraded = True
            defect = "DARKNESS"

        return {
            "is_degraded": is_degraded,
            "defect": defect,
            "blur_score": round(blur_score, 1),
            "mean_intensity": round(mean_intensity, 1)
        }

    def summarize_scene(self, tracks: List[ObjectState], optical_quality: Dict[str, Any]) -> Dict[str, Any]:
        """
        Builds a comprehensive scene summary.
        """
        if optical_quality.get("is_degraded", False):
            return {
                "path_state": "UNCERTAIN",
                "path_message": f"Visibility is reduced ({optical_quality.get('defect')})",
                "forward_clear": False,
                "objects_count": len(tracks),
                "left_count": sum(1 for t in tracks if t.sector == "LEFT"),
                "forward_count": sum(1 for t in tracks if t.sector == "FORWARD"),
                "right_count": sum(1 for t in tracks if t.sector == "RIGHT"),
            }

        # Check forward path obstacles
        forward_obstacles = [t for t in tracks if t.sector == "FORWARD" and t.distance_m <= 6.0]
        
        if len(forward_obstacles) > 0:
            # Sort by distance
            forward_obstacles.sort(key=lambda x: x.distance_m)
            nearest = forward_obstacles[0]
            path_state = "OBSTRUCTED"
            path_message = f"Obstacle ahead ({nearest.class_name} at ~{nearest.distance_m}m)"
            forward_clear = False
        else:
            path_state = "CLEAR"
            path_message = "Path clear. Safe to walk."
            forward_clear = True

        return {
            "path_state": path_state,
            "path_message": path_message,
            "forward_clear": forward_clear,
            "objects_count": len(tracks),
            "left_count": sum(1 for t in tracks if t.sector == "LEFT"),
            "forward_count": sum(1 for t in tracks if t.sector == "FORWARD"),
            "right_count": sum(1 for t in tracks if t.sector == "RIGHT"),
            "nearest_forward_distance_m": forward_obstacles[0].distance_m if forward_obstacles else None
        }
