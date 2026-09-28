"""
Graph neural network service.

The saved weights were trained on synthetic template graphs, so no GNN probability is
returned. Graph statistics of the supplied HTML are reported instead.
"""

from typing import Any, Dict

from component_status import unavailable
from multimodal_fusion import analyse_dom


class GNNService:
    @staticmethod
    def predict(html_content: str, url: str) -> Dict[str, Any]:
        return {"model": unavailable("gnn"), "dom_graph": analyse_dom(url, html_content)}
