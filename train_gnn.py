"""
PyTorch Graph Neural Network (GNN) Multi-Dataset Training & Test Evaluation Engine.
Equally trains & evaluates PhishingGNN on 4 merged Kaggle dataset sources:
1. duygujones/website-phishing-detection-ml-project
2. waawerufidelis/website-phishing
3. kragg033/phishing-detection
4. sindhi586/phishing-domain-detection-project

Calculates held-out Test Accuracy, Precision, Recall, F1-Score and saves model weights to gnn_model.pt.
"""

import os
import sys
import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import numpy as np
from typing import Tuple, Dict, List

from dataset_loader import load_dataset
from gnn_model import PhishingGNN, NODE_FEATURE_DIM


def convert_df_to_graphs(sub_df: pd.DataFrame) -> List[Tuple[torch.Tensor, torch.Tensor, float, str]]:
    """
    Rapidly converts dataframe rows into PyTorch graph tuples (X, E, y, source).
    """
    node_count = 15
    edges = [(0, 1), (1, 0), (1, 2), (2, 1), (1, 3), (3, 1)]
    for i in range(4, node_count):
        edges.append((0, i))
        edges.append((i, 0))
    edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()

    graphs = []
    labels = sub_df['label'].values
    sources = sub_df['dataset_source'].values
    sfh_vals = sub_df.get('sfh_external', pd.Series(np.zeros(len(sub_df)))).values
    iframe_vals = sub_df.get('iframe_hidden', pd.Series(np.zeros(len(sub_df)))).values
    anchor_vals = sub_df.get('url_of_anchor_ratio', pd.Series(np.zeros(len(sub_df)))).values

    for i in range(len(sub_df)):
        x = torch.zeros((node_count, NODE_FEATURE_DIM), dtype=torch.float32)
        is_phish = (labels[i] == 1)

        x[0, 0] = 1.0
        x[1, 1] = 1.0
        x[1, 11] = float(sfh_vals[i])
        x[1, 12] = float(iframe_vals[i])

        x[2, 2] = 1.0
        x[2, 11] = float(sfh_vals[i])

        x[3, 3] = 1.0

        for n in range(4, node_count):
            x[n, (n % 5) + 4] = 1.0
            x[n, 10] = (n / node_count)
            x[n, 11] = float(anchor_vals[i])

        graphs.append((x, edge_index, float(labels[i]), str(sources[i])))

    return graphs


def evaluate_test_set(model: nn.Module, test_graphs: List[Tuple]) -> Dict[str, float]:
    """
    Evaluates PyTorch GNN model performance on held-out test graphs.
    Returns Accuracy, Precision, Recall, and F1-Score metrics.
    """
    model.eval()
    tp = 0
    fp = 0
    tn = 0
    fn = 0
    per_source_stats = {}

    with torch.no_grad():
        for x, edge_index, target, src in test_graphs:
            _, prob = model.extract_graph_embedding(x, edge_index)
            pred = 1.0 if prob.item() >= 0.5 else 0.0

            if src not in per_source_stats:
                per_source_stats[src] = {"correct": 0, "total": 0}
            per_source_stats[src]["total"] += 1

            if pred == target:
                per_source_stats[src]["correct"] += 1

            if pred == 1.0 and target == 1.0: tp += 1
            elif pred == 1.0 and target == 0.0: fp += 1
            elif pred == 0.0 and target == 0.0: tn += 1
            elif pred == 0.0 and target == 1.0: fn += 1

    acc = (tp + tn) / max(1, tp + tn + fp + fn) * 100.0
    prec = tp / max(1, tp + fp) * 100.0
    rec = tp / max(1, tp + fn) * 100.0
    f1 = (2 * prec * rec) / max(0.001, prec + rec)

    return {
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "per_source": per_source_stats
    }


def train_and_evaluate_model(epochs: int = 5, train_ratio: float = 0.8):
    print("=" * 75, flush=True)
    print("  PYTORCH GNN MULTI-DATASET TRAINING & EVALUATION ENGINE", flush=True)
    print("  Merged Sources: 4 Kaggle Datasets (Equal 25% Ratio)", flush=True)
    print("=" * 75, flush=True)

    df = load_dataset()
    total_samples = len(df)
    print(f"\n[1/4] Loaded Unified Merged Dataset: {total_samples} samples across 4 Kaggle sources", flush=True)

    # 80/20 Train/Test Split
    df_shuffled = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    train_size = int(total_samples * train_ratio)
    
    train_df = df_shuffled.iloc[:train_size]
    test_df = df_shuffled.iloc[train_size:]

    print(f"      [OK] Train Partition: {len(train_df)} samples (80%)", flush=True)
    print(f"      [OK] Test Partition:  {len(test_df)} samples (20%)", flush=True)

    # Sample representative graphs for rapid training & test evaluation
    train_sample = train_df.sample(n=min(1000, len(train_df)), random_state=42)
    test_sample = test_df.sample(n=min(400, len(test_df)), random_state=42)

    train_graphs = convert_df_to_graphs(train_sample)
    test_graphs = convert_df_to_graphs(test_sample)

    model = PhishingGNN(input_dim=NODE_FEATURE_DIM, hidden_dim=64, embedding_dim=64)
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.BCELoss()

    print("\n[2/4] Training PyTorch Graph Neural Network...", flush=True)
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        correct = 0

        for x, edge_index, target, _ in train_graphs:
            y_true = torch.tensor([[target]], dtype=torch.float32)

            optimizer.zero_grad()
            _, prob = model.extract_graph_embedding(x, edge_index)

            loss = criterion(prob, y_true)
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            pred = 1.0 if prob.item() >= 0.5 else 0.0
            if pred == target:
                correct += 1

        avg_loss = total_loss / len(train_graphs)
        acc = (correct / len(train_graphs)) * 100.0
        print(f"      Epoch [{epoch:02d}/{epochs:02d}] - Training Loss: {avg_loss:.4f} | Training Acc: {acc:.2f}%", flush=True)

    # Held-Out Test Evaluation
    print("\n[3/4] Evaluating Held-Out Test Performance (20% Split)...", flush=True)
    metrics = evaluate_test_set(model, test_graphs)

    print(f"      ==========================================", flush=True)
    print(f"      HELD-OUT TEST EVALUATION METRICS:", flush=True)
    print(f"      ==========================================", flush=True)
    print(f"      - Test Accuracy:   {metrics['accuracy']:.2f}%", flush=True)
    print(f"      - Test Precision:  {metrics['precision']:.2f}%", flush=True)
    print(f"      - Test Recall:     {metrics['recall']:.2f}%", flush=True)
    print(f"      - Test F1-Score:   {metrics['f1_score']:.2f}%", flush=True)
    print(f"      - Confusion Matrix: TP={metrics['tp']}, FP={metrics['fp']}, TN={metrics['tn']}, FN={metrics['fn']}", flush=True)
    print(f"      ==========================================", flush=True)

    print("\n      Accuracy Breakdown Across 4 Kaggle Source Streams:", flush=True)
    for src_name, stats in metrics['per_source'].items():
        src_acc = (stats['correct'] / max(1, stats['total'])) * 100.0
        print(f"      -> [{src_name}]: {src_acc:.1f}% ({stats['correct']}/{stats['total']} test samples)", flush=True)

    # Save Model Weights
    model_save_path = os.path.join(os.path.dirname(__file__), "gnn_model.pt")
    torch.save(model.state_dict(), model_save_path)
    print(f"\n[4/4] Saved Trained Model Weights to {model_save_path}", flush=True)
    print("=" * 75 + "\n", flush=True)


if __name__ == "__main__":
    train_and_evaluate_model(epochs=5, train_ratio=0.8)
