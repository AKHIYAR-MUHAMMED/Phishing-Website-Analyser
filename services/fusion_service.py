"""
Scan pipeline service. Runs multimodal_fusion once; returns no verdict until a trained fusion
model exists.
"""

from typing import Any, Dict

from multimodal_fusion import get_detector


class FusionService:
    @staticmethod
    async def predict(url: str, html_content: str = "", image_path: str = "") -> Dict[str, Any]:
        return await get_detector().detect_url(url, html_content, image_path)
