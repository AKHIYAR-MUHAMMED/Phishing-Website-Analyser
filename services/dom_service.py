"""
HTML DOM structural statistics service (built from request-supplied HTML only).
"""

from typing import Any, Dict

from multimodal_fusion import analyse_dom


class DOMService:
    @staticmethod
    def parse(html_content: str, url: str) -> Dict[str, Any]:
        return analyse_dom(url, html_content)
