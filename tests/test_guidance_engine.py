import pytest
from intelligence.guidance_engine import GuidanceEngine

def test_guidance_engine_3_second_cycle_and_persistence():
    engine = GuidanceEngine(guidance_cycle_sec=3.0)
    t0 = 100.0

    # 1. t=0s: Person appears in corridor at 2.5m (Right is clear)
    obs_person = {
        "track_id": 7,
        "name": "person",
        "distance_m": 2.5,
        "spatial_sector": "CENTER",
        "path_relevance": "HIGH",
        "motion_state": "STATIONARY",
        "risk_level": "CAUTION"
    }
    res0 = engine.evaluate_navigation([obs_person], timestamp=t0, language="te-IN")
    assert res0 is not None
    assert res0["should_speak"] is True
    assert "సార్, మీ ముందు ఒక వ్యక్తి ఉన్నారు" in res0["instruction"]
    assert "కుడివైపుకి జరగండి" in res0["instruction"]
    assert res0["reason"] == "NEW_OBSTACLE"

    # 2. t=1.0s: Within 3-second cycle -> SILENCE
    res1 = engine.evaluate_navigation([obs_person], timestamp=t0 + 1.0, language="te-IN")
    assert res1 is None

    # 3. t=2.0s: Still within 3-second cycle -> SILENCE
    res2 = engine.evaluate_navigation([obs_person], timestamp=t0 + 2.0, language="te-IN")
    assert res2 is None

    # 4. t=3.2s: 3 seconds elapsed, person still blocking path -> Persistent Reminder
    res3 = engine.evaluate_navigation([obs_person], timestamp=t0 + 3.2, language="te-IN")
    assert res3 is not None
    assert res3["should_speak"] is True
    assert "సార్, ఇంకా ముందు వ్యక్తి ఉన్నారు" in res3["instruction"]
    assert res3["reason"] == "STILL_BLOCKING_PATH_REMINDER"

def test_danger_escalation_bypasses_3s_cycle():
    engine = GuidanceEngine(guidance_cycle_sec=3.0)
    t0 = 100.0

    # Initial medium obstacle
    obs_car_far = {
        "track_id": 9,
        "name": "car",
        "distance_m": 3.8,
        "spatial_sector": "CENTER",
        "motion_state": "STATIONARY",
        "risk_level": "MEDIUM"
    }
    res0 = engine.evaluate_navigation([obs_car_far], timestamp=t0, language="te-IN")
    assert res0 is not None

    # 1.2s later (within 3s cycle): Car suddenly rushes close (distance drops to 1.1m, risk URGENT)
    obs_car_close = {
        "track_id": 9,
        "name": "car",
        "distance_m": 1.1,
        "spatial_sector": "CENTER",
        "motion_state": "APPROACHING",
        "risk_level": "URGENT"
    }
    res_override = engine.evaluate_navigation([obs_car_close], timestamp=t0 + 1.2, language="te-IN")
    assert res_override is not None
    assert res_override["should_speak"] is True
    assert res_override["reason"] == "DANGER_ESCALATION_OVERRIDE"
    assert res_override["interrupt_audio"] is True
    assert "సార్, కారు ముందుకు వస్తోంది. ఆగండి." in res_override["instruction"]

def test_directional_sidestep_and_full_blockage():
    engine = GuidanceEngine()

    # 1. Obstacle on LEFT -> Right is clear -> Recommend move RIGHT
    obs_left = {"track_id": 11, "name": "chair", "distance_m": 2.0, "spatial_sector": "LEFT", "risk_level": "CAUTION"}
    res_left = engine.evaluate_navigation([obs_left], timestamp=1.0, language="te-IN")
    assert "ఎడమవైపు అడ్డంకి ఉంది" in res_left["instruction"]
    assert "కుడివైపుకి జరగండి" in res_left["instruction"]

    # 2. Obstacle on RIGHT -> Left is clear -> Recommend move LEFT
    engine_2 = GuidanceEngine()
    obs_right = {"track_id": 12, "name": "box", "distance_m": 2.0, "spatial_sector": "RIGHT", "risk_level": "CAUTION"}
    res_right = engine_2.evaluate_navigation([obs_right], timestamp=1.0, language="te-IN")
    assert "కుడివైపు అడ్డంకి ఉంది" in res_right["instruction"]
    assert "ఎడమవైపుకి జరగండి" in res_right["instruction"]

    # 3. Both LEFT and RIGHT are blocked -> Must NOT recommend sideways move -> STOP!
    engine_3 = GuidanceEngine()
    obs_both = [
        {"track_id": 13, "name": "chair", "distance_m": 2.0, "spatial_sector": "LEFT", "risk_level": "CAUTION"},
        {"track_id": 14, "name": "table", "distance_m": 2.1, "spatial_sector": "RIGHT", "risk_level": "CAUTION"}
    ]
    res_both = engine_3.evaluate_navigation(obs_both, timestamp=1.0, language="te-IN")
    assert res_both is not None
    assert "సార్, ముందంతా అడ్డంకిగా ఉంది. ఆగండి." in res_both["instruction"]
    assert res_both["recommended_action"] == "STOP_BLOCKED"
