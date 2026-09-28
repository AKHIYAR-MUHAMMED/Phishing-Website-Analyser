"""
Regression guard: fabricated metrics, literal latencies and client-side fallbacks must not return.

Two checks:
1. Source files that produce API or dashboard output contain none of the known fabricated
   literals or fallback functions removed in the Phase 1 honesty pass.
2. API responses contain none of the old fabricated fields.
"""

import os
import re

import pytest
from fastapi.testclient import TestClient

from api import app

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OUTPUT_SOURCES = [
    "api.py", "component_status.py", "multimodal_fusion.py", "llm_ensemble.py", "database.py",
    "mlops_service.py", "run.py", "dashboard/app.js", "dashboard/index.html",
] + [os.path.join("services", f) for f in sorted(os.listdir(os.path.join(REPO_ROOT, "services"))) if f.endswith(".py")]

FORBIDDEN_PATTERNS = {
    "literal percentage metric": r"100\.00?%",
    "literal throughput": r"req/sec",
    "literal 14 ms latency": r"\b14\s?ms\b|latency_ms\"?\s*[:=]\s*14\b|default=14\b",
    "confidence floor": r"max\(\s*95",
    "fabricated confidence default": r"99\.8|99\.1|98\.2|96\.8|94\.5",
    "heuristic LLM fallback": r"evaluate_phishing_heuristics",
    "client-side fallback verdict": r"renderFallback|getSample10LLMEngines",
    "fabricated dataset size": r"102,?070|10,000|6,000",
    "unconditional health claim": r"100% OPERATIONAL",
}


@pytest.mark.parametrize("relpath", OUTPUT_SOURCES)
def test_source_has_no_fabricated_literals(relpath):
    with open(os.path.join(REPO_ROOT, relpath), encoding="utf-8") as f:
        text = f.read()
    hits = {name: re.findall(pattern, text) for name, pattern in FORBIDDEN_PATTERNS.items()}
    hits = {name: found for name, found in hits.items() if found}
    assert not hits, f"{relpath}: {hits}"


FORBIDDEN_RESPONSE_KEYS = {
    "confidence_score", "overall_threat_score", "threat_score", "scan_latency_ms", "test_accuracy",
    "test_precision", "test_recall", "test_f1_score", "roc_auc", "throughput", "risk_level",
    "attack_category", "recommended_actions", "consensus_threat_score", "bayesian_threat_score",
}


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _keys(item)


@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/v1/scan", {"url": "http://paypal-security-verification-center.com/signin",
                              "html_content": "<form><input type='password'></form>"}),
    ("post", "/api/v1/batch-scan", {"urls": ["http://paypal-verify.example", "https://github.com"]}),
    ("post", "/models/llm/predict", {"url": "http://paypal-verify.example"}),
    ("get", "/api/v1/metrics", None),
    ("get", "/dashboard/system", None),
    ("get", "/dashboard/datasets", None),
    ("get", "/dashboard/history", None),
])
def test_responses_contain_no_fabricated_fields(method, path, body):
    client = TestClient(app)
    response = client.post(path, json=body) if method == "post" else client.get(path)
    assert response.status_code == 200
    found = FORBIDDEN_RESPONSE_KEYS & set(_keys(response.json()))
    assert not found, f"{path} returned fabricated fields: {found}"
