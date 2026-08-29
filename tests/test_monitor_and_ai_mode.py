import pytest
from fastapi.testclient import TestClient
from server import app

@pytest.fixture
def client():
    return TestClient(app)

def test_user_and_monitor_routes(client):
    res_user = client.get("/user")
    assert res_user.status_code == 200
    assert "MARK 2.0" in res_user.text

    res_mon = client.get("/monitor")
    assert res_mon.status_code == 200
    assert "MARK GUARDIAN" in res_mon.text

def test_events_endpoint(client):
    res_events = client.get("/events")
    assert res_events.status_code == 200
    assert "events" in res_events.json()

def test_set_ai_mode_endpoint(client):
    # Disable AI Mode
    res_off = client.post("/api/set_ai_mode", json={"enabled": False})
    assert res_off.status_code == 200
    assert res_off.json()["ai_mode"] is False

    # Re-enable AI Mode
    res_on = client.post("/api/set_ai_mode", json={"enabled": True})
    assert res_on.status_code == 200
    assert res_on.json()["ai_mode"] is True
