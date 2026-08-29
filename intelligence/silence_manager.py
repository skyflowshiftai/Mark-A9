import time
from typing import Dict, Any, Optional
from vision.tracker import TrackedEntity
import config

class SilenceManager:
    def __init__(self, cooldown_sec: float = config.ALERT_COOLDOWN_SEC):
        self.cooldown_sec = cooldown_sec
        self.last_global_alert_time = -100.0
        self.last_spoken_track_id: Optional[int] = None
        self.last_spoken_risk_level: Optional[str] = None
        self.last_spoken_phrase = ""

    def evaluate_speech_decision(
        self,
        primary_track: Optional[TrackedEntity],
        phrase: str,
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Applies MARK Silence Policy:
        - Speaks when a hazard matters
        - Stays silent when safe or repetitive
        - Escalates only when risk increases
        """
        if timestamp is None:
            timestamp = time.time()

        # 1. No primary hazard or below threshold -> Intentional Silence
        if primary_track is None or primary_track.risk_level == "SILENT":
            return {
                "should_speak": False,
                "reason": "SILENCE_SAFE_PATH",
                "phrase": "",
                "risk_level": "LOW"
            }

        # 2. Check time elapsed since last global alert
        dt_global = timestamp - self.last_global_alert_time
        dt_track = timestamp - primary_track.last_alert_time

        # 3. Check if risk has escalated (e.g. CAUTION -> URGENT)
        is_same_track = (primary_track.track_id == self.last_spoken_track_id)
        has_risk_escalated = (
            primary_track.risk_level == "URGENT" and
            self.last_spoken_risk_level != "URGENT"
        )

        should_speak = False
        reason = "COOLDOWN_ACTIVE"

        if has_risk_escalated:
            # Urgent escalation overrides normal cooldown
            should_speak = True
            reason = "RISK_ESCALATED"
        elif not is_same_track and dt_global >= 1.5:
            # New distinct hazard
            should_speak = True
            reason = "NEW_HAZARD"
        elif is_same_track:
            if dt_track >= self.cooldown_sec and primary_track.alert_count < config.MAX_REPEAT_ALERT_COUNT:
                should_speak = True
                reason = "PERSISTENT_THREAT_REPEAT"
            elif primary_track.alert_count >= config.MAX_REPEAT_ALERT_COUNT:
                should_speak = False
                reason = "MAX_REPEATS_SUPPRESSED"
        elif dt_global >= self.cooldown_sec:
            should_speak = True
            reason = "COOLDOWN_CLEARED"

        if should_speak:
            self.last_global_alert_time = timestamp
            self.last_spoken_track_id = primary_track.track_id
            self.last_spoken_risk_level = primary_track.risk_level
            self.last_spoken_phrase = phrase
            primary_track.last_alert_time = timestamp
            primary_track.alert_count += 1

        return {
            "should_speak": should_speak,
            "reason": reason,
            "phrase": phrase if should_speak else "",
            "risk_level": primary_track.risk_level,
            "track_id": primary_track.track_id
        }
