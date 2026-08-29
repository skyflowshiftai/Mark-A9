import time
from typing import Dict, Any, List, Optional

class AdaptiveMemory:
    """
    MARK 2.0 Multi-Tier Memory Store.
    
    Separates memory into:
    1. EPISODIC MEMORY: What happened during previous sessions & frames.
    2. SEMANTIC MEMORY: Verified facts about user preferences and spatial physics.
    3. PROCEDURAL MEMORY: Verified movement and guidance strategies.
    4. FAILURE MEMORY: Known mistakes, false positives, and conditions that caused them.
    """
    def __init__(self):
        self.episodic_memory: List[Dict[str, Any]] = []
        self.semantic_memory: Dict[str, Any] = {
            "preferred_language": "te-IN",
            "preferred_address": "సార్",
            "critical_distance_threshold_m": 1.5,
            "caution_distance_threshold_m": 3.0,
            "user_walking_speed_mps": 1.1
        }
        self.procedural_memory: List[Dict[str, Any]] = [
            {
                "id": "PROC_001",
                "condition": "approaching_vehicle_crossing_path",
                "strategy": "PRIORITIZE_OVER_STATIONARY_OBSTACLES",
                "verified": True,
                "confidence": 0.98
            },
            {
                "id": "PROC_002",
                "condition": "both_lateral_corridors_blocked",
                "strategy": "RECOMMEND_STOP_DO_NOT_SIDESTEP",
                "verified": True,
                "confidence": 0.99
            }
        ]
        self.failure_memory: List[Dict[str, Any]] = []
        self.verified_cases: List[Dict[str, Any]] = [
            {
                "case_id": "CASE_001",
                "situation": "Road crossing / hallway navigation",
                "observation": "Motorcycle distance 4m -> 3m -> 2m -> 1.2m approaching",
                "action": "Warned stop immediately",
                "outcome": "SUCCESS",
                "lesson": "Approaching vehicles crossing user path receive higher priority than stationary nearby objects.",
                "status": "VERIFIED"
            },
            {
                "case_id": "CASE_002",
                "situation": "Hallway corridor with obstacle on left and right",
                "observation": "Left chair at 1.8m, Right box at 2.0m",
                "action": "Halt / do not suggest sidestepping into obstacle",
                "outcome": "SUCCESS",
                "lesson": "When both lateral corridors are occupied, emit emergency stop directive.",
                "status": "VERIFIED"
            }
        ]

    def log_episode(self, episode: Dict[str, Any]):
        episode["timestamp"] = episode.get("timestamp", time.time())
        self.episodic_memory.append(episode)
        if len(self.episodic_memory) > 100:
            self.episodic_memory.pop(0)

    def record_failure(self, failure_record: Dict[str, Any]):
        failure_record["timestamp"] = time.time()
        self.failure_memory.append(failure_record)

    def add_verified_case(self, case: Dict[str, Any]):
        case["status"] = "VERIFIED"
        self.verified_cases.append(case)

    def search_similar_cases(self, situation_tags: List[str]) -> List[Dict[str, Any]]:
        matches = []
        for case in self.verified_cases:
            lesson = case.get("lesson", "").lower()
            if any(tag.lower() in lesson for tag in situation_tags):
                matches.append(case)
        return matches

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_episodes": len(self.episodic_memory),
            "total_verified_cases": len(self.verified_cases),
            "total_failures_recorded": len(self.failure_memory),
            "semantic_keys": list(self.semantic_memory.keys()),
            "procedural_rules": len(self.procedural_memory)
        }
