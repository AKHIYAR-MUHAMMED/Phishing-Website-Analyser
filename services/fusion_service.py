"""
Multimodal Fusion Network Dedicated Microservice.
Exposes POST /models/fusion/predict endpoint fusing output scores from GNN, ViT, BERT, Ensemble, and LLMs.
"""

from typing import Dict, Any
from multimodal_fusion import get_detector


class FusionService:
    @staticmethod
    async def predict(url: str, html_content: str = "", image_path: str = "") -> Dict[str, Any]:
        detector = get_detector()
        return await detector.detect_url(url, html_content, image_path)
