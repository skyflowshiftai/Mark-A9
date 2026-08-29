from typing import Tuple, Dict, Any
import config

def estimate_relative_distance(class_name: str, bbox_height_px: float, frame_height_px: int) -> Dict[str, Any]:
    """
    Computes relative distance estimation using calibrated reference heights and bounding-box ratio.
    Honesty Rule: Emits clear qualitative proximity (NEAR, MEDIUM, FAR) rather than uncalibrated precision.
    """
    if bbox_height_px <= 5.0 or frame_height_px <= 0:
        return {
            "distance_m": None,
            "status": "UNKNOWN",
            "proximity_zone": "UNKNOWN",
            "display_str": "UNKNOWN"
        }

    # Reference height in meters
    ref_height = config.PHYSICAL_REFERENCE_HEIGHTS_M.get(class_name.lower(), config.DEFAULT_REFERENCE_HEIGHT_M)
    
    # Standard pinhole calculation for internal risk ranking
    raw_dist = (ref_height * config.FOCAL_LENGTH_PX) / bbox_height_px
    estimated_m = round(max(0.3, min(20.0, raw_dist)), 1)

    # Proximity zone based on normalized height fraction
    bbox_ratio = bbox_height_px / frame_height_px
    if bbox_ratio >= config.PROXIMITY_CLOSE_MIN_BBOX_H or estimated_m < 1.5:
        proximity_zone = "NEAR"      # Immediate walking corridor / close proximity
    elif bbox_ratio >= config.PROXIMITY_MEDIUM_MIN_BBOX_H or estimated_m <= 3.5:
        proximity_zone = "MEDIUM"    # Mid-range caution
    else:
        proximity_zone = "FAR"       # Awareness horizon

    return {
        "distance_m": estimated_m,
        "status": "ESTIMATED",
        "proximity_zone": proximity_zone,
        "display_str": f"{proximity_zone}"
    }

def calculate_spatial_sector(norm_center_x: float) -> str:
    """
    Determines horizontal sector: LEFT, CENTER, or RIGHT.
    """
    if norm_center_x < config.ZONE_LEFT_MAX:
        return "LEFT"
    elif norm_center_x > config.ZONE_RIGHT_MIN:
        return "RIGHT"
    return "CENTER"
