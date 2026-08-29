import os
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple

# Calibrated physical reference heights (meters)
PHYSICAL_HEIGHTS_M = {
    "person": 1.70,
    "bicycle": 1.05,
    "car": 1.50,
    "motorcycle": 1.15,
    "bus": 3.20,
    "truck": 3.00,
    "dog": 0.60,
    "cat": 0.30,
    "chair": 0.85,
    "couch": 0.85,
    "potted plant": 0.60,
    "bed": 0.65,
    "dining table": 0.75,
    "tv": 0.60,
    "laptop": 0.25,
    "door": 2.00,
    "stairs": 1.20,
    "bottle": 0.25,
    "cup": 0.15,
    "backpack": 0.45,
    "suitcase": 0.65,
    "traffic light": 0.90,
    "stop sign": 0.80,
    "bench": 0.85,
}
DEFAULT_HEIGHT_M = 1.00
FOCAL_LENGTH_PX = 550.0

class MarkDetector:
    def __init__(self, model_name: str = "yolov8n.pt", conf_thresh: float = 0.35):
        self.conf_thresh = conf_thresh
        self.model_name = model_name
        self.model = None
        self._load_yolo()

    def _load_yolo(self):
        try:
            from ultralytics import YOLO
            # Look in local models dir or auto-download
            models_dir = os.path.join(os.path.dirname(__file__), "models")
            os.makedirs(models_dir, exist_ok=True)
            model_path = os.path.join(models_dir, self.model_name)

            if not os.path.exists(model_path):
                model_path = self.model_name

            print(f"[MARK 2.0 Detector] Loading YOLOv8 from {model_path}...")
            self.model = YOLO(model_path)
            print("[MARK 2.0 Detector] YOLOv8 initialized successfully.")
        except Exception as e:
            print(f"[MARK 2.0 Detector Warning] Error loading YOLO model: {e}")
            self.model = None

    def process_frame(self, frame_bgr: np.ndarray) -> Dict[str, Any]:
        """
        Runs YOLOv8 detection, estimates metric distance, determines spatial direction,
        and assigns RED / YELLOW / GREEN threat classifications.
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return {
                "objects": [],
                "highest_threat": "SILENT",
                "total_objects": 0
            }

        h, w = frame_bgr.shape[:2]
        detected_objects: List[Dict[str, Any]] = []
        highest_threat = "SILENT"

        if self.model is not None:
            try:
                results = self.model.predict(
                    source=frame_bgr,
                    conf=self.conf_thresh,
                    verbose=False
                )

                if results and len(results) > 0:
                    res = results[0]
                    if boxes is not None:
                        for box in boxes:
                            cls_id = int(box.cls[0].item())
                            cls_name = res.names.get(cls_id, f"object_{cls_id}").lower()
                            conf = float(box.conf[0].item())
                            
                            if cls_name == "person" and conf < 0.48:
                                continue

                            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                            box_width_px = max(1.0, x2 - x1)
                            box_height_px = max(5.0, y2 - y1)
                            aspect_ratio = box_width_px / box_height_px

                            # Reject thin vertical slivers (e.g. wood grain texture artifacts)
                            if cls_name == "person":
                                if aspect_ratio < 0.20 or aspect_ratio > 1.5 or box_height_px < 45.0:
                                    continue
                            center_x = (x1 + x2) / 2.0
                            center_x_norm = center_x / max(1, w)

                            # 1. Distance Calculation (Box size formula)
                            real_height = PHYSICAL_HEIGHTS_M.get(cls_name.lower(), DEFAULT_HEIGHT_M)
                            distance_m = round(max(0.3, min(25.0, (real_height * FOCAL_LENGTH_PX) / box_height_px)), 1)

                            # 2. Position in frame (LEFT / CENTER / RIGHT)
                            if center_x_norm < 0.35:
                                direction = "LEFT"
                            elif center_x_norm > 0.65:
                                direction = "RIGHT"
                            else:
                                direction = "CENTER"

                            # 3. Threat Calculator
                            # RED: under 1 meter
                            # YELLOW: 1 to 3 meters
                            # GREEN: above 3 meters
                            if distance_m < 1.0 or (direction == "CENTER" and distance_m <= 1.4):
                                threat = "RED"
                            elif 1.0 <= distance_m <= 3.0:
                                threat = "YELLOW"
                            else:
                                threat = "GREEN"

                            # Threat priority update
                            if threat == "RED":
                                highest_threat = "RED"
                            elif threat == "YELLOW" and highest_threat != "RED":
                                highest_threat = "YELLOW"
                            elif threat == "GREEN" and highest_threat == "SILENT":
                                highest_threat = "GREEN"

                            detected_objects.append({
                                "name": cls_name,
                                "confidence": round(conf, 2),
                                "distance": distance_m,
                                "direction": direction,
                                "threat": threat,
                                "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                                "norm_bbox": [
                                    round(x1 / w, 4),
                                    round(y1 / h, 4),
                                    round(x2 / w, 4),
                                    round(y2 / h, 4)
                                ]
                            })
            except Exception as e:
                print(f"[MARK 2.0 Detector Error] Prediction error: {e}")

        # Sort objects by distance (closest first)
        detected_objects.sort(key=lambda x: x["distance"])

        return {
            "objects": detected_objects,
            "highest_threat": highest_threat,
            "total_objects": len(detected_objects)
        }
