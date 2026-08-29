from typing import Dict, Any, Optional

class TeluguInstructionEngine:
    """
    Direct Vision-to-Telugu Instruction & Movement Guidance Engine.
    Synthesizes natural, respectful ("సార్, ...") Telugu safety and navigation directives.
    """
    def __init__(self):
        self.object_telugu_names = {
            "car": "కారు",
            "truck": "ట్రక్",
            "bus": "బస్సు",
            "motorcycle": "బైక్",
            "vehicle": "వాహనం",
            "person": "వ్యక్తి",
            "chair": "కుర్చీ",
            "table": "బల్ల",
            "dining table": "బల్ల",
            "bottle": "బాటిల్",
            "step": "మెట్టు",
            "stairs": "మెట్లు",
            "door": "తలుపు",
            "dog": "కుక్క",
            "cat": "పిల్లి",
            "backpack": "బ్యాగ్",
            "container": "వస్తువు",
            "packet": "ప్యాకెట్"
        }

    def generate_instruction(self, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Translates structured object or event record into a direct Telugu voice instruction.
        """
        if not data:
            return {
                "shouldSpeak": False,
                "instruction": "",
                "priority": "silent"
            }

        obj = str(data.get("object") or data.get("name") or "object").lower()
        risk = str(data.get("risk") or data.get("risk_level") or data.get("threat") or "low").lower()
        direction = str(data.get("direction") or data.get("spatial_sector") or "front").lower()
        distance = float(data.get("distance") or data.get("distance_m") or 3.0)
        motion = str(data.get("motion") or data.get("motion_state") or "stationary").lower()
        is_approaching = (motion == "approaching" or "closing" in motion)

        # ── 1. 🔴 DANGER / URGENT (< 1.5m or Approaching Vehicle) ──
        if risk in ("high", "urgent", "critical") or distance < 1.5:
            if obj in ("car", "truck", "bus", "motorcycle", "vehicle") or is_approaching:
                return {
                    "shouldSpeak": True,
                    "instruction": "సార్, కారు ముందుకు వస్తోంది. ఆగండి." if obj == "car" else "సార్, వాహనం వస్తోంది. ఆగండి.",
                    "priority": "high",
                    "audio_priority": "CRITICAL"
                }
            elif any(s in obj for s in ("step", "stair", "curb", "ledge")):
                return {
                    "shouldSpeak": True,
                    "instruction": "సార్, మెట్టు ఉంది. జాగ్రత్త.",
                    "priority": "high",
                    "audio_priority": "CRITICAL"
                }
            elif distance < 1.0:
                return {
                    "shouldSpeak": True,
                    "instruction": "సార్, చాలా దగ్గరగా ఉంది. ఆగండి.",
                    "priority": "high",
                    "audio_priority": "CRITICAL"
                }
            else:
                return {
                    "shouldSpeak": True,
                    "instruction": "సార్, ముందు అడ్డంకి ఉంది. ఆగండి.",
                    "priority": "high",
                    "audio_priority": "CRITICAL"
                }

        # ── 2. 🟡 ACTIONABLE GUIDANCE (1.5m - 3.0m) ──
        if distance <= 3.0 or risk in ("medium", "caution"):
            if obj == "person":
                if "left" in direction:
                    instruction = "సార్, ఎడమవైపు వ్యక్తి ఉన్నారు. కుడివైపుకి జరగండి."
                elif "right" in direction:
                    instruction = "సార్, కుడివైపు వ్యక్తి ఉన్నారు. ఎడమవైపుకి జరగండి."
                else:
                    instruction = "సార్, మీ ముందు ఒక వ్యక్తి ఉన్నారు. కాస్త కుడివైపుకి జరగండి."
                return {
                    "shouldSpeak": True,
                    "instruction": instruction,
                    "priority": "medium",
                    "audio_priority": "MEDIUM"
                }
            elif "left" in direction:
                return {
                    "shouldSpeak": True,
                    "instruction": "సార్, ఎడమవైపు అడ్డంకి ఉంది. కుడివైపుకి జరగండి.",
                    "priority": "medium",
                    "audio_priority": "MEDIUM"
                }
            elif "right" in direction:
                return {
                    "shouldSpeak": True,
                    "instruction": "సార్, కుడివైపు అడ్డంకి ఉంది. ఎడమవైపుకి జరగండి.",
                    "priority": "medium",
                    "audio_priority": "MEDIUM"
                }
            else:
                return {
                    "shouldSpeak": True,
                    "instruction": "సార్, ముందే అడ్డంకి ఉంది. కాస్త కుడివైపుకి జరగండి.",
                    "priority": "medium",
                    "audio_priority": "MEDIUM"
                }

        # ── 3. 🟢 AWARENESS (3.0m - 5.0m) ──
        if distance <= 5.0:
            if obj == "person":
                return {
                    "shouldSpeak": True,
                    "instruction": "సార్, మీ ముందు ఒక వ్యక్తి ఉన్నారు.",
                    "priority": "medium",
                    "audio_priority": "LOW"
                }
            return {
                "shouldSpeak": True,
                "instruction": "సార్, ముందు అడ్డంకి ఉంది.",
                "priority": "medium",
                "audio_priority": "LOW"
            }

        # ── 4. ⚪ SILENCE (> 5.0m) ──
        return {
            "shouldSpeak": False,
            "instruction": "దారి ఖాళీగా ఉంది.",
            "priority": "silent",
            "audio_priority": "LOW"
        }

    def format_currency_telugu(self, denomination: int) -> str:
        denom_map = {
            500: "ఐదు వందల రూపాయల నోటు.",
            200: "రెండు వందల రూపాయల నోటు.",
            100: "వంద రూపాయల నోటు.",
            50: "యాభై రూపాయల నోటు.",
            20: "ఇరవై రూపాయల నోటు.",
            10: "పది రూపాయల నోటు."
        }
        return denom_map.get(denomination, f"{denomination} రూపాయల నోటు.")

    def format_safety_query_telugu(
        self,
        highest_risk: str,
        nearest_obj: Optional[str] = None,
        is_uncertain: bool = False
    ) -> str:
        """
        Responsible multi-factor safety evaluation response in Telugu.
        """
        if is_uncertain:
            return "సార్, ముందున్న దారి స్పష్టంగా కనిపించడం లేదు. జాగ్రత్తగా ఉండండి."

        if highest_risk in ("URGENT", "RED", "HIGH", "CAUTION"):
            if nearest_obj and "car" in nearest_obj.lower():
                return "సార్, కారు దగ్గరగా ఉంది. ఆగండి."
            return "సార్, ముందే అడ్డంకి ఉంది. ఆగండి."

        return "సార్, ప్రస్తుతం దారి ఖాళీగా ఉంది."

    def format_emergency_telugu(self) -> str:
        return "సహాయం అవసరం. అత్యవసర మోడ్ ప్రారంభమైంది."
