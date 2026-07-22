"""
Screenshot Capture & Image Preprocessing Service.
"""

from typing import Dict, Any
from vision_model import analyze_screenshot


class ScreenshotService:
    @staticmethod
    def capture(url: str, image_path: str = "") -> Dict[str, Any]:
        return analyze_screenshot(image_path, url)
