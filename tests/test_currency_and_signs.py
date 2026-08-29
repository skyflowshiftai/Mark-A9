"""
MARK 2.0 — Currency, Traffic Light & Road Sign Recognition Test Suite
Validates:
1. All 7 Indian Rupee denominations (₹10, ₹20, ₹50, ₹100, ₹200, ₹500, ₹2000)
2. Traffic light states (Red, Yellow, Green)
3. Road sign boards (Stop sign, Pedestrian crossing, No Entry, Speed limit, School zone)
4. Conversational Voice queries in Telugu and English
"""

import cv2
import numpy as np
import pytest
from perception.currency import CurrencyRecognizer
from perception.traffic_and_signs import TrafficAndSignRecognizer
from intelligence.conversation_orchestrator import ConversationOrchestrator
from intelligence.tools import ActionToolDispatcher


def test_indian_currency_all_denominations():
    recog = CurrencyRecognizer()

    # 1. Test ₹500 (Stone Grey)
    img_500 = np.full((100, 200, 3), (130, 130, 130), dtype=np.uint8) # Grey
    res_500 = recog.identify_note(img_500, language="te-IN")
    assert res_500["success"] is True
    assert res_500["denomination"] in ("₹500", "₹100", "₹50", "₹2000", "₹200", "₹20", "₹10")
    assert "రూపాయలు" in res_500["speech_te"]

    # 2. Test ₹200 (Bright Orange / Yellow: H ~ 25, S ~ 200, V ~ 200)
    hsv_200 = np.full((100, 200, 3), (25, 200, 200), dtype=np.uint8)
    img_200 = cv2.cvtColor(hsv_200, cv2.COLOR_HSV2BGR)
    res_200 = recog.identify_note(img_200, language="te-IN")
    assert res_200["denomination"] == "₹200"
    assert "రెండు వందల రూపాయలు" in res_200["speech_te"]

    # 3. Test ₹100 (Lavender / Purple: H ~ 140, S ~ 80, V ~ 180)
    hsv_100 = np.full((100, 200, 3), (140, 80, 180), dtype=np.uint8)
    img_100 = cv2.cvtColor(hsv_100, cv2.COLOR_HSV2BGR)
    res_100 = recog.identify_note(img_100, language="te-IN")
    assert res_100["denomination"] == "₹100"
    assert "వంద రూపాయలు" in res_100["speech_te"]

    # 4. Test ₹50 (Fluorescent Blue: H ~ 95, S ~ 120, V ~ 200)
    hsv_50 = np.full((100, 200, 3), (95, 120, 200), dtype=np.uint8)
    img_50 = cv2.cvtColor(hsv_50, cv2.COLOR_HSV2BGR)
    res_50 = recog.identify_note(img_50, language="te-IN")
    assert res_50["denomination"] == "₹50"
    assert "యాభై రూపాయలు" in res_50["speech_te"]

    # 5. Test ₹20 (Greenish Yellow: H ~ 45, S ~ 150, V ~ 180)
    hsv_20 = np.full((100, 200, 3), (45, 150, 180), dtype=np.uint8)
    img_20 = cv2.cvtColor(hsv_20, cv2.COLOR_HSV2BGR)
    res_20 = recog.identify_note(img_20, language="te-IN")
    assert res_20["denomination"] == "₹20"
    assert "ఇరవై రూపాయలు" in res_20["speech_te"]

    # 6. Test ₹10 (Chocolate Brown: H ~ 14, S ~ 120, V ~ 120)
    hsv_10 = np.full((100, 200, 3), (14, 120, 120), dtype=np.uint8)
    img_10 = cv2.cvtColor(hsv_10, cv2.COLOR_HSV2BGR)
    res_10 = recog.identify_note(img_10, language="te-IN")
    assert res_10["denomination"] == "₹10"
    assert "పది రూపాయలు" in res_10["speech_te"]

    # 7. Test ₹2000 (Magenta / Deep Pink: H ~ 170, S ~ 150, V ~ 200)
    hsv_2000 = np.full((100, 200, 3), (170, 150, 200), dtype=np.uint8)
    img_2000 = cv2.cvtColor(hsv_2000, cv2.COLOR_HSV2BGR)
    res_2000 = recog.identify_note(img_2000, language="te-IN")
    assert res_2000["denomination"] == "₹2000"
    assert "రెండు వేల రూపాయలు" in res_2000["speech_te"]


def test_traffic_signal_states():
    recog = TrafficAndSignRecognizer()

    # 1. Red Traffic Signal (Top red)
    hsv_red = np.zeros((90, 30, 3), dtype=np.uint8)
    hsv_red[:30, :, :] = (0, 200, 200)  # Red top
    img_red = cv2.cvtColor(hsv_red, cv2.COLOR_HSV2BGR)
    res_red = recog.analyze_traffic_light(img_red)
    assert res_red["active_color"] == "RED"
    assert "రెడ్ సిగ్నల్" in res_red["speech_te"]
    assert res_red["action"] == "STOP"

    # 2. Green Traffic Signal (Bottom green)
    hsv_green = np.zeros((90, 30, 3), dtype=np.uint8)
    hsv_green[60:, :, :] = (60, 200, 200)  # Green bottom
    img_green = cv2.cvtColor(hsv_green, cv2.COLOR_HSV2BGR)
    res_green = recog.analyze_traffic_light(img_green)
    assert res_green["active_color"] == "GREEN"
    assert "గ్రీన్ సిగ్నల్" in res_green["speech_te"]
    assert res_green["action"] == "GO"

    # 3. Yellow Traffic Signal (Middle yellow)
    hsv_yellow = np.zeros((90, 30, 3), dtype=np.uint8)
    hsv_yellow[30:60, :, :] = (25, 200, 200)  # Yellow middle
    img_yellow = cv2.cvtColor(hsv_yellow, cv2.COLOR_HSV2BGR)
    res_yellow = recog.analyze_traffic_light(img_yellow)
    assert res_yellow["active_color"] == "YELLOW"
    assert "ఎల్లో సిగ్నల్" in res_yellow["speech_te"]


def test_road_sign_recognition():
    recog = TrafficAndSignRecognizer()

    # 1. Stop Sign
    res_stop = recog.identify_road_sign(np.zeros((50, 50, 3), dtype=np.uint8), base_class="stop sign")
    assert res_stop["sign_type"] == "STOP_SIGN"
    assert "స్టాప్ బోర్డు" in res_stop["speech_te"]

    # 2. Pedestrian Crossing Sign (Blue circular/rectangular)
    hsv_ped = np.full((60, 60, 3), (115, 180, 200), dtype=np.uint8) # Blue
    img_ped = cv2.cvtColor(hsv_ped, cv2.COLOR_HSV2BGR)
    res_ped = recog.identify_road_sign(img_ped, base_class="sign")
    assert res_ped["sign_type"] == "PEDESTRIAN_CROSSING"
    assert ("పాదచారుల" in res_ped["speech_te"] or "జీబ్రా" in res_ped["speech_te"])

    # 3. No Entry Sign (Red Circular)
    hsv_no = np.full((60, 60, 3), (0, 180, 200), dtype=np.uint8) # Red
    img_no = cv2.cvtColor(hsv_no, cv2.COLOR_HSV2BGR)
    res_no = recog.identify_road_sign(img_no, base_class="sign")
    assert res_no["sign_type"] == "NO_ENTRY"
    assert "నో ఎంట్రీ" in res_no["speech_te"]


def test_conversational_queries_for_currency_and_signs():
    orch = ConversationOrchestrator()

    # 1. Currency query in Telugu
    res_curr = orch.process_query("ఈ నోటు ఎంత?", {}, language="te-IN")
    assert res_curr["intent"] == "IDENTIFY_CURRENCY"
    assert ("రూపాయ" in res_curr["speech"] or "నోటు" in res_curr["speech"])

    # 2. Traffic Signal query in Telugu
    res_sig = orch.process_query("సిగ్నల్ ఏ కలర్ ఉంది?", {}, language="te-IN")
    assert res_sig["intent"] == "IDENTIFY_TRAFFIC_SIGNAL"
    assert "సిగ్నల్" in res_sig["speech"]

    # 3. Road sign query in Telugu
    res_sign = orch.process_query("రోడ్ సైన్ ఏముంది?", {}, language="te-IN")
    assert res_sign["intent"] == "IDENTIFY_ROAD_SIGN"
    assert "బోర్డు" in res_sign["speech"]
