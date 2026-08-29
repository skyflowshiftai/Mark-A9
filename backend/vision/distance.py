import math

# Calibrated physical reference dimensions (height in meters) for common obstacles/entities
REFERENCE_HEIGHTS_M = {
    "person": 1.70,
    "bicycle": 1.05,
    "car": 1.50,
    "motorcycle": 1.15,
    "bus": 3.20,
    "truck": 3.00,
    "traffic light": 0.90,
    "fire hydrant": 0.75,
    "stop sign": 0.80,
    "bench": 0.85,
    "dog": 0.55,
    "cat": 0.30,
    "backpack": 0.45,
    "umbrella": 0.90,
    "handbag": 0.35,
    "suitcase": 0.65,
    "bottle": 0.25,
    "chair": 0.85,
    "couch": 0.85,
    "potted plant": 0.60,
    "bed": 0.65,
    "dining table": 0.75,
    "tv": 0.60,
    "laptop": 0.25,
    "door": 2.00,
    "stairs": 1.20,
    "pole": 2.50,
    "trash can": 0.85,
}
DEFAULT_HEIGHT_M = 1.00

def estimate_distance_meters(
    object_class: str,
    bbox_height_px: float,
    image_height_px: int = 360,
    focal_length_px: float = 550.0
) -> float:
    """
    Estimates metric distance (in meters) using pinhole camera projection:
    Distance = (Real_Height * Focal_Length) / Pixel_Height
    """
    if bbox_height_px <= 2:
        return 25.0

    real_height = REFERENCE_HEIGHTS_M.get(object_class.lower(), DEFAULT_HEIGHT_M)
    
    # Avoid zero division
    distance = (real_height * focal_length_px) / max(bbox_height_px, 5.0)
    
    # Clamp to realistic physical range [0.3m, 30.0m]
    return round(max(0.3, min(30.0, distance)), 2)

def calculate_spatial_sector(
    center_x_norm: float,
    left_boundary: float = 0.35,
    right_boundary: float = 0.65
) -> str:
    """
    Partitions field of view into lateral corridors:
    - LEFT: [0.0, left_boundary)
    - FORWARD: [left_boundary, right_boundary]
    - RIGHT: (right_boundary, 1.0]
    """
    if center_x_norm < left_boundary:
        return "LEFT"
    elif center_x_norm > right_boundary:
        return "RIGHT"
    return "FORWARD"
