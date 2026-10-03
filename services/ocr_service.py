"""
OCR service. Disabled in the Phase 0 honesty pass: the previous text tokens were simulated.
"""

from typing import Any, Dict

from component_status import unavailable


class OCRService:
    @staticmethod
    def extract_text(url: str, image_path: str = "") -> Dict[str, Any]:
        return unavailable("visual")

    @staticmethod
    def analyze_text(url: str, image_path: str = "") -> Dict[str, Any]:
        return unavailable("visual")
