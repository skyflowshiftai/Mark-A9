import time
import numpy as np
from collections import deque
from typing import List, Dict, Any, Optional
import config
from .distance import estimate_relative_distance
from .motion import estimate_relative_motion
from .spatial import compute_spatial_position
from .geometry import analyze_object_geometry
from .hybrid_recognizer import HybridRecognizer

hybrid_recognizer = HybridRecognizer()

class TrackedEntity:
    def __init__(self, track_id: int, detection: Dict[str, Any], timestamp: float, crop_bgr: Optional[np.ndarray] = None):
        self.track_id = track_id
        self.raw_class_name = detection["class_name"]
        self.class_name = self.raw_class_name
        self.confidence = detection["confidence"]
        
        self.bbox = list(detection["bbox"])
        self.norm_bbox = list(detection["norm_bbox"])
        self.center = list(detection["center"])
        self.previous_center = list(detection["center"])
        self.norm_center = list(detection["norm_center"])

        self.frame_width = detection.get("frame_width", 640)
        self.frame_height = detection.get("frame_height", 360)

        self.first_seen = timestamp
        self.last_seen = timestamp
        self.frames_seen = 1
        self.frames_missing = 0
        self.state = "NEW"  # NEW -> CONFIRMED -> ACTIVE -> TEMPORARILY_LOST -> REACQUIRED -> DEPARTED

        self.risk_level = "LOW"
        self.risk_score = 0.0
        self.risk_reason = "No immediate hazard"
        self.last_alert_time = -100.0
        self.alert_count = 0

        # Temporal Class Stability Rolling Queue (bounded maxlen=6)
        self.class_history = deque(maxlen=6)
        
        # 1. Evaluate Recognition through Multi-Signal Confidence Gate
        recog = hybrid_recognizer.evaluate_recognition(
            self.raw_class_name,
            self.confidence,
            self.class_history,
            crop_bgr=crop_bgr
        )
        self.display_name = recog["display_name"]
        self.recognition_status = recog["recognition_status"]
        self.is_confident = recog["is_confident"]
        self.detector_candidate = recog["detector_candidate"]
        self.stability = recog["stability"]
        self.voice_name = recog["voice_name"]

        # 2. Distance / Proximity with Temporal EMA
        self.distance_info = estimate_relative_distance(
            self.raw_class_name,
            detection["height_px"],
            self.frame_height
        )
        raw_dist = self.distance_info.get("distance_m", 2.0)
        self.smoothed_distance_m = float(raw_dist) if raw_dist is not None else 2.0
        self.distance_info["distance_m"] = round(self.smoothed_distance_m, 2)
        self.proximity = self.distance_info.get("proximity_zone", "MEDIUM")

        # 3. 3x3 Spatial Position & Path Relevance Engine
        self.spatial_info = compute_spatial_position(
            self.norm_center[0],
            self.norm_center[1],
            self.proximity
        )
        self.spatial_sector = self.spatial_info["horizontal"]
        self.spatial_zone = self.spatial_info["zone"]
        self.path_relevance = self.spatial_info["path_relevance"]

        # 4. 2D Bounding Box Geometry & Relative Size Engine
        self.geom_info = analyze_object_geometry(
            self.bbox,
            self.frame_width,
            self.frame_height
        )

        # 5. Temporal Motion History (bounded maxlen=20)
        self.history = deque(maxlen=config.MAX_HISTORY_LEN)
        self.history.append({
            "timestamp": timestamp,
            "bbox": list(self.bbox),
            "center": list(self.center),
            "norm_center": list(self.norm_center),
            "distance_m": self.smoothed_distance_m
        })

        self.motion_info = {
            "motion_state": "STATIONARY",
            "motion_direction": "NONE",
            "velocity_x": 0.0,
            "velocity_y": 0.0,
            "approach_tendency": "STATIONARY",
            "is_rapid_approach": False
        }
        self.velocity_x = 0.0
        self.velocity_y = 0.0

        # 6. OCR Metadata
        self.ocr_info = {
            "available": (self.recognition_status == "RECOGNIZED_OCR"),
            "text": recog.get("display_name") if self.recognition_status == "RECOGNIZED_OCR" else None
        }

    def update(self, detection: Dict[str, Any], timestamp: float, alpha: float = 0.35, crop_bgr: Optional[np.ndarray] = None):
        """
        Updates tracked entity with new detection, applies EMA box smoothing,
        and re-evaluates recognition, geometry, spatial position, and motion.
        """
        self.last_seen = timestamp
        self.frames_seen += 1
        self.frames_missing = 0
        
        # Lifecycle transition
        if self.state == "TEMPORARILY_LOST":
            self.state = "REACQUIRED"
        elif self.frames_seen >= 3:
            self.state = "ACTIVE"
        elif self.frames_seen >= 2:
            self.state = "CONFIRMED"

        self.confidence = detection["confidence"]
        self.raw_class_name = detection["class_name"]
        self.class_name = self.raw_class_name
        self.frame_width = detection.get("frame_width", self.frame_width)
        self.frame_height = detection.get("frame_height", self.frame_height)

        # Re-evaluate recognition through Confidence Gate
        recog = hybrid_recognizer.evaluate_recognition(
            self.raw_class_name,
            self.confidence,
            self.class_history,
            crop_bgr=crop_bgr
        )
        self.display_name = recog["display_name"]
        self.recognition_status = recog["recognition_status"]
        self.is_confident = recog["is_confident"]
        self.detector_candidate = recog["detector_candidate"]
        self.stability = recog["stability"]
        self.voice_name = recog["voice_name"]

        # EMA smoothing on bounding box to eliminate jitter
        for i in range(4):
            self.bbox[i] = round(alpha * detection["bbox"][i] + (1.0 - alpha) * self.bbox[i], 1)
            self.norm_bbox[i] = round(alpha * detection["norm_bbox"][i] + (1.0 - alpha) * self.norm_bbox[i], 4)

        self.previous_center = list(self.center)
        self.center = [
            round((self.bbox[0] + self.bbox[2]) / 2.0, 1),
            round((self.bbox[1] + self.bbox[3]) / 2.0, 1)
        ]
        self.norm_center = [
            round(self.center[0] / max(1, self.frame_width), 4),
            round(self.center[1] / max(1, self.frame_height), 4)
        ]

        # Update Distance & Proximity with Outlier Rejection and EMA Smoothing
        self.distance_info = estimate_relative_distance(
            self.raw_class_name,
            detection["height_px"],
            self.frame_height
        )
        raw_dist = self.distance_info.get("distance_m", 2.0)
        if raw_dist is not None:
            # Outlier step clamp if jump is unrealistically large (> 2.0m)
            diff = raw_dist - self.smoothed_distance_m
            if abs(diff) > 2.0 and self.frames_seen > 2:
                clamped_step = np.clip(diff, -0.40, 0.40)
                self.smoothed_distance_m = round(self.smoothed_distance_m + clamped_step, 2)
            else:
                self.smoothed_distance_m = round(0.35 * raw_dist + 0.65 * self.smoothed_distance_m, 2)
            self.distance_info["distance_m"] = self.smoothed_distance_m

        # Update proximity zones
        if self.smoothed_distance_m <= 1.5:
            self.proximity = "NEAR"
        elif self.smoothed_distance_m <= 3.5:
            self.proximity = "MEDIUM"
        else:
            self.proximity = "FAR"
        self.distance_info["proximity_zone"] = self.proximity

        # Update 3x3 Spatial Position & Path Relevance
        self.spatial_info = compute_spatial_position(
            self.norm_center[0],
            self.norm_center[1],
            self.proximity
        )
        self.spatial_sector = self.spatial_info["horizontal"]
        self.spatial_zone = self.spatial_info["zone"]
        self.path_relevance = self.spatial_info["path_relevance"]

        # Update 2D Geometry & Relative Size
        self.geom_info = analyze_object_geometry(
            self.bbox,
            self.frame_width,
            self.frame_height
        )

        # Append to bounded history
        self.history.append({
            "timestamp": timestamp,
            "bbox": list(self.bbox),
            "center": list(self.center),
            "norm_center": list(self.norm_center),
            "distance_m": self.smoothed_distance_m
        })

        # Calculate Relative Motion & Direction from trajectory history
        self.motion_info = estimate_relative_motion(self.history, timestamp)
        
        # Multi-frame velocity & movement classification
        if len(self.history) >= 3:
            dt = max(0.01, self.history[-1]["timestamp"] - self.history[0]["timestamp"])
            ddist = self.history[-1]["distance_m"] - self.history[0]["distance_m"]
            dx = self.history[-1]["center"][0] - self.history[0]["center"][0]
            range_rate = ddist / dt
            lateral_rate = abs(dx) / dt

            if range_rate < -0.25:
                self.motion_info["motion_state"] = "APPROACHING"
            elif range_rate > 0.25:
                self.motion_info["motion_state"] = "MOVING_AWAY"
            elif lateral_rate > 35.0:
                self.motion_info["motion_state"] = "LATERAL_MOVEMENT"
            else:
                self.motion_info["motion_state"] = "STATIONARY"

        self.velocity_x = self.motion_info["velocity_x"]
        self.velocity_y = self.motion_info["velocity_y"]

        # OCR info
        self.ocr_info = {
            "available": (self.recognition_status == "RECOGNIZED_OCR"),
            "text": recog.get("display_name") if self.recognition_status == "RECOGNIZED_OCR" else None
        }

    def mark_missed(self):
        """
        Gracefully handles missed frame: projects trajectory and transitions to TEMPORARILY_LOST.
        """
        self.frames_missing += 1
        self.state = "TEMPORARILY_LOST"
        # Project center based on last velocity
        self.center[0] += self.velocity_x * 0.08
        self.center[1] += self.velocity_y * 0.08

    def to_dict(self) -> Dict[str, Any]:
        """
        Emits authoritative Canonical Object Intelligence Record.
        """
        dist_val = self.distance_info.get("distance_m", self.smoothed_distance_m)
        if dist_val is None:
            dist_val = 2.0

        return {
            "track_id": self.track_id,
            "id": self.track_id,
            "state": self.state,
            "detector_class": self.raw_class_name,
            "raw_class_name": self.raw_class_name,
            "recognized_name": self.display_name,
            "name": self.display_name,
            "class_name": self.display_name,
            "recognition_state": self.recognition_status,
            "recognition_status": self.recognition_status,
            "is_confident": self.is_confident,
            "confidence": self.confidence,
            "stability": self.stability,
            "bbox": self.bbox,
            "bbox_dict": {
                "x1": self.bbox[0],
                "y1": self.bbox[1],
                "x2": self.bbox[2],
                "y2": self.bbox[3]
            },
            "norm_bbox": self.norm_bbox,
            "center": {
                "x": self.center[0],
                "y": self.center[1],
                "nx": self.norm_center[0],
                "ny": self.norm_center[1]
            },
            "position": {
                "horizontal": self.spatial_info["horizontal"],
                "vertical": self.spatial_info["vertical"],
                "zone": self.spatial_info["zone"]
            },
            "spatial_sector": self.spatial_info["horizontal"],
            "direction": self.spatial_info["horizontal"],
            "spatial_zone": self.spatial_info["zone"],
            "shape": {
                "category": self.geom_info["shape_category"],
                "aspect_ratio": self.geom_info["aspect_ratio"],
                "area_ratio": self.geom_info["area_ratio"]
            },
            "shape_category": self.geom_info["shape_category"],
            "size": {
                "category": self.geom_info["relative_size"]
            },
            "relative_size": self.geom_info["relative_size"],
            "proximity": self.proximity,
            "proximity_zone": self.proximity,
            "distance": dist_val,
            "distance_m": dist_val,
            "distance_status": self.distance_info.get("status", "ESTIMATED"),
            "motion": {
                "state": self.motion_info["motion_state"],
                "direction": self.motion_info["motion_direction"],
                "velocity_x": self.velocity_x,
                "velocity_y": self.velocity_y
            },
            "motion_state": self.motion_info["motion_state"],
            "motion_direction": self.motion_info["motion_direction"],
            "path_relevance": self.path_relevance,
            "ocr": self.ocr_info,
            "risk": {
                "level": self.risk_level,
                "score": round(self.risk_score, 2),
                "reason": self.risk_reason
            },
            "risk_level": self.risk_level,
            "threat": self.risk_level,
            "risk_score": round(self.risk_score, 2),
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "frames_seen": self.frames_seen,
            "frames_missing": self.frames_missing
        }

class ObjectTracker:
    def __init__(
        self,
        max_disappeared: int = config.MAX_DISAPPEARED_FRAMES,
        iou_threshold: float = config.IOU_THRESHOLD,
        confirmation_frames: int = config.CONFIRMATION_FRAMES
    ):
        self.next_track_id = 1
        self.tracks: Dict[int, TrackedEntity] = {}
        self.max_disappeared = max_disappeared
        self.iou_threshold = iou_threshold
        self.confirmation_frames = confirmation_frames

    def update(self, detections: List[Dict[str, Any]], timestamp: Optional[float] = None) -> List[TrackedEntity]:
        if timestamp is None:
            timestamp = time.time()

        # Handle empty detections: mark all as missed gracefully
        if len(detections) == 0:
            for track_id in list(self.tracks.keys()):
                self.tracks[track_id].mark_missed()
                if self.tracks[track_id].frames_missing > self.max_disappeared:
                    del self.tracks[track_id]
            return [t for t in self.tracks.values() if t.frames_missing == 0 and t.frames_seen >= self.confirmation_frames]

        # Handle initial state
        if len(self.tracks) == 0:
            for det in detections:
                self._register_track(det, timestamp)
            return [t for t in self.tracks.values() if t.frames_seen >= self.confirmation_frames]

        # Compute IoU matching matrix across ALL tracks (including TEMPORARILY_LOST)
        track_ids = list(self.tracks.keys())
        iou_matrix = np.zeros((len(track_ids), len(detections)), dtype=np.float32)

        for i, tid in enumerate(track_ids):
            for j, det in enumerate(detections):
                iou_matrix[i, j] = self._compute_iou(self.tracks[tid].bbox, det["bbox"])

        matched_tracks = set()
        matched_detections = set()

        # Pass 1: Greedy match highest IoU first
        if iou_matrix.size > 0:
            while True:
                max_iou = np.max(iou_matrix)
                if max_iou < self.iou_threshold:
                    break
                
                i, j = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
                tid = track_ids[i]

                # Match if same class OR strong spatial overlap (>0.30 IoU)
                is_same_class = (self.tracks[tid].raw_class_name == detections[j]["class_name"])
                if is_same_class or max_iou >= 0.30:
                    self.tracks[tid].update(detections[j], timestamp)
                    matched_tracks.add(tid)
                    matched_detections.add(j)
                    iou_matrix[i, :] = -1.0
                    iou_matrix[:, j] = -1.0
                else:
                    # Only suppress this specific pair, leave others open
                    iou_matrix[i, j] = -1.0

        # Pass 2: Centroid Proximity & Re-acquisition for unmatched detections
        for j, det in enumerate(detections):
            if j in matched_detections:
                continue
            
            best_tid = None
            best_dist = 220.0 # Max centroid pixel distance for re-acquisition
            for tid in track_ids:
                if tid in matched_tracks:
                    continue
                dist = np.hypot(self.tracks[tid].center[0] - det["center"][0], self.tracks[tid].center[1] - det["center"][1])
                is_same_class = (self.tracks[tid].raw_class_name == det["class_name"])
                max_allowed = best_dist if is_same_class else (best_dist * 0.6)
                if dist < max_allowed:
                    best_dist = dist
                    best_tid = tid

            if best_tid is not None:
                self.tracks[best_tid].update(det, timestamp)
                matched_tracks.add(best_tid)
                matched_detections.add(j)

        # Pass 3: Unmatched tracks -> gracefully mark missed / TEMPORARILY_LOST
        for tid in track_ids:
            if tid not in matched_tracks:
                self.tracks[tid].mark_missed()
                if self.tracks[tid].frames_missing > self.max_disappeared:
                    del self.tracks[tid]

        # Pass 4: Unmatched detections -> register new track
        for j, det in enumerate(detections):
            if j not in matched_detections:
                self._register_track(det, timestamp)

        return [t for t in self.tracks.values() if t.frames_missing == 0 and t.frames_seen >= self.confirmation_frames]

    def _register_track(self, detection: Dict[str, Any], timestamp: float):
        track = TrackedEntity(self.next_track_id, detection, timestamp)
        self.tracks[self.next_track_id] = track
        self.next_track_id += 1

    @staticmethod
    def _compute_iou(boxA, boxB) -> float:
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        interArea = max(0.0, xB - xA) * max(0.0, yB - yA)
        boxAArea = max(1.0, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
        boxBArea = max(1.0, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))

        iou = interArea / float(boxAArea + boxBArea - interArea)
        return float(iou)
