"""
Regression tests: the experimental demo pipeline (POST /api/v2/analyze) must report "unavailable"
when a successfully fetched response contains no analysable HTML page.

Before this check an empty, non-HTML or element-less 200 response still ran through the pipeline:
the DOM-graph/GNN stage either did not run (so the verdict came from the URL and an empty-text
heuristic alone) or ran on parse_dom_to_graph()'s synthetic fallback graph, and the result was
labelled "benign" or "phishing" as if it described a page.

Every unavailable result must carry a reason, no component output, no GNN score, no fusion and no
fused score. These tests do not assert any score or model-quality value for analysable pages.
"""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

import analysis_pipeline
from api import app

client = TestClient(app)

SCORED_VERDICTS = {"benign", "phishing"}

HTML_PAGE = b"<html><head><title>Hello</title></head><body><h1>Hello</h1><p>A plain local test page.</p></body></html>"

# path -> (status, content type or None for "send no Content-Type header", body)
ROUTES = {
    "/empty-html": (200, "text/html; charset=utf-8", b""),
    "/empty-octet": (200, "application/octet-stream", b""),
    "/empty-no-type": (200, None, b""),
    "/whitespace": (200, "text/html", b"   \n\t \r\n  "),
    "/octet": (200, "application/octet-stream", b"\x00\x01\x02binary\x03data"),
    "/pdf": (200, "application/pdf", b"%PDF-1.4\n%fake pdf body"),
    "/plain": (200, "text/plain; charset=utf-8", b"just some plain text, no markup at all"),
    "/json": (200, "application/json", b'{"ok": true, "items": [1, 2, 3]}'),
    "/xml-app": (200, "application/xml", b"<root><item>1</item></root>"),
    "/xml-text": (200, "text/xml", b"<root><item>1</item></root>"),
    "/json-as-html": (200, "text/html", b'{"ok": true}'),
    "/text-as-html": (200, "text/html", b"plain words with no markup"),
    "/blank-html": (200, "text/html", b"<html></html>"),
    "/scaffold-only": (200, "text/html", b"<html><head></head><body></body></html>"),
    "/comment-only": (200, "text/html", b"<!-- nothing here -->"),
    "/no-type-html": (200, None, HTML_PAGE),
    "/404-empty": (404, "text/html", b""),
    "/page": (200, "text/html; charset=utf-8", HTML_PAGE),
    "/page-upper": (200, "TEXT/HTML", HTML_PAGE),
    "/page-xhtml": (200, "application/xhtml+xml", HTML_PAGE),
    "/page-minimal": (200, "text/html", b"<html><body><p>hi</p></body></html>"),
    "/page-fragment": (200, "text/html", b"<div>just a fragment</div>"),
}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        status, content_type, body = ROUTES.get(self.path, (404, "text/html", b"not found"))
        self.send_response(status)
        if content_type is not None:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield lambda path: f"http://127.0.0.1:{httpd.server_address[1]}{path}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def stages_must_not_run(monkeypatch):
    """Fails the test if the DOM-graph or GNN stage is reached."""
    def boom(*args, **kwargs):
        raise AssertionError("a pipeline stage ran for a response with no analysable HTML")
    monkeypatch.setattr(analysis_pipeline, "parse_dom_to_graph", boom)
    monkeypatch.setattr(analysis_pipeline, "_get_demo_gnn", boom)
    monkeypatch.setattr(analysis_pipeline, "analyze_text_heuristically", boom)


def _analyze(url: str) -> dict:
    response = client.post("/api/v2/analyze", json={"url": url})
    assert response.status_code == 200
    return response.json()


def _assert_unavailable_without_scoring(body: dict) -> None:
    assert body["verdict"] == "unavailable"
    assert body["verdict"] not in SCORED_VERDICTS
    assert isinstance(body["verdict_reason"], str) and body["verdict_reason"].strip()
    assert body["components"] == {}
    assert "fusion" not in body
    assert "verdict_confidence_caveat" not in body
    serialised = json.dumps(body)
    assert "threat_score" not in serialised
    assert "fused_score" not in serialised
    assert "graph_stats" not in serialised


# --- responses with no analysable HTML --------------------------------------------------------

@pytest.mark.parametrize("path,reason_fragment", [
    ("/empty-html", "empty response"),
    ("/empty-octet", "empty response"),
    ("/empty-no-type", "empty response"),
    ("/whitespace", "only whitespace"),
    ("/octet", "application/octet-stream"),
    ("/pdf", "application/pdf"),
    ("/plain", "text/plain"),
    ("/json", "application/json"),
    ("/xml-app", "application/xml"),
    ("/xml-text", "text/xml"),
    ("/json-as-html", "no elements"),
    ("/text-as-html", "no elements"),
    ("/blank-html", "no elements"),
    ("/scaffold-only", "no elements"),
    ("/comment-only", "no elements"),
])
def test_response_without_analysable_html_is_unavailable(server, stages_must_not_run, path, reason_fragment):
    body = _analyze(server(path))
    _assert_unavailable_without_scoring(body)
    assert body["crawl"]["status"] == "ok"
    assert body["crawl"]["http_status"] == 200
    assert reason_fragment in body["verdict_reason"]


def test_all_unavailable_reasons_share_one_consistent_shape(server):
    for path in ("/empty-html", "/whitespace", "/octet", "/pdf", "/plain", "/json", "/xml-app", "/blank-html"):
        body = _analyze(server(path))
        assert body["verdict_reason"].endswith(("to analyze.", "to analyze"))
        assert set(body) == {"url", "components", "crawl", "verdict", "verdict_reason", "elapsed_ms_total"}


def test_html_without_a_content_type_header_is_currently_unavailable(server, stages_must_not_run):
    """Known crawler limitation, documented rather than changed here: crawler.fetch_url() only keeps
    the body of a textual Content-Type, so real HTML sent with no Content-Type header never reaches
    the pipeline. It is reported as unavailable (never scored), not mistaken for an empty page."""
    body = _analyze(server("/no-type-html"))
    _assert_unavailable_without_scoring(body)
    assert "no content type was provided" in body["verdict_reason"]
    assert "empty response" not in body["verdict_reason"]


def test_unavailable_reason_never_echoes_more_than_the_media_type():
    result = {"status": "ok", "http_status": 200, "html": "", "html_length_bytes": 5,
              "content_type": "application/x-evil; charset=utf-8; boundary=" + "A" * 500}
    reason = analysis_pipeline._no_analysable_html_reason(result)
    assert "application/x-evil" in reason
    assert "boundary" not in reason and "charset" not in reason
    assert len(reason) < 250


# --- existing behaviour is preserved ----------------------------------------------------------

def test_http_error_with_an_empty_body_still_reports_the_http_error(server):
    body = _analyze(server("/404-empty"))
    _assert_unavailable_without_scoring(body)
    assert body["crawl"]["http_status"] == 404
    assert "404" in body["verdict_reason"]


def test_unreachable_url_keeps_its_existing_reason():
    body = _analyze("http://127.0.0.1:9/x")
    _assert_unavailable_without_scoring(body)
    assert body["verdict_reason"] == "Crawl did not complete; no page content to analyze."


def test_invalid_url_keeps_its_existing_reason():
    body = _analyze("not a url")
    _assert_unavailable_without_scoring(body)
    assert body["verdict_reason"] == "Crawl did not complete; no page content to analyze."


@pytest.mark.parametrize("path", ["/page", "/page-upper", "/page-xhtml", "/page-minimal", "/page-fragment"])
def test_normal_html_page_still_follows_the_full_pipeline(server, path):
    calls = []
    real_parse = analysis_pipeline.parse_dom_to_graph

    def spy(*args, **kwargs):
        calls.append(args)
        return real_parse(*args, **kwargs)

    analysis_pipeline.parse_dom_to_graph = spy
    try:
        body = _analyze(server(path))
    finally:
        analysis_pipeline.parse_dom_to_graph = real_parse

    assert len(calls) == 1
    assert body["verdict"] in SCORED_VERDICTS
    assert set(body["components"]) == {"url_lexical", "gnn", "semantic"}
    assert body["components"]["semantic"]["status"] == "heuristic"
    assert body["components"]["gnn"]["status"] == "real_small_sample_model"
    assert "threat_score" in body["components"]["gnn"]
    assert body["fusion"]["contributing_components"] == ["gnn", "url_lexical", "semantic_heuristic"]
    assert "fused_score" in body["fusion"]
    assert body["fusion"]["method"].startswith("unweighted mean")
    assert "verdict_confidence_caveat" in body
    assert "verdict_reason" not in body


def test_normal_page_response_keys_are_unchanged(server):
    body = _analyze(server("/page"))
    assert set(body) == {"url", "components", "crawl", "verdict", "fusion",
                         "verdict_confidence_caveat", "elapsed_ms_total"}


# --- the demo page can show the new reasons ---------------------------------------------------

def test_demo_page_renders_the_unavailable_reason_for_these_responses():
    html = client.get("/demo").text
    assert "verdict === 'unavailable'" in html
    assert "data.verdict_reason" in html


def test_analyze_url_returns_unavailable_directly(server):
    body = asyncio.run(analysis_pipeline.analyze_url(server("/empty-html")))
    assert body["verdict"] == "unavailable"
    assert "fusion" not in body and body["components"] == {}
