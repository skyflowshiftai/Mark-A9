import time
from typing import Dict, Any, List, Optional, Tuple

class GuidanceEngine:
    """
    MARK 2.0 Assistive Navigation & Guidance State Machine.
    
    Transforms perception into an active, respectful navigation guide with:
    1. Obstacle tracking and persistence memory
    2. Actual Free Space / Lateral Corridor Clearance Analysis (Left, Center, Right)
    3. 3-Second Guidance Cycle (Speak -> 3s Silence/Reassess -> Remind only if still blocked)
    4. Danger Escalation Override (Immediate interrupt on critical danger)
    """
    def __init__(self, guidance_cycle_sec: float = 3.0):
        self.guidance_cycle_sec = guidance_cycle_sec
        # State memory: track_id -> dict of obstacle state & alert timestamps
        self.obstacle_memory: Dict[int, Dict[str, Any]] = {}
        self.global_last_spoken_time = -100.0
        self.last_spoken_track_id: Optional[int] = None

    def evaluate_navigation(
        self,
        tracks: List[Any],
        timestamp: Optional[float] = None,
        language: str = "te-IN"
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates active tracks through the 3-Second Navigation State Machine.
        Returns actionable guidance directive or None (Silence).
        """
        if timestamp is None:
            timestamp = time.perf_counter()

        if not tracks:
            # Path clear -> Clean up memory of disappeared tracks
            self.obstacle_memory.clear()
            return None

        # 1. Parse all visible obstacles
        all_obs_data = []
        for t in tracks:
            d = t.to_dict() if hasattr(t, "to_dict") else t
            score, eval_data = self._score_obstacle(d)
            if eval_data["relevance"] != "IGNORE":
                all_obs_data.append((score, eval_data))

        if not all_obs_data:
            return None

        # 2. Analyze Lateral Corridor Clearance (Is Left, Center, or Right blocked?)
        left_blocked = any(
            (o["direction"] == "LEFT" or "LEFT" in o["zone"]) and o["distance_m"] <= 3.5 
            for _, o in all_obs_data
        )
        right_blocked = any(
            (o["direction"] == "RIGHT" or "RIGHT" in o["zone"]) and o["distance_m"] <= 3.5 
            for _, o in all_obs_data
        )
        center_blocked = any(
            o["direction"] == "CENTER" and o["distance_m"] <= 3.5 
            for _, o in all_obs_data
        )

        # Sort most critical / path-relevant obstacle first
        all_obs_data.sort(key=lambda x: x[0], reverse=True)
        top_score, top_obs = all_obs_data[0]
        track_id = top_obs["track_id"]

        # Compute True Actionable Sidestep based on actual clear space
        if left_blocked and right_blocked:
            recommended_action = "STOP_BLOCKED"
        elif top_obs["direction"] == "LEFT":
            recommended_action = "MOVE_RIGHT" if not right_blocked else "STOP_BLOCKED"
        elif top_obs["direction"] == "RIGHT":
            recommended_action = "MOVE_LEFT" if not left_blocked else "STOP_BLOCKED"
        else: # CENTER obstacle
            if not right_blocked:
                recommended_action = "MOVE_RIGHT"
            elif not left_blocked:
                recommended_action = "MOVE_LEFT"
            else:
                recommended_action = "STOP_BLOCKED"

        top_obs["recommended_action"] = recommended_action
        top_obs["left_blocked"] = left_blocked
        top_obs["right_blocked"] = right_blocked

        # 3. Check State Machine Memory & 3-Second Guidance Cycle
        prev_state = self.obstacle_memory.get(track_id)
        should_speak = False
        is_persistent_reminder = False
        interrupt_audio = False
        reason = "NORMAL"

        curr_risk = top_obs["risk_level"]
        dist = top_obs["distance_m"]
        is_critical_danger = (curr_risk == "URGENT" or dist < 1.5 or top_obs["is_approaching_vehicle"])

        if prev_state is None:
            # State 1: New Obstacle Enters Awareness/Guidance Range
            should_speak = True
            interrupt_audio = is_critical_danger
            reason = "NEW_OBSTACLE"
            self.obstacle_memory[track_id] = {
                "track_id": track_id,
                "object": top_obs["object"],
                "distance": dist,
                "direction": top_obs["direction"],
                "risk": curr_risk,
                "first_seen": timestamp,
                "last_spoken": timestamp,
                "repeat_count": 1
            }
        else:
            dt = timestamp - prev_state["last_spoken"]
            prev_risk = prev_state["risk"]
            prev_dist = prev_state["distance"]

            # State 2: Danger Escalation Exception (Bypasses 3-second cycle immediately)
            if (is_critical_danger and prev_risk != "URGENT") or (prev_dist - dist >= 1.0 and dist <= 2.0):
                should_speak = True
                interrupt_audio = True
                reason = "DANGER_ESCALATION_OVERRIDE"
                prev_state["last_spoken"] = timestamp
                prev_state["risk"] = curr_risk
                prev_state["distance"] = dist
                prev_state["repeat_count"] += 1

            # State 3: 3-Second Guidance Cycle Reassessment
            elif dt >= self.guidance_cycle_sec:
                if top_obs["path_relevance"] in ("HIGH", "MEDIUM") and dist <= 4.0:
                    should_speak = True
                    is_persistent_reminder = True
                    reason = "STILL_BLOCKING_PATH_REMINDER"
                    prev_state["last_spoken"] = timestamp
                    prev_state["distance"] = dist
                    prev_state["repeat_count"] += 1
                else:
                    should_speak = False
                    reason = "SAFE_ENOUGH_SILENCE"
            else:
                # State 4: Within 3-Second Quiet Window -> Intentional Silence
                should_speak = False
                reason = "WITHIN_3S_COOLDOWN_WINDOW"

        # Clean up tracks not seen in current frame
        active_ids = {o["track_id"] for _, o in all_obs_data}
        self.obstacle_memory = {tid: s for tid, s in self.obstacle_memory.items() if tid in active_ids}

        if should_speak:
            self.global_last_spoken_time = timestamp
            self.last_spoken_track_id = track_id

            if language.startswith("te"):
                instruction = self._synthesize_telugu_guidance(top_obs, is_persistent_reminder)
            else:
                instruction = self._synthesize_english_guidance(top_obs, is_persistent_reminder)

            return {
                "should_speak": True,
                "instruction": instruction,
                "interrupt_audio": interrupt_audio,
                "priority": "CRITICAL" if is_critical_danger else ("HIGH" if top_obs["path_relevance"] == "HIGH" else "MEDIUM"),
                "object": top_obs["object"],
                "distance": dist,
                "direction": top_obs["direction"],
                "recommended_action": recommended_action,
                "reason": reason,
                "track_id": track_id
            }

        return None

    def _score_obstacle(self, d: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        obj_name = d.get("recognized_name") or d.get("class_name") or d.get("name") or "Object"
        raw_class = (d.get("raw_class_name") or d.get("detector_class") or obj_name).lower()
        dist_m = float(d.get("distance_m") or d.get("distance") or 3.0)
        direction = str(d.get("spatial_sector") or d.get("direction") or "CENTER").upper()
        zone = str(d.get("spatial_zone") or "CENTER-MIDDLE").upper()
        path_rel = str(d.get("path_relevance") or "MEDIUM").upper()
        motion = str(d.get("motion_state") or (d.get("motion", {}).get("state") if isinstance(d.get("motion"), dict) else "STATIONARY")).upper()
        approach = str(d.get("approach_tendency") or "STATIONARY").upper()
        risk = str(d.get("risk_level") or d.get("threat") or "LOW").upper()
        track_id = int(d.get("track_id") or d.get("id") or 1)

        is_vehicle = raw_class in ("car", "truck", "bus", "motorcycle", "vehicle")
        is_step = any(s in raw_class for s in ("step", "stair", "curb", "ledge"))
        is_approaching = (motion == "APPROACHING" or approach in ("CLOSING_IN", "APPROACHING"))

        obs_dir = "LEFT" if ("LEFT" in direction or "LEFT" in zone) else ("RIGHT" if ("RIGHT" in direction or "RIGHT" in zone) else "CENTER")

        if dist_m > 5.5 and not is_vehicle:
            relevance = "IGNORE"
            score = 0.0
        elif dist_m < 1.5 or is_vehicle or is_step:
            relevance = "CRITICAL"
            score = 10.0 + (10.0 - dist_m) + (3.0 if is_vehicle else 0.0)
        elif dist_m <= 3.0 or path_rel == "HIGH":
            relevance = "GUIDANCE"
            score = 6.0 + (6.0 - dist_m)
        else:
            relevance = "AWARENESS"
            score = 3.0 + (5.5 - dist_m)

        eval_data = {
            "track_id": track_id,
            "object": obj_name,
            "raw_class": raw_class,
            "distance_m": dist_m,
            "direction": obs_dir,
            "zone": zone,
            "path_relevance": path_rel,
            "risk_level": risk,
            "relevance": relevance,
            "is_vehicle": is_vehicle,
            "is_step": is_step,
            "is_approaching_vehicle": (is_vehicle and is_approaching)
        }

        return score, eval_data

    def _synthesize_telugu_guidance(self, obs: Dict[str, Any], is_reminder: bool) -> str:
        raw = obs["raw_class"]
        dist = obs["distance_m"]
        dir_code = obs["direction"]
        rec = obs["recommended_action"]
        is_approaching = obs["is_approaching_vehicle"]

        # 1. 🔴 Immediate Danger / Car (< 1.5m or approaching)
        if obs["is_vehicle"] and (is_approaching or dist <= 2.0):
            return "సార్, కారు ముందుకు వస్తోంది. ఆగండి." if raw == "car" else "సార్, వాహనం దగ్గరకు వస్తోంది. ఆగండి."

        if dist < 1.0:
            return "సార్, చాలా దగ్గరగా ఉంది. ఆగండి."

        if obs["is_step"]:
            return "సార్, మెట్టు ఉంది. జాగ్రత్త."

        # If both sides are blocked -> Stop
        if rec == "STOP_BLOCKED":
            return "సార్, ముందంతా అడ్డంకిగా ఉంది. ఆగండి."

        # 2. 🟡 Actionable Movement Guidance (1m - 3m)
        if dist <= 3.0:
            sidestep = "కాస్త కుడివైపుకి జరగండి." if rec == "MOVE_RIGHT" else "కాస్త ఎడమవైపుకి జరగండి."

            if is_reminder:
                if raw == "person":
                    return f"సార్, ఇంకా ముందు వ్యక్తి ఉన్నారు. {sidestep}"
                return f"సార్, ఇంకా ముందే అడ్డంకి ఉంది. {sidestep}"

            if raw == "person":
                return f"సార్, మీ ముందు ఒక వ్యక్తి ఉన్నారు. {sidestep}"
            elif dir_code == "LEFT":
                return "సార్, ఎడమవైపు అడ్డంకి ఉంది. కుడివైపుకి జరగండి."
            elif dir_code == "RIGHT":
                return "సార్, కుడివైపు అడ్డంకి ఉంది. ఎడమవైపుకి జరగండి."
            else:
                return f"సార్, ముందే అడ్డంకి ఉంది. {sidestep}"

        # 3. 🟢 Calm Awareness (3m - 5m)
        if raw == "person":
            return "సార్, మీ ముందు ఒక వ్యక్తి ఉన్నారు."
        elif dir_code == "LEFT":
            return "సార్, ఎడమవైపు అడ్డంకి ఉంది."
        elif dir_code == "RIGHT":
            return "సార్, కుడివైపు అడ్డంకి ఉంది."
        return "సార్, ముందు అడ్డంకి ఉంది."

    def _synthesize_english_guidance(self, obs: Dict[str, Any], is_reminder: bool) -> str:
        raw = obs["raw_class"]
        dist = obs["distance_m"]
        dir_code = obs["direction"]
        rec = obs["recommended_action"]

        if obs["is_vehicle"] and (obs["is_approaching_vehicle"] or dist <= 2.0):
            return "Warning. Vehicle approaching. Stop."

        if dist < 1.0:
            return "Obstacle very close. Stop."

        if obs["is_step"]:
            return "Step down ahead. Careful."

        if rec == "STOP_BLOCKED":
            return "Path completely blocked ahead. Stop."

        sidestep_en = "Step right." if rec == "MOVE_RIGHT" else "Step left."

        if dist <= 3.0:
            if is_reminder:
                return f"Person still ahead. {sidestep_en}" if raw == "person" else f"Obstacle still ahead. {sidestep_en}"
            if raw == "person":
                return f"Person ahead. {sidestep_en}"
            return f"Obstacle ahead on {dir_code.lower()}. {sidestep_en}"

        return "Person ahead." if raw == "person" else f"Obstacle on your {dir_code.lower()}."
