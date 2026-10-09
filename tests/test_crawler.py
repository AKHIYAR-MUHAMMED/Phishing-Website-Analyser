"""
Crawler tests against a local test server (tests/local_server.py). No test in this file
touches a real website (CLAUDE.md section 17.6).
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from api import app
from component_status import AVAILABLE, UNAVAILABLE
from crawler import fetch_url
from local_server import SLOW_DELAY_SECONDS, closed_port_url

client = TestClient(app)


def test_ok_response_is_fully_reported(http_server):
    result = asyncio.run(fetch_url(http_server.url("/ok")))
    assert result["status"] == "ok"
    assert result["http_status"] == 200
    assert result["final_url"] == http_server.url("/ok")
    assert result["redirect_count"] == 0
    assert result["title"] == "Sign in"
    assert "<form" in result["html"]
    assert result["html_length_bytes"] > 0
    assert result["elapsed_ms"] >= 0
    assert result["crawled_at"]  # non-empty ISO timestamp


def test_empty_body_reports_ok_with_no_html(http_server):
    result = asyncio.run(fetch_url(http_server.url("/empty")))
    assert result["status"] == "ok"
    assert result["html"] == ""
    assert result["html_length_bytes"] == 0


def test_http_error_status_is_reported_not_hidden(http_server):
    result = asyncio.run(fetch_url(http_server.url("/404")))
    assert result["status"] == "ok"  # the network fetch itself succeeded
    assert result["http_status"] == 404


def test_redirects_are_followed_and_counted(http_server):
    result = asyncio.run(fetch_url(http_server.url("/redirect-a")))
    assert result["status"] == "ok"
    assert result["final_url"] == http_server.url("/ok")
    assert result["redirect_count"] == 2


def test_too_many_redirects_is_an_explicit_error(http_server):
    result = asyncio.run(fetch_url(http_server.url("/loop"), max_redirects=3))
    assert result["status"] == "error"
    assert result["error_type"] == "too_many_redirects"


def test_timeout_is_an_explicit_error(http_server):
    result = asyncio.run(fetch_url(http_server.url("/slow"), timeout=SLOW_DELAY_SECONDS / 4))
    assert result["status"] == "error"
    assert result["error_type"] == "timeout"


def test_connection_error_is_explicit(http_server):
    result = asyncio.run(fetch_url(closed_port_url()))
    assert result["status"] == "error"
    assert result["error_type"] == "connection_error"


def test_non_html_content_is_not_decoded_as_html(http_server):
    result = asyncio.run(fetch_url(http_server.url("/nonhtml")))
    assert result["status"] == "ok"
    assert result["html"] == ""
    assert "octet-stream" in result["content_type"]


def test_content_too_large_is_an_explicit_error(http_server):
    result = asyncio.run(fetch_url(http_server.url("/big"), max_content_bytes=100))
    assert result["status"] == "error"
    assert result["error_type"] == "content_too_large"


def test_malformed_html_does_not_crash(http_server):
    result = asyncio.run(fetch_url(http_server.url("/malformed")))
    assert result["status"] == "ok"
    assert isinstance(result["title"], str)


@pytest.mark.parametrize("url", ["not-a-url", "ftp://example.com/file", "javascript:alert(1)", ""])
def test_invalid_url_is_rejected_before_any_network_call(url):
    result = asyncio.run(fetch_url(url))
    assert result["status"] == "error"
    assert result["error_type"] == "invalid_url"


def test_scan_endpoint_live_crawls_the_local_server(http_server):
    """Integration test: /scan with no html_content performs a real (local) crawl and the
    crawled HTML feeds into DOM analysis, exactly like request-supplied HTML does."""
    response = client.post("/api/v1/scan", json={"url": http_server.url("/ok")})
    assert response.status_code == 200
    data = response.json()

    assert data["crawl"]["status"] == AVAILABLE
    assert data["crawl"]["source"] == "live_crawl"
    assert data["crawl"]["http_status"] == 200

    dom = data["modalities"]["dom_graph"]
    assert dom["status"] == AVAILABLE
    assert dom["form_nodes"] == 1
    assert dom["password_input_nodes"] == 1


def test_scan_endpoint_reports_crawl_failure_explicitly():
    response = client.post("/api/v1/scan", json={"url": closed_port_url()})
    assert response.status_code == 200
    data = response.json()
    assert data["crawl"]["status"] == UNAVAILABLE
    assert data["crawl"]["error_type"] == "connection_error"
    assert data["modalities"]["dom_graph"]["status"] == UNAVAILABLE
