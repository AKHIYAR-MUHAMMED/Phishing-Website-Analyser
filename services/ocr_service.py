"""
OCR Visual Text Overlay Extraction Service.
"""

from typing import Dict, Any, List
from vision_model import analyze_screenshot


class OCRService:
    @staticmethod
    def extract_text(url: str, image_path: str = "") -> List[str]:
        res = analyze_screenshot(image_path, url)
        return res.get("ocr_extracted_text", ["Sign In", "Account Verification"])
