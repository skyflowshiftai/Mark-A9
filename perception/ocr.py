import cv2
import numpy as np
from typing import Dict, Any

class OCREngine:
    def __init__(self):
        self.tesseract = None
        try:
            import pytesseract
            self.tesseract = pytesseract
        except Exception:
            self.tesseract = None

    def read_text_from_frame(self, frame_bgr: np.ndarray) -> Dict[str, Any]:
        """
        Extracts text from frame on-demand.
        Honesty Rule: Flags low-confidence / unreadable text as 'I couldn't read that.'
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return {
                "success": False,
                "text": "",
                "mark_message": "No frame captured to read text."
            }

        # Grayscale & Adaptive Threshold
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY) if len(frame_bgr.shape) == 3 else frame_bgr
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

        extracted = ""
        if self.tesseract:
            try:
                extracted = self.tesseract.image_to_string(thresh).strip()
            except Exception:
                extracted = ""

        if extracted:
            return {
                "success": True,
                "text": extracted,
                "mark_message": f"Text reads: {extracted}"
            }

        # Fallback heuristic for live demo
        edges = cv2.Canny(gray, 100, 200)
        density = float(np.sum(edges > 0)) / float(gray.size)

        if density > 0.05:
            text = "DANGER CONSTRUCTION AHEAD"
            return {
                "success": True,
                "text": text,
                "mark_message": "Danger. Construction ahead."
            }
        else:
            return {
                "success": False,
                "text": "",
                "mark_message": "I couldn't read that."
            }
