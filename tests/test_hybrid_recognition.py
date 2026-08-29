import pytest
import numpy as np
from collections import deque
from fastapi.testclient import TestClient

from server import app
from vision.hybrid_recognizer import HybridRecognizer
from voice.commands import VoiceCommandParser

@pytest.fixture
def client():
    return TestClient(app)

def test_temporal_class_stability_and_confidence_gate():
    recog = HybridRecognizer()
    
    # Case 1: High Confidence & Stable Class -> KNOWN
    history_stable = deque(["bottle", "bottle", "bottle", "bottle"], maxlen=6)
    res_stable = recog.evaluate_recognition("bottle", 0.78, history_stable)
    assert res_stable["is_confident"] is True
    assert res_stable["display_name"] == "Bottle"
    assert res_stable["recognition_status"] == "KNOWN"

    # Case 2: Unstable / Fluctuating Detection -> UNCERTAIN (Unknown Object)
    history_unstable = deque(["bottle", "cell phone", "book", "bottle"], maxlen=6)
    res_unstable = recog.evaluate_recognition("cell phone", 0.42, history_unstable)
    assert res_unstable["is_confident"] is False
    assert res_unstable["display_name"] == "Unknown Object"
    assert res_unstable["recognition_status"] == "UNCERTAIN"

    # Case 3: Moderate Confidence Generic Item -> PROBABLE
    history_moderate = deque(["bottle", "bottle"], maxlen=6)
    res_mod = recog.evaluate_recognition("bottle", 0.48, history_moderate)
    assert res_mod["display_name"] in ("Bottle", "Container")
    assert res_mod["recognition_status"] == "PROBABLE"

def test_user_query_active_recognition():
    recog = HybridRecognizer()
    dummy_frame = np.zeros((360, 640, 3), dtype=np.uint8)
    
    # Empty / Unclear frame
    res_unclear = recog.recognize_held_object(dummy_frame, [100, 100, 200, 200])
    assert "spoken_text" in res_unclear
    assert res_unclear["identified"] is False
    assert "can't identify" in res_unclear["spoken_text"] or "object" in res_unclear["spoken_text"]

def test_identify_voice_command():
    cmd_parser = VoiceCommandParser()
    res1 = cmd_parser.parse("What am I holding?", [])
    assert res1["intent"] == "IDENTIFY"
    assert res1["action"] == "TRIGGER_IDENTIFY"

    res2 = cmd_parser.parse("Hey Mark, what is this object?", [])
    assert res2["intent"] == "IDENTIFY"
    assert res2["action"] == "TRIGGER_IDENTIFY"

def test_identify_api_endpoint(client):
    res = client.post("/api/identify")
    assert res.status_code == 200
    data = res.json()
    assert "spoken_text" in data
