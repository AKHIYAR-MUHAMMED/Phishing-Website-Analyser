"""
OCR Visual Text Overlay Extraction Service.
"""

from typing import Dict, Any, List
from vision_model import analyze_screenshot

SENSITIVE_KEYWORDS = {"login", "signin", "password", "verify", "account", "bank", "security", "credential", "update"}


class OCRService:
    """Microservice interface for OCR visual text extraction and credential phishing analysis."""

    @staticmethod
    def extract_text(url: str, image_path: str = "") -> List[str]:
        """Extracts text tokens from webpage screenshot OCR overlay."""
        res = analyze_screenshot(image_path, url)
        return res.get("ocr_extracted_text", ["Sign In", "Account Verification"])

    @staticmethod
    def analyze_text(url: str, image_path: str = "") -> Dict[str, Any]:
        """Analyzes OCR extracted text for sensitive credential harvester keywords."""
        extracted_tokens = OCRService.extract_text(url, image_path)
        lowered_text = " ".join(extracted_tokens).lower()
        matched_keywords = [kw for kw in SENSITIVE_KEYWORDS if kw in lowered_text]

        return {
            "extracted_tokens": extracted_tokens,
            "matched_sensitive_keywords": matched_keywords,
            "credential_harvester_risk": len(matched_keywords) > 0,
            "keyword_density_score": round(len(matched_keywords) / max(1, len(extracted_tokens)), 2)
        }

