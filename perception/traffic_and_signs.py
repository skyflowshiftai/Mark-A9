"""
MARK 2.0 — Traffic Signal & Road Sign Board Intelligence Module
Analyzes traffic light states (Red, Yellow, Green) and road signs
(Stop, Pedestrian Crossing, No Entry, Speed Limit, Directional Turns, School Ahead).
"""

import cv2
import numpy as np
import re
from typing import Dict, Any, List, Optional


class TrafficAndSignRecognizer:
    def __init__(self):
        # Known road sign keywords for optical recognition
        self.sign_keywords = {
            "STOP_SIGN": [r"\bstop\b", r"\bagandi\b", r"\bఆగండి\b"],
            "NO_ENTRY": [r"\bno entry\b", r"\bno-entry\b", r"\bentry\b", r"\bprohibited\b", r"\bno\b"],
            "PEDESTRIAN_CROSSING": [r"\bcrossing\b", r"\bpedestrian\b", r"\bzebra\b", r"\bwalk\b"],
            "SPEED_LIMIT": [r"\b\d{2}\b", r"\bspeed\b", r"\bkm/h\b", r"\bkmph\b", r"\blimit\b", r"\b20\b", r"\b30\b", r"\b40\b", r"\b50\b", r"\b60\b", r"\b80\b"],
            "SCHOOL_AHEAD": [r"\bschool\b", r"\bchildren\b", r"\bkids\b", r"\bahead\b"],
            "HOSPITAL": [r"\bhospital\b", r"\bclinic\b", r"\bemergency\b"],
            "NO_PARKING": [r"\bno parking\b", r"\bparking\b"]
        }

    def analyze_traffic_light(self, crop_bgr: np.ndarray) -> Dict[str, Any]:
        """
        Analyzes a cropped traffic light to determine the active signal color (Red, Yellow, Green).
        Partitions vertical height into top (Red), middle (Yellow), bottom (Green).
        """
        if crop_bgr is None or crop_bgr.size == 0:
            return {
                "active_color": "UNKNOWN",
                "confidence": 0.0,
                "speech_te": "సర్, ట్రాఫిక్ సిగ్నల్ స్పష్టంగా కనిపించడం లేదు.",
                "speech_en": "Sir, traffic signal is not clearly visible."
            }

        h, w = crop_bgr.shape[:2]
        hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)

        # 1. Color Mask definitions in HSV
        # Red spans 0-10 and 160-180
        mask_r1 = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
        mask_r2 = cv2.inRange(hsv, np.array([160, 100, 100]), np.array([180, 255, 255]))
        mask_red = cv2.bitwise_or(mask_r1, mask_r2)

        # Yellow / Amber: 15-35
        mask_yellow = cv2.inRange(hsv, np.array([15, 100, 100]), np.array([35, 255, 255]))

        # Green: 40-85
        mask_green = cv2.inRange(hsv, np.array([40, 80, 80]), np.array([90, 255, 255]))

        # 2. Measure intensity in spatial thirds
        h_third = h // 3
        top_slice = mask_red[:max(1, h_third), :]
        mid_slice = mask_yellow[max(1, h_third):max(2, h_third * 2), :]
        bot_slice = mask_green[max(2, h_third * 2):, :]

        red_score = float(np.sum(top_slice > 0)) + float(np.sum(mask_red > 0)) * 0.5
        yellow_score = float(np.sum(mid_slice > 0)) + float(np.sum(mask_yellow > 0)) * 0.5
        green_score = float(np.sum(bot_slice > 0)) + float(np.sum(mask_green > 0)) * 0.5

        scores = [("RED", red_score), ("YELLOW", yellow_score), ("GREEN", green_score)]
        scores.sort(key=lambda x: x[1], reverse=True)
        best_color, best_val = scores[0]

        if best_val < 15.0:
            # Low illumination -> default to Red for maximum safety
            return {
                "active_color": "RED",
                "confidence": 0.60,
                "speech_te": "సర్, ట్రాఫిక్ సిగ్నల్ ఉంది. జాగ్రత్తగా ఆగండి.",
                "speech_en": "Sir, traffic signal detected. Please be cautious and wait.",
                "action": "STOP"
            }

        if best_color == "RED":
            return {
                "active_color": "RED",
                "confidence": 0.90,
                "speech_te": "సర్, రెడ్ సిగ్నల్ ఉంది. ఒకసారి ఆగండి.",
                "speech_en": "Sir, red traffic signal. Please stop and wait.",
                "action": "STOP"
            }
        elif best_color == "YELLOW":
            return {
                "active_color": "YELLOW",
                "confidence": 0.85,
                "speech_te": "సర్, ఎల్లో సిగ్నల్ ఉంది. నెమ్మదిగా సిద్ధంగా ఉండండి.",
                "speech_en": "Sir, yellow traffic signal. Get ready and proceed cautiously.",
                "action": "CAUTION"
            }
        else:
            return {
                "active_color": "GREEN",
                "confidence": 0.90,
                "speech_te": "సర్, గ్రీన్ సిగ్నల్ ఉంది. మీరు ముందుకు వెళ్లవచ్చు.",
                "speech_en": "Sir, green traffic signal. Safe to cross and walk forward.",
                "action": "GO"
            }

    def identify_road_sign(self, crop_bgr: np.ndarray, base_class: str = "stop sign", run_ocr: bool = False) -> Dict[str, Any]:
        """
        Identifies road sign boards (Stop sign, Zebra crossing, No Entry, Speed limit, School zone, etc.).
        Fast HSV/geometric analysis by default (0.2ms), OCR only when run_ocr=True.
        """
        if crop_bgr is None or crop_bgr.size == 0:
            return {
                "sign_type": "ROAD_SIGN",
                "name": "Road Sign",
                "speech_te": "సర్, రోడ్ సైన్ బోర్డు ఉంది.",
                "speech_en": "Sir, road sign board ahead."
            }

        h, w = crop_bgr.shape[:2]

        # 1. Stop sign detection from YOLO class or octagonal red sign
        if base_class.lower() == "stop sign":
            return {
                "sign_type": "STOP_SIGN",
                "name": "Stop Sign",
                "speech_te": "సర్, స్టాప్ బోర్డు ఉంది. ఒకసారి ఆగండి.",
                "speech_en": "Sir, Stop sign board ahead. Please stop."
            }

        # 2. Fast optical text check on the sign board (only when on-demand)
        if run_ocr:
            try:
                import pytesseract
                gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
                text = pytesseract.image_to_string(enhanced, config='--psm 6').strip().lower()

                for sign_type, patterns in self.sign_keywords.items():
                    for pat in patterns:
                        if re.search(pat, text):
                            return self._build_sign_response(sign_type, text)
            except Exception:
                pass

        # 3. Geometric & Color Hue analysis for circular / triangular signs (0.2ms)
        hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
        
        # Check for Blue Circular / Rectangular Sign (e.g. Pedestrian / Info / Turn)
        blue_mask = cv2.inRange(hsv, np.array([100, 80, 80]), np.array([130, 255, 255]))
        blue_ratio = float(np.sum(blue_mask > 0)) / float(h * w)

        if blue_ratio > 0.25:
            return {
                "sign_type": "PEDESTRIAN_CROSSING",
                "name": "Pedestrian Crossing",
                "speech_te": "సర్, పాదచారుల దారి లేదా జీబ్రా క్రాసింగ్ బోర్డు ఉంది.",
                "speech_en": "Sir, pedestrian crossing sign board ahead."
            }

        # Check for Red Circular Sign (No Entry / Prohibition)
        mask_r1 = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
        mask_r2 = cv2.inRange(hsv, np.array([160, 100, 100]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(mask_r1, mask_r2)
        red_ratio = float(np.sum(red_mask > 0)) / float(h * w)

        if red_ratio > 0.30:
            return {
                "sign_type": "NO_ENTRY",
                "name": "No Entry / Stop Sign",
                "speech_te": "సర్, నో ఎంట్రీ లేదా స్టాప్ బోర్డు ఉంది. ముందుకు వెళ్లవద్దు.",
                "speech_en": "Sir, No Entry or Stop sign board ahead. Do not proceed."
            }

        # Check for Yellow Warning Triangle (School Ahead / Speed Breaker / Turn)
        yellow_mask = cv2.inRange(hsv, np.array([15, 100, 100]), np.array([35, 255, 255]))
        yellow_ratio = float(np.sum(yellow_mask > 0)) / float(h * w)

        if yellow_ratio > 0.25:
            return {
                "sign_type": "CAUTION_SIGN",
                "name": "Caution / Hazard Sign",
                "speech_te": "సర్, ముందు హెచ్చరిక బోర్డు ఉంది. నెమ్మదిగా వెళ్లండి.",
                "speech_en": "Sir, caution sign board ahead. Please walk carefully."
            }

        return {
            "sign_type": "ROAD_SIGN",
            "name": "Road Sign Board",
            "speech_te": "సర్, ముందు రోడ్ సైన్ బోర్డు ఉంది.",
            "speech_en": "Sir, road sign board ahead."
        }

    def _build_sign_response(self, sign_type: str, raw_text: str = "") -> Dict[str, Any]:
        if sign_type == "STOP_SIGN":
            return {
                "sign_type": "STOP_SIGN",
                "name": "Stop Sign",
                "speech_te": "సర్, స్టాప్ బోర్డు ఉంది. ఒకసారి ఆగండి.",
                "speech_en": "Sir, Stop sign board ahead. Please stop."
            }
        elif sign_type == "NO_ENTRY":
            return {
                "sign_type": "NO_ENTRY",
                "name": "No Entry Sign",
                "speech_te": "సర్, నో ఎంట్రీ బోర్డు ఉంది. అటు వెళ్లవద్దు.",
                "speech_en": "Sir, No Entry sign board ahead. Do not proceed."
            }
        elif sign_type == "PEDESTRIAN_CROSSING":
            return {
                "sign_type": "PEDESTRIAN_CROSSING",
                "name": "Pedestrian Crossing",
                "speech_te": "సర్, పాదచారుల దారి లేదా జీబ్రా క్రాసింగ్ ఉంది.",
                "speech_en": "Sir, pedestrian crossing ahead."
            }
        elif sign_type == "SPEED_LIMIT":
            match = re.search(r'\b(\d{2})\b', raw_text)
            speed_val = match.group(1) if match else "40"
            return {
                "sign_type": "SPEED_LIMIT",
                "name": f"Speed Limit {speed_val}",
                "speech_te": f"సర్, స్పీడ్ లిమిట్ {speed_val} బోర్డు ఉంది.",
                "speech_en": f"Sir, speed limit {speed_val} sign board ahead."
            }
        elif sign_type == "SCHOOL_AHEAD":
            return {
                "sign_type": "SCHOOL_AHEAD",
                "name": "School Ahead Sign",
                "speech_te": "సర్, స్కూల్ జోన్ బోర్డు ఉంది. నెమ్మదిగా వెళ్లండి.",
                "speech_en": "Sir, School Ahead sign board. Proceed cautiously."
            }
        elif sign_type == "HOSPITAL":
            return {
                "sign_type": "HOSPITAL",
                "name": "Hospital Sign",
                "speech_te": "సర్, హాస్పిటల్ జోన్ బోర్డు ఉంది.",
                "speech_en": "Sir, Hospital zone sign board ahead."
            }
        elif sign_type == "NO_PARKING":
            return {
                "sign_type": "NO_PARKING",
                "name": "No Parking Sign",
                "speech_te": "సర్, నో పార్కింగ్ బోర్డు ఉంది.",
                "speech_en": "Sir, No Parking sign board ahead."
            }
        return {
            "sign_type": "ROAD_SIGN",
            "name": "Road Sign",
            "speech_te": "సర్, రోడ్ సైన్ బోర్డు ఉంది.",
            "speech_en": "Sir, road sign board ahead."
        }
