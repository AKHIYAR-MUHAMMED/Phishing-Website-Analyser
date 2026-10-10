"""
Regression tests: the experimental demo pipeline (POST /api/v2/analyze) must not analyse or score
an HTTP error response as if it were the requested page.

The crawler reports status "ok" for any HTTP response and records the code in http_status, so a
server-generated "404 File not found" page used to flow through the GNN, the lexical features and
the semantic heuristic and come out labelled "benign". An HTTP error (status >= 400) is not the
target page, so the result must be "unavailable" with no components, fusion or verdict.

These tests do not assert any score or model-quality value.
"""

import socket

import pytest
from fastapi.testclient import TestClient

import analysis_pipeline
from api import app

client = TestClient(app)

SCORED_VERDICTS = {"benign", "phishing"}


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


def _closed_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --- HTTP error responses -------------------------------------------------------------------

def test_http_404_is_unavailable_and_not_scored(http_server):
    body = _analyze(http_server.url("/404"))
    _assert_unavailable_without_scoring(body)
    assert body["crawl"]["http_status"] == 404
    assert "404" in body["verdict_reason"]


def test_unknown_path_404_is_unavailable_and_not_scored(http_server):
    body = _analyze(http_server.url("/definitely-missing-page"))
    _assert_unavailable_without_scoring(body)
    assert body["crawl"]["http_status"] == 404


@pytest.mark.parametrize("http_status", [400, 403, 404, 410, 500, 503])
def test_any_http_error_status_is_unavailable(monkeypatch, http_status):
    async def fake_fetch(url):
        return {
            "status": "ok",
            "requested_url": url,
            "final_url": url,
            "http_status": http_status,
            "content_type": "text/html",
            "html": "<html><head><title>Error response</title></head><body>Error</body></html>",
            "title": "Error response",
            "visible_text": "Error response Error",
            "elapsed_ms": 1.0,
        }

    monkeypatch.setattr(analysis_pipeline, "fetch_url", fake_fetch)
    body = _analyze("http://login.example.com/page")
    _assert_unavailable_without_scoring(body)
    assert body["crawl"]["http_status"] == http_status
    assert str(http_status) in body["verdict_reason"]


# --- Existing behaviour that must be preserved ----------------------------------------------

def test_http_200_page_still_runs_the_full_pipeline(http_server):
    body = _analyze(http_server.url("/ok"))
    assert body["crawl"]["status"] == "ok"
    assert body["crawl"]["http_status"] == 200
    assert body["verdict"] in SCORED_VERDICTS
    assert {"url_lexical", "gnn", "semantic"} <= set(body["components"])
    assert body["fusion"]["contributing_components"]
    assert "verdict_confidence_caveat" in body


def test_unreachable_url_is_unavailable_with_the_existing_reason():
    body = _analyze(f"http://127.0.0.1:{_closed_local_port()}/page")
    _assert_unavailable_without_scoring(body)
    assert body["crawl"]["status"] == "error"
    assert body["crawl"]["error_type"] == "connection_error"
    assert body["verdict_reason"] == "Crawl did not complete; no page content to analyze."


def test_invalid_url_is_unavailable_with_the_existing_reason():
    body = _analyze("not a url")
    _assert_unavailable_without_scoring(body)
    assert body["crawl"]["status"] == "error"
    assert body["crawl"]["error_type"] == "invalid_url"
    assert body["verdict_reason"] == "Crawl did not complete; no page content to analyze."


# --- API / UI consistency -------------------------------------------------------------------

def test_demo_page_renders_the_api_unavailable_reason():
    """
    The /demo page renders any verdict other than benign/phishing as "Unavailable" and shows
    data.verdict_reason. The 404 result above carries exactly those fields, so the UI shows the
    same unavailable state as the API instead of a benign card.
    """
    html = client.get("/demo").text
    unavailable_branch = html.index("verdict === 'unavailable'")
    assert "Unavailable" in html[unavailable_branch:unavailable_branch + 400]
    assert "data.verdict_reason" in html[unavailable_branch:unavailable_branch + 600]
    # the benign/phishing card is built only after the unavailable branch has returned
    assert html.index("const isPhish") > unavailable_branch


def test_http_404_result_has_the_fields_the_demo_page_reads(http_server):
    body = _analyze(http_server.url("/404"))
    assert body.get("verdict") == "unavailable"
    assert body.get("verdict_reason")
    assert body["crawl"]["http_status"] == 404
    assert body["crawl"]["final_url"].endswith("/404")
