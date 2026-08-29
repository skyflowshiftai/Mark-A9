import re
import cv2
import numpy as np
from typing import Dict, Any, List, Optional
from collections import deque, Counter

class HybridRecognizer:
    """
    Separates raw detection from object recognition.
    Enforces a Confidence Gate and Temporal Class Stability to prevent hallucinating 
    or forcing unknown objects (e.g. biscuit packets) into random COCO classes.
    """
    def __init__(self):
        # Known common food/household package keyword patterns for secondary OCR
        self.text_signatures = {
            "biscuit packet": [r"\bparle\b", r"\bgood day\b", r"\bbritannia\b", r"\boreo\b", r"\bbiscuit\b", r"\bcookie\b", r"\bmarie\b", r"\b50-50\b", r"\bcrackjack\b", r"\bmonaco\b", r"\bdigestive\b", r"\bbake\b"],
            "food packet": [r"\blays\b", r"\bchips\b", r"\bkurkure\b", r"\bmaggi\b", r"\bnoodles\b", r"\bsnack\b", r"\bnamkeen\b", r"\bhaldiram\b", r"\bbikaji\b"],
            "medicine / box": [r"\btablet\b", r"\bcapsule\b", r"\bsyrup\b", r"\bmg\b", r"\bdettol\b", r"\bparacetamol\b", r"\bpharma\b", r"\bcrocin\b"],
            "personal care": [r"\bsoap\b", r"\bshampoo\b", r"\bcolgate\b", r"\bpaste\b", r"\bdove\b", r"\bnivea\b", r"\blotion\b"]
        }

        # Known distinct physical categories with strong visual cues
        self.strong_visual_classes = {
            "person", "car", "motorcycle", "bus", "truck", "bicycle", 
            "dog", "cat", "chair", "bench", "couch", "bed", "dining table",
            "laptop", "cell phone", "keyboard", "mouse", "tv", "bottle",
            "cup", "book", "backpack", "suitcase", "traffic light", "stop sign"
        }

    def evaluate_recognition(
        self,
        candidate_class: str,
        confidence: float,
        class_history: deque,
        crop_bgr: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Evaluates detector output through a Multi-Signal Confidence Gate:
        1. Temporal Stability across recent frames (rolling history)
        2. Detector Confidence threshold
        3. Secondary OCR Crop Text (if available)
        """
        # Append latest candidate to history
        class_history.append(candidate_class)
        history_len = len(class_history)

        # 1. Compute Temporal Class Stability
        counts = Counter(class_history)
        most_common_cls, most_common_count = counts.most_common(1)[0]
        stability_ratio = round(most_common_count / max(1, history_len), 2)

        # 2. Check for Text on the Object (Secondary OCR Recognition)
        ocr_label = None
        detected_text = ""
        if crop_bgr is not None and crop_bgr.size > 0:
            ocr_res = self._scan_crop_text(crop_bgr)
            if ocr_res["found"]:
                ocr_label = ocr_res["category"]
                detected_text = ocr_res["text"]

        # 3. Decision Logic through Confidence Gate
        # Case A: Secondary OCR identified a specific package/item
        if ocr_label:
            return {
                "display_name": f"{ocr_label.capitalize()}" + (f" ({detected_text[:12]})" if detected_text else ""),
                "recognition_status": "RECOGNIZED_OCR",
                "is_confident": True,
                "detector_candidate": candidate_class,
                "confidence": max(confidence, 0.85),
                "stability": stability_ratio,
                "voice_name": ocr_label
            }

        # Case B: Unstable Fluctuating Detection -> UNCERTAIN (Unknown Object)
        if stability_ratio < 0.50:
            return {
                "display_name": "Unknown Object",
                "recognition_status": "UNCERTAIN",
                "is_confident": False,
                "detector_candidate": candidate_class,
                "confidence": confidence,
                "stability": stability_ratio,
                "voice_name": "unknown object"
            }

        # Case C: Stable Detection on recognizable categories (Laptop, Keyboard, Person, Chair, Bottle, etc.)
        if most_common_cls.lower() in self.strong_visual_classes:
            return {
                "display_name": most_common_cls.capitalize(),
                "recognition_status": "KNOWN" if confidence >= 0.50 else "PROBABLE",
                "is_confident": confidence >= 0.40,
                "detector_candidate": most_common_cls,
                "confidence": confidence,
                "stability": stability_ratio,
                "voice_name": most_common_cls.lower()
            }

        # Case D: Other detected COCO objects
        if confidence >= 0.40:
            return {
                "display_name": candidate_class.capitalize(),
                "recognition_status": "PROBABLE",
                "is_confident": True,
                "detector_candidate": candidate_class,
                "confidence": confidence,
                "stability": stability_ratio,
                "voice_name": candidate_class.lower()
            }

        # Case E: Low Confidence -> UNKNOWN OBJECT
        return {
            "display_name": "Unknown Object",
            "recognition_status": "UNCERTAIN",
            "is_confident": False,
            "detector_candidate": candidate_class,
            "confidence": confidence,
            "stability": stability_ratio,
            "voice_name": "unknown object"
        }

    def recognize_held_object(self, frame_bgr: np.ndarray, bbox: List[float]) -> Dict[str, Any]:
        """
        Active Query Mode ('Hey Mark, what is this?').
        Crops center region, applies edge & OCR analysis, and returns honest answer.
        """
        if frame_bgr is None or frame_bgr.size == 0 or len(bbox) < 4:
            return {
                "success": False,
                "spoken_text": "I can't see any object clearly. Please hold it in front of the camera.",
                "identified": False
            }

        h, w = frame_bgr.shape[:2]
        x1 = max(0, int(bbox[0]))
        y1 = max(0, int(bbox[1]))
        x2 = min(w, int(bbox[2]))
        y2 = min(h, int(bbox[3]))

        crop = frame_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return {
                "success": False,
                "spoken_text": "I can't identify it clearly. Please hold it closer.",
                "identified": False
            }

        # Run OCR on crop
        ocr_res = self._scan_crop_text(crop)
        if ocr_res["found"]:
            category = ocr_res["category"]
            text = ocr_res["text"]
            return {
                "success": True,
                "spoken_text": f"This looks like a {category}. Text says: {text}." if text else f"This looks like a {category}.",
                "identified": True,
                "category": category,
                "text": text
            }

        # Inspect aspect ratio & edge texture
        aspect_ratio = (x2 - x1) / max(1.0, (y2 - y1))
        if 0.5 <= aspect_ratio <= 1.8:
            return {
                "success": True,
                "spoken_text": "Packet or rectangular object detected, but the label is unclear.",
                "identified": False,
                "category": "packet-like object"
            }

        return {
            "success": True,
            "spoken_text": "I see an object here, but I can't identify it clearly. Please show it closer.",
            "identified": False,
            "category": "unknown object"
        }

    def _scan_crop_text(self, crop_bgr: np.ndarray) -> Dict[str, Any]:
        """
        Fast local text scanner for brand/product packaging.
        """
        try:
            import pytesseract
            gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            # Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            text = pytesseract.image_to_string(enhanced, config='--psm 6').strip()
            
            if text and len(text) >= 3:
                clean_text = text.lower()
                for cat, patterns in self.text_signatures.items():
                    for pat in patterns:
                        if re.search(pat, clean_text):
                            return {
                                "found": True,
                                "category": cat,
                                "text": text.split('\n')[0][:20]
                            }

                # General readable text found on item
                clean_first_line = re.sub(r'[^a-zA-Z0-9\s]', '', text.split('\n')[0]).strip()
                if len(clean_first_line) >= 3:
                    return {
                        "found": True,
                        "category": "labeled item",
                        "text": clean_first_line[:16]
                    }
        except Exception:
            pass

        return {"found": False, "category": "", "text": ""}

    @staticmethod
    def _get_conservative_label(candidate: str) -> str:
        c = candidate.lower()
        if c in ("bottle", "cup", "bowl", "vase"):
            return "Container"
        elif c in ("book", "cell phone", "remote", "laptop", "keyboard"):
            return "Packet / Rectangular item"
        elif c in ("backpack", "handbag", "suitcase"):
            return "Bag / Luggage"
        elif c in ("chair", "bench", "couch"):
            return "Seating obstacle"
        return "Object"
