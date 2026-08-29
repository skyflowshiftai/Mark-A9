import pytest
from collections import deque
from vision.tracker import ObjectTracker
from vision.spatial import compute_spatial_position
from vision.geometry import analyze_object_geometry
from vision.motion import estimate_relative_motion

def test_spatial_position_3x3_grid():
    # Top-Left
    p_tl = compute_spatial_position(0.15, 0.15, proximity="FAR")
    assert p_tl["horizontal"] == "LEFT"
    assert p_tl["vertical"] == "TOP"
    assert p_tl["zone"] == "TOP-LEFT"
    assert p_tl["path_relevance"] == "LOW"

    # Center-Middle with NEAR proximity (Walking corridor)
    p_cm = compute_spatial_position(0.50, 0.50, proximity="NEAR")
    assert p_cm["horizontal"] == "CENTER"
    assert p_cm["vertical"] == "MIDDLE"
    assert p_cm["zone"] == "CENTER-MIDDLE"
    assert p_cm["path_relevance"] == "HIGH"

    # Bottom-Right
    p_br = compute_spatial_position(0.85, 0.85, proximity="MEDIUM")
    assert p_br["horizontal"] == "RIGHT"
    assert p_br["vertical"] == "BOTTOM"
    assert p_br["zone"] == "BOTTOM-RIGHT"

def test_geometry_and_relative_size():
    # Very Tall object (like standing person / door)
    g_tall = analyze_object_geometry([100, 50, 160, 320], frame_width=640, frame_height=360)
    assert g_tall["shape_category"] in ("VERY_TALL", "TALL")
    assert g_tall["relative_size"] in ("SMALL", "MEDIUM")

    # Wide object (like table or vehicle)
    g_wide = analyze_object_geometry([100, 100, 500, 300], frame_width=640, frame_height=360)
    assert g_wide["shape_category"] in ("WIDE", "VERY_WIDE")
    assert g_wide["relative_size"] == "LARGE"

def test_canonical_object_intelligence_record():
    tracker = ObjectTracker(confirmation_frames=1)
    
    det = {
        "class_name": "bottle",
        "confidence": 0.84,
        "bbox": [210, 120, 390, 320],
        "norm_bbox": [0.33, 0.33, 0.61, 0.89],
        "center": [300.0, 220.0],
        "norm_center": [0.47, 0.61],
        "width_px": 180.0,
        "height_px": 200.0,
        "frame_width": 640,
        "frame_height": 360
    }

    tracks = tracker.update([det], timestamp=1.0)
    assert len(tracks) == 1
    t = tracks[0]
    rec = t.to_dict()

    # Verify all Canonical Object Intelligence fields
    assert "track_id" in rec
    assert "detector_class" in rec
    assert "recognized_name" in rec
    assert "recognition_state" in rec
    assert "confidence" in rec
    assert "bbox" in rec
    assert "center" in rec
    assert "position" in rec
    assert "shape" in rec
    assert "size" in rec
    assert "motion" in rec
    assert "proximity" in rec
    assert "path_relevance" in rec
    assert "ocr" in rec
    assert "risk" in rec
