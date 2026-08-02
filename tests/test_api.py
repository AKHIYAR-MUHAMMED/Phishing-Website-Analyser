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


def test_screenshot_datasets_endpoints():
    res1 = client.get("/api/v1/screenshot-datasets")
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["status"] == "CONNECTED"
    assert d1["active_connectors"] == 6

    res2 = client.post("/api/v1/screenshot-datasets/connect?dataset_key=all")
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["total_connected_screenshots"] == 102070


def test_dataset_export_and_validate_endpoints():
    res_export = client.get("/api/v1/datasets/export")
    assert res_export.status_code == 200
    d_exp = res_export.json()
    assert d_exp["status"] == "SUCCESSFULLY_PUBLISHED"
    assert "csv_path" in d_exp
    assert "json_path" in d_exp

    res_val = client.get("/api/v1/datasets/validate")
    assert res_val.status_code == 200
    d_val = res_val.json()
    assert d_val["status"] == "VALID"
    assert d_val["null_value_count"] == 0
    assert d_val["missing_screenshot_files"] == 0


def test_fetch_external_datasets_endpoint():
    response = client.post("/api/v1/datasets/fetch-external")
    assert response.status_code == 200
    data = response.json()
    assert "total_external_datasets" in data
    assert data["total_external_datasets"] == 3
    assert "datasets" in data
    assert "lnu_phish" in data["datasets"]
    assert "phish360" in data["datasets"]
    assert "huggingface_screenshots" in data["datasets"]


def test_screenshot_upload_endpoint():
    # Test uploading dummy PNG byte stream
    dummy_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    response = client.post(
        "/api/v1/screenshot/upload",
        files={"file": ("test_phishing_screenshot.png", dummy_png_bytes, "image/png")},
        data={"target_url": "http://paypal-security-check.com/login"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "vit_threat_score" in data
    assert "detected_logo" in data
    assert "file_info" in data
    assert data["file_info"]["filename"] == "test_phishing_screenshot.png"


def test_screenshot_analyze_endpoint():
    payload = {
        "url": "http://paypal-security-verification-center.com/signin",
        "image_path": "sample_paypal.png"
    }
    response = client.post("/api/v1/screenshot/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "vit_threat_score" in data
    assert "mdpi_2026_visual_suite" in data


