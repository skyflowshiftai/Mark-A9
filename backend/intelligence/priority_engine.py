from typing import List, Optional
from ..vision.tracker import ObjectState

class PriorityEngine:
    def rank_tracks(self, tracks: List[ObjectState]) -> List[ObjectState]:
        """
        Ranks objects by urgency:
        Priority key = (Risk Score * 2) - Distance + (10 if FORWARD else 0)
        """
        if not tracks:
            return []

        def priority_key(track: ObjectState):
            corridor_bonus = 15.0 if track.sector == "FORWARD" else 0.0
            return (track.risk_score * 2.0) - (track.distance_m * 1.5) + corridor_bonus

        sorted_tracks = sorted(tracks, key=priority_key, reverse=True)
        return sorted_tracks

    def select_primary_hazard(self, tracks: List[ObjectState]) -> Optional[ObjectState]:
        """
        Selects the single most critical hazard requiring immediate attention.
        """
        ranked = self.rank_tracks(tracks)
        if ranked and ranked[0].risk_score >= 35:
            return ranked[0]
        return None
