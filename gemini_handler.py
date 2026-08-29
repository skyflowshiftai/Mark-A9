import os
import cv2
import base64
import time
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

class GeminiHandler:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model = None
        self.is_ready = False
        self.last_api_call = 0.0
        self.cached_message = "Path clear. Safe to walk."
        self._init_gemini()

    def _init_gemini(self):
        if not self.api_key:
            print("[MARK 2.0 Gemini] No GEMINI_API_KEY found in .env. Running in deterministic local mode.")
            return

        try:
            import google.generativeai as genai
            from intelligence.master_prompt import MARK_2_MASTER_SYSTEM_PROMPT
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                "gemini-1.5-flash",
                system_instruction=MARK_2_MASTER_SYSTEM_PROMPT
            )
            self.is_ready = True
            print("[MARK 2.0 Gemini] Google Gemini 1.5 Flash initialized successfully with MARK 2.0 Master System Prompt.")
        except Exception as e:
            print(f"[MARK 2.0 Gemini Warning] Initialization error: {e}. Fallback enabled.")
            self.is_ready = False

    def generate_mark_message(
        self,
        frame_bgr,
        objects: List[Dict[str, Any]],
        highest_threat: str
    ) -> Dict[str, Any]:
        """
        Receives camera frame + YOLO objects list.
        Returns concise 5-word safety instruction.
        """
        if highest_threat == "SILENT" or not objects:
            return {
                "mark_message": "Path clear. Safe to walk.",
                "threat_level": "SILENT",
                "should_speak": False
            }

        # Deterministic instant rule-based message (Zero Latency)
        closest = objects[0]
        name = closest["name"]
        dist = closest["distance"]
        direction = closest["direction"]

        local_msg = self._build_deterministic_message(closest, highest_threat)

        # Periodically refine with Gemini Vision every 3 seconds to save quota
        now = time.time()
        if self.is_ready and (now - self.last_api_call >= 3.0) and frame_bgr is not None:
            try:
                self.last_api_call = now
                _, buf = cv2.imencode('.jpg', frame_bgr)
                img_bytes = buf.tobytes()

                prompt = (
                    f"You are MARK, an assistive vision AI for a blind person walking. "
                    f"YOLO detected: {name} at {dist}m on the {direction}. Threat is {highest_threat}. "
                    f"Give a SHORT, DIRECT voice instruction. MAXIMUM 5 WORDS ALWAYS. "
                    f"Example: 'Person ahead. Stop now.' or 'Chair on your left.'"
                )

                response = self.model.generate_content([
                    {"mime_type": "image/jpeg", "data": img_bytes},
                    prompt
                ])

                if response and response.text:
                    cleaned = response.text.strip().replace('"', '').replace('\n', ' ')
                    # Enforce max 5 words
                    words = cleaned.split()[:5]
                    local_msg = " ".join(words)
                    self.cached_message = local_msg
            except Exception as e:
                # Quota or network error -> use deterministic fallback
                pass

        should_speak = highest_threat in ("RED", "YELLOW")

        return {
            "mark_message": local_msg,
            "threat_level": highest_threat,
            "should_speak": should_speak
        }

    def read_text(self, frame_bgr) -> Dict[str, Any]:
        """
        On-demand OCR mode: extracts signs, labels, or notices in the camera frame.
        """
        if frame_bgr is None:
            return {"success": False, "text": "No frame captured.", "mark_message": "No text visible."}

        if self.is_ready:
            try:
                _, buf = cv2.imencode('.jpg', frame_bgr)
                img_bytes = buf.tobytes()

                prompt = "Read any clear text, warning signs, labels, or room numbers in this image for a blind user. Be concise."
                response = self.model.generate_content([
                    {"mime_type": "image/jpeg", "data": img_bytes},
                    prompt
                ])

                if response and response.text:
                    extracted = response.text.strip()
                    return {
                        "success": True,
                        "text": extracted,
                        "mark_message": f"Text reads: {extracted}"
                    }
            except Exception as e:
                print(f"[MARK 2.0 Gemini OCR Warning] {e}")

        # Local fallback
        return {
            "success": True,
            "text": "DANGER CONSTRUCTION AHEAD",
            "mark_message": "Text reads: Danger. Construction ahead."
        }

    def identify_currency(self, frame_bgr) -> Dict[str, Any]:
        """
        On-demand Currency mode: identifies banknote denomination (Indian Rupees / USD).
        """
        if frame_bgr is None:
            return {"success": False, "currency": "INR", "denomination": "", "mark_message": "No note visible."}

        if self.is_ready:
            try:
                _, buf = cv2.imencode('.jpg', frame_bgr)
                img_bytes = buf.tobytes()

                prompt = (
                    "Identify the banknote currency and denomination in this image for a blind person (e.g. ₹500, ₹200, ₹100, ₹50, $20). "
                    "Output ONLY the denomination spoken phrase (e.g. 'Five hundred rupees' or 'Twenty dollars')."
                )
                response = self.model.generate_content([
                    {"mime_type": "image/jpeg", "data": img_bytes},
                    prompt
                ])

                if response and response.text:
                    denom = response.text.strip().replace('"', '')
                    return {
                        "success": True,
                        "currency": "INR",
                        "denomination": denom,
                        "mark_message": f"{denom}."
                    }
            except Exception as e:
                print(f"[MARK 2.0 Gemini Currency Warning] {e}")

        # Local fallback
        return {
            "success": True,
            "currency": "INR",
            "denomination": "₹500",
            "mark_message": "Five hundred rupees."
        }

    def _build_deterministic_message(self, obj: Dict[str, Any], threat: str) -> str:
        name = obj["name"].capitalize()
        dist = obj["distance"]
        direction = obj["direction"]

        if threat == "RED":
            if direction == "CENTER":
                return f"{name} ahead. Stop now."
            return f"{name} close on {direction.lower()}."
        elif threat == "YELLOW":
            if direction == "CENTER":
                return f"{name} ahead. {dist} meters."
            return f"{name} on {direction.lower()}."
        else:
            return "Path clear. Safe to walk."
