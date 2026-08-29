import os
import cv2
import numpy as np
from typing import List, Dict, Any
import config

CLASS_THRESHOLDS = {
    "person": 0.28,        # Ultra-high sensitivity for humans
    "traffic light": 0.26, # High sensitivity for traffic signals
    "stop sign": 0.26,     # High sensitivity for stop & road signs
    "car": 0.28,
    "bus": 0.28,
    "truck": 0.28,
    "motorcycle": 0.28,
    "bicycle": 0.28,
    "chair": 0.28,
    "bottle": 0.28,
    "cup": 0.28,
    "laptop": 0.35,
    "cell phone": 0.28,
    "book": 0.30,
    "keyboard": 0.30,
    "clock": 0.55,
    "tie": 0.60,
    "fire hydrant": 0.40
}
DEFAULT_THRESH = 0.28

class ObjectDetector:
    def __init__(self, model_name: str = config.MODEL_NAME, conf_thresh: float = config.CONFIDENCE_THRESHOLD):
        self.model_name = model_name
        self.conf_thresh = conf_thresh
        self.device = config.DEVICE
        self.model = None
        self.is_loaded = False
        self.class_names = {}
        self._load_model()

    def _load_model(self):
        try:
            from ultralytics import YOLO
            # Check local directory first
            model_path = self.model_name
            if not os.path.exists(model_path):
                models_dir_path = os.path.join(os.path.dirname(__file__), "..", "models", self.model_name)
                if os.path.exists(models_dir_path):
                    model_path = models_dir_path

            print(f"[MARK Detector] Loading {model_path} onto {self.device.upper()}...")
            self.model = YOLO(model_path)
            self.model.to(self.device)
            self.class_names = self.model.names if hasattr(self.model, "names") else {}
            self.is_loaded = True
            print(f"[MARK Detector] YOLOv8n initialized successfully on {self.device.upper()} with {len(self.class_names)} supported COCO classes.")
        except Exception as e:
            print(f"[MARK Detector Error] Failed to load YOLO model: {e}")
            self.model = None
            self.is_loaded = False

    def detect(self, frame_bgr: np.ndarray) -> List[Dict[str, Any]]:
        """
        Returns a list of raw detections with normalized coordinates and class info.
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return []

        h, w = frame_bgr.shape[:2]
        detections = []

        if self.is_loaded and self.model is not None:
            try:
                results = self.model.predict(
                    source=frame_bgr,
                    conf=self.conf_thresh,
                    iou=self.iou_thresh,
                    verbose=False
                )

                if results and len(results) > 0:
                    res = results[0]
                    boxes = res.boxes
                    if boxes is not None:
                        for box in boxes:
                            cls_id = int(box.cls[0].item())
                            cls_name = res.names.get(cls_id, f"class_{cls_id}")
                            conf = float(box.conf[0].item())
                            
                            # xyxy in pixel coords
                            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                            
                            # Normalized coords [0.0, 1.0]
                            norm_x1 = max(0.0, min(1.0, x1 / max(1, w)))
                            norm_y1 = max(0.0, min(1.0, y1 / max(1, h)))
                            norm_x2 = max(0.0, min(1.0, x2 / max(1, w)))
                            norm_y2 = max(0.0, min(1.0, y2 / max(1, h)))

                            detections.append({
                                "class_name": cls_name,
                                "confidence": round(conf, 3),
                                "pixel_box": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                                "norm_box": [round(norm_x1, 4), round(norm_y1, 4), round(norm_x2, 4), round(norm_y2, 4)],
                                "width_px": round(x2 - x1, 1),
                                "height_px": round(y2 - y1, 1),
                                "center_x_norm": round((norm_x1 + norm_x2) / 2.0, 4),
                                "center_y_norm": round((norm_y1 + norm_y2) / 2.0, 4),
                            })
            except Exception as e:
                print(f"[MARK Detector Error] Inference error: {e}")

        return detections
