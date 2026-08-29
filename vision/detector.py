import os
import cv2
import torch
import numpy as np
from typing import List, Dict, Any, Optional
import config

# Optimize CPU multi-threading
torch.set_num_threads(4)

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
    "laptop": 0.35,        # Prevents wooden table planes from misclassifying as laptop
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
        Runs multi-class object detection with geometric plausibility gates and strict NMS.
        Filters out spurious texture artifacts while maintaining high recall across distances.
        """
        if not self.is_loaded or self.model is None or frame_bgr is None or frame_bgr.size == 0:
            return []

        h, w = frame_bgr.shape[:2]
        raw_candidates: List[Dict[str, Any]] = []

        try:
            results = self.model.predict(
                source=frame_bgr,
                conf=0.20,
                iou=0.50,
                max_det=25,
                device=self.device,
                verbose=False,
                imgsz=config.INFERENCE_SIZE
            )

            if results and len(results) > 0:
                res = results[0]
                boxes = res.boxes
                if boxes is not None:
                    for box in boxes:
                        cls_id = int(box.cls[0].item())
                        cls_name = res.names.get(cls_id, f"object_{cls_id}").lower()
                        conf = float(box.conf[0].item())

                        # 1. Class-adaptive confidence threshold
                        min_req_conf = CLASS_THRESHOLDS.get(cls_name, DEFAULT_THRESH)
                        if conf < min_req_conf:
                            continue

                        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                        bw = max(1.0, x2 - x1)
                        bh = max(1.0, y2 - y1)
                        aspect_ratio = bw / bh

                        # 2. Geometric Plausibility Gate
                        if cls_name == "person":
                            if aspect_ratio < 0.12 or aspect_ratio > 2.5:
                                continue
                            if bh < 15.0 or bw < 6.0:
                                continue

                        # Reject extreme aspect ratios on small items
                        if aspect_ratio < 0.06 or aspect_ratio > 7.0:
                            continue

                        cx = (x1 + x2) / 2.0
                        cy = (y1 + y2) / 2.0

                        raw_candidates.append({
                            "class_id": cls_id,
                            "class_name": cls_name,
                            "confidence": round(conf, 3),
                            "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                            "norm_bbox": [
                                round(x1 / w, 4),
                                round(y1 / h, 4),
                                round(x2 / w, 4),
                                round(y2 / h, 4)
                            ],
                            "center": [round(cx, 1), round(cy, 1)],
                            "norm_center": [round(cx / w, 4), round(cy / h, 4)],
                            "width_px": round(bw, 1),
                            "height_px": round(bh, 1),
                            "frame_width": w,
                            "frame_height": h
                        })
        except Exception as e:
            if config.DEBUG_LOGGING:
                print(f"[MARK Detector Inference Error] {e}")

        # 3. Post-Detection Deduplication (Class-Aware Overlap Suppression)
        final_detections: List[Dict[str, Any]] = []
        raw_candidates.sort(key=lambda d: d["confidence"], reverse=True)

        for cand in raw_candidates:
            is_dup = False
            for keep in final_detections:
                if cand["class_name"] == keep["class_name"]:
                    iou, containment = self._calc_iou_and_containment(cand["bbox"], keep["bbox"])
                    if iou > 0.45 or containment > 0.85:
                        is_dup = True
                        break
            if not is_dup:
                final_detections.append(cand)

        return final_detections

    @staticmethod
    def _calc_iou_and_containment(b1: List[float], b2: List[float]):
        x_left = max(b1[0], b2[0])
        y_top = max(b1[1], b2[1])
        x_right = min(b1[2], b2[2])
        y_bottom = min(b1[3], b2[3])

        if x_right < x_left or y_bottom < y_top:
            return 0.0, 0.0

        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        b1_area = max(1.0, (b1[2] - b1[0]) * (b1[3] - b1[1]))
        b2_area = max(1.0, (b2[2] - b2[0]) * (b2[3] - b2[1]))

        iou = intersection_area / float(b1_area + b2_area - intersection_area + 1e-6)
        containment = intersection_area / float(min(b1_area, b2_area))
        return float(iou), float(containment)
