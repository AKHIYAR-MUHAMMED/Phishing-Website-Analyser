"""
Screenshot service.

Disabled in the Phase 0 honesty pass: the previous analysis was simulated, and uploads were
written into the tracked data/ directory without being analysed.
"""

from typing import Any, Dict

from component_status import unavailable


class ScreenshotService:
    @staticmethod
    def capture(url: str, image_path: str = "") -> Dict[str, Any]:
        return unavailable("visual")

    @staticmethod
    def analyze_upload(**_kwargs) -> Dict[str, Any]:
        return unavailable("visual")
