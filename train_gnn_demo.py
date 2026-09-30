"""
Retrains PhishingGNN on the REAL, small Phase 3 dataset (E:\\Final Project\\phishguard-phase3-pilot)
instead of train_gnn.py's fixed 15-node synthetic template. Does not touch train_gnn.py or the
original gnn_model.pt — writes a separate gnn_model_demo.pt plus a metrics.json.

Honesty note (this is small): the eligible pool currently has 28 real labeled samples total
(train=12, val=14, test=2, per Phase 3's own frozen split). This is far too small to claim any
generalizing accuracy. Metrics below are reported anyway, exactly as computed, with that caveat
attached in metrics.json itself — never presented as a validated model.
"""
import csv
import json
import random
from pathlib import Path

import torch
import torch.nn as nn

from gnn_model import PhishingGNN, parse_dom_to_graph

PILOT_DIR = Path(r"E:\Final Project\phishguard-phase3-pilot")
SEED = 42


def _load_split_rows():
    with open(PILOT_DIR / "derived" / "selection_pilot2.csv", newline="", encoding="utf-8") as f:
        selection_rows = list(csv.DictReader(f))
    with open(PILOT_DIR / "manifest.csv", newline="", encoding="utf-8") as f:
        manifest_rows = list(csv.DictReader(f))
    manifest_by_url = {r["normalized_url"]: r for r in manifest_rows if r["crawl_status"] == "ok"}

    by_split = {"train": [], "val": [], "test": []}
    for row in selection_rows:
        if row["eligible"] != "True" or row["split"] not in by_split:
            continue
        manifest_row = manifest_by_url.get(row["normalized_url"])
        if not manifest_row or not manifest_row.get("html_snapshot_path"):
            continue
        html_path = PILOT_DIR / "raw" / "html" / Path(manifest_row["html_snapshot_path"]).name
        if not html_path.exists():
            continue
        html = html_path.read_text(encoding="utf-8", errors="replace")
        by_split[row["split"]].append({
            "url": manifest_row.get("final_url") or manifest_row["url"],
            "html": html,
            "label": int(row["label"]),
        })
    return by_split


def _evaluate(model, samples):
    if not samples:
        return {"n": 0}
    correct = 0
    losses = []
    loss_fn = nn.BCELoss()
    with torch.no_grad():
        for s in samples:
            x, edge_index, _ = parse_dom_to_graph(s["html"], s["url"])
            _, prob = model.extract_graph_embedding(x, edge_index)
            target = torch.tensor([[float(s["label"])]])
            losses.append(loss_fn(prob, target).item())
            pred = 1 if prob.item() >= 0.5 else 0
            correct += int(pred == s["label"])
    return {
        "n": len(samples),
        "accuracy": correct / len(samples),
        "mean_bce_loss": sum(losses) / len(losses),
    }


def main():
    random.seed(SEED)
    torch.manual_seed(SEED)

    by_split = _load_split_rows()
    train_samples = by_split["train"]
    print(f"train={len(train_samples)} val={len(by_split['val'])} test={len(by_split['test'])}")
    if len(train_samples) < 4:
        raise SystemExit("Too few real training samples to proceed.")

    model = PhishingGNN()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCELoss()

    epochs = 30
    history = []
    for epoch in range(epochs):
        random.shuffle(train_samples)
        epoch_loss = 0.0
        for s in train_samples:
            x, edge_index, _ = parse_dom_to_graph(s["html"], s["url"])
            optimizer.zero_grad()
            _, prob = model.extract_graph_embedding(x, edge_index)
            target = torch.tensor([[float(s["label"])]])
            loss = loss_fn(prob, target)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
        history.append(epoch_loss / len(train_samples))
        if epoch % 5 == 0 or epoch == epochs - 1:
            print(f"epoch {epoch}: mean_train_loss={history[-1]:.4f}")

    model.eval()
    train_metrics = _evaluate(model, train_samples)
    val_metrics = _evaluate(model, by_split["val"])
    test_metrics = _evaluate(model, by_split["test"])

    weights_path = Path(__file__).parent / "gnn_model_demo.pt"
    torch.save(model.state_dict(), weights_path)

    metrics = {
        "HONESTY_NOTE": (
            "Trained on N=12 real webpage DOM graphs from the Phase 3 pilot collection "
            "(8 phishing, 4 benign) using train_gnn_demo.py, not the synthetic 15-node template "
            "train_gnn.py used. This dataset is far too small to support a generalization claim. "
            "Metrics below are reported exactly as computed, for demo transparency only, and "
            "must never be cited as validated model performance."
        ),
        "seed": SEED,
        "epochs": epochs,
        "train_loss_curve": history,
        "train_metrics": train_metrics,
        "val_metrics": val_metrics,
        "test_metrics": test_metrics,
    }
    metrics_path = Path(__file__).parent / "gnn_model_demo_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Saved weights to {weights_path}")
    print(f"Saved metrics to {metrics_path}")
    print(json.dumps({"train": train_metrics, "val": val_metrics, "test": test_metrics}, indent=2))


if __name__ == "__main__":
    main()
