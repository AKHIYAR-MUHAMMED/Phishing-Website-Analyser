"""
Section 21.1 item 2: feed digests are generated and secrets are redacted. fetch_feed_bytes is
only ever exercised against the local test server here.
"""

import asyncio
import hashlib

import pytest

from dataset.feeds import compute_feed_digest, fetch_feed_bytes


def test_compute_feed_digest_redacts_secret_and_hashes_correctly():
    raw = b"url,label\nhttp://x.example,1\n"
    endpoint = "http://data.phishtank.com/data/online-valid.csv?app_key=SuperSecretValue123456"
    digest = compute_feed_digest("phishtank", endpoint, raw, row_count=1)
    assert "SuperSecretValue123456" not in digest["endpoint"]
    assert digest["sha256"] == hashlib.sha256(raw).hexdigest()
    assert digest["row_count"] == 1
    assert digest["source"] == "phishtank"
    assert digest["timestamp"]


def test_fetch_feed_bytes_against_local_server(http_server):
    body = asyncio.run(fetch_feed_bytes(http_server.url("/ok")))
    assert body  # LOGIN_PAGE_HTML content


def test_fetch_feed_bytes_raises_on_http_error(http_server):
    with pytest.raises(Exception):
        asyncio.run(fetch_feed_bytes(http_server.url("/404")))


def test_fetch_feed_bytes_blocks_real_host():
    with pytest.raises(Exception):
        asyncio.run(fetch_feed_bytes("https://example.com/feed.txt"))
