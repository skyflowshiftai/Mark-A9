import pytest
from intelligence.situational_agent import SituationalVoiceAgent

def test_person_lifecycle_new_silence_and_resolution():
    agent = SituationalVoiceAgent(reassess_cooldown_sec=3.0)

    # 1. NEW: Person appears at 2.5m -> Initial courteous warning
    track_p1 = [{"entity_id": "p1", "raw_class_name": "person", "distance_m": 2.5, "movement": "STATIONARY"}]
    res_new = agent.process_state(track_p1, timestamp=100.0, language="te-IN")
    assert res_new["should_speak"] is True
    assert "మీ ముందు ఒక వ్యక్తి ఉన్నారు... ఆగండి ఒకసారి." in res_new["speech"]
    assert res_new["event"]["status"] == "CONFIRMED"

    # 2. TRACKED: Person stays stationary at t=101.0s (within 3s window) -> SILENCE
    res_silence = agent.process_state(track_p1, timestamp=101.0, language="te-IN")
    assert res_silence["should_speak"] is False

    # 3. RESOLVED: Person moves away at t=103.0s, path clear
    # First frame disappeared
    agent.process_state([], timestamp=103.0, language="te-IN")
    # Second frame disappeared (confirmation)
    res_resolved = agent.process_state([], timestamp=105.0, language="te-IN")
    assert res_resolved["should_speak"] is True
    assert "మీ ముందు ఇప్పుడు ఎవరూ లేరు. ఇప్పుడు మీరు ముందుకు వెళ్లవచ్చు." in res_resolved["speech"]
    assert res_resolved["event"]["status"] == "RESOLVED"

def test_approaching_danger_escalation():
    agent = SituationalVoiceAgent(reassess_cooldown_sec=3.0)

    # 1. Person at 2.8m
    track_init = [{"entity_id": "p2", "raw_class_name": "person", "distance_m": 2.8, "movement": "STATIONARY"}]
    agent.process_state(track_init, timestamp=200.0, language="te-IN")

    # 2. Person approaches rapidly to 1.7m -> Escalates warning immediately
    track_approach = [{"entity_id": "p2", "raw_class_name": "person", "distance_m": 1.7, "movement": "APPROACHING"}]
    res_esc = agent.process_state(track_approach, timestamp=201.0, language="te-IN")
    assert res_esc["should_speak"] is True
    assert "ఒక వ్యక్తి మీ వైపు వస్తున్నారు... ఆగండి." in res_esc["speech"]

def test_critical_car_danger_interrupt():
    agent = SituationalVoiceAgent(reassess_cooldown_sec=3.0)

    track_car_init = [{"entity_id": "c1", "raw_class_name": "car", "distance_m": 3.0, "movement": "APPROACHING"}]
    agent.process_state(track_car_init, timestamp=300.0, language="te-IN")

    # Car rushes to 1.1m -> Immediate Critical Stop
    track_car_close = [{"entity_id": "c1", "raw_class_name": "car", "distance_m": 1.1, "movement": "APPROACHING"}]
    res_car = agent.process_state(track_car_close, timestamp=301.0, language="te-IN")
    assert res_car["should_speak"] is True
    assert "ఆగండి. వాహనం చాలా దగ్గరగా ఉంది." in res_car["speech"]
    assert res_car["priority"] == "CRITICAL"
    assert res_car["interrupt_audio"] is True

def test_situational_conversational_queries():
    agent = SituationalVoiceAgent()

    # Clear path query
    ans_clear = agent.answer_situational_query("IS_SAFE", {"active_tracks": []}, language="te-IN")
    assert "దారి క్లియర్గా ఉంది" in ans_clear

    # Uncertain query
    ans_unc = agent.answer_situational_query("IS_SAFE", {"active_tracks": [], "is_uncertain": True}, language="te-IN")
    assert "పరిస్థితి స్పష్టంగా లేదు" in ans_unc

    # OCR text query
    ans_ocr = agent.answer_situational_query("READ_TEXT", {"last_ocr_text": "DANGER - CONSTRUCTION AHEAD"}, language="te-IN")
    assert "నిర్మాణ పనులు" in ans_ocr

    # Currency ₹500 query
    ans_curr = agent.answer_situational_query("IDENTIFY_CURRENCY", {"last_currency_text": "₹500 Note"}, language="te-IN")
    assert "ఐదు వందల రూపాయల నోటు" in ans_curr
