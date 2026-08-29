import os
import torch

# ── Hardware & Model Configuration ──
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_NAME = "yolov8n.pt"

CONFIDENCE_THRESHOLD = 0.30
FRAME_WIDTH = 640
FRAME_HEIGHT = 360
INFERENCE_SIZE = 416  # High-speed optimized resolution for <15ms real-time CPU detection

# ── Tracking & Temporal Parameters ──
MAX_DISAPPEARED_FRAMES = 12
IOU_THRESHOLD = 0.30
CONFIRMATION_FRAMES = 1
MAX_HISTORY_LEN = 20

# ── Spatial & Walking Corridor Zones ──
# Horizontal partition (0.0 to 1.0)
ZONE_LEFT_MAX = 0.33
ZONE_RIGHT_MIN = 0.66

# Vertical / Proximity thresholds (fraction of frame height)
PROXIMITY_CLOSE_MIN_BBOX_H = 0.40   # Large bbox -> NEAR (< 1.5m)
PROXIMITY_MEDIUM_MIN_BBOX_H = 0.18  # Medium bbox -> MEDIUM (1.5 - 3.5m)
                                    # Small bbox -> FAR (> 3.5m)

# Calibrated physical reference heights (meters) for relative distance estimation
PHYSICAL_REFERENCE_HEIGHTS_M = {
    "person": 1.70,
    "bicycle": 1.05,
    "car": 1.50,
    "motorcycle": 1.15,
    "bus": 3.20,
    "truck": 3.00,
    "dog": 0.60,
    "cat": 0.30,
    "chair": 0.85,
    "dining table": 0.75,
    "bench": 0.85,
    "bottle": 0.25,
    "cup": 0.15,
    "backpack": 0.45,
    "handbag": 0.35,
    "suitcase": 0.70,
    "cell phone": 0.15,
    "laptop": 0.25,
    "book": 0.20,
    "stairs": 1.20,
    "door": 2.00
}
DEFAULT_REFERENCE_HEIGHT_M = 0.80
FOCAL_LENGTH_PX = 550.0  # Standard pinhole calibration for 720p/360p downscaled webcams

# ── Risk Engine Weights (0.0 to 1.0) ──
WEIGHT_PROXIMITY = 0.35
WEIGHT_MOTION = 0.25
WEIGHT_HAZARD_TYPE = 0.20
WEIGHT_CORRIDOR = 0.15
WEIGHT_PERSISTENCE = 0.05

# Hazard Type Base Weights (0.0 to 1.0)
HAZARD_CLASS_WEIGHTS = {
    # High-Risk Dynamic Hazards
    "car": 1.0,
    "truck": 1.0,
    "bus": 1.0,
    "motorcycle": 0.9,
    "train": 1.0,
    "bicycle": 0.8,
    "dog": 0.7,
    "cow": 0.7,
    "horse": 0.7,
    # Walking Obstacles & Trip Hazards
    "stairs": 0.9,
    "chair": 0.7,
    "bench": 0.65,
    "dining table": 0.6,
    "fire hydrant": 0.6,
    "stop sign": 0.5,
    "traffic light": 0.5,
    "suitcase": 0.6,
    "backpack": 0.4,
    # Awareness & Nearby Objects
    "person": 0.55,
    "bottle": 0.30,
    "cup": 0.20,
    "laptop": 0.25,
    "cell phone": 0.15,
    "book": 0.15
}
DEFAULT_HAZARD_WEIGHT = 0.35

# Risk Level Classification Thresholds
RISK_THRESHOLD_URGENT = 0.75
RISK_THRESHOLD_CAUTION = 0.50
RISK_THRESHOLD_AWARENESS = 0.25

# ── Voice Controller & Silence Policy ──
ALERT_COOLDOWN_SEC = 2.5
MAX_REPEAT_ALERT_COUNT = 2
SILENCE_ENABLED = True

# ── Demo & Debug Mode ──
DEMO_MODE = False
DEBUG_LOGGING = True
