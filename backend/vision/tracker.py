import math
import time
import numpy as np
from typing import List, Dict, Any
from .distance import estimate_distance_meters, calculate_spatial_sector

def calculate_iou(boxA, boxB) -> float:
    if not boxA or not boxB or len(boxA) < 4 or len(boxB) < 4:
        return 0.0
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0.0, xB - xA) * max(0.0, yB - yA)
    boxAArea = max(1.0, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    boxBArea = max(1.0, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))
    return float(interArea / float(boxAArea + boxBArea - interArea + 1e-6))

class ObjectState:
    def __init__(self, track_id: int, detection: Dict[str, Any], timestamp: float):
        self.track_id = track_id
        self.class_name = detection["class_name"]
        self.confidence = detection["confidence"]
        self.pixel_box = detection["pixel_box"]
        self.norm_box = detection["norm_box"]
        
        # Position and spatial estimation
        self.center_x_norm = detection["center_x_norm"]
        self.center_y_norm = detection["center_y_norm"]
        self.height_px = detection["height_px"]
        self.width_px = detection["width_px"]
        
        self.distance_m = estimate_distance_meters(self.class_name, self.height_px)
        self.sector = calculate_spatial_sector(self.center_x_norm)
        
        # History for velocity & trajectory estimation
        self.history = [{
            "timestamp": timestamp,
            "center_x_norm": self.center_x_norm,
            "center_y_norm": self.center_y_norm,
            "distance_m": self.distance_m,
            "height_px": self.height_px
        }]
        
        # Kinematics
        self.movement_direction = "STATIONARY"
        self.movement_speed = "ZERO"
        self.approach_velocity_mps = 0.0  # meters per second (positive = approaching)
        self.disappeared_frames = 0
        self.hit_count = 1
        
        # Risk & Alert bookkeeping
        self.risk_score = 0
        self.risk_level = "LOW"
        self.last_alert_time = 0.0
        self.alert_count = 0

    def update(self, detection: Dict[str, Any], timestamp: float, alpha: float = 0.35):
        self.confidence = detection["confidence"]
        self.pixel_box = detection["pixel_box"]
        self.norm_box = detection["norm_box"]
        
        new_center_x = detection["center_x_norm"]
        new_center_y = detection["center_y_norm"]
        new_height_px = detection["height_px"]
        new_width_px = detection["width_px"]
        
        raw_dist = estimate_distance_meters(self.class_name, new_height_px)
        
        # Exponential Moving Average (EMA) smoothing for distance & position
        self.distance_m = round(alpha * raw_dist + (1.0 - alpha) * self.distance_m, 2)
        self.center_x_norm = round(alpha * new_center_x + (1.0 - alpha) * self.center_x_norm, 4)
        self.center_y_norm = round(alpha * new_center_y + (1.0 - alpha) * self.center_y_norm, 4)
        self.height_px = round(alpha * new_height_px + (1.0 - alpha) * self.height_px, 1)
        self.width_px = round(alpha * new_width_px + (1.0 - alpha) * self.width_px, 1)
        
        self.sector = calculate_spatial_sector(self.center_x_norm)
        self.disappeared_frames = 0
        self.hit_count += 1
        
        # Append history
        self.history.append({
            "timestamp": timestamp,
            "center_x_norm": self.center_x_norm,
            "center_y_norm": self.center_y_norm,
            "distance_m": self.distance_m,
            "height_px": self.height_px
        })
        
        # Keep maximum 20 historical frames
        if len(self.history) > 20:
            self.history.pop(0)
            
        self._calculate_kinematics()

    def _calculate_kinematics(self):
        if len(self.history) < 3:
            self.movement_direction = "STATIONARY"
            self.movement_speed = "ZERO"
            return
            
        first = self.history[0]
        last = self.history[-1]
        dt = max(0.05, last["timestamp"] - first["timestamp"])
        
        # Distance delta (positive = getting closer)
        delta_dist = first["distance_m"] - last["distance_m"]
        self.approach_velocity_mps = round(delta_dist / dt, 2)
        
        # Lateral movement
        delta_x = last["center_x_norm"] - first["center_x_norm"]
        
        # Determine Direction
        if self.approach_velocity_mps > 0.4:
            self.movement_direction = "APPROACHING"
        elif self.approach_velocity_mps < -0.4:
            self.movement_direction = "RECEDING"
        elif abs(delta_x) > 0.10:
            self.movement_direction = "LATERAL_RIGHT" if delta_x > 0 else "LATERAL_LEFT"
        else:
            self.movement_direction = "STATIONARY"
            
        # Determine Speed
        abs_speed = abs(self.approach_velocity_mps)
        if abs_speed > 2.0:
            self.movement_speed = "HIGH"
        elif abs_speed > 0.8:
            self.movement_speed = "MEDIUM"
        elif abs_speed > 0.2:
            self.movement_speed = "LOW"
        else:
            self.movement_speed = "ZERO"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "pixel_box": self.pixel_box,
            "norm_box": self.norm_box,
            "distance_m": self.distance_m,
            "sector": self.sector,
            "movement_direction": self.movement_direction,
            "movement_speed": self.movement_speed,
            "approach_velocity_mps": self.approach_velocity_mps,
            "hit_count": self.hit_count,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "is_in_path": self.sector == "FORWARD" and self.distance_m <= 8.0,
        }


class ObjectTracker:
    def __init__(self, max_disappeared: int = 15, max_distance_norm: float = 0.25, smoothing_alpha: float = 0.35, iou_threshold: float = 0.20):
        self.next_track_id = 1
        self.tracks: Dict[int, ObjectState] = {}
        self.max_disappeared = max_disappeared
        self.max_distance_norm = max_distance_norm
        self.smoothing_alpha = smoothing_alpha
        self.iou_threshold = iou_threshold

    def update(self, detections: List[Dict[str, Any]], timestamp: float = None) -> List[ObjectState]:
        if timestamp is None:
            timestamp = time.time()

        # If no tracks exist yet, register all detections
        if len(self.tracks) == 0:
            for det in detections:
                self._register(det, timestamp)
            return list(self.tracks.values())

        # If no detections in current frame, mark all tracks as disappeared
        if len(detections) == 0:
            disappeared_ids = []
            for tid, state in self.tracks.items():
                state.disappeared_frames += 1
                if state.disappeared_frames > self.max_disappeared:
                    disappeared_ids.append(tid)
            for tid in disappeared_ids:
                del self.tracks[tid]
            return [t for t in self.tracks.values() if t.disappeared_frames == 0]

        # Associate existing tracks with new detections using IoU + Centroid distance
        track_ids = list(self.tracks.keys())
        iou_matrix = np.zeros((len(track_ids), len(detections)))
        for i, tid in enumerate(track_ids):
            for j, det in enumerate(detections):
                iou_matrix[i, j] = calculate_iou(self.tracks[tid].pixel_box, det["pixel_box"])

        matched_tracks = set()
        matched_detections = set()

        if iou_matrix.size > 0:
            while True:
                max_iou = np.max(iou_matrix)
                if max_iou < self.iou_threshold:
                    break
                
                i, j = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
                tid = track_ids[i]

                is_same_class = (self.tracks[tid].class_name == detections[j]["class_name"])
                if is_same_class or max_iou >= 0.35:
                    self.tracks[tid].update(detections[j], timestamp, self.smoothing_alpha)
                    matched_tracks.add(tid)
                    matched_detections.add(j)
                    iou_matrix[i, :] = -1.0
                    iou_matrix[:, j] = -1.0
                else:
                    iou_matrix[i, j] = -1.0

        for j, det in enumerate(detections):
            if j in matched_detections:
                continue
            
            best_tid = None
            best_dist = 180.0
            for tid in track_ids:
                if tid in matched_tracks:
                    continue
                dist = math.hypot(self.tracks[tid].center_x_norm - det["center_x_norm"], self.tracks[tid].center_y_norm - det["center_y_norm"])
                is_same_class = (self.tracks[tid].class_name == det["class_name"])
                max_allowed = best_dist if is_same_class else (best_dist * 0.6)
                if dist < max_allowed:
                    best_dist = dist
                    best_tid = tid

            if best_tid is not None:
                self.tracks[best_tid].update(det, timestamp, self.smoothing_alpha)
                matched_tracks.add(best_tid)
                matched_detections.add(j)

        for tid in track_ids:
            if tid not in matched_tracks:
                self.tracks[tid].disappeared_frames += 1

        for j, det in enumerate(detections):
            if j not in matched_detections:
                self._register(det, timestamp)

        expired = [tid for tid, state in self.tracks.items() if state.disappeared_frames > self.max_disappeared]
        for tid in expired:
            del self.tracks[tid]

        return [t for t in self.tracks.values() if t.disappeared_frames == 0]

    def _register(self, detection: Dict[str, Any], timestamp: float):
        state = ObjectState(self.next_track_id, detection, timestamp)
        self.tracks[self.next_track_id] = state
        self.next_track_id += 1
