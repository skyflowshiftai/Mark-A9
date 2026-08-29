from typing import Dict, Any, Tuple
import config

def compute_spatial_position(norm_center_x: float, norm_center_y: float, proximity: str = "MEDIUM") -> Dict[str, Any]:
    """
    Computes 3x3 semantic spatial positioning and central walking corridor relevance.
    """
    # 1. Horizontal Position
    if norm_center_x < 0.33:
        h_pos = "LEFT"
    elif norm_center_x > 0.66:
        h_pos = "RIGHT"
    else:
        h_pos = "CENTER"

    # 2. Vertical Position
    if norm_center_y < 0.33:
        v_pos = "TOP"
    elif norm_center_y > 0.66:
        v_pos = "BOTTOM"
    else:
        v_pos = "MIDDLE"

    # 3. 3x3 Combined Zone
    if h_pos == "CENTER" and v_pos == "MIDDLE":
        zone = "CENTER-MIDDLE"
    elif h_pos == "CENTER":
        zone = f"{v_pos}-CENTER"
    elif v_pos == "MIDDLE":
        zone = f"{h_pos}-MIDDLE"
    else:
        zone = f"{v_pos}-{h_pos}"

    # 4. Walking Corridor Path Relevance (Center 40% of horizontal field)
    is_in_corridor = (0.30 <= norm_center_x <= 0.70)
    if is_in_corridor and proximity == "NEAR":
        path_relevance = "HIGH"
    elif is_in_corridor or proximity == "NEAR":
        path_relevance = "MEDIUM"
    else:
        path_relevance = "LOW"

    return {
        "horizontal": h_pos,
        "vertical": v_pos,
        "zone": zone,
        "in_corridor": is_in_corridor,
        "path_relevance": path_relevance
    }
