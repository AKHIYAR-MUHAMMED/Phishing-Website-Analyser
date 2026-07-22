"""
PyTorch Vision Transformer (ViT) Dedicated Microservice.
Exposes POST /models/vit/predict endpoint analyzing webpage screenshot patch embeddings.
"""

from typing import Dict, Any
from vision_model import analyze_screenshot, get_vit_model


class ViTService:
    @staticmethod
    def predict(url: str, image_path: str = "") -> Dict[str, Any]:
        model = get_vit_model()
        res = analyze_screenshot(image_path, url)
        return {
            "model_name": "PyTorch Vision Transformer (ViT)",
            "vit_threat_score": res["vit_threat_score"],
            "detected_logo": res["detected_logo"],
            "form_layout_verdict": res["form_layout_verdict"],
            "ocr_extracted_text": res["ocr_extracted_text"]
        }
