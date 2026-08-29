import time
from typing import Dict, Any, List, Optional
from intelligence.situational_agent import SituationalVoiceAgent
from intelligence.tools import ActionToolDispatcher

class ConversationOrchestrator:
    """
    MARK 2.0 Vision-Grounded Humanized Personal Voice Assistant.
    
    'JARVIS talks because it knows things. MARK talks because it sees things.'
    Humanized conversational companion that:
    - Observes continuously, but speaks selectively (event-driven).
    - Remembers what it saw and maintains world-state continuity.
    - Answers on-demand queries ("ఇంకా ఉన్నారా?", "అతను వెళ్లిపోయాడా?", "నేను వెళ్లవచ్చా?")
    - Handles push-to-talk microphone inputs seamlessly.
    - Executes actions immediately (AI mode on/off, family call, emergency).
    """
    def __init__(self, guidance_engine=None, tools: Optional[ActionToolDispatcher] = None):
        self.guidance_engine = guidance_engine
        self.situational_agent = SituationalVoiceAgent()
        self.tools = tools or ActionToolDispatcher()
        self.last_instruction_spoken = None
        self.last_instruction_time = 0.0
        self.interaction_count = 0
        self.preferred_language = "te-IN"
        self.is_ai_mode_active = True
        self.last_discussed_entity = None

    def process_query(
        self,
        query: str,
        world_state: Dict[str, Any],
        language: str = "te-IN"
    ) -> Dict[str, Any]:
        """
        Interprets user intent against CURRENT LIVE WORLD STATE, invokes backend tools,
        and returns respectful, concise spoken Telugu responses.
        """
        q = (query or "").strip().lower()
        self.preferred_language = language
        self.interaction_count += 1

        if not q or q in ("...", ""):
            speech = "సర్, మీ మాట నాకు వినిపించలేదు. మరోసారి చెప్పండి." if language.startswith("te") else "Sir, I couldn't hear your voice clearly. Please say again."
            return {
                "intent": "UNCLEAR_SPEECH",
                "speech": speech,
                "action": "NONE",
                "priority": "normal"
            }

        active_tracks = world_state.get("active_tracks", [])
        highest_threat = world_state.get("highest_threat", "SILENT")
        ocr_text = world_state.get("last_ocr_text", "")
        currency_text = world_state.get("last_currency_text", "")
        is_uncertain = world_state.get("is_uncertain", False)
        camera_healthy = world_state.get("camera_healthy", True)
        frame_bgr = world_state.get("frame_bgr", None)

        intent = self._classify_intent(q)

        # ── 1. EMERGENCY INTENT (Immediate override) ──
        if intent == "EMERGENCY":
            res = self.tools.emergency_call(source="VOICE_COMMAND")
            speech = res["spoken_feedback_te"] if language.startswith("te") else res["spoken_feedback_en"]
            return {
                "intent": "EMERGENCY",
                "speech": speech,
                "action": "EMERGENCY_CALL",
                "target": res.get("target"),
                "priority": "critical"
            }

        # ── 2. FAMILY CALL REQUEST ──
        elif intent == "FAMILY_CALL_REQUEST":
            res = self.tools.call_family(reason="User Voice Command")
            speech = res["spoken_feedback_te"] if language.startswith("te") else res["spoken_feedback_en"]
            return {
                "intent": "FAMILY_CALL_REQUEST",
                "speech": speech,
                "action": "CALL_FAMILY",
                "target": res.get("target"),
                "priority": "high"
            }

        # ── 3. AI MODE ENABLE ──
        elif intent == "ENABLE_AI_MODE":
            self.is_ai_mode_active = True
            res = self.tools.set_ai_mode(True)
            speech = res["spoken_feedback_te"] if language.startswith("te") else res["spoken_feedback_en"]
            return {
                "intent": "ENABLE_AI_MODE",
                "speech": speech,
                "action": "ENABLE_AI_MODE",
                "priority": "normal"
            }

        # ── 4. AI MODE DISABLE ──
        elif intent == "DISABLE_AI_MODE":
            self.is_ai_mode_active = False
            res = self.tools.set_ai_mode(False)
            speech = res["spoken_feedback_te"] if language.startswith("te") else res["spoken_feedback_en"]
            return {
                "intent": "DISABLE_AI_MODE",
                "speech": speech,
                "action": "DISABLE_AI_MODE",
                "priority": "normal"
            }

        # ── 5. STILL PRESENT QUERY ("ఇంకా ఉన్నారా?", "అతను ఇంకా అక్కడే ఉన్నాడా?") ──
        elif intent == "STILL_PRESENT":
            return self._handle_still_present(active_tracks, is_uncertain, language)

        # ── 6. HAS LEFT QUERY ("అతను వెళ్లిపోయాడా?", "వాళ్లు వెళ్లిపోయారా?") ──
        elif intent == "HAS_LEFT":
            return self._handle_has_left(active_tracks, is_uncertain, language)

        # ── 7. IS SAFE / CAN I WALK ("నేను వెళ్లవచ్చా?", "ఇప్పుడు నేను వెళ్లవచ్చా?") ──
        elif intent == "IS_SAFE":
            return self._handle_is_safe(active_tracks, highest_threat, is_uncertain, camera_healthy, language)

        # ── 8. WHAT AHEAD ("నా ముందు ఏముంది?", "ఎవరైనా ఉన్నారా?") ──
        elif intent == "WHAT_AHEAD":
            return self._handle_what_ahead(active_tracks, is_uncertain, language)

        # ── 9. IS MOVING ("అతను కదులుతున్నాడా?") ──
        elif intent == "IS_MOVING":
            return self._handle_is_moving(active_tracks, language)

        # ── 10. TALK TO ME ("మార్క్, నాతో మాట్లాడవా?") ──
        elif intent == "TALK_TO_ME":
            return self._handle_talk_to_me(language)

        # ── 11. VOICE MUTE / STOP ──
        elif intent == "VOICE_SILENT_MODE":
            res = self.tools.set_voice_mode(True)
            speech = res["spoken_feedback_te"] if language.startswith("te") else res["spoken_feedback_en"]
            return {
                "intent": "VOICE_SILENT_MODE",
                "speech": speech,
                "action": "VOICE_SILENT_MODE",
                "priority": "normal"
            }

        # ── 12. VOICE RESUME ──
        elif intent == "RESUME_VOICE":
            res = self.tools.set_voice_mode(False)
            speech = res["spoken_feedback_te"] if language.startswith("te") else res["spoken_feedback_en"]
            return {
                "intent": "RESUME_VOICE",
                "speech": speech,
                "action": "RESUME_VOICE",
                "priority": "normal"
            }

        # ── 13. SYSTEM STATUS QUERY ──
        elif intent == "GET_AI_STATUS":
            res = self.tools.get_ai_status(self.is_ai_mode_active)
            speech = res["spoken_feedback_te"] if language.startswith("te") else res["spoken_feedback_en"]
            return {
                "intent": "GET_AI_STATUS",
                "speech": speech,
                "action": "GET_AI_STATUS",
                "priority": "normal"
            }

        # ── 14. GUARDIAN MANUAL EXPLANATION ──
        elif intent == "GUARDIAN_MODE_EXPLANATION":
            res = self.tools.explain_guardian_manual_activation()
            speech = res["spoken_feedback_te"] if language.startswith("te") else res["spoken_feedback_en"]
            return {
                "intent": "GUARDIAN_MODE_EXPLANATION",
                "speech": speech,
                "action": "EXPLAIN_GUARDIAN_MANUAL",
                "priority": "normal"
            }

        # ── 15. WHERE_TO_GO ("నేను ఎటు వెళ్లాలి?") ──
        elif intent == "WHERE_TO_GO":
            return self._handle_where_to_go(active_tracks, language)

        # ── 16. DESCRIBE_SCENE ("నా చుట్టూ ఏముంది?") ──
        elif intent == "DESCRIBE_SCENE":
            return self._handle_describe_scene(active_tracks, language)

        # ── 17. READ_TEXT ("ఇది ఏం రాసుంది?") ──
        elif intent == "READ_TEXT":
            return self._handle_read_text(ocr_text, frame_bgr, language)

        # ── 18. IDENTIFY_CURRENCY ("ఇది ఎంత నోటు?", "కరెన్సీ ఎంత?") ──
        elif intent == "IDENTIFY_CURRENCY":
            return self._handle_currency(currency_text, frame_bgr, language)

        # ── 19. IDENTIFY_TRAFFIC_SIGNAL ("సిగ్నల్ ఏ కలర్ ఉంది?", "ట్రాఫిక్ లైట్ చూడు") ──
        elif intent == "IDENTIFY_TRAFFIC_SIGNAL":
            return self._handle_traffic_signal(active_tracks, frame_bgr, language)

        # ── 20. IDENTIFY_ROAD_SIGN ("రోడ్ సైన్ ఏముంది?", "బోర్డు చూడు") ──
        elif intent == "IDENTIFY_ROAD_SIGN":
            return self._handle_road_sign(active_tracks, frame_bgr, language)

        # ── 21. REPEAT ("మళ్ళీ చెప్పు") ──
        elif intent == "REPEAT":
            fallback = "సర్, ఇంకా ఏమీ చెప్పలేదు." if language.startswith("te") else "Sir, no previous instruction."
            speech = self.last_instruction_spoken or fallback
            return {
                "intent": "REPEAT",
                "speech": speech,
                "priority": "normal"
            }

        # Default fallback: Ground in immediate forward view
        return self._handle_what_ahead(active_tracks, is_uncertain, language)

    def _classify_intent(self, q: str) -> str:
        # Emergency & Help check (immediate override)
        if any(w in q for w in (
            "help", "sos", "emergency", "హెల్ప్", "ఆపద", "సహాయం", "ప్రమాదం", "ఎమర్జెన్సీ",
            "కాపాడండి", "ఎవరైనా రండి", "need help", "i need help", "call help", "call police",
            "call someone", "call 108", "call 100", "save me", "danger", "సహాయం చేయి", "సాయం చేయి"
        )):
            return "EMERGENCY"

        # Family call check
        if any(w in q for w in ("ఫ్యామిలీ", "family", "మా వాళ్ల", "ఇంటికి", "అమ్మకి", "నాన్నకి", "నా వాళ్ల", "మా వాళ్లతో", "call family", "call my family", "family call", "call home")):
            if any(c in q for c in ("కాల్", "ఫోన్", "మాట్లాడాలి", "మాట్లాడించు", "చేయి", "చెయ్యి", "call", "phone", "dial")):
                return "FAMILY_CALL_REQUEST"

        # Guardian mode check (Manual explanation)
        if "guardian" in q or "గార్డియన్" in q:
            return "GUARDIAN_MODE_EXPLANATION"

        # AI Mode on/off check
        if any(w in q for w in ("ai mode on", "ai assistance on", "monitoring start", "మార్క్ ఆన్", "mark on", "గమనించు", "observe cheyyi", "start cheyyi")):
            return "ENABLE_AI_MODE"
        if any(w in q for w in ("ai mode off", "monitoring aapu", "monitoring stop", "mark stop", "మార్క్ ఆపు", "stop cheyyi", "ఆఫ్ చేయి")):
            return "DISABLE_AI_MODE"

        # Voice mute/resume
        if any(w in q for w in ("silent ga undu", "voice aapu", "మాట్లాడొద్దు", "stop alerts", "silent")):
            return "VOICE_SILENT_MODE"
        if any(w in q for w in ("మళ్లీ మాట్లాడు", "voice on", "alerts on", "resume", "యాక్టివ్")):
            return "RESUME_VOICE"

        # Has Left check ("అతను వెళ్లిపోయాడా?", "వాళ్లు వెళ్లిపోయారా?")
        if any(w in q for w in ("వెళ్లిపోయాడా", "వెళ్లిపోయారా", "gone", "has he left", "did they leave", "వెళ్లిపోయారా")):
            return "HAS_LEFT"

        # Still Present check ("ఇంకా ఉన్నారా?", "అతను ఇంకా అక్కడే ఉన్నాడా?", "person ఇంకా ఉందా?")
        if any(w in q for w in ("ఇంకా ఉన్నారా", "ఇంకా ఉన్నాడా", "ఇంకా ఉందా", "still there", "is he still there", "are they still there", "అక్కడే ఉన్నాడా")):
            return "STILL_PRESENT"

        # Status check
        if any(w in q for w in ("on lo undha", "ai mode on aa", "status enti", "active aa", "చేస్తున్నావ్", "chestunnav")):
            return "GET_AI_STATUS"

        # Movement follow-up
        if any(w in q for w in ("కదులుతున్నాడా", "కదులుతుందా", "moving", "is he moving", "వస్తున్నారా", "ఎటు వెళ్తున్నాడు")):
            return "IS_MOVING"

        # Companion talk
        if any(w in q for w in ("నాతో మాట్లాడు", "నాతో మాట్లాడవా", "talk to me", "నాతో ఉండు", "నాతో ఉన్నావా", "మార్క్ చెప్పు", "మార్క్?")):
            return "TALK_TO_ME"

        # Safe to walk check
        if any(w in q for w in ("safe", "సేఫ్", "నడవవచ్చా", "సురక్షిత", "వెళ్లవచ్చా", "బాగుందా", "దారి క్లియర్", "దారి ఖాళీ")):
            return "IS_SAFE"

        if any(w in q for w in ("ఎటు", "దారి", "ఎక్కడికి", "where", "direction", "which way", "route")):
            return "WHERE_TO_GO"
        if any(w in q for w in ("చుట్టూ", "describe", "scene", "పరిసరాలు", "మొత్తం")):
            return "DESCRIBE_SCENE"
        if any(w in q for w in ("సిగ్నల్", "లైట్", "ట్రాఫిక్", "traffic light", "traffic signal", "signal", "red light", "green light", "yellow light")):
            return "IDENTIFY_TRAFFIC_SIGNAL"
        if any(w in q for w in ("రోడ్ సైన్", "సైన్ బోర్డు", "స్టాప్", "బోర్డు", "sign board", "road sign", "stop sign", "crossing", "zebra")):
            return "IDENTIFY_ROAD_SIGN"
        if any(w in q for w in ("చదువు", "రాసి", "read", "text")):
            return "READ_TEXT"
        if any(w in q for w in ("నోటు", "డబ్బు", "కరెన్సీ", "రూపాయ", "currency", "money", "note", "rupee", "cash")):
            return "IDENTIFY_CURRENCY"
        if any(w in q for w in ("మళ్ళీ", "repeat", "again", "చెప్పు")):
            return "REPEAT"

        return "WHAT_AHEAD"

    def _handle_still_present(self, tracks: List[Any], is_uncertain: bool, language: str) -> Dict[str, Any]:
        """
        Answers 'ఇంకా ఉన్నారా?' by checking LIVE active tracks.
        """
        if is_uncertain:
            speech = "సర్, ముందు పరిస్థితి స్పష్టంగా లేదు... ఒకసారి ఆగండి." if language.startswith("te") else "Sir, situation is unclear. Please wait."
            return {"intent": "STILL_PRESENT", "speech": speech, "priority": "high"}

        has_person = False
        has_obstacle = False
        for t in tracks:
            d = t.to_dict() if hasattr(t, "to_dict") else t
            cls = (d.get("raw_class_name") or d.get("detector_class") or "").lower()
            dist = float(d.get("distance_m") or d.get("distance") or 3.0)
            if dist <= 4.0:
                if "person" in cls:
                    has_person = True
                else:
                    has_obstacle = True

        if has_person:
            speech = "అవును సర్, ఇంకా మీ ముందే ఉన్నారు." if language.startswith("te") else "Yes sir, they are still right in front of you."
        elif has_obstacle:
            speech = "అవును సర్, మీ ముందు ఇంకా అడ్డంకి ఉంది." if language.startswith("te") else "Yes sir, there is still an obstacle ahead."
        else:
            speech = "లేదు సర్, ఇప్పుడు మీ ముందు ఎవరూ లేరు." if language.startswith("te") else "No sir, nobody is ahead now."

        self.last_instruction_spoken = speech
        return {"intent": "STILL_PRESENT", "speech": speech, "priority": "normal"}

    def _handle_has_left(self, tracks: List[Any], is_uncertain: bool, language: str) -> Dict[str, Any]:
        """
        Answers 'అతను వెళ్లిపోయాడా?' by checking LIVE active tracks.
        """
        if is_uncertain:
            speech = "సర్, ముందు పరిస్థితి స్పష్టంగా లేదు... ఒకసారి ఆగండి." if language.startswith("te") else "Sir, situation is unclear. Please wait."
            return {"intent": "HAS_LEFT", "speech": speech, "priority": "high"}

        has_person = any(
            ("person" in (t.to_dict() if hasattr(t, "to_dict") else t).get("raw_class_name", "").lower())
            for t in tracks
        )

        if not has_person:
            speech = "అవును సర్, ఇప్పుడు ఆయన అక్కడ లేరు. ముందు దారి క్లియర్గా ఉంది, మీరు ముందుకు వెళ్లవచ్చు." if language.startswith("te") else "Yes sir, they have left. Path ahead is clear, you can walk."
        else:
            speech = "లేదు సర్, ఇంకా మీ ముందే ఉన్నారు... ఒకసారి ఆగండి." if language.startswith("te") else "No sir, they are still ahead. Please stop."

        self.last_instruction_spoken = speech
        return {"intent": "HAS_LEFT", "speech": speech, "priority": "normal"}

    def _handle_what_ahead(self, tracks: List[Any], is_uncertain: bool, language: str) -> Dict[str, Any]:
        if is_uncertain:
            speech = "సర్, ముందు పరిస్థితి స్పష్టంగా లేదు... ఒకసారి ఆగండి." if language.startswith("te") else "Sir, the path ahead is unclear. Please wait."
            return {"intent": "WHAT_AHEAD", "speech": speech, "priority": "high"}

        front_obstacles = []
        for t in tracks:
            d = t.to_dict() if hasattr(t, "to_dict") else t
            dist = float(d.get("distance_m") or d.get("distance") or 3.0)
            if dist <= 4.5:
                front_obstacles.append((dist, d))

        if not front_obstacles:
            speech = "సర్, ప్రస్తుతం మీ ముందు ఎవరూ లేరు. దారి క్లియర్గా ఉంది." if language.startswith("te") else "Sir, nobody is ahead. Path is clear."
            self.last_instruction_spoken = speech
            self.last_discussed_entity = None
            return {"intent": "WHAT_AHEAD", "speech": speech, "priority": "normal"}

        front_obstacles.sort(key=lambda x: x[0])
        nearest_dist, nearest_obs = front_obstacles[0]
        self.last_discussed_entity = nearest_obs
        raw_class = (nearest_obs.get("raw_class_name") or nearest_obs.get("detector_class") or "obstacle").lower()

        if language.startswith("te"):
            if "car" in raw_class or "vehicle" in raw_class:
                speech = "సర్, మీ ముందు వాహనం ఉంది."
            elif "person" in raw_class:
                speech = "సర్, మీ ముందు ఒక వ్యక్తి ఉన్నారు."
            elif "chair" in raw_class:
                speech = "సర్, మీ ముందు కుర్చీ ఉంది."
            else:
                speech = "సర్, మీ ముందు అడ్డంకి ఉంది... ఆగండి."
        else:
            speech = f"Sir, there is a {raw_class} ahead."

        self.last_instruction_spoken = speech
        return {"intent": "WHAT_AHEAD", "speech": speech, "priority": "medium"}

    def _handle_is_moving(self, tracks: List[Any], language: str) -> Dict[str, Any]:
        target = self.last_discussed_entity
        if not target and tracks:
            d = tracks[0].to_dict() if hasattr(tracks[0], "to_dict") else tracks[0]
            target = d

        if not target:
            speech = "సర్, ప్రస్తుతం మీ ముందు ఎవరూ లేరు." if language.startswith("te") else "Sir, no one is currently ahead."
            return {"intent": "IS_MOVING", "speech": speech, "priority": "normal"}

        motion = str(target.get("motion_state") or (target.get("motion") or {}).get("state") or "STATIONARY").upper()

        if language.startswith("te"):
            if motion == "APPROACHING":
                speech = "అవును సర్, ఆ వ్యక్తి మీ వైపు కదులుతున్నారు."
            elif motion == "MOVING_AWAY":
                speech = "సర్, ఆ వ్యక్తి మీ నుండి దూరంగా వెళ్తున్నారు."
            else:
                speech = "లేదు సర్, ఆ వ్యక్తి అక్కడే నిలబడి ఉన్నారు."
        else:
            if motion == "APPROACHING":
                speech = "Yes sir, they are moving toward you."
            elif motion == "MOVING_AWAY":
                speech = "Sir, they are moving away."
            else:
                speech = "No sir, they are stationary."

        self.last_instruction_spoken = speech
        return {"intent": "IS_MOVING", "speech": speech, "priority": "normal"}

    def _handle_talk_to_me(self, language: str) -> Dict[str, Any]:
        speech = "నమస్కారం సర్, నేను మీతోనే ఉన్నాను. మీకు సహాయం చేయడానికి సిద్ధంగా ఉన్నాను." if language.startswith("te") else "Hello sir, I am right here with you, ready to guide you."
        self.last_instruction_spoken = speech
        return {"intent": "TALK_TO_ME", "speech": speech, "priority": "normal"}

    def _handle_is_safe(self, tracks: List[Any], threat: str, is_uncertain: bool, camera_healthy: bool, language: str) -> Dict[str, Any]:
        if not camera_healthy:
            speech = "సర్, కెమెరా నుంచి సమాచారం సరిగ్గా రావడం లేదు. ఒకసారి ఆగండి." if language.startswith("te") else "Sir, camera feed is degraded. Please stop."
            return {"intent": "IS_SAFE", "speech": speech, "priority": "high"}

        if is_uncertain:
            speech = "సర్, ముందు పరిస్థితి స్పష్టంగా లేదు... ఒకసారి ఆగండి." if language.startswith("te") else "Sir, situation ahead is unclear. Please wait."
            return {"intent": "IS_SAFE", "speech": speech, "priority": "high"}

        danger_tracks = []
        for t in tracks:
            d = t.to_dict() if hasattr(t, "to_dict") else t
            dist = float(d.get("distance_m") or d.get("distance") or 3.0)
            if dist <= 2.2:
                danger_tracks.append(d)

        if not danger_tracks and threat in ("GREEN", "SILENT"):
            speech = "సర్, ప్రస్తుతం మీ ముందు దారి క్లియర్గా ఉంది. మీరు ముందుకు వెళ్లవచ్చు." if language.startswith("te") else "Sir, path ahead is currently clear. You can move forward."
            self.last_instruction_spoken = speech
            return {"intent": "IS_SAFE", "speech": speech, "priority": "normal"}
        else:
            speech = "సర్, ఇంకా అడ్డంకి ఉంది. ఒకసారి ఆగండి." if language.startswith("te") else "Sir, obstacle ahead. Please stop."
            self.last_instruction_spoken = speech
            return {"intent": "IS_SAFE", "speech": speech, "priority": "high"}

    def _handle_where_to_go(self, tracks: List[Any], language: str) -> Dict[str, Any]:
        speech = "సర్, మీ ముందు దారి క్లియర్గా ఉంది, నెమ్మదిగా ముందుకు వెళ్లండి." if language.startswith("te") else "Sir, path ahead is clear, safe to walk."
        self.last_instruction_spoken = speech
        return {"intent": "WHERE_TO_GO", "speech": speech, "priority": "normal"}

    def _handle_describe_scene(self, tracks: List[Any], language: str) -> Dict[str, Any]:
        if not tracks:
            speech = "సర్, పరిసరాలు ప్రశాంతంగా ఉన్నాయి. దారి క్లియర్గా ఉంది." if language.startswith("te") else "Sir, surroundings are clear."
            return {"intent": "DESCRIBE_SCENE", "speech": speech, "priority": "normal"}

        count = len(tracks)
        speech = f"సర్, మీ చుట్టూ {count} వస్తువులు ఉన్నాయి." if language.startswith("te") else f"Sir, there are {count} objects around you."
        return {"intent": "DESCRIBE_SCENE", "speech": speech, "priority": "normal"}

    def _handle_read_text(self, ocr_text: str, frame_bgr: Optional[Any] = None, language: str = "te-IN") -> Dict[str, Any]:
        res = self.tools.read_text(frame_bgr=frame_bgr, cached_ocr=ocr_text)
        speech = res["spoken_feedback_te"] if language.startswith("te") else res["spoken_feedback_en"]
        self.last_instruction_spoken = speech
        return {"intent": "READ_TEXT", "speech": speech, "priority": "normal"}

    def _handle_currency(self, currency_text: str, frame_bgr: Optional[Any] = None, language: str = "te-IN") -> Dict[str, Any]:
        res = self.tools.identify_currency(frame_bgr=frame_bgr, cached_curr=currency_text)
        speech = res["spoken_feedback_te"] if language.startswith("te") else res["spoken_feedback_en"]
        self.last_instruction_spoken = speech
        return {"intent": "IDENTIFY_CURRENCY", "speech": speech, "priority": "normal", "denomination": res.get("denomination", "₹500")}

    def _handle_traffic_signal(self, tracks: List[Any], frame_bgr: Optional[Any] = None, language: str = "te-IN") -> Dict[str, Any]:
        res = self.tools.identify_traffic_signal(frame_bgr=frame_bgr, active_tracks=tracks)
        speech = res["spoken_feedback_te"] if language.startswith("te") else res["spoken_feedback_en"]
        self.last_instruction_spoken = speech
        return {"intent": "IDENTIFY_TRAFFIC_SIGNAL", "speech": speech, "priority": "high", "active_color": res.get("active_color", "RED")}

    def _handle_road_sign(self, tracks: List[Any], frame_bgr: Optional[Any] = None, language: str = "te-IN") -> Dict[str, Any]:
        res = self.tools.identify_road_sign(frame_bgr=frame_bgr, active_tracks=tracks)
        speech = res["spoken_feedback_te"] if language.startswith("te") else res["spoken_feedback_en"]
        self.last_instruction_spoken = speech
        return {"intent": "IDENTIFY_ROAD_SIGN", "speech": speech, "priority": "normal", "sign_type": res.get("sign_type", "STOP_SIGN")}
