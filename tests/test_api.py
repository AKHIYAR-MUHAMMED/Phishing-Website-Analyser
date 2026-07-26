"""
PhishGuard-X Service-Oriented API Gateway Automated Test Suite.
Tests endpoints:
- POST /models/gnn/predict
- POST /models/vit/predict
- POST /models/bert/predict
- POST /models/fusion/predict
- POST /api/v1/scan
- GET /dashboard/system
- GET /dashboard/datasets
- GET /api/v1/health
"""

from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "OPERATIONAL"


def test_dedicated_gnn_model_endpoint():
    payload = {"url": "http://paypal-security-check.com/login", "html_content": "<input type='password'>"}
    response = client.post("/models/gnn/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "gnn_threat_score" in data
    assert "PyTorch" in data["model_name"]


def test_dedicated_vit_model_endpoint():
    payload = {"url": "http://paypal-security-check.com/login", "image_path": ""}
    response = client.post("/models/vit/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "vit_threat_score" in data
    assert "detected_logo" in data


def test_dedicated_bert_model_endpoint():
    payload = {"url": "http://paypal-security-check.com/login"}
    response = client.post("/models/bert/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "bert_threat_score" in data
    assert "semantic_intent_verdict" in data


def test_dedicated_fusion_model_endpoint():
    payload = {"url": "http://paypal-security-check.com/login", "html_content": ""}
    response = client.post("/models/fusion/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "overall_threat_score" in data
    assert "PHISHING" in data["final_verdict"]


def test_central_api_gateway_scan_pipeline():
    payload = {"url": "http://paypal-security-verification-center.com/signin?account_login=update", "html_content": ""}
    response = client.post("/api/v1/scan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "final_verdict" in data
    assert data["overall_threat_score"] > 50.0
    assert "xai_evidence_matrix" in data


def test_dashboard_system_endpoint():
    response = client.get("/dashboard/system")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert data["active_modalities"] == 9


def test_dashboard_datasets_endpoint():
    response = client.get("/dashboard/datasets")
    assert response.status_code == 200
    data = response.json()
    assert data["total_samples"] == 10000
    assert data["test_accuracy"] == "100.00%"


def test_llm_list_endpoint():
    response = client.get("/models/llm/list")
    assert response.status_code == 200
    data = response.json()
    assert data["total_engines"] == 10
    assert len(data["engines"]) == 10


def test_single_llm_endpoint():
    payload = {"url": "http://paypal-security-check.com/login"}
    response = client.post("/models/llm/gpt55/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "threat_score" in data
    assert "verdict" in data


def test_compare_llm_endpoint():
    payload = {"engine_ids": ["gpt55", "claude4opus", "deepseekv3"], "url": "http://paypal-security-check.com/login"}
    response = client.post("/models/llm/compare", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["compared_engines_count"] == 3
    assert "comparison_verdict" in data


def test_rf_model_endpoint():
    payload = {"url": "http://paypal-security-check.com/login"}
    response = client.post("/models/rf/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["model_name"] == "Random Forest Classifier"


def test_catboost_model_endpoint():
    payload = {"url": "http://paypal-security-check.com/login"}
    response = client.post("/models/catboost/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["model_name"] == "CatBoost Gradient Boosting"


def test_autoencoder_model_endpoint():
    payload = {"url": "http://paypal-security-check.com/login"}
    response = client.post("/models/autoencoder/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "anomaly_score" in data


def test_xai_model_endpoint():
    payload = {"url": "http://paypal-security-check.com/login"}
    response = client.post("/models/xai/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_batch_scan_endpoint():
    payload = {"urls": ["http://paypal-security-check.com/login", "https://github.com/torvalds/linux"]}
    response = client.post("/api/v1/batch-scan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_scanned"] == 2
    assert len(data["batch_results"]) == 2

