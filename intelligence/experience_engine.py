import time
from typing import Dict, Any, List, Optional
from intelligence.adaptive_memory import AdaptiveMemory

class ExperienceEngine:
    """
    MARK 2.0 Experience Learning Engine.
    
    Converts completed interaction cycles into structured empirical cases:
    OBSERVE -> INTERPRET -> VERIFY -> PRIORITIZE -> ACT -> OBSERVE OUTCOME -> REFLECT -> UPDATE MEMORY
    """
    def __init__(self, memory: Optional[AdaptiveMemory] = None):
        self.memory = memory or AdaptiveMemory()
        self.recorded_cases: List[Dict[str, Any]] = []

    def record_interaction(
        self,
        situation: str,
        observation: str,
        confidence: float,
        decision: str,
        action: str,
        outcome: str = "UNKNOWN",
        user_feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a structured experience case from an interaction.
        """
        outcome_upper = outcome.upper()
        if outcome_upper not in ("SUCCESS", "PARTIAL_SUCCESS", "FAILURE", "UNKNOWN"):
            outcome_upper = "UNKNOWN"

        failure_reason = ""
        lesson = ""
        generalization = "SIMILAR_CASES"
        memory_status = "CANDIDATE"

        if outcome_upper == "FAILURE":
            failure_reason = self._diagnose_failure(decision, action, user_feedback)
            lesson = self._formulate_lesson(situation, failure_reason)
            memory_status = "CANDIDATE"
            self.memory.record_failure({
                "situation": situation,
                "observation": observation,
                "action": action,
                "reason": failure_reason
            })
        elif outcome_upper == "SUCCESS":
            lesson = f"In {situation.lower()}, verified action '{action}' achieved safe user navigation."
            memory_status = "CANDIDATE"

        case_record = {
            "case_id": f"CASE_{int(time.time()*1000)%1000000:06d}",
            "situation": situation,
            "observation": observation,
            "confidence": round(confidence, 2),
            "decision": decision,
            "action": action,
            "outcome": outcome_upper,
            "failure_reason": failure_reason,
            "lesson": lesson,
            "generalization": generalization,
            "memory_status": memory_status,
            "regression_test": f"Test that in situation '{situation}', system avoids failure '{failure_reason}' and chooses action '{action}'",
            "timestamp": time.time()
        }

        self.recorded_cases.append(case_record)
        self.memory.log_episode(case_record)
        return case_record

    def _diagnose_failure(self, decision: str, action: str, feedback: Optional[str]) -> str:
        if feedback:
            return f"User reported: {feedback}"
        if "move_right" in action.lower() or "right" in action.lower():
            return "Recommended lateral move into uncleared or occupied right corridor."
        return "Warning timing or distance calculation mismatched physical obstacle proximity."

    def _formulate_lesson(self, situation: str, failure_reason: str) -> str:
        return f"When in situation '{situation}', verify lateral clearance and distance stability before executing action to prevent: {failure_reason}"

    def get_candidate_lessons(self) -> List[Dict[str, Any]]:
        return [c for c in self.recorded_cases if c.get("memory_status") == "CANDIDATE"]
