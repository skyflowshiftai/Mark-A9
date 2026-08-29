import pytest
from fastapi.testclient import TestClient

from server import app
from intelligence.adaptive_memory import AdaptiveMemory
from intelligence.experience_engine import ExperienceEngine
from intelligence.ai_teacher import AITeacher

@pytest.fixture
def client():
    return TestClient(app)

def test_adaptive_memory_store():
    mem = AdaptiveMemory()
    assert len(mem.verified_cases) >= 2
    assert "preferred_language" in mem.semantic_memory

    # Search similar cases
    matches = mem.search_similar_cases(["vehicle", "approaching"])
    assert len(matches) >= 1
    assert "CASE_001" == matches[0]["case_id"]

def test_experience_engine_and_failure_diagnosis():
    mem = AdaptiveMemory()
    engine = ExperienceEngine(memory=mem)

    # 1. Record Success
    case_succ = engine.record_interaction(
        situation="Corridor navigation",
        observation="Chair on left at 1.5m",
        confidence=0.92,
        decision="Recommend move right",
        action="move_right",
        outcome="SUCCESS"
    )
    assert case_succ["outcome"] == "SUCCESS"
    assert case_succ["memory_status"] == "CANDIDATE"

    # 2. Record Failure
    case_fail = engine.record_interaction(
        situation="Corridor navigation",
        observation="Chair on left at 1.5m, wall on right",
        confidence=0.88,
        decision="Recommend move right",
        action="move_right",
        outcome="FAILURE",
        user_feedback="Hit right wall"
    )
    assert case_fail["outcome"] == "FAILURE"
    assert "Hit right wall" in case_fail["failure_reason"]
    assert len(mem.failure_memory) == 1

def test_ai_teacher_regression_evaluation():
    mem = AdaptiveMemory()
    engine = ExperienceEngine(memory=mem)
    teacher = AITeacher(memory=mem)

    # Record candidate lesson
    case = engine.record_interaction(
        situation="Road crossing",
        observation="Vehicle approaching at 2m",
        confidence=0.95,
        decision="Halt immediately",
        action="STOP",
        outcome="SUCCESS"
    )

    eval_res = teacher.evaluate_candidate_lesson(case)
    assert eval_res["decision"] == "ADOPT_PROPOSED"
    assert case["memory_status"] == "VERIFIED"
    assert any(c.get("case_id") == case["case_id"] for c in mem.verified_cases)

def test_experience_rest_endpoints(client):
    # 1. Record interaction
    res_rec = client.post("/api/experience/record", json={
        "situation": "Crosswalk",
        "observation": "Car approaching 1.2m",
        "confidence": 0.96,
        "decision": "Stop",
        "action": "STOP",
        "outcome": "SUCCESS"
    })
    assert res_rec.status_code == 200
    assert res_rec.json()["status"] == "RECORDED"

    # 2. Get cases
    res_cases = client.get("/api/experience/cases")
    assert res_cases.status_code == 200
    data = res_cases.json()
    assert "summary" in data
    assert "verified_cases" in data

    # 3. Trigger evaluation
    res_eval = client.post("/api/experience/evaluate")
    assert res_eval.status_code == 200
    assert res_eval.json()["status"] == "EVALUATION_COMPLETE"
