import pytest
import numpy as np
import time
from fastapi.testclient import TestClient

from backend.app import app
from backend.vision.detector import ObjectDetector
from backend.vision.tracker import ObjectTracker
from backend.vision.distance import estimate_distance_meters, calculate_spatial_sector
from backend.vision.scene import SceneAnalyzer
from backend.intelligence.risk_engine import RiskEngine
from backend.intelligence.prediction import TrajectoryPredictor
from backend.intelligence.priority_engine import PriorityEngine
from backend.intelligence.decision_engine import DecisionEngine
from backend.voice.commands import CommandEngine
from backend.recognition.ocr import OCREngine
from backend.recognition.currency import CurrencyRecognizer
from backend.emergency.emergency import EmergencyManager

@pytest.fixture
def client():
    return TestClient(app)

def test_distance_and_spatial_estimation():
    # Test pinhole distance calculation
    dist_person = estimate_distance_meters("person", bbox_height_px=150, image_height_px=360, focal_length_px=550.0)
    assert 5.0 <= dist_person <= 8.0

    dist_car = estimate_distance_meters("car", bbox_height_px=200, image_height_px=360, focal_length_px=550.0)
    assert 3.0 <= dist_car <= 6.0

    # Test spatial sectors
    assert calculate_spatial_sector(0.15) == "LEFT"
    assert calculate_spatial_sector(0.50) == "FORWARD"
    assert calculate_spatial_sector(0.85) == "RIGHT"

def test_object_tracker_lifecycle():
    tracker = ObjectTracker(max_disappeared=5)
    
    # Frame 1: Detection of a person
    det1 = [{
        "class_name": "person",
        "confidence": 0.92,
        "pixel_box": [100, 100, 160, 260],
        "norm_box": [0.15, 0.27, 0.25, 0.72],
        "height_px": 160.0,
        "width_px": 60.0,
        "center_x_norm": 0.20,
        "center_y_norm": 0.50
    }]
    
    tracks1 = tracker.update(det1, timestamp=1.0)
    assert len(tracks1) == 1
    assert tracks1[0].track_id == 1
    assert tracks1[0].hit_count == 1

    # Frame 2: Person moves slightly closer (height increases)
    det2 = [{
        "class_name": "person",
        "confidence": 0.94,
        "pixel_box": [105, 90, 175, 275],
        "norm_box": [0.16, 0.25, 0.27, 0.76],
        "height_px": 185.0,
        "width_px": 70.0,
        "center_x_norm": 0.21,
        "center_y_norm": 0.50
    }]
    
    tracks2 = tracker.update(det2, timestamp=1.1)
    assert len(tracks2) == 1
    assert tracks2[0].track_id == 1
    assert tracks2[0].hit_count == 2

def test_risk_engine_calculation():
    tracker = ObjectTracker()
    det = {
        "class_name": "car",
        "confidence": 0.95,
        "pixel_box": [150, 100, 350, 300],
        "norm_box": [0.35, 0.28, 0.65, 0.83],
        "height_px": 200.0,
        "width_px": 200.0,
        "center_x_norm": 0.50,
        "center_y_norm": 0.55
    }
    track = tracker.update([det], timestamp=1.0)[0]
    
    risk_engine = RiskEngine()
    score = risk_engine.compute_risk(track)
    
    assert 0 <= score <= 100
    assert track.risk_level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

def test_decision_engine_green_silence():
    decision_engine = DecisionEngine(alert_cooldown_sec=3.0, green_silence=True)
    optical_quality = {"is_degraded": False, "defect": None}
    
    # Empty tracks -> Must be silent
    decision = decision_engine.evaluate(tracks=[], optical_quality=optical_quality, timestamp=1.0)
    assert decision["decision_state"] == "SILENCE"
    assert decision["should_speak"] is False
    assert decision["voice_message"] == ""

def test_decision_engine_optical_degradation():
    decision_engine = DecisionEngine()
    optical_quality = {"is_degraded": True, "defect": "BLUR"}
    
    decision = decision_engine.evaluate(tracks=[], optical_quality=optical_quality, timestamp=1.0)
    assert decision["decision_state"] == "WARNING"
    assert decision["voice_message"] == "Visibility is reduced."

def test_command_engine_parsing():
    cmd_engine = CommandEngine()
    scene_summary = {"forward_clear": True, "path_message": "Path clear."}
    
    # Scene query
    res_scene = cmd_engine.process_command("What's ahead?", tracks=[], scene_summary=scene_summary)
    assert res_scene["intent"] == "SCENE"
    assert "No obstacles" in res_scene["response"] or "clear" in res_scene["response"]

    # Safety query
    res_safety = cmd_engine.process_command("Am I safe?", tracks=[], scene_summary=scene_summary)
    assert res_safety["intent"] == "SAFETY"
    assert "Safe to walk" in res_safety["response"]

    # Emergency query
    res_emerg = cmd_engine.process_command("Hey Mark help", tracks=[], scene_summary=scene_summary)
    assert res_emerg["intent"] == "EMERGENCY"
    assert res_emerg["action"] == "TRIGGER_EMERGENCY"

def test_ocr_and_currency_modules():
    dummy_frame = np.zeros((360, 640, 3), dtype=np.uint8)
    
    ocr = OCREngine()
    res_ocr = ocr.extract_text(dummy_frame)
    assert "spoken_message" in res_ocr

    currency = CurrencyRecognizer()
    res_curr = currency.recognize_currency(dummy_frame)
    assert "denomination" in res_curr
    assert "spoken_message" in res_curr

def test_emergency_manager():
    em = EmergencyManager()
    assert em.is_active is False
    
    em.trigger(source="TEST_TRIGGER")
    assert em.is_active is True
    assert em.trigger_source == "TEST_TRIGGER"
    
    em.resolve()
    assert em.is_active is False

def test_rest_api_endpoints(client):
    # GET /api/status
    res_status = client.get("/api/status")
    assert res_status.status_code == 200
    data = res_status.json()
    assert data["system_name"] == "MARK 2.0"
    assert data["mode"] == "ASSISTIVE_AI"

    # GET /api/detections
    res_det = client.get("/api/detections")
    assert res_det.status_code == 200
    assert "tracks" in res_det.json()

    # POST /api/command
    res_cmd = client.post("/api/command", json={"command": "Am I safe?"})
    assert res_cmd.status_code == 200
    assert res_cmd.json()["intent"] == "SAFETY"

    # POST /api/ocr
    res_ocr = client.post("/api/ocr")
    assert res_ocr.status_code == 200

    # POST /api/currency
    res_curr = client.post("/api/currency")
    assert res_curr.status_code == 200

    # POST /api/emergency
    res_emerg = client.post("/api/emergency", json={"action": "TRIGGER"})
    assert res_emerg.status_code == 200
    assert res_emerg.json()["status"] == "EMERGENCY_ACTIVE"
