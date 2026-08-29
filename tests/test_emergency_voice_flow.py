"""
MARK 2.0 — Emergency Voice Workflow & Telephony End-to-End Test Suite
Validates:
1. Voice SOS ("మార్క్ ఎమర్జెన్సీ") initiates call to configured contact (+19497385095)
2. Family Call voice requests ("మా వాళ్లకి కాల్ చెయ్యి")
3. Emergency state lifecycle & resolution
4. Empty/Unclear speech graceful fallback
"""

import pytest
from emergency.emergency import EmergencyManager
from intelligence.tools import ActionToolDispatcher
from intelligence.conversation_orchestrator import ConversationOrchestrator


def test_voice_sos_emergency_trigger_and_telephony():
    em = EmergencyManager(contact_phone="+19497385095")
    tools = ActionToolDispatcher(emergency_mgr=em)
    orch = ConversationOrchestrator(tools=tools)

    res = orch.process_query("మార్క్ ఎమర్జెన్సీ", {}, language="te-IN")

    assert res["intent"] == "EMERGENCY"
    assert res["action"] == "EMERGENCY_CALL"
    assert res["target"] == "+19497385095"
    assert "కుటుంబ సభ్యులకు కాల్ చేస్తున్నాను" in res["speech"] or "సహాయం" in res["speech"]
    
    status = em.get_status()
    assert status["is_active"] is True
    assert status["call_status"] == "CALL_REQUESTED"
    assert status["contact_phone"] == "+19497385095"


def test_voice_family_call_request():
    em = EmergencyManager(contact_phone="+19497385095")
    tools = ActionToolDispatcher(emergency_mgr=em)
    orch = ConversationOrchestrator(tools=tools)

    res = orch.process_query("మా వాళ్లకి కాల్ చెయ్యి", {}, language="te-IN")

    assert res["intent"] == "FAMILY_CALL_REQUEST"
    assert res["action"] == "CALL_FAMILY"
    assert res["target"] == "+19497385095"
    assert "కాల్ చేస్తున్నాను" in res["speech"]
    
    status = em.get_status()
    assert status["is_active"] is True
    assert status["call_status"] == "CALL_REQUESTED"


def test_emergency_lifecycle_and_resolution():
    em = EmergencyManager()
    
    # 1. Trigger
    em.trigger(source="VOICE_COMMAND")
    assert em.get_status()["is_active"] is True
    assert em.get_status()["call_status"] == "CALL_REQUESTED"

    # 2. Update Call state
    em.update_call_status("CALL_CONNECTED")
    assert em.get_status()["call_status"] == "CALL_CONNECTED"

    # 3. Resolve
    res = em.resolve()
    assert res["status"] == "RESOLVED"
    assert em.get_status()["is_active"] is False
    assert em.get_status()["call_status"] == "IDLE"


def test_empty_speech_fallback_prompt():
    orch = ConversationOrchestrator()
    res = orch.process_query("", {}, language="te-IN")

    assert res["intent"] == "UNCLEAR_SPEECH"
    assert "సర్, మీ మాట నాకు వినిపించలేదు" in res["speech"]
