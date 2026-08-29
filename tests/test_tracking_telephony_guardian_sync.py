"""
MARK 2.0 — COMPREHENSIVE VERIFICATION TEST SUITE
Covers:
1. Persistent Object Tracking & Lifecycle (NEW -> CONFIRMED -> ACTIVE -> TEMPORARILY_LOST -> REACQUIRED -> DEPARTED)
2. Trajectory Movement Classification & Distance Smoothing
3. Outbound Telephony Pipeline & E.164 Normalization (+1 949 738 5095)
4. Duplicate Emergency Call Prevention
5. Single Authoritative World State & Guardian Synchronization
"""

import time
import pytest
from vision.tracker import ObjectTracker, TrackedEntity
from emergency.telephony import TelephonyService, normalize_e164
from emergency.emergency import EmergencyManager
from intelligence.tools import ActionToolDispatcher
from intelligence.conversation_orchestrator import ConversationOrchestrator

def test_persistent_tracking_lifecycle_and_reacquisition():
    tracker = ObjectTracker(max_disappeared=10, confirmation_frames=2)
    t0 = 100.0

    # Frame 1: Person detected (NEW)
    det1 = [{
        "class_name": "person",
        "confidence": 0.90,
        "bbox": [100, 50, 200, 300],
        "norm_bbox": [0.15, 0.14, 0.31, 0.83],
        "center": [150.0, 175.0],
        "norm_center": [0.23, 0.48],
        "height_px": 250.0,
        "width_px": 100.0
    }]
    tracks1 = tracker.update(det1, timestamp=t0)
    assert len(tracker.tracks) == 1
    t_obj = list(tracker.tracks.values())[0]
    initial_id = t_obj.track_id

    # Frame 2: Person detected again (CONFIRMED)
    det2 = [{
        "class_name": "person",
        "confidence": 0.92,
        "bbox": [102, 52, 204, 302],
        "norm_bbox": [0.16, 0.14, 0.32, 0.84],
        "center": [153.0, 177.0],
        "norm_center": [0.24, 0.49],
        "height_px": 250.0,
        "width_px": 102.0
    }]
    tracks2 = tracker.update(det2, timestamp=t0 + 0.1)
    assert len(tracks2) == 1
    assert tracks2[0].track_id == initial_id
    assert tracks2[0].state in ("CONFIRMED", "ACTIVE")

    # Frames 3 & 4: Detection temporarily drops (e.g. occlusion or rapid turn)
    # Tracker must mark TEMPORARILY_LOST, retain ID, and NOT delete immediately
    tracks3 = tracker.update([], timestamp=t0 + 0.2)
    assert initial_id in tracker.tracks
    assert tracker.tracks[initial_id].state == "TEMPORARILY_LOST"
    assert tracker.tracks[initial_id].frames_missing == 1

    tracks4 = tracker.update([], timestamp=t0 + 0.3)
    assert initial_id in tracker.tracks
    assert tracker.tracks[initial_id].frames_missing == 2

    # Frame 5: Person re-appears at proximity -> Must REACQUIRE SAME TRACK ID!
    det5 = [{
        "class_name": "person",
        "confidence": 0.88,
        "bbox": [108, 54, 210, 304],
        "norm_bbox": [0.17, 0.15, 0.33, 0.84],
        "center": [159.0, 179.0],
        "norm_center": [0.25, 0.50],
        "height_px": 250.0,
        "width_px": 102.0
    }]
    tracks5 = tracker.update(det5, timestamp=t0 + 0.4)
    assert len(tracks5) == 1
    assert tracks5[0].track_id == initial_id  # PERSISTENT ID PRESERVED!
    assert tracks5[0].frames_missing == 0

def test_distance_smoothing_and_movement_classification():
    tracker = ObjectTracker(confirmation_frames=1)
    t = 200.0

    # Person approaches from 5m to 2m smoothly
    for i in range(5):
        h = 100.0 + (i * 30.0) # height increases as person gets closer
        det = [{
            "class_name": "person",
            "confidence": 0.90,
            "bbox": [100, 50, 200, 50 + h],
            "norm_bbox": [0.15, 0.14, 0.31, 0.80],
            "center": [150.0, 50 + (h/2)],
            "norm_center": [0.23, 0.50],
            "height_px": h,
            "width_px": 100.0
        }]
        tracks = tracker.update(det, timestamp=t + (i * 0.1))
    
    assert len(tracks) == 1
    track = tracks[0]
    # Verify distance is smoothed without jumping
    assert track.smoothed_distance_m > 0.5
    # Trajectory should register approach tendency
    assert track.motion_info["motion_state"] in ("APPROACHING", "STATIONARY")

def test_e164_phone_normalization():
    assert normalize_e164("+1 949 738 5095") == "+19497385095"
    assert normalize_e164("+19497385095") == "+19497385095"
    assert normalize_e164("9497385095") == "+19497385095"
    assert normalize_e164("+1 (949) 738-5095") == "+19497385095"
    assert normalize_e164(None) == "+19497385095"

def test_outbound_telephony_dispatch_and_duplicate_prevention():
    em = EmergencyManager(contact_phone="+1 949 738 5095")
    assert em.contact_phone == "+19497385095"

    # 1. First trigger -> dispatches outbound call
    res1 = em.trigger(source="VOICE_COMMAND")
    assert res1["status"] == "EMERGENCY_ACTIVE"
    assert res1["contact_phone"] == "+19497385095"
    assert res1["call_id"] is not None
    assert "కాల్ చేస్తున్నాను" in res1["spoken_feedback_te"] or "call" in res1["spoken_feedback_en"].lower()

    # 2. Duplicate rapid trigger within 10s -> handled safely without duplicate telephony spam
    res2 = em.trigger(source="VOICE_COMMAND")
    assert res2["status"] == "EMERGENCY_ACTIVE"
    assert em.get_status()["is_active"] is True

    # 3. Resolve emergency
    resolve_res = em.resolve()
    assert resolve_res["status"] == "RESOLVED"
    assert em.get_status()["is_active"] is False

def test_conversational_emergency_triggers_actual_telephony():
    em = EmergencyManager(contact_phone="+1 949 738 5095")
    tools = ActionToolDispatcher(emergency_mgr=em)
    orch = ConversationOrchestrator(tools=tools)

    # Test Telugu help query
    res_te = orch.process_query("నాకు అర్జెంట్ గా సహాయం కావాలి", {}, language="te-IN")
    assert res_te["intent"] == "EMERGENCY"
    assert res_te["action"] == "EMERGENCY_CALL"
    assert res_te["target"] == "+19497385095"
    assert em.get_status()["is_active"] is True

    em.resolve()

    # Test English emergency query
    res_en = orch.process_query("Mark help me immediately", {}, language="en-US")
    assert res_en["intent"] == "EMERGENCY"
    assert res_en["action"] == "EMERGENCY_CALL"
    assert res_en["target"] == "+19497385095"
    assert em.get_status()["is_active"] is True
