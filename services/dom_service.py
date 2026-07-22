"""
HTML DOM Structural Parsing Service.
"""

from typing import Dict, Any
from dataset_loader import extract_dom_graph_features


class DOMService:
    @staticmethod
    def parse(html_content: str, url: str) -> Dict[str, Any]:
        return extract_dom_graph_features(html_content, url)
