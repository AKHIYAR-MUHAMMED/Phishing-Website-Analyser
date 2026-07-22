"""
PhishGuard-X Service Registry Automated Unit Test Suite.
Validates individual microservice layer implementations.
"""

import asyncio

from services import (
    CrawlerService,
    SSLService,
    WHOISService,
    DNSService,
    DOMService,
    JavaScriptService,
    ScreenshotService,
    OCRService,
    GraphService,
    FeatureService,
    GNNService,
    ViTService,
    BERTService,
    EnsembleService,
    LLMService,
    FusionService,
    ExplainabilityService,
    DatasetService,
    DashboardService
)


def test_crawler_service():
    res = CrawlerService.crawl("http://paypal-verification.com/login", "")
    assert res["domain"] == "paypal-verification.com"
    assert len(res["html_content"]) > 0


def test_ssl_service():
    res = SSLService.analyze("http://paypal-verification.com/login")
    assert "has_ssl" in res
    assert "tls_version" in res


def test_whois_and_dns_services():
    whois = WHOISService.analyze("http://paypal-verification.com/login")
    dns = DNSService.analyze("http://paypal-verification.com/login")
    assert "registration_age_days" in whois
    assert "dns_records" in dns


def test_dom_and_js_services():
    dom = DOMService.parse("<html><body></body></html>", "http://test.com")
    js = JavaScriptService.parse("eval('code');", "")
    assert "sfh_external" in dom
    assert "eval_usage_count" in js


def test_vision_services():
    shot = ScreenshotService.capture("http://paypal-verification.com/login")
    ocr = OCRService.extract_text("http://paypal-verification.com/login")
    assert "vit_threat_score" in shot
    assert len(ocr) > 0


def test_gnn_and_bert_model_services():
    gnn = GNNService.predict("<form></form>", "http://test.com")
    bert = BERTService.predict("http://paypal-verification.com/login")
    assert gnn["gnn_threat_score"] >= 0.0
    assert bert["bert_threat_score"] > 80.0


def test_ensemble_and_llm_model_services():
    ensemble_svc = EnsembleService()
    ens = ensemble_svc.predict({}, "http://paypal-verification.com/login")
    llm = asyncio.run(LLMService.predict("http://paypal-verification.com/login", "", {}, {"gnn_threat_score": 0.95, "graph_stats": {}, "structural_indicators": {}}))
    assert ens["ensemble_threat_score"] > 80.0
    assert llm["consensus_verdict"] == "PHISHING"


def test_fusion_and_xai_services():
    fusion = asyncio.run(FusionService.predict("http://paypal-verification.com/login", ""))
    xai = ExplainabilityService.generate_xai_report(fusion)
    assert fusion["overall_threat_score"] > 50.0
    assert len(xai) > 0


def test_dataset_and_dashboard_services():
    ds = DatasetService.get_dataset_statistics()
    dash = DashboardService.get_telemetry()
    assert ds["total_samples"] == 10000
    assert dash["status"] == "OPERATIONAL"
