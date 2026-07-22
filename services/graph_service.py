"""
DOM Graph Structure & Network Topology Service.
"""

from typing import Dict, Any
from gnn_model import analyze_dom_graph


class GraphService:
    @staticmethod
    def generate_graph(html_content: str, url: str) -> Dict[str, Any]:
        return analyze_dom_graph(html_content, url)
