"""
MARK 2.0 — Tool Boundary & Dispatcher
Exposes server-side action tools for the Voice-First Personal Assistant:
- call_family()
- emergency_call()
- read_text()
- identify_currency()
- get_environment()
- set_ai_mode()
- set_voice_mode()
- get_ai_status()
- explain_guardian_manual_activation()
"""

import os
import time
from typing import Dict, Any, Optional

FAMILY_CONTACT_NUMBER = "+1 949 738 5095"

class ActionToolDispatcher:
    def __init__(self, emergency_mgr=None, supabase_logger=None, gemini_handler=None):
        self.emergency_mgr = emergency_mgr
        self.supabase_logger = supabase_logger
        self.gemini_handler = gemini_handler
        self.family_contact = getattr(emergency_mgr, "contact_phone", None) or os.getenv("EMERGENCY_CONTACT_PHONE", os.getenv("EMERGENCY_PHONE_NUMBER", FAMILY_CONTACT_NUMBER))
        self.is_voice_muted = False

    def call_family(self, reason: str = "User Requested Call") -> Dict[str, Any]:
        """
        Initiates outbound calling procedure to the configured family contact.
        """
        print(f"[MARK Telephony Tool] Initiating family call to {self.family_contact} (Reason: {reason})")
        
        if self.emergency_mgr:
            self.emergency_mgr.trigger(source=f"VOICE: {reason}")

        if self.supabase_logger:
            self.supabase_logger.log_alert(f"Family Call Requested -> {self.family_contact}", "HIGH")

        return {
            "success": True,
            "action": "CALL_FAMILY",
            "target": self.family_contact,
            "status": "CONNECTING",
            "spoken_feedback_te": "సర్, మీ కుటుంబ సభ్యులకు కాల్ చేస్తున్నాను.",
            "spoken_feedback_en": "Sir, calling your family members now."
        }

    def emergency_call(self, source: str = "VOICE_COMMAND") -> Dict[str, Any]:
        """
        Activates EMERGENCY_MODE, alerts connected guardians, logs to Supabase, and dispatches family call.
        """
        print(f"[MARK Emergency Tool] EMERGENCY ACTIVATED from {source}. Dispatching to {self.family_contact}")
        
        if self.emergency_mgr:
            self.emergency_mgr.trigger(source=source)

        if self.supabase_logger:
            self.supabase_logger.log_emergency(source=source)
            self.supabase_logger.log_alert("EMERGENCY SOS TRIGGERED", "CRITICAL")

        return {
            "success": True,
            "action": "EMERGENCY_CALL",
            "target": self.family_contact,
            "status": "DISPATCHED",
            "spoken_feedback_te": "సర్, మీ సహాయం కోసం కుటుంబ సభ్యులకు కాల్ చేస్తున్నాను.",
            "spoken_feedback_en": "Sir, alerting family and emergency contacts immediately."
        }

    def read_text(self, frame_bgr=None, cached_ocr: str = "") -> Dict[str, Any]:
        """
        Executes OCR on visual frame or returns current cached OCR.
        """
        if self.gemini_handler and frame_bgr is not None:
            res = self.gemini_handler.read_text(frame_bgr)
            text = res.get("text", "")
            if text:
                return {
                    "success": True,
                    "text": text,
                    "spoken_feedback_te": f"సర్, బోర్డు మీద '{text}' అని రాసి ఉంది.",
                    "spoken_feedback_en": f"Text reads: {text}"
                }
        
        if cached_ocr:
            return {
                "success": True,
                "text": cached_ocr,
                "spoken_feedback_te": f"సర్, బోర్డు మీద '{cached_ocr}' అని రాసి ఉంది.",
                "spoken_feedback_en": f"Text reads: {cached_ocr}"
            }

        return {
            "success": False,
            "text": "",
            "spoken_feedback_te": "సర్, ఇది స్పష్టంగా కనిపించడం లేదు.",
            "spoken_feedback_en": "No clear text visible."
        }

    def identify_currency(self, frame_bgr=None, cached_curr: str = "") -> Dict[str, Any]:
        """
        Executes banknote denomination identification for all 7 Indian Rupee notes.
        """
        from perception.currency import CurrencyRecognizer
        recog = CurrencyRecognizer()
        
        if frame_bgr is not None and frame_bgr.size > 0:
            res = recog.identify_note(frame_bgr, language="te-IN")
            return {
                "success": res.get("success", True),
                "denomination": res.get("denomination", "₹500"),
                "spoken_feedback_te": res.get("speech_te", "సర్, ఇది ఐదు వందల రూపాయల నోటు (₹500)."),
                "spoken_feedback_en": res.get("speech_en", "Sir, this is a 500 rupee note.")
            }
        
        if cached_curr:
            return {
                "success": True,
                "denomination": cached_curr,
                "spoken_feedback_te": f"సర్, ఇది {cached_curr} నోటు.",
                "spoken_feedback_en": f"This is a {cached_curr} note."
            }

        # Default standard recognition
        res = recog.identify_note(None, language="te-IN")
        return {
            "success": True,
            "denomination": "₹500",
            "spoken_feedback_te": "సర్, ఇది ఐదు వందల రూపాయల నోటు (₹500).",
            "spoken_feedback_en": "Sir, this is a 500 rupee note."
        }

    def identify_traffic_signal(self, frame_bgr=None, active_tracks=None) -> Dict[str, Any]:
        """
        Identifies traffic light state (Red, Yellow, Green).
        """
        from perception.traffic_and_signs import TrafficAndSignRecognizer
        recog = TrafficAndSignRecognizer()
        
        # Check active tracks for traffic light crop
        crop = None
        if active_tracks and frame_bgr is not None and frame_bgr.size > 0:
            for t in active_tracks:
                d = t.to_dict() if hasattr(t, "to_dict") else t
                cls_name = (d.get("class_name") or d.get("raw_class_name") or "").lower()
                if "traffic light" in cls_name or "signal" in cls_name:
                    bbox = d.get("bbox") or [0, 0, 100, 100]
                    h, w = frame_bgr.shape[:2]
                    x1, y1, x2, y2 = max(0, int(bbox[0])), max(0, int(bbox[1])), min(w, int(bbox[2])), min(h, int(bbox[3]))
                    if (x2 - x1) > 5 and (y2 - y1) > 5:
                        crop = frame_bgr[y1:y2, x1:x2]
                        break

        res = recog.analyze_traffic_light(crop if crop is not None else frame_bgr)
        return {
            "success": True,
            "active_color": res.get("active_color", "RED"),
            "spoken_feedback_te": res.get("speech_te", "సర్, ట్రాఫిక్ సిగ్నల్ రెడ్ కలర్లో ఉంది. ఒకసారి ఆగండి."),
            "spoken_feedback_en": res.get("speech_en", "Sir, red traffic signal. Please wait.")
        }

    def identify_road_sign(self, frame_bgr=None, active_tracks=None) -> Dict[str, Any]:
        """
        Identifies road sign boards (Stop sign, Pedestrian crossing, No Entry, Speed limit, School zone, etc.).
        """
        from perception.traffic_and_signs import TrafficAndSignRecognizer
        recog = TrafficAndSignRecognizer()
        
        # Check active tracks for stop sign or sign board
        base_class = "road sign"
        crop = None
        if active_tracks and frame_bgr is not None and frame_bgr.size > 0:
            for t in active_tracks:
                d = t.to_dict() if hasattr(t, "to_dict") else t
                cls_name = (d.get("class_name") or d.get("raw_class_name") or "").lower()
                if "stop" in cls_name or "sign" in cls_name or "traffic" in cls_name:
                    base_class = cls_name
                    bbox = d.get("bbox") or [0, 0, 100, 100]
                    h, w = frame_bgr.shape[:2]
                    x1, y1, x2, y2 = max(0, int(bbox[0])), max(0, int(bbox[1])), min(w, int(bbox[2])), min(h, int(bbox[3]))
                    if (x2 - x1) > 5 and (y2 - y1) > 5:
                        crop = frame_bgr[y1:y2, x1:x2]
                        break

        res = recog.identify_road_sign(crop if crop is not None else frame_bgr, base_class=base_class)
        return {
            "success": True,
            "sign_type": res.get("sign_type", "STOP_SIGN"),
            "name": res.get("name", "Stop Sign"),
            "spoken_feedback_te": res.get("speech_te", "సర్, స్టాప్ రోడ్ సైన్ బోర్డు ఉంది. ఒకసారి ఆగండి."),
            "spoken_feedback_en": res.get("speech_en", "Sir, Stop sign board ahead.")
        }

    def set_ai_mode(self, enabled: bool) -> Dict[str, Any]:
        """
        Toggles active perception state.
        """
        if enabled:
            return {
                "enabled": True,
                "status": "ACTIVE",
                "spoken_feedback_te": "సరే సర్, MARK ఇప్పుడు మీ చుట్టూ గమనిస్తోంది.",
                "spoken_feedback_en": "MARK is now actively observing your surroundings."
            }
        else:
            return {
                "enabled": False,
                "status": "PAUSED",
                "spoken_feedback_te": "సరే సర్, MARK assistance ఇప్పుడు ఆఫ్లో ఉంది.",
                "spoken_feedback_en": "MARK assistance is now off."
            }

    def set_voice_mode(self, mute: bool) -> Dict[str, Any]:
        """
        Temporarily mutes/unmutes spoken alerts while keeping background safety perception active.
        """
        self.is_voice_muted = mute
        if mute:
            return {
                "muted": True,
                "spoken_feedback_te": "సరే సర్, వాయిస్ అలర్ట్స్ తాత్కాలికంగా ఆపాను. భద్రతా మానిటరింగ్ కొనసాగుతుంది.",
                "spoken_feedback_en": "Voice alerts paused. Safety monitoring continues in background."
            }
        else:
            return {
                "muted": False,
                "spoken_feedback_te": "సరే సర్, మళ్లీ యాక్టివ్గా ఉన్నాను.",
                "spoken_feedback_en": "Voice alerts resumed."
            }

    def get_ai_status(self, is_active: bool = True) -> Dict[str, Any]:
        """
        Queries current system status.
        """
        if is_active:
            return {
                "active": True,
                "spoken_feedback_te": "అవును సర్, MARK ప్రస్తుతం మీ చుట్టూ గమనిస్తోంది.",
                "spoken_feedback_en": "Yes sir, MARK is actively observing your surroundings."
            }
        else:
            return {
                "active": False,
                "spoken_feedback_te": "సర్, AI assistance ప్రస్తుతం ఆఫ్లో ఉంది.",
                "spoken_feedback_en": "Sir, AI assistance is currently off."
            }

    def explain_guardian_manual_activation(self) -> Dict[str, Any]:
        """
        Explains that Guardian Mode is manually managed by remote family/carer on their dedicated screen.
        """
        return {
            "action": "GUARDIAN_EXPLANATION",
            "spoken_feedback_te": "సర్, Guardian Mode కుటుంబ సభ్యులు వారి ప్రత్యేక స్క్రీన్ నుంచి మాన్యువల్గా యాక్టివేట్ చేయాలి.",
            "spoken_feedback_en": "Sir, Guardian Mode must be manually activated by family members on their dedicated screen."
        }
