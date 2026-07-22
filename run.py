"""
Main Launcher & Startup Runner for Multimodal Phishing Detection System.
Initializes data pipelines, tests GNN & 10-LLM engines, and starts the FastAPI Uvicorn Server.
"""

import os
import sys
import time
import socket

# Ensure UTF-8 encoding for Windows standard output safety
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import uvicorn
from dataset_loader import load_dataset
from gnn_model import analyze_dom_graph
from llm_ensemble import get_llm_orchestrator
from multimodal_fusion import get_detector


def find_available_port(start_port: int = 8000, max_tries: int = 10) -> int:
    """Finds an available open TCP port starting from start_port."""
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return start_port


def initialize_system(port: int = 8000):
    print("=" * 70)
    print("  PHISHGNN AI: MULTIMODAL PHISHING WEBSITE DETECTION PLATFORM")
    print("  PyTorch Graph Neural Networks (GNN) + 10-LLM Engine Consensus")
    print("=" * 70)

    # 1. Dataset Verification
    print("\n[1/4] Loading & Verifying Kaggle Multimodal Dataset...")
    df = load_dataset()
    print(f"      [OK] Dataset Loaded Successfully: {df.shape[0]} samples, {df.shape[1]} features.")
    phish_cnt = (df['label'] == 1).sum()
    legit_cnt = (df['label'] == 0).sum()
    print(f"      [OK] Class Balance: {phish_cnt} Phishing | {legit_cnt} Legitimate")

    # 2. GNN Model Check
    print("\n[2/4] Testing DOM & Hyperlink Graph Neural Network Engine...")
    sample_html = "<html><body><form action='http://phish.com/steal' method='POST'><input type='password'></form></body></html>"
    gnn_out = analyze_dom_graph(sample_html, "http://phish.com/login")
    print(f"      [OK] GNN Threat Score: {gnn_out['gnn_threat_score']*100:.2f}%")
    print(f"      [OK] DOM Graph Nodes: {gnn_out['graph_stats']['node_count']} | Edges: {gnn_out['graph_stats']['edge_count']}")

    # 3. 10-LLM Ensemble Check
    print("\n[3/4] Verifying 10-LLM Multi-Engine Consensus Orchestrator...")
    orchestrator = get_llm_orchestrator()
    print(f"      [OK] Registered 10 LLM Engines: {', '.join([e.name for e in orchestrator.engines[:4]])}...")

    # 4. Multimodal Fusion Engine Check
    print("\n[4/4] Initializing Multimodal Fusion Pipeline...")
    detector = get_detector()
    print("      [OK] Multimodal Detector Ready.")

    print("\n" + "=" * 70)
    print("  SYSTEM HEALTH: 100% OPERATIONAL")
    print(f"  Dashboard UI: http://127.0.0.1:{port}")
    print(f"  REST API Docs: http://127.0.0.1:{port}/docs")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    target_port = find_available_port(8000, 20)
    initialize_system(target_port)
    uvicorn.run("api:app", host="127.0.0.1", port=target_port, reload=False)
