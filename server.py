import os
import json
import base64
import time
import psutil
import cv2
import numpy as np
from typing import Dict, Any, Optional
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

import config
from vision.detector import ObjectDetector
from vision.tracker import ObjectTracker
from intelligence.risk_engine import RiskEngine
from intelligence.priority_engine import PriorityEngine
from intelligence.obstacle_priority_engine import ObstaclePriorityEngine
from intelligence.telugu_instruction_engine import TeluguInstructionEngine
from intelligence.guidance_engine import GuidanceEngine
from intelligence.conversation_orchestrator import ConversationOrchestrator
from intelligence.adaptive_memory import AdaptiveMemory
from intelligence.experience_engine import ExperienceEngine
from intelligence.ai_teacher import AITeacher
from intelligence.situational_agent import SituationalVoiceAgent
from voice.voice_controller import VoiceController
from voice.commands import VoiceCommandParser
from voice.tts_service import TTSService
from perception.ocr import OCREngine
from perception.currency import CurrencyRecognizer
from perception.traffic_and_signs import TrafficAndSignRecognizer
from emergency.emergency import EmergencyManager
from supabase_logger import SupabaseLogger
from intelligence.attention_manager import AttentionManager
from emergency_caller import make_emergency_call

app = FastAPI(
    title="MARK 2.0 AI Perception & Tracking Engine",
    description="Real-Time Object Detection, Tracking & Risk Engine for Visually Impaired Users",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Initialize Core Modules (Single Load at Startup) ──
detector = ObjectDetector(model_name=config.MODEL_NAME, conf_thresh=config.CONFIDENCE_THRESHOLD)
tracker = ObjectTracker(max_disappeared=config.MAX_DISAPPEARED_FRAMES, iou_threshold=config.IOU_THRESHOLD)
risk_engine = RiskEngine()
priority_engine = PriorityEngine()
obstacle_priority_engine = ObstaclePriorityEngine()
guidance_engine = GuidanceEngine(guidance_cycle_sec=3.0)
telugu_engine = TeluguInstructionEngine()
orchestrator = ConversationOrchestrator(guidance_engine=guidance_engine)
adaptive_memory = AdaptiveMemory()
experience_engine = ExperienceEngine(memory=adaptive_memory)
ai_teacher = AITeacher(memory=adaptive_memory)
situational_agent = SituationalVoiceAgent(reassess_cooldown_sec=3.0)
attention_manager = AttentionManager(min_confirm_frames=3, departure_confirm_frames=6, normal_cooldown_sec=4.0)
voice_controller = VoiceController()
command_parser = VoiceCommandParser()
tts_service = TTSService()
ocr_engine = OCREngine()
currency_recognizer = CurrencyRecognizer()
traffic_sign_recognizer = TrafficAndSignRecognizer()
emergency_manager = EmergencyManager()
logger = SupabaseLogger()

safety_event_log = deque(maxlen=50)

# ── System Runtime State & Telemetry ──
system_state = {
    "is_active": True,
    "ai_mode": True,
    "last_frame_bgr": None,
    "last_tracks": [],
    "last_detections": [],
    "highest_threat": "SILENT",
    "last_mark_message": "Mark online. Walk safe.",
    "fps": 0.0,
    "latency_ms": 0.0,
    "latency_breakdown": {
        "detection_ms": 0.0,
        "priority_ms": 0.0,
        "instruction_ms": 0.0,
        "tts_ms": 0.0,
        "total_ms": 0.0
    },
    "start_time": time.time()
}

# ── REST API Endpoints ──

@app.post("/api/set_ai_mode")
async def set_ai_mode(payload: Dict[str, Any] = Body(...)):
    enabled = payload.get("enabled", True)
    system_state["ai_mode"] = bool(enabled)
    return {
        "status": "SUCCESS",
        "ai_mode": system_state["ai_mode"]
    }

@app.get("/api/status")
async def get_status():
    mem = psutil.virtual_memory()
    return {
        "status": "ONLINE",
        "system_name": "MARK 2.0",
        "device": config.DEVICE.upper(),
        "detector_model": detector.model_name,
        "detector_loaded": detector.is_loaded,
        "system_active": system_state["is_active"],
        "active_tracks_count": len(system_state["last_tracks"]),
        "highest_threat": system_state["highest_threat"],
        "last_mark_message": system_state["last_mark_message"],
        "emergency": emergency_manager.get_status(),
        "telemetry": {
            "fps": round(system_state["fps"], 1),
            "latency_ms": round(system_state["latency_ms"], 1),
            "cpu_percent": psutil.cpu_percent(),
            "ram_used_gb": round(mem.used / (1024**3), 2),
            "ram_total_gb": round(mem.total / (1024**3), 2)
        }
    }

@app.get("/api/detections")
async def get_detections():
    return {
        "tracks_count": len(system_state["last_tracks"]),
        "tracks": [t.to_dict() for t in system_state["last_tracks"]],
        "highest_threat": system_state["highest_threat"]
    }

@app.get("/api/alerts")
async def get_alerts():
    return {
        "last_message": system_state["last_mark_message"],
        "recent_alerts": logger.recent_alerts,
        "emergency": emergency_manager.get_status()
    }

@app.get("/api/history")
async def get_history():
    return {
        "sessions": logger.get_history()
    }

@app.post("/api/session/start")
async def start_session():
    session_id = logger.start_session()
    system_state["last_mark_message"] = "Mark online. Walk safe."
    return {
        "status": "SESSION_STARTED",
        "session_id": session_id,
        "greeting": "Mark online. Walk safe."
    }

@app.post("/api/session/stop")
async def stop_session():
    summary = logger.end_session()
    return {
        "status": "SESSION_STOPPED",
        "summary": summary
    }

@app.post("/api/read-text")
@app.post("/api/ocr")
async def handle_ocr():
    frame = system_state.get("last_frame_bgr")
    res = ocr_engine.read_text_from_frame(frame)
    system_state["last_mark_message"] = res["mark_message"]
    logger.log_alert(res["mark_message"], "INFO")
    return res

@app.post("/api/currency")
async def handle_currency():
    frame = system_state.get("last_frame_bgr")
    res = currency_recognizer.identify_note(frame)
    system_state["last_mark_message"] = res["mark_message"]
    logger.log_alert(res["mark_message"], "INFO")
    return res

@app.post("/api/identify")
async def handle_identify():
    frame = system_state.get("last_frame_bgr")
    if frame is None or frame.size == 0:
        return {
            "success": False,
            "spoken_text": "No frame captured to analyze.",
            "identified": False
        }
    
    h, w = frame.shape[:2]
    # Look for the most central active track, or use center crop
    bbox = [int(w * 0.25), int(h * 0.20), int(w * 0.75), int(h * 0.80)]
    if system_state["last_tracks"]:
        center_track = min(system_state["last_tracks"], key=lambda t: abs(t.center[0] - w/2.0))
        bbox = center_track.bbox

    from vision.hybrid_recognizer import HybridRecognizer
    recog = HybridRecognizer()
    res = recog.recognize_held_object(frame, bbox)
    system_state["last_mark_message"] = res["spoken_text"]
    logger.log_alert(res["spoken_text"], "INFO")
    return res

@app.post("/api/emergency")
@app.post("/api/emergency/trigger")
async def handle_emergency(payload: Dict[str, Any] = Body(default={})):
    action = payload.get("action", "TRIGGER")
    if action == "RESOLVE":
        res = emergency_manager.resolve()
    else:
        res = emergency_manager.trigger(source=payload.get("source", "BUTTON"))
        system_state["last_mark_message"] = "Emergency alert activated."
        logger.log_alert("Emergency alert activated.", "URGENT")
        try:
            import threading
            call_thread = threading.Thread(
                target=make_emergency_call,
                daemon=True
            )
            call_thread.start()
            print("[MARK 2.0] EMERGENCY CALL INITIATED TO +916303318876")
        except Exception as e:
            print(f"[MARK 2.0] Emergency call failed: {e}")
    return res

@app.post("/api/emergency/resolve")
async def handle_emergency_resolve():
    res = emergency_manager.resolve()
    return res

@app.post("/api/mark/voice-instruction")
async def handle_mark_voice_instruction(payload: Dict[str, Any] = Body(...)):
    event = payload.get("event", {})
    lang = payload.get("language", "te-IN")
    
    if lang.startswith("te"):
        res = telugu_engine.generate_instruction(event)
    else:
        eval_res = obstacle_priority_engine.evaluate_single_obstacle(event, time.time())
        res = {
            "shouldSpeak": (eval_res["priority"] != "IGNORE"),
            "instruction": eval_res["instruction"],
            "priority": eval_res["priority"].lower()
        }
    return res

@app.post("/api/tts")
async def handle_tts(payload: Dict[str, Any] = Body(...)):
    text = payload.get("text", "")
    priority = payload.get("priority", "normal")
    language = payload.get("language", "en")
    
    audio_bytes, mime_type, latency_ms = tts_service.synthesize_speech(text, priority=priority, language=language)
    if audio_bytes is not None:
        return Response(
            content=audio_bytes,
            media_type=mime_type,
            headers={
                "X-TTS-Latency-Ms": str(latency_ms),
                "X-TTS-Provider": "sarvam_bulbul_v3" if language.startswith("te") else tts_service.provider
            }
        )
    return {
        "status": "FALLBACK_CLIENT_SPEECH",
        "text": text,
        "priority": priority,
        "language": language,
        "tts_latency_ms": latency_ms,
        "provider": "client/telugu_speech" if language.startswith("te") else "client/natural_speech"
    }

@app.get("/api/safety-log")
async def get_safety_log():
    return {
        "events": list(safety_event_log)
    }

@app.post("/api/experience/record")
async def record_experience(payload: Dict[str, Any] = Body(...)):
    situation = payload.get("situation", "General navigation")
    observation = payload.get("observation", "Object detected in corridor")
    confidence = float(payload.get("confidence", 0.9))
    decision = payload.get("decision", "Warned user")
    action = payload.get("action", "move_right")
    outcome = payload.get("outcome", "SUCCESS")
    feedback = payload.get("feedback")
    
    case = experience_engine.record_interaction(
        situation=situation,
        observation=observation,
        confidence=confidence,
        decision=decision,
        action=action,
        outcome=outcome,
        user_feedback=feedback
    )
    return {
        "status": "RECORDED",
        "case": case
    }

@app.get("/api/experience/cases")
async def get_experience_cases():
    return {
        "summary": adaptive_memory.get_summary(),
        "verified_cases": adaptive_memory.verified_cases,
        "candidate_lessons": experience_engine.get_candidate_lessons(),
        "failures": adaptive_memory.failure_memory
    }

@app.post("/api/experience/evaluate")
async def evaluate_experience():
    candidates = experience_engine.get_candidate_lessons()
    res = ai_teacher.run_nightly_eval(candidates)
    return {
        "status": "EVALUATION_COMPLETE",
        "result": res,
        "total_verified": len(adaptive_memory.verified_cases)
    }

@app.post("/api/command")
@app.post("/api/conversation")
async def handle_conversation(payload: Dict[str, Any] = Body(...)):
    command_text = payload.get("command") or payload.get("query") or ""
    lang = payload.get("language", "te-IN")
    
    last_frame_time = system_state.get("last_frame_time", 0.0)
    now = time.time()
    camera_healthy = (system_state.get("last_frame_bgr") is not None) and (now - last_frame_time < 4.0)
    
    world_state = {
        "active_tracks": system_state.get("last_tracks", []) if camera_healthy else [],
        "highest_threat": system_state.get("highest_threat", "SILENT"),
        "is_uncertain": not camera_healthy,
        "camera_healthy": camera_healthy,
        "frame_bgr": system_state.get("last_frame_bgr")
    }
    
    res = orchestrator.process_query(command_text, world_state, language=lang)
    
    if res.get("intent") == "HELP":
        emergency_manager.trigger(source="VOICE")
    
    system_state["last_mark_message"] = res["speech"]
    logger.log_alert(res["speech"], res.get("priority", "NORMAL").upper())
    return res

# ── Multi-Client Connection Manager for Guardian & Caretaker Live Monitoring ──
connected_websockets: set = set()

async def broadcast_detection_update(payload: dict, exclude_ws: WebSocket = None):
    payload_text = json.dumps(payload)
    dead_sockets = set()
    for ws in list(connected_websockets):
        if ws is exclude_ws:
            continue
        try:
            await ws.send_text(payload_text)
        except Exception:
            dead_sockets.add(ws)
    connected_websockets.difference_update(dead_sockets)

# ── High-Speed Perception & Tracking WebSocket ──

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    print(f"[MARK 2.0 Server] High-speed perception WebSocket connected. Active listeners: {len(connected_websockets)}")

    # Send latest state immediately if available
    if system_state.get("last_payload"):
        try:
            await websocket.send_text(json.dumps(system_state["last_payload"]))
        except Exception:
            pass

    fps_tracker = []

    try:
        while True:
            data = await websocket.receive_text()
            if not data:
                continue

            packet = json.loads(data)
            msg_type = packet.get("type", "frame")

            if msg_type == "frame":
                img_b64 = packet.get("image", "")
                if not img_b64:
                    continue

                t0 = time.perf_counter()

                # Decode Base64 JPEG frame to OpenCV BGR array
                img_bytes = base64.b64decode(img_b64)
                np_arr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if frame is not None:
                    system_state["last_frame_bgr"] = frame
                    system_state["last_frame_time"] = time.time()

                    # 1. YOLOv8n Object Detection
                    t_det_start = time.perf_counter()
                    raw_detections = detector.detect(frame)
                    t_det_end = time.perf_counter()
                    system_state["last_detections"] = raw_detections

                    # 2. Persistent Multi-Object Tracking (IoU + Centroid)
                    t_track_start = time.perf_counter()
                    active_tracks = tracker.update(raw_detections, timestamp=t0)
                    t_track_end = time.perf_counter()
                    system_state["last_tracks"] = active_tracks

                    # 3. Multi-Signal Risk Assessment & Specialized Recognition (Traffic Lights / Signs)
                    fh, fw = frame.shape[:2]
                    for track in active_tracks:
                        cname = track.class_name.lower()
                        if ("traffic light" in cname or "signal" in cname) and hasattr(track, "bbox"):
                            bx1, by1, bx2, by2 = max(0, int(track.bbox[0])), max(0, int(track.bbox[1])), min(fw, int(track.bbox[2])), min(fh, int(track.bbox[3]))
                            if (bx2 - bx1) > 6 and (by2 - by1) > 6:
                                tl_res = traffic_sign_recognizer.analyze_traffic_light(frame[by1:by2, bx1:bx2])
                                track.recognized_name = f"Traffic Light ({tl_res.get('active_color', 'Signal')})"
                        elif ("stop" in cname or "sign" in cname) and hasattr(track, "bbox"):
                            bx1, by1, bx2, by2 = max(0, int(track.bbox[0])), max(0, int(track.bbox[1])), min(fw, int(track.bbox[2])), min(fh, int(track.bbox[3]))
                            if (bx2 - bx1) > 6 and (by2 - by1) > 6:
                                sign_res = traffic_sign_recognizer.identify_road_sign(frame[by1:by2, bx1:bx2], base_class=cname)
                                track.recognized_name = sign_res.get("name", "Road Sign")

                        risk_engine.evaluate_track_risk(track)
                        logger.log_detection({
                            "name": getattr(track, "recognized_name", None) or track.class_name,
                            "distance": track.distance_info.get("distance_m"),
                            "direction": track.spatial_sector,
                            "threat": track.risk_level
                        })

                    # Check real AI Mode State (controls autonomous guidance only)
                    ai_mode_active = packet.get("ai_mode", system_state.get("ai_mode", True))
                    system_state["ai_mode"] = ai_mode_active

                    # 4. Attention & Situation Engine (Single Authority for Autonomous Voice)
                    lang_pref = packet.get("language", "te-IN")
                    t_prio_start = time.perf_counter()
                    attention_eval = attention_manager.evaluate_scene(active_tracks, timestamp=t0, language=lang_pref)
                    t_prio_end = time.perf_counter()

                    primary_hazard = priority_engine.select_primary_hazard(active_tracks)
                    highest_threat = primary_hazard.risk_level if primary_hazard else "SILENT"
                    if attention_eval and attention_eval.get("priority") == "CRITICAL":
                        highest_threat = "URGENT"
                    elif attention_eval and attention_eval.get("priority") == "HIGH":
                        highest_threat = "CAUTION"
                    system_state["highest_threat"] = highest_threat

                    # 5. Autonomous Voice Dispatch (Speak ONLY upon meaningful semantic state transitions)
                    t_inst_start = time.perf_counter()
                    if ai_mode_active and attention_eval and attention_eval.get("should_speak"):
                        spoken_phrase = attention_eval["speech"]
                        voice_eval = {
                            "should_speak": True,
                            "spoken_phrase": spoken_phrase,
                            "spoken_message": spoken_phrase,
                            "priority": attention_eval.get("priority", "HIGH"),
                            "interrupt_audio": attention_eval.get("interrupt_audio", False),
                            "reason": attention_eval.get("debug_reason", "ATTENTION_EVENT"),
                            "language": lang_pref
                        }
                        system_state["last_mark_message"] = spoken_phrase
                        logger.log_alert(spoken_phrase, highest_threat)
                    else:
                        voice_eval = {
                            "should_speak": False,
                            "spoken_phrase": "",
                            "spoken_message": "",
                            "priority": "LOW",
                            "interrupt_audio": False,
                            "reason": attention_eval.get("debug_reason", "SILENCE_BY_DESIGN") if ai_mode_active else "AI_MODE_PAUSED"
                        }
                    t_inst_end = time.perf_counter()

                    # Fine-grained Latency Measurements
                    det_ms = round((t_det_end - t_det_start) * 1000.0, 1)
                    track_ms = round((t_track_end - t_track_start) * 1000.0, 1)
                    prio_ms = round((t_prio_end - t_prio_start) * 1000.0, 2)
                    inst_ms = round((t_inst_end - t_inst_start) * 1000.0, 2)
                    total_ms = round((time.perf_counter() - t0) * 1000.0, 1)

                    system_state["latency_ms"] = total_ms
                    system_state["latency_breakdown"] = {
                        "detection_ms": det_ms,
                        "tracking_ms": track_ms,
                        "priority_ms": prio_ms,
                        "instruction_ms": inst_ms,
                        "tts_ms": 0.5,
                        "total_ms": total_ms
                    }

                    # Calculate FPS
                    t_now = time.time()
                    fps_tracker.append(t_now)
                    if len(fps_tracker) > 15:
                        fps_tracker.pop(0)
                    if len(fps_tracker) > 1:
                        system_state["fps"] = round((len(fps_tracker) - 1) / (fps_tracker[-1] - fps_tracker[0]), 1)

                    # Prepare Lightweight Telemetry Payload (No heavy Base64 image back to user)
                    telemetry_payload = {
                        "type": "detection_update",
                        "timestamp": packet.get("timestamp", time.time()),
                        "server_time": time.time(),
                        "camera_status": "ACTIVE",
                        "ai_mode": True,
                        "objects": [t.to_dict() for t in active_tracks],
                        "highest_threat": highest_threat,
                        "total_objects": len(active_tracks),
                        "primary_hazard": primary_hazard.to_dict() if primary_hazard else None,
                        "mark_message": system_state["last_mark_message"],
                        "voice_output": voice_eval,
                        "emergency": emergency_manager.get_status(),
                        "stats": {
                            "detections_count": logger.total_detections_count,
                            "alerts_count": logger.total_alerts_count,
                            "fps": system_state["fps"],
                            "latency_ms": total_ms,
                            "latency_breakdown": system_state["latency_breakdown"]
                        },
                        "recent_alerts": logger.recent_alerts
                    }

                    system_state["last_payload"] = telemetry_payload
                    # 1. Send ultra-fast lightweight telemetry (<1KB) back to user camera
                    await websocket.send_text(json.dumps(telemetry_payload))

                    # 2. Broadcast full payload with image only to remote guardians/observers
                    if len(connected_websockets) > 1:
                        guardian_payload = {**telemetry_payload, "image": img_b64}
                        await broadcast_detection_update(guardian_payload, exclude_ws=websocket)

            elif msg_type == "command":
                cmd = packet.get("command", "")
                res = command_parser.parse(cmd, system_state["last_tracks"])
                if res["action"] == "TRIGGER_EMERGENCY":
                    emergency_manager.trigger(source="VOICE")

                system_state["last_mark_message"] = res["speech"]
                await websocket.send_text(json.dumps({
                    "type": "command_response",
                    "response": res
                }))

    except WebSocketDisconnect:
        connected_websockets.discard(websocket)
        print(f"[MARK 2.0 Server] WebSocket client disconnected. Remaining: {len(connected_websockets)}")
    except Exception as e:
        connected_websockets.discard(websocket)
        print(f"[MARK 2.0 Server Error] WebSocket exception: {e}")
    finally:
        connected_websockets.discard(websocket)

# ── Serve Static Frontend Routes ──
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/styles.css")
    async def serve_css():
        res = FileResponse(os.path.join(frontend_path, "styles.css"), media_type="text/css")
        res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return res

    @app.get("/app.js")
    async def serve_js():
        res = FileResponse(os.path.join(frontend_path, "app.js"), media_type="application/javascript")
        res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return res

    @app.get("/app_workspace.js")
    async def serve_app_workspace_js():
        res = FileResponse(os.path.join(frontend_path, "app_workspace.js"), media_type="application/javascript")
        res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return res

    @app.get("/user")
    @app.get("/mark")
    async def serve_user():
        res = FileResponse(os.path.join(frontend_path, "user.html"))
        res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return res

    @app.get("/monitor")
    @app.get("/guardian")
    @app.get("/guardian/{session_id}")
    async def serve_guardian(session_id: str = "DEMO-01"):
        res = FileResponse(os.path.join(frontend_path, "guardian.html"))
        res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return res

    @app.get("/guardian.js")
    async def serve_guardian_js():
        res = FileResponse(os.path.join(frontend_path, "guardian.js"), media_type="application/javascript")
        res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return res

    @app.get("/events")
    async def get_events():
        return {
            "events": list(safety_event_log)
        }

    @app.get("/app")
    async def serve_app():
        res = FileResponse(os.path.join(frontend_path, "app.html"))
        res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return res

    @app.get("/")
    async def serve_index():
        res = FileResponse(os.path.join(frontend_path, "index.html"))
        res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return res
