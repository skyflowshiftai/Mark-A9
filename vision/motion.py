from typing import List, Dict, Any, Tuple
from collections import deque
import numpy as np

def estimate_relative_motion(history: deque, current_time: float) -> Dict[str, Any]:
    """
    Analyzes temporal object history to determine approach tendency, relative velocity,
    and image-plane direction vector.
    """
    if len(history) < 2:
        return {
            "motion_state": "STATIONARY",
            "motion_direction": "NONE",
            "velocity_x": 0.0,
            "velocity_y": 0.0,
            "approach_tendency": "STATIONARY",
            "is_rapid_approach": False
        }

    # Compare current state with previous state
    curr = history[-1]
    prev = history[-2]

    dt = max(0.01, curr["timestamp"] - prev["timestamp"])
    
    # Delta center in pixel coordinates
    dx = (curr["center"][0] - prev["center"][0]) / dt
    dy = (curr["center"][1] - prev["center"][1]) / dt

    # Delta height (proxy for closing distance: expanding box = approaching)
    curr_h = curr["bbox"][3] - curr["bbox"][1]
    prev_h = prev["bbox"][3] - prev["bbox"][1]
    dh_ratio = (curr_h - prev_h) / max(1.0, prev_h)

    # Multi-frame trend over last 4 frames if available
    if len(history) >= 4:
        first = history[-4]
        first_h = first["bbox"][3] - first["bbox"][1]
        overall_dh_ratio = (curr_h - first_h) / max(1.0, first_h)
    else:
        overall_dh_ratio = dh_ratio

    # Image-plane cardinal direction
    if abs(dx) > 30.0:
        dir_x = "RIGHT" if dx > 0 else "LEFT"
    else:
        dir_x = ""

    if abs(dy) > 30.0:
        dir_y = "DOWN" if dy > 0 else "UP"
    else:
        dir_y = ""

    motion_dir = f"{dir_y} {dir_x}".strip() if (dir_x or dir_y) else "NONE"

    # Classification of relative approach tendency
    if overall_dh_ratio > 0.08:
        motion_state = "APPROACHING"
        approach_tendency = "CLOSING_IN"
        is_rapid = overall_dh_ratio > 0.20
    elif overall_dh_ratio < -0.08:
        motion_state = "MOVING_AWAY"
        approach_tendency = "RECEDING"
        is_rapid = False
    elif abs(dx) > 35.0 or abs(dy) > 35.0:
        motion_state = "MOVING"
        approach_tendency = "LATERAL"
        is_rapid = False
    else:
        motion_state = "STATIONARY"
        approach_tendency = "STATIONARY"
        is_rapid = False

    return {
        "motion_state": motion_state,
        "motion_direction": motion_dir,
        "velocity_x": round(dx, 1),
        "velocity_y": round(dy, 1),
        "approach_tendency": approach_tendency,
        "is_rapid_approach": is_rapid
    }
