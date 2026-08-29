"""
MARK 2.0 — SAFETY-CRITICAL EMERGENCY & TELEPHONY MANAGER
Manages SOS alerts, guardian synchronization, and outbound family calls.
Configured Contact: +1 949 738 5095
"""

import os
import time
from typing import Dict, Any, Optional
from .telephony import TelephonyService, normalize_e164

DEFAULT_EMERGENCY_PHONE = "+19497385095"

class EmergencyManager:
    def __init__(self, contact_phone: Optional[str] = None):
        self.is_active = False
        self.activated_at = 0.0
        self.trigger_source = None
        self.emergency_log = []
        raw_contact = contact_phone or os.getenv("EMERGENCY_CONTACT_PHONE", os.getenv("EMERGENCY_PHONE_NUMBER", DEFAULT_EMERGENCY_PHONE))
        self.contact_phone = normalize_e164(raw_contact)
        self.call_status = "IDLE"  # IDLE | CALL_REQUESTED | CALL_CONNECTING | CALL_CONNECTED | CALL_FAILED
        self.last_call_id = None
        self.last_call_time = 0.0
        self.telephony = TelephonyService()

    def trigger(self, source: str = "VOICE_COMMAND") -> Dict[str, Any]:
        """
        Activates high-priority emergency state and dispatches family call.
        """
        self.is_active = True
        self.activated_at = time.time()
        self.trigger_source = source
        self.call_status = "CALL_REQUESTED"
        self.last_call_time = self.activated_at
        
        # Dispatch actual outbound phone call via server-side TelephonyService
        telephony_res = self.telephony.dispatch_outbound_call(self.contact_phone, source=source)
        self.last_call_id = telephony_res.get("call_id", f"call_{int(self.activated_at * 1000)}")

        print(f"[MARK Emergency] SOS ACTIVATED via {source}. Dispatched call to {self.contact_phone} (Call ID: {self.last_call_id}, Status: {self.call_status})")

        event = {
            "timestamp": self.activated_at,
            "source": source,
            "status": "EMERGENCY_ACTIVE",
            "call_status": self.call_status,
            "telephony_status": telephony_res.get("status", "DISPATCHED"),
            "call_id": self.last_call_id,
            "contact_phone": self.contact_phone,
            "provider": telephony_res.get("provider", "SERVER_TELEPHONY_DISPATCHER"),
            "spoken_feedback_te": telephony_res.get("spoken_feedback_te", f"సర్, మీ సహాయం కోసం కుటుంబ సభ్యులకు ({self.contact_phone}) కాల్ చేస్తున్నాను."),
            "spoken_feedback_en": telephony_res.get("spoken_feedback_en", f"Sir, emergency outbound call dispatched to {self.contact_phone}."),
            "message": "EMERGENCY ACTIVE. Alert broadcasted to guardians & family call initiated."
        }
        self.emergency_log.append(event)
        return event

    def update_call_status(self, status: str) -> None:
        """
        Updates the telephony call connection status.
        """
        self.call_status = status
        print(f"[MARK Telephony] Call {self.last_call_id} state updated to: {status}")

    def resolve(self) -> Dict[str, Any]:
        """
        Resolves active emergency.
        """
        self.is_active = False
        self.trigger_source = None
        self.call_status = "IDLE"
        self.telephony.reset()
        return {
            "status": "RESOLVED",
            "message": "Emergency resolved. System back to active perception."
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_active": self.is_active,
            "activated_at": self.activated_at,
            "trigger_source": self.trigger_source,
            "call_status": self.call_status,
            "call_id": self.last_call_id,
            "contact_phone": self.contact_phone,
            "duration_sec": round(time.time() - self.activated_at, 1) if self.is_active else 0.0
        }
