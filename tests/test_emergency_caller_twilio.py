import os
import pytest
from emergency_caller import make_emergency_call
from emergency.emergency import EmergencyManager
from intelligence.tools import ActionToolDispatcher
from intelligence.conversation_orchestrator import ConversationOrchestrator

def test_make_emergency_call_logic(monkeypatch):
    class MockCall:
        sid = "CA1234567890abcdef1234567890abcdef"

    class MockCalls:
        def create(self, **kwargs):
            assert "Mark A9 needs your help" in kwargs["twiml"]
            assert kwargs["to"] in ("+916303318876", "+19497385095")
            return MockCall()

    class MockClient:
        def __init__(self, sid, token):
            self.calls = MockCalls()

    monkeypatch.setattr("emergency_caller.Client", MockClient)

    sid = make_emergency_call()
    assert sid == "CA1234567890abcdef1234567890abcdef"

def test_help_me_voice_command_initiates_twilio_emergency(monkeypatch):
    class MockCall:
        sid = "CA9999999999abcdef9999999999abcdef"

    class MockCalls:
        def create(self, **kwargs):
            return MockCall()

    class MockClient:
        def __init__(self, sid, token):
            self.calls = MockCalls()

    monkeypatch.setattr("emergency_caller.Client", MockClient)

    em = EmergencyManager(contact_phone="+19497385095")
    tools = ActionToolDispatcher(emergency_mgr=em)
    orch = ConversationOrchestrator(tools=tools)

    res = orch.process_query("Help Me", {}, language="en-US")
    assert res["intent"] == "EMERGENCY"
    assert res["action"] == "EMERGENCY_CALL"
    assert res["target"] == "+19497385095"
    assert em.get_status()["is_active"] is True
    assert em.get_status()["call_id"] == "CA9999999999abcdef9999999999abcdef"

def test_sos_button_trigger_initiates_twilio_emergency(monkeypatch):
    class MockCall:
        sid = "CA8888888888abcdef8888888888abcdef"

    class MockCalls:
        def create(self, **kwargs):
            return MockCall()

    class MockClient:
        def __init__(self, sid, token):
            self.calls = MockCalls()

    monkeypatch.setattr("emergency_caller.Client", MockClient)

    em = EmergencyManager(contact_phone="+19497385095")
    event = em.trigger(source="BUTTON")
    assert event["status"] == "EMERGENCY_ACTIVE"
    assert event["call_id"] == "CA8888888888abcdef8888888888abcdef"
    assert event["provider"] == "TWILIO"
