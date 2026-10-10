"""
Single source of truth for the honest status of every system component.

Status values:
- "available"        genuine computation on real input
- "heuristic"        genuine computation, but a hand-written rule (not a learned model)
- "experimental"      genuine computation exists and runs (elsewhere in the project, e.g. the
                      /demo pipeline), but on too little real data to call it validated/production
- "not_configured"    the integration exists but no credential/key is present to run it
- "unavailable"      disabled or not yet built; never returns a score
- "not_implemented"  no implementation exists in this repository
- "not_evaluated"    no evaluation on real held-out data has been run

A component that is not "available" must never contribute a number to a verdict.
"""

from typing import Any, Dict, List

AVAILABLE = "available"
HEURISTIC = "heuristic"
EXPERIMENTAL = "experimental"
NOT_CONFIGURED = "not_configured"
UNAVAILABLE = "unavailable"
NOT_IMPLEMENTED = "not_implemented"
NOT_EVALUATED = "not_evaluated"

REASONS: Dict[str, str] = {
    "crawler": (
        "Fetches the URL with a single GET request (timeout, redirect-count and response-size "
        "limits apply; no forms are submitted; see crawler/fetcher.py). Used only when the "
        "request supplies no HTML; request-supplied HTML is always used instead, unchanged."
    ),
    "gnn": (
        "This endpoint (/api/v1/scan) reports DOM-graph structure statistics only (see "
        "dom_graph above) and does not run a GNN forward pass; the original weights "
        "(gnn_model.pt) were trained on synthetic template graphs, not real webpage DOMs, so "
        "they would not produce a valid phishing probability if used. A separate, real GNN "
        "forward pass is active in the live /demo pipeline (analysis_pipeline.py), using a "
        "checkpoint (gnn_model_demo.pt) retrained on real Phase 3 webpage DOM graphs — but on "
        "only 12 real training samples (a HISTORICAL checkpoint), so that output is for "
        "demonstration only and does not establish generalization or production accuracy; it has "
        "been observed to give a very high signal to a harmless local test page. Open /demo to "
        "exercise it live; this Scanner tab does not yet call it."
    ),
    "visual": (
        "Screenshot, ViT, Phishpedia, VisualPhishNet, pHash/FAISS and OCR outputs were simulated "
        "(keyword rules and random vectors). No visual model exists; the component is disabled."
    ),
    "bert": (
        "The BERT component was untrained and its score was keyword-based. Disabled; "
        "a single language-model branch is planned (Phase 6)."
    ),
    "classical_ml": (
        "No classical ML model (Random Forest, XGBoost, CatBoost, ...) is trained; previous scores "
        "were keyword rules. Honest baselines are planned (Phase 7)."
    ),
    "anomaly": "Autoencoder / Isolation Forest scores were fabricated. Disabled; no anomaly model exists.",
    "whois_dns": "WHOIS and DNS outputs were fabricated from URL keywords; no real lookup is performed. Disabled.",
    "ssl": "SSL/TLS outputs were fabricated from URL keywords; no certificate is inspected. Disabled.",
    "threat_intel": "Threat-intelligence results were fabricated from URL keywords; no feed is queried. Disabled.",
    "fusion": (
        "No trained fusion model exists. The previous hand-weighted average of simulated scores "
        "was removed. A learned fusion model is planned (Phase 8)."
    ),
    "explanation": "No genuine explanation method is implemented yet (planned: Phase 9).",
    "evaluation": (
        "No model has been evaluated on real held-out data using this project's formal evaluation "
        "pipeline (planned: Phase 10). HISTORICAL: raw observations from the one-off small-sample "
        "GNN retrain (train n=12, val n=14, test n=1 — see gnn_model_demo_metrics.json) are kept "
        "unchanged for transparency, but these are training observations only, not a held-out "
        "evaluation, and must never be cited as accuracy, precision, recall, F1, ROC-AUC or any "
        "validated performance metric, nor combined with any future evaluation on a later dataset "
        "version."
    ),
    "dataset": (
        "A real Phase 3 dataset has been collected (dataset version v5, stored locally in "
        "phishguard-phase3-pilot/ and not committed to this repository) from PhishTank/OpenPhish "
        "(phishing) and Tranco (benign) with real crawled HTML snapshots. Per its generated dataset "
        "card (DATASET_CARD.md): 679 eligible samples (331 phishing, 348 benign), domain-grouped "
        "splits train=408 (199/209), val=135 (66/69), test=136 (66/70), with zero cross-split "
        "domain leakage and zero label conflicts. A later snapshot-integrity re-check found that one "
        "of those rows (in the train split) no longer verifies, so the integrity-verified pool is 678 "
        "(330 phishing, 348 benign); that row has not been replaced or reassigned, and the card and "
        "the frozen v5 split files are unchanged. Dataset collection is complete, but no model has "
        "yet been retrained or evaluated on it: the GNN checkpoint used in /demo was trained "
        "earlier on only 12 samples from the original pilot. This endpoint does not yet compute "
        "live statistics from the dataset. The previously committed CSV files (data/*.csv) remain "
        "label-conditional random features and must never be used for training or evaluation "
        "(CLAUDE.md section 6)."
    ),
    "benchmark": (
        "Previously returned numbers copied from another paper (Jarczewski et al., MDPI 2026). "
        "They are not this project's results and belong only in the literature review."
    ),
    "screenshot_datasets": "Previously returned hard-coded metadata; no screenshot data is downloaded.",
    "scan_history": (
        "Scan persistence is not implemented yet (planned: Phase 13). The committed phishguard_x.db "
        "contains seeded demonstration rows, which are not shown."
    ),
    "auth": "Authentication is not implemented. The previous endpoint issued a token for any credentials.",
    "retraining": (
        "The retraining pipeline trained on the synthetic dataset and logged literal metrics. Disabled."
    ),
    "llm_aggregate": (
        "No calibrated aggregation of language-model outputs exists. The previous 'Bayesian consensus' "
        "used literal reliabilities. A single semantic branch is planned (Phase 6)."
    ),
}


def unavailable(component: str, reason: str = None, status: str = UNAVAILABLE) -> Dict[str, Any]:
    """Standard payload for a component that must not produce a score."""
    return {
        "component": component,
        "status": status,
        "reason": reason or REASONS.get(component, "Component unavailable."),
    }


def component_registry() -> List[Dict[str, Any]]:
    """Status of every component, as reported to the dashboard."""
    from llm_ensemble import get_llm_orchestrator

    llm_engines = get_llm_orchestrator().list_engines()
    llm_ready = [e["name"] for e in llm_engines if e["implemented"] and e["api_key_configured"]]

    return [
        {"id": "crawler", "name": "Web crawler", "status": AVAILABLE, "reason": REASONS["crawler"]},
        {"id": "url_features", "name": "URL lexical features", "status": AVAILABLE,
         "reason": "Computed from the URL string (observed features, not a classifier)."},
        {"id": "dom_graph", "name": "DOM graph construction", "status": AVAILABLE,
         "reason": "Built from request-supplied HTML. Known limitations are listed in CLAUDE.md section 5.1."},
        {"id": "js_indicators", "name": "JavaScript regex indicators", "status": HEURISTIC,
         "reason": "Regex pattern counts over the HTML; not an AST parser and not a classifier."},
        {"id": "gnn", "name": "Graph neural network", "status": EXPERIMENTAL, "reason": REASONS["gnn"]},
        {"id": "llm", "name": "LLM API clients", "status": AVAILABLE if llm_ready else NOT_CONFIGURED,
         "reason": ("API key configured for: " + ", ".join(llm_ready)) if llm_ready
         else "No LLM API key is configured, so no language-model output is produced. The /demo "
              "pipeline's semantic score comes from a disclosed rule-based heuristic instead, "
              "never presented as an LLM result."},
        {"id": "visual", "name": "Visual / screenshot models", "status": UNAVAILABLE, "reason": REASONS["visual"]},
        {"id": "bert", "name": "BERT encoder", "status": UNAVAILABLE, "reason": REASONS["bert"]},
        {"id": "classical_ml", "name": "Classical ML baselines", "status": UNAVAILABLE, "reason": REASONS["classical_ml"]},
        {"id": "anomaly", "name": "Anomaly detection", "status": UNAVAILABLE, "reason": REASONS["anomaly"]},
        {"id": "whois_dns", "name": "WHOIS / DNS", "status": UNAVAILABLE, "reason": REASONS["whois_dns"]},
        {"id": "ssl", "name": "SSL / TLS inspection", "status": UNAVAILABLE, "reason": REASONS["ssl"]},
        {"id": "threat_intel", "name": "Threat intelligence", "status": UNAVAILABLE, "reason": REASONS["threat_intel"]},
        {"id": "fusion", "name": "Multimodal fusion", "status": UNAVAILABLE, "reason": REASONS["fusion"]},
        {"id": "explanation", "name": "Explainability", "status": UNAVAILABLE, "reason": REASONS["explanation"]},
        {"id": "evaluation", "name": "Evaluation metrics", "status": NOT_EVALUATED, "reason": REASONS["evaluation"]},
        {"id": "dataset", "name": "Training dataset", "status": UNAVAILABLE, "reason": REASONS["dataset"]},
        {"id": "scan_history", "name": "Scan history", "status": UNAVAILABLE, "reason": REASONS["scan_history"]},
    ]
