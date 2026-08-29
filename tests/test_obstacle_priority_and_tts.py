import pytest
import time
from fastapi.testclient import TestClient

from server import app
from intelligence.obstacle_priority_engine import ObstaclePriorityEngine
from intelligence.audio_priority_queue import AudioPriorityQueue
from voice.tts_service import TTSService

@pytest.fixture
def client():
    return TestClient(app)

def test_obstacle_priority_distance_rules():
    engine = ObstaclePriorityEngine()

    # 1. Critical Hazard (< 1.5m)
    obs_crit = {
        "track_id": 1,
        "name": "car",
        "distance_m": 1.2,
        "spatial_sector": "LEFT",
        "motion_state": "APPROACHING"
    }
    eval_crit = engine.evaluate_single_obstacle(obs_crit, time.time())
    assert eval_crit["priority"] == "CRITICAL"
    assert "Stop" in eval_crit["instruction"]
    assert "left" in eval_crit["instruction"]

    # 2. High Hazard (1.5m - 3.0m)
    obs_high = {
        "track_id": 2,
        "name": "chair",
        "distance_m": 2.2,
        "spatial_sector": "CENTER",
        "motion_state": "STATIONARY"
    }
    eval_high = engine.evaluate_single_obstacle(obs_high, time.time())
    assert eval_high["priority"] == "HIGH"
    assert "Warning" in eval_high["instruction"]

    # 3. Medium Hazard (3.0m - 6.0m)
    obs_med = {
        "track_id": 3,
        "name": "person",
        "distance_m": 4.5,
        "spatial_sector": "RIGHT",
        "motion_state": "STATIONARY"
    }
    eval_med = engine.evaluate_single_obstacle(obs_med, time.time())
    assert eval_med["priority"] == "MEDIUM"
    assert "Person" in eval_med["instruction"]

    # 4. Ignore (> 6.0m)
    obs_far = {
        "track_id": 4,
        "name": "tree",
        "distance_m": 8.5,
        "spatial_sector": "RIGHT"
    }
    eval_far = engine.evaluate_single_obstacle(obs_far, time.time())
    assert eval_far["priority"] == "IGNORE"

def test_cooldown_and_threat_escalation_bypass():
    engine = ObstaclePriorityEngine()
    t0 = 100.0

    # First event: Medium threat
    obs_med = {"track_id": 5, "name": "person", "distance_m": 4.0, "spatial_sector": "CENTER"}
    res1 = engine.evaluate_scene([obs_med], timestamp=t0)
    assert res1 is not None
    assert res1["should_speak"] is True
    assert res1["reason"] == "NEW_OBSTACLE"

    # Same event 0.5s later -> Suppressed by cooldown
    res2 = engine.evaluate_scene([obs_med], timestamp=t0 + 0.5)
    assert res2 is None

    # Threat Escalation 0.8s later (Distance drops to 1.1m -> CRITICAL)
    obs_crit = {"track_id": 5, "name": "person", "distance_m": 1.1, "spatial_sector": "CENTER"}
    res3 = engine.evaluate_scene([obs_crit], timestamp=t0 + 0.8)
    assert res3 is not None
    assert res3["should_speak"] is True
    assert res3["reason"] == "THREAT_ESCALATED"
    assert res3["interrupt_audio"] is True

def test_audio_priority_queue_interruption():
    queue = AudioPriorityQueue()

    # Enqueue Medium Alert
    q1 = queue.enqueue_alert({"priority": "MEDIUM", "instruction": "Person ahead."})
    assert q1["action"] == "ENQUEUED"

    # Critical Alert arrives -> Immediate interruption
    q2 = queue.enqueue_alert({"priority": "CRITICAL", "instruction": "Stop. Car approaching from your left."})
    assert q2["action"] == "INTERRUPT_IMMEDIATE"
    assert q2["alert"]["priority"] == "CRITICAL"

def test_tts_service_and_endpoint(client):
    tts = TTSService()
    audio, mime, lat = tts.synthesize_speech("Warning. Car approaching.", "high")
    assert lat >= 0.0

    # Test POST /api/tts
    res = client.post("/api/tts", json={"text": "Stop. Obstacle directly ahead.", "priority": "critical"})
    assert res.status_code == 200

    # Test GET /api/safety-log
    res_log = client.get("/api/safety-log")
    assert res_log.status_code == 200
    assert "events" in res_log.json()
