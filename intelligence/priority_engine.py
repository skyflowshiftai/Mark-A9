from typing import List, Optional
from vision.tracker import TrackedEntity
import config

class PriorityEngine:
    def rank_tracks(self, tracks: List[TrackedEntity]) -> List[TrackedEntity]:
        """
        Ranks tracks by:
        1. Risk Score
        2. Walking Path Corridor Relevance
        3. Proximity
        4. Detector Confidence
        """
        if not tracks:
            return []

        def get_priority_key(t: TrackedEntity):
            path_bonus = 0.20 if getattr(t, "path_relevance", "LOW") == "HIGH" else (0.10 if getattr(t, "path_relevance", "LOW") == "MEDIUM" else 0.0)
            prox_bonus = 0.15 if getattr(t, "proximity", "MEDIUM") == "NEAR" else (0.05 if getattr(t, "proximity", "MEDIUM") == "MEDIUM" else 0.0)
            return t.risk_score + path_bonus + prox_bonus + (t.confidence * 0.05)

        return sorted(tracks, key=get_priority_key, reverse=True)

    def select_primary_hazard(self, tracks: List[TrackedEntity]) -> Optional[TrackedEntity]:
        """
        Selects the single most critical hazard deserving auditory attention.
        Returns None if all tracks are below awareness threshold (Green Silence).
        """
        ranked = self.rank_tracks(tracks)
        if ranked and ranked[0].risk_score >= config.RISK_THRESHOLD_AWARENESS:
            return ranked[0]
        return None
