"""
Section 21.1 end-to-end integration tests (C2, C3 regressions): real cross-module pipelines,
not single-function fixtures. Local test server only; no real network access.
"""

import asyncio

from dataset.capture import capture_url
from dataset.dataset_card import generate_card
from dataset.feeds import compute_feed_digest, fetch_feed_bytes
from dataset.manifest import append_capture_row, load_manifest
from dataset.selection import build_selection


def test_redacted_feed_digest_flows_cleanly_through_generate_card(http_server):
    """C2 regression, end to end: a feed endpoint containing a real secret-shaped query param
    must come out of compute_feed_digest() already redacted, and generate_card() (which scans
    its own output for secret-shaped text and raises rather than returning a leaking card) must
    accept that digest without raising."""
    raw_bytes = asyncio.run(fetch_feed_bytes(http_server.url("/ok")))
    leaking_endpoint = "http://feed.example/data.csv?app_key=SuperSecretValue123456"

    digest = compute_feed_digest("test_source", leaking_endpoint, raw_bytes, row_count=5)

    assert "SuperSecretValue123456" not in digest["endpoint"]
    assert "app_key=REDACTED" in digest["endpoint"]

    card = generate_card([], [], "v1", feed_digests=[digest])
    assert "SuperSecretValue123456" not in card
    assert "test_source" in card
    assert "app_key=REDACTED" in card


def test_capture_through_manifest_selection_and_card_is_one_consistent_pipeline(tmp_path, http_server):
    """C3 regression, end to end: capture_url()'s output must survive append_capture_row/
    load_manifest round-tripping, build_selection() must emit a real "label" column derived
    from that manifest (not a hand-typed fixture value), and generate_card()'s counts must
    match what build_selection() actually produced — not a separately hand-typed expectation."""
    manifest_path = tmp_path / "manifest.csv"

    phishing_row = asyncio.run(capture_url(
        http_server.url("/ok"), source="test", label=1, collection_run_date="2026-01-01",
        manifest_rows=[], snapshot_dir=tmp_path,
    ))
    # capture_url resolves the registered domain from the URL itself, and both fixture URLs
    # share the local test server's 127.0.0.1 host — overridden here to two distinct domains so
    # this test exercises normal (non-shared-domain) selection/split behavior, matching how two
    # real, differently-hosted URLs would arrive from the crawler.
    phishing_row["registered_domain"] = phishing_row["final_registered_domain"] = "phish.example"
    append_capture_row(phishing_row, manifest_path)

    manifest_rows = load_manifest(manifest_path)
    benign_row = asyncio.run(capture_url(
        http_server.url("/big/100"), source="test", label=0, collection_run_date="2026-01-01",
        manifest_rows=manifest_rows, snapshot_dir=tmp_path,
    ))
    benign_row["registered_domain"] = benign_row["final_registered_domain"] = "benign.example"
    append_capture_row(benign_row, manifest_path)

    manifest_rows = load_manifest(manifest_path)
    assert len(manifest_rows) == 2
    assert phishing_row["html_sha256"] != benign_row["html_sha256"]

    selection_rows = build_selection(manifest_rows, None, "v1", seed=1)
    by_label = {row["label"]: row for row in selection_rows}
    assert by_label[1]["eligible"] is True
    assert by_label[0]["eligible"] is True
    assert by_label[1]["split"] and by_label[0]["split"]

    card = generate_card(manifest_rows, selection_rows, "v1")
    assert "Total capture attempts: 2" in card
    assert "In modelling pool (eligible AND split): 2" in card
    assert "phishing (label 1): 1" in card
    assert "benign (label 0): 1" in card
