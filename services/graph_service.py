"""
DOM graph structure service. Reports graph statistics only; no GNN output (see gnn_service).
"""

from typing import Any, Dict

from multimodal_fusion import analyse_dom


class GraphService:
    @staticmethod
    def generate_graph(html_content: str, url: str) -> Dict[str, Any]:
        return analyse_dom(url, html_content)
