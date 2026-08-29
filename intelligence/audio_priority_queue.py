import time
from typing import Dict, Any, List, Optional
from collections import deque

PRIORITY_LEVELS = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "IGNORE": 0
}

class AudioPriorityQueue:
    """
    Manages audio playback prioritization and instant interruption for safety alerts.
    """
    def __init__(self):
        self.queue: List[Dict[str, Any]] = []
        self.current_playing: Optional[Dict[str, Any]] = None

    def enqueue_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enqueues an alert and determines whether it should immediately interrupt active audio.
        """
        priority = alert.get("priority", "MEDIUM").upper()
        level = PRIORITY_LEVELS.get(priority, 1)

        alert_item = {
            "id": int(time.time() * 1000),
            "priority": priority,
            "level": level,
            "instruction": alert.get("instruction", ""),
            "object": alert.get("object", ""),
            "created_at": time.time(),
            "interrupt_audio": alert.get("interrupt_audio", False) or (priority == "CRITICAL")
        }

        # If Critical or Urgent, flush lower-priority items and interrupt immediately
        if alert_item["interrupt_audio"] or level >= 4:
            # Purge non-critical items
            self.queue = [item for item in self.queue if item["level"] >= 4]
            self.current_playing = alert_item
            return {
                "action": "INTERRUPT_IMMEDIATE",
                "alert": alert_item
            }

        # Otherwise insert in sorted priority order
        self.queue.append(alert_item)
        self.queue.sort(key=lambda x: x["level"], reverse=True)

        return {
            "action": "ENQUEUED",
            "alert": alert_item,
            "queue_size": len(self.queue)
        }

    def pop_next(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves the highest priority item from the queue.
        """
        if self.queue:
            item = self.queue.pop(0)
            self.current_playing = item
            return item
        self.current_playing = None
        return None

    def clear(self):
        self.queue.clear()
        self.current_playing = None
