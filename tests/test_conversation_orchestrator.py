import pytest
from intelligence.conversation_orchestrator import ConversationOrchestrator

def test_what_ahead_intent_grounded_in_perception():
    orch = ConversationOrchestrator()

    # 1. Clear world -> Respectful reassuring guidance
    world_clear = {"active_tracks": [], "highest_threat": "SILENT"}
    res_clear = orch.process_query("నా ముందు ఏమన్నా ఉన్నాయా?", world_clear, language="te-IN")
    assert res_clear["intent"] == "WHAT_AHEAD"
    assert "ఎవరూ లేరు" in res_clear["speech"] or "దారి క్లియర్గా ఉంది" in res_clear["speech"]

    # 2. Person in view at 2.2m
    obs_person = [{"class_name": "person", "raw_class_name": "person", "distance_m": 2.2, "spatial_sector": "LEFT", "motion_state": "APPROACHING"}]
    world_person = {"active_tracks": obs_person, "highest_threat": "CAUTION"}
    res_person = orch.process_query("నా ముందు ఏముంది?", world_person, language="te-IN")
    assert "మీ ముందు ఒక వ్యక్తి ఉన్నారు" in res_person["speech"]

    # 3. Contextual follow-up: "Is he moving?" ("అతను కదులుతున్నాడా?")
    res_moving = orch.process_query("అతను కదులుతున్నాడా?", world_person, language="te-IN")
    assert res_moving["intent"] == "IS_MOVING"
    assert "మీ వైపు కదులుతున్నారు" in res_moving["speech"]

def test_still_present_and_has_left_queries():
    orch = ConversationOrchestrator()

    obs_person = [{"class_name": "person", "raw_class_name": "person", "distance_m": 2.0, "spatial_sector": "CENTER"}]
    world_person = {"active_tracks": obs_person, "highest_threat": "CAUTION"}
    world_empty = {"active_tracks": [], "highest_threat": "SILENT"}

    # 1. "ఇంకా ఉన్నారా?" while person is present -> "అవును సర్, ఇంకా మీ ముందే ఉన్నారు."
    res_still_yes = orch.process_query("మార్క్, ఇంకా ఉన్నారా?", world_person, language="te-IN")
    assert res_still_yes["intent"] == "STILL_PRESENT"
    assert "ఇంకా మీ ముందే ఉన్నారు" in res_still_yes["speech"]

    # 2. "ఇంకా ఉన్నారా?" after person leaves -> "లేదు సర్, ఇప్పుడు మీ ముందు ఎవరూ లేరు."
    res_still_no = orch.process_query("అతను ఇంకా ఉన్నాడా?", world_empty, language="te-IN")
    assert res_still_no["intent"] == "STILL_PRESENT"
    assert "ఇప్పుడు మీ ముందు ఎవరూ లేరు" in res_still_no["speech"]

    # 3. "అతను వెళ్లిపోయాడా?" after person leaves -> "అవును సర్, ఇప్పుడు ఆయన అక్కడ లేరు. ముందు దారి క్లియర్గా ఉంది"
    res_left_yes = orch.process_query("అతను వెళ్లిపోయాడా?", world_empty, language="te-IN")
    assert res_left_yes["intent"] == "HAS_LEFT"
    assert "ఇప్పుడు ఆయన అక్కడ లేరు" in res_left_yes["speech"]

def test_camera_failure_safety_guard():
    orch = ConversationOrchestrator()
    world_degraded = {"active_tracks": [], "camera_healthy": False}
    res = orch.process_query("నేను వెళ్లవచ్చా?", world_degraded, language="te-IN")
    assert res["intent"] == "IS_SAFE"
    assert "కెమెరా నుంచి సమాచారం సరిగ్గా రావడం లేదు" in res["speech"]

def test_companion_talk_to_me_intent():
    orch = ConversationOrchestrator()
    res = orch.process_query("మార్క్, నాతో మాట్లాడవా?", {}, language="te-IN")
    assert res["intent"] == "TALK_TO_ME"
    assert "నేను మీతోనే ఉన్నాను" in res["speech"]

def test_is_safe_intent_vision_verification():
    orch = ConversationOrchestrator()

    # 1. Dangerous car at 1.1m -> Refuse safety
    obs_car = [{"class_name": "car", "raw_class_name": "car", "distance_m": 1.1, "spatial_sector": "CENTER"}]
    world_danger = {"active_tracks": obs_car, "highest_threat": "URGENT"}
    res_danger = orch.process_query("నేను సేఫ్గా వెళ్లవచ్చా?", world_danger, language="te-IN")
    assert res_danger["intent"] == "IS_SAFE"
    assert "అడ్డంకి ఉంది" in res_danger["speech"]
    assert res_danger["priority"] == "high"

    # 2. Safe clear world -> Confirm safety
    world_safe = {"active_tracks": [], "highest_threat": "SILENT"}
    res_safe = orch.process_query("నేను సేఫ్గా ఉన్నానా?", world_safe, language="te-IN")
    assert "దారి క్లియర్గా ఉంది" in res_safe["speech"]

def test_where_to_go_intent_lateral_clearance():
    orch = ConversationOrchestrator()

    # Left is blocked -> Recommend Right
    world_left_block = {"active_tracks": [{"spatial_sector": "LEFT", "distance_m": 2.0}]}
    res_dir = orch.process_query("నేను ఎటు వెళ్లాలి?", world_left_block, language="te-IN")
    assert res_dir["intent"] == "WHERE_TO_GO"
    assert "ముందుకు వెళ్లండి" in res_dir["speech"]

def test_repeat_and_emergency_intents():
    orch = ConversationOrchestrator()
    orch.last_instruction_spoken = "సర్, కుడివైపుకి జరగండి."

    # Repeat
    res_rep = orch.process_query("మళ్ళీ చెప్పు", {}, language="te-IN")
    assert res_rep["intent"] == "REPEAT"
    assert res_rep["speech"] == "సర్, కుడివైపుకి జరగండి."

    # Help / Emergency
    res_help = orch.process_query("మార్క్, నాకు హెల్ప్ కావాలి", {}, language="te-IN")
    assert res_help["intent"] == "EMERGENCY"
    assert ("సహాయం" in res_help["speech"] or "కాల్ చేస్తున్నాను" in res_help["speech"])
    assert res_help["action"] == "EMERGENCY_CALL"
    assert "+1" in res_help["target"]

    # Family call
    res_fam = orch.process_query("నా ఫ్యామిలీకి కాల్ చేయి", {}, language="te-IN")
    assert res_fam["intent"] == "FAMILY_CALL_REQUEST"
    assert ("కాల్ చేస్తున్నాను" in res_fam["speech"] or "ఫ్యామిలీ" in res_fam["speech"])
    assert res_fam["action"] == "CALL_FAMILY"
    assert "+1" in res_fam["target"]

def test_voice_first_dashboard_control_commands():
    orch = ConversationOrchestrator()

    # 1. AI mode toggle ON
    res_on = orch.process_query("AI mode on cheyyi", {}, language="te-IN")
    assert res_on["intent"] == "ENABLE_AI_MODE"
    assert "గమనిస్తోంది" in res_on["speech"]

    # 2. AI mode toggle OFF
    res_off = orch.process_query("AI mode off cheyyi", {}, language="te-IN")
    assert res_off["intent"] == "DISABLE_AI_MODE"
    assert "ఆఫ్లో ఉంది" in res_off["speech"]

    # 3. Voice silent mode
    res_silence = orch.process_query("silent ga undu", {}, language="te-IN")
    assert res_silence["intent"] == "VOICE_SILENT_MODE"
    assert "వాయిస్ అలర్ట్స్ తాత్కాలికంగా ఆపాను" in res_silence["speech"]

    # 4. Voice resume
    res_resume = orch.process_query("మళ్లీ మాట్లాడు", {}, language="te-IN")
    assert res_resume["intent"] == "RESUME_VOICE"
    assert "మళ్లీ యాక్టివ్గా ఉన్నాను" in res_resume["speech"]

    # 5. Guardian mode explanation (Manual only)
    res_guard = orch.process_query("Guardian mode on", {}, language="te-IN")
    assert res_guard["intent"] == "GUARDIAN_MODE_EXPLANATION"
    assert "ప్రత్యేక స్క్రీన్ నుంచి మాన్యువల్గా" in res_guard["speech"]
