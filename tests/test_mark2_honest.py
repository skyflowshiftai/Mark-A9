import pytest
import numpy as np
from fastapi.testclient import TestClient
from server import app
from detector import MarkDetector
from gemini_handler import GeminiHandler
from retell_handler import RetellHandler
from supabase_logger import SupabaseLogger

@pytest.fixture
def client():
    return TestClient(app)

def test_detector_threat_levels():
    detector = MarkDetector()
    dummy_frame = np.zeros((360, 640, 3), dtype=np.uint8)
    
    res = detector.process_frame(dummy_frame)
    assert "objects" in res
    assert "highest_threat" in res
    assert "total_objects" in res

def test_gemini_handler_message_generation():
    gemini = GeminiHandler()
    dummy_frame = np.zeros((360, 640, 3), dtype=np.uint8)
    
    # 1. Silent when no objects
    out_silent = gemini.generate_mark_message(dummy_frame, [], "SILENT")
    assert out_silent["threat_level"] == "SILENT"
    assert out_silent["should_speak"] is False

    # 2. Red threat -> max 5 words
    sample_obj = [{
        "name": "person",
        "distance": 0.8,
        "direction": "CENTER",
        "threat": "RED"
    }]
    out_red = gemini.generate_mark_message(dummy_frame, sample_obj, "RED")
    assert out_red["threat_level"] == "RED"
    assert out_red["should_speak"] is True
    words = out_red["mark_message"].split()
    assert len(words) <= 5

    # 3. Read text & Currency
    ocr_res = gemini.read_text(dummy_frame)
    assert "mark_message" in ocr_res

    curr_res = gemini.identify_currency(dummy_frame)
    assert "mark_message" in curr_res

def test_retell_voice_rules():
    retell = RetellHandler(cooldown_sec=1.0)
    
    # 1. Silent threat -> Should not speak
    r_silent = retell.evaluate_voice_output("Path clear.", "GREEN")
    assert r_silent["should_speak"] is False

    # 2. Red threat 1st time -> Speak
    r_red1 = retell.evaluate_voice_output("Person ahead. Stop now.", "RED")
    assert r_red1["should_speak"] is True

    # 3. Same threat immediately -> Cooldown active (do not speak)
    r_red_cooldown = retell.evaluate_voice_output("Person ahead. Stop now.", "RED")
    assert r_red_cooldown["should_speak"] is False

    # 4. Wake-word commands
    cmd_emerg = retell.process_voice_command("Hey Mark help", [], "SILENT")
    assert cmd_emerg["action"] == "EMERGENCY"

    cmd_safe = retell.process_voice_command("Hey Mark am I safe", [], "SILENT")
    assert "Safe to walk" in cmd_safe["speech"]

def test_supabase_logger_sessions():
    logger = SupabaseLogger()
    
    sess_id = logger.start_session()
    assert sess_id.startswith("sess_")
    assert logger.current_session_id == sess_id

    logger.log_detection({"name": "person", "distance": 1.2, "direction": "CENTER", "threat": "RED"})
    logger.log_alert("Person ahead. Stop.", "RED")
    
    assert logger.total_detections_count == 1
    assert logger.total_alerts_count == 1
    assert len(logger.recent_alerts) == 1

    summary = logger.end_session()
    assert summary["session_id"] == sess_id
    assert logger.current_session_id is None

    history = logger.get_history()
    assert len(history) >= 1

def test_server_rest_endpoints(client):
    # GET /api/status
    res_status = client.get("/api/status")
    assert res_status.status_code == 200
    assert res_status.json()["status"] == "ONLINE"

    # POST /api/session/start
    res_start = client.post("/api/session/start")
    assert res_start.status_code == 200
    assert res_start.json()["status"] == "SESSION_STARTED"

    # POST /api/read-text
    res_text = client.post("/api/read-text")
    assert res_text.status_code == 200

    # POST /api/currency
    res_curr = client.post("/api/currency")
    assert res_curr.status_code == 200

    # POST /api/emergency
    res_emerg = client.post("/api/emergency")
    assert res_emerg.status_code == 200
    assert res_emerg.json()["status"] == "EMERGENCY_ACTIVE"

    # POST /api/command
    res_cmd = client.post("/api/command", json={"command": "Hey Mark am I safe"})
    assert res_cmd.status_code == 200

    # POST /api/session/stop
    res_stop = client.post("/api/session/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] == "SESSION_STOPPED"

    # GET /api/history
    res_hist = client.get("/api/history")
    assert res_hist.status_code == 200
    assert "sessions" in res_hist.json()
