"""
PhishGuard-X Service-Oriented Architecture (SOA) Test Runner.
Executes automated tests covering API Gateway Gateway Routing, Model Services, and Data Collectors.
"""

import sys

# Import tests
from tests.test_api import (
    test_health_check,
    test_dedicated_gnn_model_endpoint,
    test_dedicated_vit_model_endpoint,
    test_dedicated_bert_model_endpoint,
    test_dedicated_fusion_model_endpoint,
    test_central_api_gateway_scan_pipeline,
    test_dashboard_system_endpoint,
    test_dashboard_datasets_endpoint,
    test_llm_list_endpoint,
    test_single_llm_endpoint,
    test_compare_llm_endpoint,
    test_rf_model_endpoint,
    test_catboost_model_endpoint,
    test_autoencoder_model_endpoint,
    test_xai_model_endpoint,
    test_batch_scan_endpoint
)
from tests.test_models import (
    test_crawler_service,
    test_ssl_service,
    test_whois_and_dns_services,
    test_dom_and_js_services,
    test_vision_services,
    test_gnn_and_bert_model_services,
    test_ensemble_and_llm_model_services,
    test_fusion_and_xai_services,
    test_dataset_and_dashboard_services
)

def run_all_tests():
    print("=" * 75)
    print("  PHISHGUARD-X SERVICE-ORIENTED ARCHITECTURE (SOA) TEST SUITE")
    print("=" * 75)

    tests = [
        ("API Gateway Health Check Endpoint", test_health_check),
        ("Dedicated GNN Model Endpoint (POST /models/gnn/predict)", test_dedicated_gnn_model_endpoint),
        ("Dedicated ViT Model Endpoint (POST /models/vit/predict)", test_dedicated_vit_model_endpoint),
        ("Dedicated BERT Model Endpoint (POST /models/bert/predict)", test_dedicated_bert_model_endpoint),
        ("Dedicated Fusion Model Endpoint (POST /models/fusion/predict)", test_dedicated_fusion_model_endpoint),
        ("Central API Gateway Scan Pipeline (POST /api/v1/scan)", test_central_api_gateway_scan_pipeline),
        ("Dashboard System Telemetry Endpoint (GET /dashboard/system)", test_dashboard_system_endpoint),
        ("Dashboard Datasets Endpoint (GET /dashboard/datasets)", test_dashboard_datasets_endpoint),
        ("10-LLM Engine List Endpoint (GET /models/llm/list)", test_llm_list_endpoint),
        ("Single LLM Model Endpoint (POST /models/llm/{engine_id}/predict)", test_single_llm_endpoint),
        ("LLM Model Comparison Endpoint (POST /models/llm/compare)", test_compare_llm_endpoint),
        ("Random Forest Model Endpoint (POST /models/rf/predict)", test_rf_model_endpoint),
        ("CatBoost Model Endpoint (POST /models/catboost/predict)", test_catboost_model_endpoint),
        ("Deep Autoencoder Model Endpoint (POST /models/autoencoder/predict)", test_autoencoder_model_endpoint),
        ("Explainable AI (XAI) Endpoint (POST /models/xai/predict)", test_xai_model_endpoint),
        ("Parallel Batch Scan Endpoint (POST /api/v1/batch-scan)", test_batch_scan_endpoint),
        ("Crawler & Ingestion Service (CrawlerService)", test_crawler_service),
        ("SSL & TLS Certificate Service (SSLService)", test_ssl_service),
        ("WHOIS & DNS Intelligence Services (WHOISService, DNSService)", test_whois_and_dns_services),
        ("DOM & JavaScript AST Services (DOMService, JavaScriptService)", test_dom_and_js_services),
        ("Screenshot & OCR Visual Services (ScreenshotService, OCRService)", test_vision_services),
        ("PyTorch GNN & BERT Model Services (GNNService, BERTService)", test_gnn_and_bert_model_services),
        ("Classical ML Ensemble & 10-LLM Services (EnsembleService, LLMService)", test_ensemble_and_llm_model_services),
        ("Multimodal Fusion & XAI Services (FusionService, ExplainabilityService)", test_fusion_and_xai_services),
        ("Dataset & Dashboard Microservices (DatasetService, DashboardService)", test_dataset_and_dashboard_services)
    ]


    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {str(e)}")
            failed += 1

    print("=" * 75)
    print(f"  RESULTS: {passed} PASSED | {failed} FAILED | TOTAL: {len(tests)}")
    print("=" * 75 + "\n")

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
