import pytest
import numpy as np
import time
from fastapi.testclient import TestClient

from server import app
from vision.detector import ObjectDetector
from vision.tracker import ObjectTracker
from vision.distance import estimate_relative_distance, calculate_spatial_sector
from vision.motion import estimate_relative_motion
from intelligence.risk_engine import RiskEngine
from intelligence.priority_engine import PriorityEngine
from intelligence.silence_manager import SilenceManager
from voice.voice_controller import VoiceController
from voice.commands import VoiceCommandParser
from perception.ocr import OCREngine
from perception.currency import CurrencyRecognizer
from emergency.emergency import EmergencyManager

@pytest.fixture
def client():
    return TestClient(app)

def test_distance_and_spatial_sectors():
    # Valid bounding box -> ESTIMATED
    res_person = estimate_relative_distance("person", bbox_height_px=150.0, frame_height_px=360)
    assert res_person["status"] == "ESTIMATED"
    assert 5.0 <= res_person["distance_m"] <= 8.0

    # Degraded/tiny bounding box -> UNKNOWN
    res_unknown = estimate_relative_distance("person", bbox_height_px=2.0, frame_height_px=360)
    assert res_unknown["status"] == "UNKNOWN"
    assert res_unknown["distance_m"] is None

    # Horizontal sectors
    assert calculate_spatial_sector(0.15) == "LEFT"
    assert calculate_spatial_sector(0.50) == "CENTER"
    assert calculate_spatial_sector(0.85) == "RIGHT"

def test_multi_object_tracker_lifecycle():
    tracker = ObjectTracker(max_disappeared=5, confirmation_frames=2)
    
    # Frame 1: Person detection
    det1 = [{
        "class_name": "person",
        "confidence": 0.90,
        "bbox": [100, 80, 180, 280],
        "norm_bbox": [0.15, 0.22, 0.28, 0.77],
        "center": [140.0, 180.0],
        "norm_center": [0.21, 0.50],
        "width_px": 80.0,
        "height_px": 200.0,
        "frame_width": 640,
        "frame_height": 360
    }]
    
    tracks1 = tracker.update(det1, timestamp=1.0)
    # Track created but 1 frame seen (confirmation requires 2)
    assert len(tracker.tracks) == 1
    assert 1 in tracker.tracks

    # Frame 2: Person moves closer
    det2 = [{
        "class_name": "person",
        "confidence": 0.93,
        "bbox": [105, 70, 195, 290],
        "norm_bbox": [0.16, 0.19, 0.30, 0.80],
        "center": [150.0, 180.0],
        "norm_center": [0.23, 0.50],
        "width_px": 90.0,
        "height_px": 220.0,
        "frame_width": 640,
        "frame_height": 360
    }]

    tracks2 = tracker.update(det2, timestamp=1.1)
    assert len(tracks2) == 1
    assert tracks2[0].track_id == 1
    assert tracks2[0].frames_seen == 2

def test_risk_engine_and_priority_ranking():
    tracker = ObjectTracker(confirmation_frames=1)
    det_car = {
        "class_name": "car",
        "confidence": 0.95,
        "bbox": [180, 60, 460, 320],
        "norm_bbox": [0.28, 0.16, 0.71, 0.88],
        "center": [320.0, 190.0],
        "norm_center": [0.50, 0.52],
        "width_px": 280.0,
        "height_px": 260.0,
        "frame_width": 640,
        "frame_height": 360
    }
    car_track = tracker.update([det_car], timestamp=1.0)[0]

    risk_engine = RiskEngine()
    score = risk_engine.evaluate_track_risk(car_track)

    assert 0.0 <= score <= 1.0
    assert car_track.risk_level in ("URGENT", "CAUTION", "AWARENESS", "SILENT")

    priority_engine = PriorityEngine()
    primary = priority_engine.select_primary_hazard([car_track])
    assert primary is not None
    assert primary.track_id == car_track.track_id

def test_silence_manager_and_voice_controller():
    tracker = ObjectTracker(confirmation_frames=1)
    det = {
        "class_name": "car",
        "confidence": 0.95,
        "bbox": [200, 50, 440, 310],
        "norm_bbox": [0.31, 0.13, 0.68, 0.86],
        "center": [320.0, 180.0],
        "norm_center": [0.50, 0.50],
        "width_px": 240.0,
        "height_px": 260.0,
        "frame_width": 640,
        "frame_height": 360
    }
    track = tracker.update([det], timestamp=1.0)[0]
    track.risk_level = "URGENT"

    vc = VoiceController()
    
    # 1. First alert -> Must speak short cue (<= 5 words)
    eval1 = vc.evaluate_voice_instruction(track, timestamp=1.0)
    assert eval1["should_speak"] is True
    words = eval1["spoken_phrase"].split()
    assert len(words) <= 5

    # 2. Immediate repeated call -> Cooldown active (do not speak)
    eval2 = vc.evaluate_voice_instruction(track, timestamp=1.2)
    assert eval2["should_speak"] is False

    # 3. None / Empty hazard -> Silence
    eval_none = vc.evaluate_voice_instruction(None, timestamp=1.0)
    assert eval_none["should_speak"] is False
    assert eval_none["spoken_phrase"] == ""

def test_ocr_currency_and_commands():
    cmd_parser = VoiceCommandParser()
    res_safe = cmd_parser.parse("Am I safe to walk?", [])
    assert res_safe["intent"] == "SAFETY"
    assert "Safe to walk" in res_safe["speech"]

    dummy_frame = np.zeros((360, 640, 3), dtype=np.uint8)
    ocr = OCREngine()
    res_ocr = ocr.read_text_from_frame(dummy_frame)
    assert "mark_message" in res_ocr

    currency = CurrencyRecognizer()
    res_curr = currency.identify_note(dummy_frame)
    assert "mark_message" in res_curr

def test_multi_class_detection_and_tracking():
    tracker = ObjectTracker(confirmation_frames=1)
    
    # Simultaneous detections: Person + Bottle + Chair + Backpack
    detections = [
        {
            "class_name": "person",
            "confidence": 0.88,
            "bbox": [100, 50, 260, 310],
            "norm_bbox": [0.15, 0.14, 0.40, 0.86],
            "center": [180.0, 180.0],
            "norm_center": [0.28, 0.50],
            "width_px": 160.0,
            "height_px": 260.0,
            "frame_width": 640,
            "frame_height": 360
        },
        {
            "class_name": "bottle",
            "confidence": 0.72,
            "bbox": [300, 180, 360, 320],
            "norm_bbox": [0.46, 0.50, 0.56, 0.88],
            "center": [330.0, 250.0],
            "norm_center": [0.51, 0.69],
            "width_px": 60.0,
            "height_px": 140.0,
            "frame_width": 640,
            "frame_height": 360
        },
        {
            "class_name": "chair",
            "confidence": 0.82,
            "bbox": [420, 120, 580, 330],
            "norm_bbox": [0.65, 0.33, 0.90, 0.91],
            "center": [500.0, 225.0],
            "norm_center": [0.78, 0.62],
            "width_px": 160.0,
            "height_px": 210.0,
            "frame_width": 640,
            "frame_height": 360
        }
    ]

    tracks = tracker.update(detections, timestamp=1.0)
    assert len(tracks) == 3
    classes = {t.class_name for t in tracks}
    assert classes == {"person", "bottle", "chair"}

    # Evaluate Risk for each
    risk_engine = RiskEngine()
    for t in tracks:
        risk_engine.evaluate_track_risk(t)

    # Priority Ranking
    priority_engine = PriorityEngine()
    ranked = priority_engine.rank_tracks(tracks)
    assert len(ranked) == 3
    # Chair or Person or Bottle in center path gets evaluated
    primary = priority_engine.select_primary_hazard(tracks)
    assert primary is not None

def test_server_rest_api_and_telemetry(client):
    res_status = client.get("/api/status")
    assert res_status.status_code == 200
    data = res_status.json()
    assert data["system_name"] == "MARK 2.0"
    assert "telemetry" in data
    assert "cpu_percent" in data["telemetry"]
    assert "ram_used_gb" in data["telemetry"]

    res_det = client.get("/api/detections")
    assert res_det.status_code == 200
    assert "tracks" in res_det.json()

    res_history = client.get("/api/history")
    assert res_history.status_code == 200
    assert "sessions" in res_history.json()
