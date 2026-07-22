"""
PyTorch Graph Attention Network (GNN/GAT) Dedicated Microservice.
Exposes POST /models/gnn/predict endpoint processing graph node matrices X and edge indices E.
"""

from typing import Dict, Any
from gnn_model import analyze_dom_graph, get_gnn_model


class GNNService:
    @staticmethod
    def predict(html_content: str, url: str) -> Dict[str, Any]:
        model = get_gnn_model()
        res = analyze_dom_graph(html_content, url)
        return {
            "model_name": "PyTorch Graph Attention Network (GNN/GAT)",
            "gnn_threat_score": float(res["gnn_threat_score"] * 100.0),
            "graph_stats": res["graph_stats"],
            "structural_indicators": res["structural_indicators"]
        }
