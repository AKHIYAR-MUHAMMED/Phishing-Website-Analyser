"""
Capture pipeline tests against the local test server only. No real network access.
"""

import asyncio

import dataset.capture as capture_module
from dataset.capture import capture_url
from dataset.eligibility import row_intrinsic_ok
from dataset.manifest import CAPTURE_COLUMNS


def test_capture_ok_page_produces_a_full_row(tmp_path, http_server):
    row = asyncio.run(capture_url(
        http_server.url("/ok"), source="test", label=1, collection_run_date="2026-01-01",
        manifest_rows=[], snapshot_dir=tmp_path,
    ))
    assert set(CAPTURE_COLUMNS) <= set(row.keys())
    assert row["crawl_status"] == "ok"
    assert row["http_status"] == 200
    assert row["html_sha256"]
    assert row["html_snapshot_path"].startswith("data/raw/html/")
    assert row["registered_domain"] == "127.0.0.1"
    assert row_intrinsic_ok(row) is True
    assert row["tls_captured"] is False  # http://, not https://


def test_capture_snapshot_is_actually_written(tmp_path, http_server):
    row = asyncio.run(capture_url(
        http_server.url("/ok"), source="test", label=1, collection_run_date="2026-01-01",
        manifest_rows=[], snapshot_dir=tmp_path,
    ))
    filename = row["html_snapshot_path"].split("/")[-1]
    assert (tmp_path / filename).exists()


def test_capture_empty_body_has_no_snapshot_and_is_row_intrinsically_ineligible(tmp_path, http_server):
    row = asyncio.run(capture_url(
        http_server.url("/empty"), source="test", label=0, collection_run_date="2026-01-01",
        manifest_rows=[], snapshot_dir=tmp_path,
    ))
    assert row["crawl_status"] == "ok"
    assert row["html_snapshot_path"] == ""
    assert row_intrinsic_ok(row) is False


def test_capture_404_is_ok_but_row_intrinsically_ineligible(tmp_path, http_server):
    row = asyncio.run(capture_url(
        http_server.url("/404"), source="test", label=0, collection_run_date="2026-01-01",
        manifest_rows=[], snapshot_dir=tmp_path,
    ))
    assert row["crawl_status"] == "ok"
    assert row["http_status"] == 404
    assert row_intrinsic_ok(row) is False


def test_capture_connection_error_records_error_fields(tmp_path):
    from local_server import closed_port_url
    row = asyncio.run(capture_url(
        closed_port_url(), source="test", label=1, collection_run_date="2026-01-01",
        manifest_rows=[], snapshot_dir=tmp_path,
    ))
    assert row["crawl_status"] == "connection_error"
    assert row["error_message"]
    assert row["html_snapshot_path"] == ""


def test_capture_skips_robots_disallowed_url(tmp_path, http_server, monkeypatch):
    async def always_disallowed(url, user_agent=None, cache=None):
        return "disallowed"
    monkeypatch.setattr(capture_module, "check_robots", always_disallowed)

    async def fail_if_called(url, **kwargs):
        raise AssertionError("fetch_url must not be called for a robots_disallowed URL")
    monkeypatch.setattr(capture_module, "fetch_url", fail_if_called)

    row = asyncio.run(capture_url(
        http_server.url("/ok"), source="test", label=1, collection_run_date="2026-01-01",
        manifest_rows=[], snapshot_dir=tmp_path,
    ))
    assert row["crawl_status"] == "robots_disallowed"
    assert row["robots_result"] == "disallowed"


def test_already_collected_skips_the_network_call_entirely(tmp_path, http_server, monkeypatch):
    async def fail_if_called(url, **kwargs):
        raise AssertionError("fetch_url must not be called for an already_collected URL")
    monkeypatch.setattr(capture_module, "fetch_url", fail_if_called)

    prior_row = {
        "normalized_url": "http://127.0.0.1:1/ok",  # any string; normalize() output is
                                                      # recomputed inside capture_url from the
                                                      # real http_server URL below and must match
    }
    from dataset.normalize import normalize_url
    target_url = http_server.url("/ok")
    prior_row["normalized_url"] = normalize_url(target_url)
    prior_row.update({"crawl_status": "ok", "http_status": 200, "html_snapshot_path": "data/raw/html/x.html"})

    row = asyncio.run(capture_url(
        target_url, source="test", label=1, collection_run_date="2026-02-01",
        manifest_rows=[prior_row], snapshot_dir=tmp_path,
    ))
    assert row["crawl_status"] == "already_collected"


def test_retry_without_overwrite_preserves_both_attempts(tmp_path, http_server):
    """Section 21.1 item 9. A prior FAILED attempt does not count as already_collected (it does
    not satisfy row_intrinsic_ok), so a later run's capture proceeds and both rows — the failed
    one and the new successful one — must coexist once appended to the manifest."""
    from dataset.manifest import append_capture_row, load_manifest
    from dataset.normalize import normalize_url

    manifest_path = tmp_path / "manifest.csv"
    target_url = http_server.url("/ok")
    normalized = normalize_url(target_url)

    failed_row = {
        "url": target_url, "normalized_url": normalized, "source": "test", "source_metadata": "{}",
        "label": 1, "collection_run_date": "2026-01-01", "retry_count": 1, "crawl_status": "timeout",
        "crawled_at": "", "final_url": "", "registered_domain": "127.0.0.1",
        "final_registered_domain": "", "domain_redirect_mismatch": False, "http_status": "",
        "redirect_count": "", "content_type": "", "html_length_bytes": "", "decoded_text_length": "",
        "visible_text_length": "", "dom_node_count": "", "script_count": "", "raw_content_sha256": "",
        "html_sha256": "", "normalized_html_sha256": "", "html_snapshot_path": "",
        "error_type": "timeout", "error_message": "simulated timeout", "robots_result": "allowed",
        "meta_refresh_detected": False, "bot_challenge_suspected": False, "tls_captured": False,
        "tls_version": "", "certificate_subject": "", "certificate_issuer": "",
        "certificate_self_signed": None, "certificate_not_after": "", "discovered_from": "",
        "feed_to_crawl_latency_seconds": "", "collection_tool_version": "", "normalization_version": "v1",
        "psl_snapshot_date": "",
    }
    append_capture_row(failed_row, manifest_path)

    manifest_rows = load_manifest(manifest_path)
    new_row = asyncio.run(capture_url(
        target_url, source="test", label=1, collection_run_date="2026-02-01",
        manifest_rows=manifest_rows, snapshot_dir=tmp_path,
    ))
    assert new_row["crawl_status"] == "ok"  # proceeded to a real fetch, not already_collected
    append_capture_row(new_row, manifest_path)

    final_rows = load_manifest(manifest_path)
    assert len(final_rows) == 2
    statuses = {r["crawl_status"] for r in final_rows}
    assert statuses == {"timeout", "ok"}


def test_capture_never_raises_on_a_real_host_blocked_by_the_network_guard(tmp_path):
    row = asyncio.run(capture_url(
        "https://example.com/", source="test", label=0, collection_run_date="2026-01-01",
        manifest_rows=[], snapshot_dir=tmp_path, check_robots_txt=False,
    ))
    assert row["crawl_status"] == "network_disabled"
