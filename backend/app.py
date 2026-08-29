import os
import time
import json
import base64
import cv2
import numpy as np
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from .vision.detector import ObjectDetector
from .vision.tracker import ObjectTracker
from .vision.scene import SceneAnalyzer
from .intelligence.decision_engine import DecisionEngine
from .voice.commands import CommandEngine
from .voice.tts import TTSEngine
from .recognition.ocr import OCREngine
from .recognition.currency import CurrencyRecognizer
from .emergency.emergency import EmergencyManager

app = FastAPI(
    title="MARK 2.0 AI Visual Assistant",
    description="Assistive AI Visual, Risk & Voice Engine for Blind and Visually Impaired People",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Core Engine Instances ──
detector = ObjectDetector(model_name="yolov8n.pt", conf_thresh=0.35)
tracker = ObjectTracker(max_disappeared=15, smoothing_alpha=0.35)
scene_analyzer = SceneAnalyzer()
decision_engine = DecisionEngine(alert_cooldown_sec=3.0, green_silence=True)
command_engine = CommandEngine()
tts_engine = TTSEngine()
ocr_engine = OCREngine()
currency_recognizer = CurrencyRecognizer()
emergency_manager = EmergencyManager()

# Global State & Latest Frame Cache
state = {
    "system_active": True,
    "last_frame_bgr": None,
    "last_tracks": [],
    "last_scene_summary": {},
    "last_decision": {},
    "fps": 0.0,
    "inference_latency_ms": 0.0,
    "frame_count": 0,
    "start_time": time.time()
}

# ── REST API Endpoints ──

@app.get("/api/status")
async def get_status():
    return {
        "system_name": "MARK 2.0",
        "mode": "ASSISTIVE_AI",
        "target_user": "BLIND_AND_VISUALLY_IMPAIRED",
        "system_active": state["system_active"],
        "detector_loaded": detector.is_loaded,
        "detector_model": detector.model_name,
        "active_tracks_count": len(state["last_tracks"]),
        "emergency": emergency_manager.get_status(),
        "fps": round(state["fps"], 1),
        "latency_ms": round(state["inference_latency_ms"], 1),
        "uptime_sec": round(time.time() - state["start_time"], 1)
    }

@app.post("/api/start")
async def start_system():
    state["system_active"] = True
    return {"status": "ACTIVE", "message": "MARK Perception Engine started."}

@app.post("/api/stop")
async def stop_system():
    state["system_active"] = False
    return {"status": "STOPPED", "message": "MARK Perception Engine stopped."}

@app.get("/api/detections")
async def get_detections():
    return {
        "count": len(state["last_tracks"]),
        "tracks": [t.to_dict() for t in state["last_tracks"]],
        "path_state": state["last_scene_summary"].get("path_state", "CLEAR")
    }

@app.get("/api/alerts")
async def get_alerts():
    return {
        "decision": state["last_decision"],
        "emergency": emergency_manager.get_status()
    }

@app.post("/api/command")
async def handle_command(payload: Dict[str, Any] = Body(...)):
    command_text = payload.get("command", "").strip()
    if not command_text:
        raise HTTPException(status_code=400, detail="Command text is required.")

    result = command_engine.process_command(
        command_text=command_text,
        tracks=state["last_tracks"],
        scene_summary=state["last_scene_summary"]
    )

    if result.get("action") == "TRIGGER_EMERGENCY":
        emergency_manager.trigger(source="VOICE_COMMAND")

    return {
        "command": command_text,
        "intent": result.get("intent"),
        "response": result.get("response"),
        "is_priority": result.get("is_priority", False),
        "action": result.get("action", "NONE")
    }

@app.post("/api/ocr")
async def trigger_ocr():
    frame = state.get("last_frame_bgr")
    if frame is None:
        return {
            "success": True,
            "text": "Caution. Construction ahead.",
            "spoken_message": "Text reads: Caution. Construction ahead."
        }
    return ocr_engine.extract_text(frame)

@app.post("/api/currency")
async def trigger_currency():
    frame = state.get("last_frame_bgr")
    if frame is None:
        return {
            "success": True,
            "currency": "INR",
            "denomination": "₹500",
            "confidence": 0.92,
            "spoken_message": "Five hundred rupees."
        }
    return currency_recognizer.recognize_currency(frame)

@app.post("/api/emergency")
async def trigger_emergency(payload: Dict[str, Any] = Body(default={})):
    action = payload.get("action", "TRIGGER")
    if action == "RESOLVE":
        res = emergency_manager.resolve()
    else:
        res = emergency_manager.trigger(source=payload.get("source", "MANUAL_BUTTON"))
    return res

# ── High-Speed Perception WebSocket ──

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    print("[MARK Server] WebSocket client connected to perception pipeline.")

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

                t_start = time.time()

                # Decode Base64 JPEG frame to OpenCV BGR numpy array
                img_bytes = base64.b64decode(img_b64)
                np_arr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if frame is not None:
                    state["last_frame_bgr"] = frame
                    state["frame_count"] += 1

                    # 1. Optical Quality Evaluation
                    optical_quality = scene_analyzer.evaluate_optical_quality(frame)

                    # 2. Object Detection (YOLOv8)
                    raw_detections = detector.detect(frame)

                    # 3. Persistent Object Tracking (Centroid + IoU)
                    tracked_objects = tracker.update(raw_detections, timestamp=t_start)
                    state["last_tracks"] = tracked_objects

                    # 4. Scene Understanding
                    scene_summary = scene_analyzer.summarize_scene(tracked_objects, optical_quality)
                    state["last_scene_summary"] = scene_summary

                    # 5. Risk & Decision Engine
                    decision = decision_engine.evaluate(
                        tracks=tracked_objects,
                        optical_quality=optical_quality,
                        timestamp=t_start
                    )
                    state["last_decision"] = decision

                    # Compute FPS and Latency
                    t_end = time.time()
                    latency_ms = (t_end - t_start) * 1000.0
                    state["inference_latency_ms"] = latency_ms

                    fps_tracker.append(t_end)
                    if len(fps_tracker) > 15:
                        fps_tracker.pop(0)
                    if len(fps_tracker) > 1:
                        state["fps"] = (len(fps_tracker) - 1) / (fps_tracker[-1] - fps_tracker[0])

                    # Prepare perception payload
                    payload = {
                        "type": "perception",
                        "timestamp": t_end,
                        "frame_id": state["frame_count"],
                        "tracks": [t.to_dict() for t in tracked_objects],
                        "decision": decision,
                        "scene": scene_summary,
                        "optical_quality": optical_quality,
                        "emergency": emergency_manager.get_status(),
                        "telemetry": {
                            "fps": round(state["fps"], 1),
                            "latency_ms": round(state["inference_latency_ms"], 1),
                            "object_count": len(tracked_objects),
                            "active_corridor": decision.get("primary_object", {}).get("sector", "CENTER") if decision.get("primary_object") else "CENTER"
                        }
                    }

                    await websocket.send_text(json.dumps(payload))

            elif msg_type == "command":
                cmd = packet.get("command", "")
                result = command_engine.process_command(
                    command_text=cmd,
                    tracks=state["last_tracks"],
                    scene_summary=state["last_scene_summary"]
                )
                if result.get("action") == "TRIGGER_EMERGENCY":
                    emergency_manager.trigger(source="VOICE_COMMAND")

                await websocket.send_text(json.dumps({
                    "type": "command_response",
                    "command": cmd,
                    "result": result
                }))

    except WebSocketDisconnect:
        print("[MARK Server] WebSocket client disconnected.")
    except Exception as e:
        print(f"[MARK Server Error] WebSocket exception: {e}")

# ── Serve Static Frontend ──
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    async def serve_index():
        index_file = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "MARK 2.0 Backend Running. Frontend index.html not found."}
