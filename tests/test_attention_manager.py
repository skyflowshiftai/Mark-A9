"""
MARK 2.0 — Attention Manager Unit & Behavioral Test Suite
Validates:
1. Dwell Gate & Confirmation
2. Initial Warning Once
3. Zero Repetition while Stationary / Unchanged
4. Distance Jitter Silence
5. Danger Escalation Transition
6. Departure Gate & Sustained Disappearance
7. Priority Ranking (Single Voice Output)
8. Conversational Query Independence
"""

import pytest
import time
from intelligence.attention_manager import AttentionManager
from intelligence.conversation_orchestrator import ConversationOrchestrator


class MockTrack:
    def __init__(self, track_id: int, class_name: str, distance_m: float, motion: str = "STATIONARY", sector: str = "CENTER"):
        self.track_id = track_id
        self.raw_class_name = class_name
        self.class_name = class_name
        self.distance_m = distance_m
        self.motion_state = motion
        self.spatial_sector = sector
        self.confidence = 0.90

    def to_dict(self):
        return {
            "track_id": self.track_id,
            "raw_class_name": self.class_name,
            "name": self.class_name,
            "distance_m": self.distance_m,
            "motion_state": self.motion_state,
            "spatial_sector": self.spatial_sector,
            "confidence": self.confidence
        }


def test_attention_dwell_gate_and_initial_warning():
    mgr = AttentionManager(min_confirm_frames=3, departure_confirm_frames=6, normal_cooldown_sec=3.0)
    
    t1 = MockTrack(1, "person", 2.2)

    # Frame 1: NEW (Dwell gate) -> SILENCE
    res1 = mgr.evaluate_scene([t1], timestamp=100.0)
    assert res1["should_speak"] is False

    # Frame 2: NEW (Dwell gate) -> SILENCE
    res2 = mgr.evaluate_scene([t1], timestamp=100.1)
    assert res2["should_speak"] is False

    # Frame 3: CONFIRMED -> Speaks Initial Warning Once
    res3 = mgr.evaluate_scene([t1], timestamp=100.2)
    assert res3["should_speak"] is True
    assert "వ్యక్తి ఉన్నారు" in res3["speech"]

    # Frame 4: WARNED & Unchanged -> ABSOLUTE SILENCE
    res4 = mgr.evaluate_scene([t1], timestamp=100.3)
    assert res4["should_speak"] is False
    assert res4["debug_reason"] == "same_track_same_zone_silent"


def test_stationary_person_zero_repetition():
    mgr = AttentionManager(min_confirm_frames=3, departure_confirm_frames=6, normal_cooldown_sec=3.0)
    t = MockTrack(12, "person", 2.0)

    # Prime entity to WARNED
    mgr.evaluate_scene([t], timestamp=10.0)
    mgr.evaluate_scene([t], timestamp=10.1)
    warn = mgr.evaluate_scene([t], timestamp=10.2)
    assert warn["should_speak"] is True

    # 100 consecutive frames over 20 seconds
    for sec in range(1, 21):
        r = mgr.evaluate_scene([t], timestamp=10.2 + sec)
        assert r["should_speak"] is False, f"Spoke unnecessarily at second {sec}"


def test_minor_distance_jitter_silence():
    mgr = AttentionManager(min_confirm_frames=3, departure_confirm_frames=6, normal_cooldown_sec=3.0)
    
    # Initial confirmation at 2.3m
    t = MockTrack(5, "person", 2.3)
    mgr.evaluate_scene([t], timestamp=1.0)
    mgr.evaluate_scene([t], timestamp=1.1)
    mgr.evaluate_scene([t], timestamp=1.2)

    # Slight movements within CAUTION zone (2.3m -> 2.1m -> 1.9m -> 1.8m)
    for dist in (2.1, 1.9, 1.8, 1.7):
        t_move = MockTrack(5, "person", dist)
        r = mgr.evaluate_scene([t_move], timestamp=5.0)
        assert r["should_speak"] is False, f"Spoke on minor distance jitter at {dist}m"


def test_danger_escalation_triggers_new_warning():
    mgr = AttentionManager(min_confirm_frames=3, departure_confirm_frames=6, normal_cooldown_sec=3.0)
    
    # Confirm in CAUTION at 2.0m
    t_caution = MockTrack(7, "person", 2.0)
    mgr.evaluate_scene([t_caution], timestamp=1.0)
    mgr.evaluate_scene([t_caution], timestamp=1.1)
    warn1 = mgr.evaluate_scene([t_caution], timestamp=1.2)
    assert warn1["should_speak"] is True

    # Approached into DANGER (< 1.3m) -> Escalation Alert
    t_danger = MockTrack(7, "person", 0.8) # Critical zone
    warn2 = mgr.evaluate_scene([t_danger], timestamp=2.0)
    assert warn2["should_speak"] is True
    assert warn2["priority"] == "CRITICAL"


def test_departure_gate_and_confirmed_departure():
    mgr = AttentionManager(min_confirm_frames=3, departure_confirm_frames=6, normal_cooldown_sec=3.0)
    
    # Confirm person
    t = MockTrack(9, "person", 2.0)
    mgr.evaluate_scene([t], timestamp=1.0)
    mgr.evaluate_scene([t], timestamp=1.1)
    mgr.evaluate_scene([t], timestamp=1.2)

    # 1 missing frame -> NO departure announcement (flicker protection)
    r1 = mgr.evaluate_scene([], timestamp=1.3)
    assert r1["should_speak"] is False

    # 2, 3, 4, 5 missing frames -> Still NO announcement
    for i in range(4):
        r_flicker = mgr.evaluate_scene([], timestamp=1.4 + i*0.1)
        assert r_flicker["should_speak"] is False

    # 6th missing frame -> Confirmed departure announcement
    r_dep = mgr.evaluate_scene([], timestamp=2.0)
    assert r_dep["should_speak"] is True
    assert "ఎవరూ లేరు" in r_dep["speech"]


def test_priority_selection_among_multiple_objects():
    mgr = AttentionManager(min_confirm_frames=1, departure_confirm_frames=6, normal_cooldown_sec=3.0)
    
    t_person = MockTrack(1, "person", 3.0)
    t_car = MockTrack(2, "car", 1.0) # Critical priority
    t_chair = MockTrack(3, "chair", 2.5)

    res = mgr.evaluate_scene([t_person, t_car, t_chair], timestamp=10.0)
    assert res["should_speak"] is True
    assert res["priority"] == "CRITICAL"
    assert "వాహనం" in res["speech"]


def test_user_conversation_independent_of_autonomous_silence():
    orchestrator = ConversationOrchestrator()
    world_state = {
        "active_tracks": [MockTrack(1, "person", 2.0)],
        "camera_healthy": True,
        "is_uncertain": False
    }

    # User asks "ఇంకా ఉన్నారా?" -> Must respond with live reality
    ans1 = orchestrator.process_query("ఇంకా ఉన్నారా?", world_state, language="te-IN")
    assert "అవును సర్, ఇంకా మీ ముందే ఉన్నారు." in ans1["speech"]

    # World state changes (person left)
    world_state_clear = {
        "active_tracks": [],
        "camera_healthy": True,
        "is_uncertain": False
    }
    ans2 = orchestrator.process_query("అతను వెళ్లిపోయాడా?", world_state_clear, language="te-IN")
    assert "అవును సర్, ఇప్పుడు ఆయన అక్కడ లేరు" in ans2["speech"]
