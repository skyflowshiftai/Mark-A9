import pytest
from fastapi.testclient import TestClient

from server import app
from intelligence.telugu_instruction_engine import TeluguInstructionEngine
from voice.sarvam_service import SarvamService

@pytest.fixture
def client():
    return TestClient(app)

def test_telugu_instruction_synthesis_rules():
    engine = TeluguInstructionEngine()

    # 1. Car Danger -> "సార్, కారు ముందుకు వస్తోంది. ఆగండి."
    res_car = engine.generate_instruction({
        "object": "car",
        "distance": 1.2,
        "direction": "front",
        "risk": "high"
    })
    assert res_car["shouldSpeak"] is True
    assert "కారు" in res_car["instruction"] or "వాహనం" in res_car["instruction"]
    assert "ఆగండి" in res_car["instruction"]
    assert res_car["priority"] == "high"

    # 2. Step Danger -> "సార్, మెట్టు ఉంది. జాగ్రత్త."
    res_step = engine.generate_instruction({
        "object": "step",
        "distance": 0.8,
        "direction": "front",
        "risk": "high"
    })
    assert res_step["shouldSpeak"] is True
    assert "మెట్టు" in res_step["instruction"]
    assert "జాగ్రత్త" in res_step["instruction"]

    # 3. Person Awareness -> "సార్, మీ ముందు ఒక వ్యక్తి ఉన్నారు."
    res_person = engine.generate_instruction({
        "object": "person",
        "distance": 2.5,
        "direction": "front",
        "risk": "medium"
    })
    assert res_person["shouldSpeak"] is True
    assert "వ్యక్తి" in res_person["instruction"]

    # 4. Safe Path -> Silence / "దారి ఖాళీగా ఉంది."
    res_safe = engine.generate_instruction({
        "object": "none",
        "distance": 10.0,
        "direction": "front",
        "risk": "low"
    })
    assert res_safe["shouldSpeak"] is False
    assert "దారి ఖాళీగా ఉంది" in res_safe["instruction"]

def test_telugu_currency_and_safety_queries():
    engine = TeluguInstructionEngine()

    # Currency
    assert engine.format_currency_telugu(500) == "ఐదు వందల రూపాయల నోటు."
    assert engine.format_currency_telugu(100) == "వంద రూపాయల నోటు."

    # "Am I safe?" Clear
    safe_ans = engine.format_safety_query_telugu(highest_risk="LOW")
    assert "ప్రస్తుతం దారి ఖాళీగా ఉంది" in safe_ans

    # "Am I safe?" Uncertain
    unc_ans = engine.format_safety_query_telugu(highest_risk="LOW", is_uncertain=True)
    assert "ముందున్న దారి స్పష్టంగా కనిపించడం లేదు" in unc_ans

    # "Am I safe?" Danger
    danger_ans = engine.format_safety_query_telugu(highest_risk="URGENT", nearest_obj="car")
    assert "కారు దగ్గరగా ఉంది" in danger_ans

def test_sarvam_service_configuration():
    sarvam = SarvamService()
    assert sarvam.model == "bulbul:v3"
    assert sarvam.language_code == "te-IN"
    assert sarvam.speaker == "ritu"
    assert sarvam.sample_rate == 22050

def test_mark_voice_instruction_endpoint(client):
    res = client.post("/api/mark/voice-instruction", json={
        "event": {
            "object": "car",
            "distance": 1.2,
            "direction": "front",
            "risk": "high"
        },
        "language": "te-IN"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["shouldSpeak"] is True
    assert "కారు" in data["instruction"] or "వాహనం" in data["instruction"]

def test_tts_telugu_endpoint(client):
    res = client.post("/api/tts", json={
        "text": "సార్, కారు ముందుకు వస్తోంది. ఆగండి.",
        "priority": "critical",
        "language": "te-IN"
    })
    assert res.status_code == 200
