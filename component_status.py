"""
Single source of truth for the honest status of every system component.

Status values:
- "available"        genuine computation on real input
- "heuristic"        genuine computation, but a hand-written rule (not a learned model)
- "unavailable"      disabled or not yet built; never returns a score
- "not_implemented"  no implementation exists in this repository
- "not_evaluated"    no evaluation on real held-out data has been run

A component that is not "available" must never contribute a number to a verdict.
"""

from typing import Any, Dict, List

AVAILABLE = "available"
HEURISTIC = "heuristic"
UNAVAILABLE = "unavailable"
NOT_IMPLEMENTED = "not_implemented"
NOT_EVALUATED = "not_evaluated"

REASONS: Dict[str, str] = {
    "crawler": (
        "Live URL fetching is not implemented yet (planned: Phase 2). "
        "Only HTML supplied in the request is analysed."
    ),
    "gnn": (
        "The saved GNN weights (gnn_model.pt) were trained on synthetic template graphs, "
        "not real webpage DOMs, so the model output is not a valid phishing probability. "
        "Retraining on real data is planned (Phase 5)."
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
        "No model has been evaluated on real held-out data. Metrics will be reported only from "
        "generated evaluation artifacts (planned: Phase 10)."
    ),
    "dataset": (
        "No genuinely collected dataset exists yet. The committed CSV files contain label-conditional "
        "random features and must not be used for training or evaluation (CLAUDE.md section 6). "
        "Collection is planned (Phase 3)."
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
        {"id": "crawler", "name": "Web crawler", "status": UNAVAILABLE, "reason": REASONS["crawler"]},
        {"id": "url_features", "name": "URL lexical features", "status": AVAILABLE,
         "reason": "Computed from the URL string (observed features, not a classifier)."},
        {"id": "dom_graph", "name": "DOM graph construction", "status": AVAILABLE,
         "reason": "Built from request-supplied HTML. Known limitations are listed in CLAUDE.md section 5.1."},
        {"id": "js_indicators", "name": "JavaScript regex indicators", "status": HEURISTIC,
         "reason": "Regex pattern counts over the HTML; not an AST parser and not a classifier."},
        {"id": "gnn", "name": "Graph neural network", "status": UNAVAILABLE, "reason": REASONS["gnn"]},
        {"id": "llm", "name": "LLM API clients", "status": AVAILABLE if llm_ready else UNAVAILABLE,
         "reason": ("API key configured for: " + ", ".join(llm_ready)) if llm_ready
         else "No LLM API key is configured, so no language-model output is produced."},
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
