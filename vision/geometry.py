from typing import Dict, Any, List

def analyze_object_geometry(bbox: List[float], frame_width: int, frame_height: int) -> Dict[str, Any]:
    """
    Computes honest bounding box geometric metrics: aspect ratio, relative area,
    and geometric shape category.
    """
    x1, y1, x2, y2 = bbox
    w = max(1.0, float(x2 - x1))
    h = max(1.0, float(y2 - y1))

    frame_area = max(1.0, float(frame_width * frame_height))
    bbox_area = w * h
    area_ratio = round(bbox_area / frame_area, 4)
    aspect_ratio = round(w / h, 3)

    # 1. Geometric Shape Classification (2D Bounding Box Geometry)
    if aspect_ratio < 0.45:
        shape_cat = "VERY_TALL"
    elif aspect_ratio < 0.80:
        shape_cat = "TALL"
    elif aspect_ratio <= 1.25:
        shape_cat = "SQUARE_LIKE"
    elif aspect_ratio <= 2.00:
        shape_cat = "WIDE"
    else:
        shape_cat = "VERY_WIDE"

    # 2. Relative Image Size Classification
    if area_ratio < 0.04:
        size_cat = "SMALL"
    elif area_ratio <= 0.20:
        size_cat = "MEDIUM"
    else:
        size_cat = "LARGE"

    return {
        "shape_category": shape_cat,
        "aspect_ratio": aspect_ratio,
        "area_ratio": area_ratio,
        "relative_size": size_cat,
        "width_px": round(w, 1),
        "height_px": round(h, 1)
    }
