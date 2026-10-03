"""
Unit tests for the pipeline, LLM clients and services (Phase 1 honesty pass).
"""

import asyncio
import json
import time

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database
import llm_ensemble
import multimodal_fusion
from component_status import AVAILABLE, HEURISTIC, NOT_IMPLEMENTED, UNAVAILABLE
from llm_ensemble import LLMEngine, get_llm_orchestrator, parse_llm_json
from mlops_service import MLOpsRegistryManager
from services import (
    BERTService, CrawlerService, DNSService, EnsembleService, ExplainabilityService, JavaScriptService,
    OCRService, ScreenshotService, SSLService, ViTService, WHOISService,
)


# --- LLM clients ---

def test_parse_llm_json_accepts_valid_answer():
    parsed = parse_llm_json('text {"threat_score": 12.5, "verdict": "legitimate", "reasoning": "r"} text')
    assert parsed == {"verdict": "LEGITIMATE", "threat_score": 12.5, "reasoning": "r"}


@pytest.mark.parametrize("text", [
    "no json here",
    '{"threat_score": 50}',
    '{"verdict": "PHISHING"}',
    '{"verdict": "MAYBE", "threat_score": 50}',
    '{"verdict": "PHISHING", "threat_score": 150}',
])
def test_parse_llm_json_rejects_incomplete_answers(text):
    with pytest.raises(ValueError):
        parse_llm_json(text)


def _mock_openai(monkeypatch, handler):
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(llm_ensemble.httpx, "AsyncClient", factory)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    return get_llm_orchestrator().find_engine("gpt55")


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_llm_valid_response_is_reported_as_model_output(monkeypatch):
    engine = _mock_openai(monkeypatch, lambda req: _chat_response(
        json.dumps({"threat_score": 30, "verdict": "LEGITIMATE", "reasoning": "looks normal"})))
    result = asyncio.run(engine.analyze("https://example.com", ""))
    assert result["status"] == "ok"
    assert result["output_type"] == "llm_generated"
    assert result["threat_score"] == 30.0
    assert result["verdict"] == "LEGITIMATE"


@pytest.mark.parametrize("handler", [
    lambda req: httpx.Response(500, json={}),
    lambda req: _chat_response("not json"),
    lambda req: _chat_response(json.dumps({"reasoning": "no verdict or score"})),
])
def test_llm_failures_never_produce_a_score(monkeypatch, handler):
    engine = _mock_openai(monkeypatch, handler)
    result = asyncio.run(engine.analyze("http://paypal-verify.example/login", ""))
    assert result["status"] == "error"
    assert result["reason"]
    assert "threat_score" not in result and "verdict" not in result


def test_llm_engines_without_client_are_not_implemented():
    report = asyncio.run(get_llm_orchestrator().run_ensemble("http://paypal-verify.example/login", ""))
    by_status = {r["engine"]: r["status"] for r in report["engine_results"]}
    assert by_status["Phi-4"] == NOT_IMPLEMENTED
    assert by_status["GPT-5.5"] == UNAVAILABLE
    assert report["engines_ok"] == 0
    assert report["status"] == UNAVAILABLE
    assert report["aggregate"]["status"] == UNAVAILABLE
    assert all("threat_score" not in r for r in report["engine_results"])


def test_unimplemented_engine_never_uses_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("network used")
    monkeypatch.setattr(llm_ensemble.httpx, "AsyncClient", fail)
    assert asyncio.run(LLMEngine("X", "Y", "").analyze("http://x.example"))["status"] == NOT_IMPLEMENTED


# --- Scan pipeline ---

def test_pipeline_latency_is_measured(monkeypatch):
    async def slow_ensemble(url, dom_snippet=""):
        # Busy-wait: asyncio.sleep can return early on Windows timer resolution.
        start = time.perf_counter()
        while time.perf_counter() - start < 0.05:
            pass
        return {"status": UNAVAILABLE, "engine_results": []}

    detector = multimodal_fusion.get_detector()
    monkeypatch.setattr(detector.llm_orchestrator, "run_ensemble", slow_ensemble)
    report = asyncio.run(detector.detect_url("https://example.com", ""))
    assert report["processing_latency_ms"] >= 50.0


def test_pipeline_output_does_not_depend_on_url_keywords():
    detector = multimodal_fusion.get_detector()
    phishy = asyncio.run(detector.detect_url("http://paypal-security-verify-login.com/signin", ""))
    benign = asyncio.run(detector.detect_url("https://github.com/torvalds/linux", ""))
    for report in (phishy, benign):
        assert report["verdict"] is None
        assert report["phishing_probability"] is None


@pytest.mark.parametrize("html", ["", "   ", "just some text without tags"])
def test_dom_analysis_unavailable_without_elements(html):
    assert multimodal_fusion.analyse_dom("http://x.example", html)["status"] == UNAVAILABLE


def test_dom_analysis_reports_truncation():
    html = "<html><body>" + "<p>x</p>" * 300 + "</body></html>"
    dom = multimodal_fusion.analyse_dom("http://x.example", html)
    assert dom["total_html_elements"] == 302
    assert dom["graph_node_count"] == multimodal_fusion.GNN_MAX_NODES
    assert dom["truncated_to_first_n_elements"] == multimodal_fusion.GNN_MAX_NODES


def test_js_indicators_are_labelled_heuristic_without_score():
    js = JavaScriptService.parse("eval('a'); atob('b');", "")
    assert js["status"] == HEURISTIC
    assert js["counts"]["eval_usage_count"] == 1
    assert "js_ast_risk_score" not in js["counts"]


# --- Services ---

def test_crawler_never_invents_html_when_network_is_blocked():
    # The autouse block_real_network fixture blocks this non-local host, so the crawl fails.
    # Even so, no synthetic page is invented, matching the pre-Phase-2 crawler's behaviour.
    res = asyncio.run(CrawlerService.crawl("http://paypal-verification.com/login", ""))
    assert res["status"] == UNAVAILABLE
    assert res["html_content"] == ""
    assert "headers" not in res


def test_crawler_uses_supplied_html_without_any_network_call():
    res = asyncio.run(CrawlerService.crawl("http://any-host-would-be-blocked.example", "<html></html>"))
    assert res["status"] == AVAILABLE
    assert res["source"] == "request_html_content"
    assert res["html_content"] == "<html></html>"


@pytest.mark.parametrize("call", [
    lambda: SSLService.analyze("http://x.example"),
    lambda: WHOISService.analyze("http://x.example"),
    lambda: DNSService.analyze("http://x.example"),
    lambda: ScreenshotService.capture("http://x.example"),
    lambda: OCRService.extract_text("http://x.example"),
    lambda: ViTService.predict("http://x.example"),
    lambda: ViTService.predict_phishpedia("http://x.example"),
    lambda: ViTService.optimize_eer("CERT Polska"),
    lambda: BERTService.predict("http://x.example"),
    lambda: EnsembleService().predict({}, "http://x.example"),
    lambda: EnsembleService().predict_autoencoder({}, "http://x.example"),
    lambda: ExplainabilityService.generate_xai_report({}),
    lambda: MLOpsRegistryManager.execute_retraining_pipeline(),
    lambda: MLOpsRegistryManager.detect_concept_drift(),
])
def test_simulated_services_are_unavailable(call):
    res = call()
    assert res["status"] == UNAVAILABLE
    assert res["reason"]


def test_init_db_does_not_seed_data(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()
    session = sessionmaker(bind=engine)()
    try:
        assert session.query(database.ScanResultDB).count() == 0
        assert session.query(database.UserDB).count() == 0
    finally:
        session.close()
