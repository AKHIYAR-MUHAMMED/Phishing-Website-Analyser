from dataset.manifest import append_capture_row, find_prior_ok_row, load_manifest

BASE_ROW = {
    "url": "http://example.com/", "normalized_url": "http://example.com/", "source": "test",
    "source_metadata": "{}", "label": 0, "collection_run_date": "2026-01-01",
    "retry_count": 0, "crawl_status": "ok", "crawled_at": "2026-01-01T00:00:00+00:00",
    "final_url": "http://example.com/", "registered_domain": "example.com",
    "final_registered_domain": "example.com", "domain_redirect_mismatch": False,
    "http_status": 200, "redirect_count": 0, "content_type": "text/html",
    "html_length_bytes": 10, "decoded_text_length": 10, "visible_text_length": 5,
    "dom_node_count": 3, "script_count": 0, "raw_content_sha256": "abc", "html_sha256": "def",
    "normalized_html_sha256": "ghi", "html_snapshot_path": "data/raw/html/def.html",
    "error_type": "", "error_message": "", "robots_result": "allowed",
    "meta_refresh_detected": False, "bot_challenge_suspected": False, "tls_captured": False,
    "tls_version": "", "certificate_subject": "", "certificate_issuer": "",
    "certificate_self_signed": None, "certificate_not_after": "", "discovered_from": "",
    "feed_to_crawl_latency_seconds": "", "collection_tool_version": "abc123",
    "normalization_version": "v1", "psl_snapshot_date": "tldextract==5.1.2",
}


def test_append_and_load_round_trip(tmp_path):
    manifest_path = tmp_path / "manifest.csv"
    append_capture_row(BASE_ROW, manifest_path)
    rows = load_manifest(manifest_path)
    assert len(rows) == 1
    assert rows[0]["url"] == "http://example.com/"
    assert rows[0]["domain_redirect_mismatch"] is False  # deserialized back to bool
    assert rows[0]["http_status"] == "200"  # non-bool columns stay strings; callers cast as needed


def test_append_never_rewrites_existing_rows(tmp_path):
    manifest_path = tmp_path / "manifest.csv"
    row1 = {**BASE_ROW, "url": "http://a.example/", "normalized_url": "http://a.example/"}
    row2 = {**BASE_ROW, "url": "http://b.example/", "normalized_url": "http://b.example/"}
    append_capture_row(row1, manifest_path)
    contents_after_first = manifest_path.read_text(encoding="utf-8")
    append_capture_row(row2, manifest_path)
    contents_after_second = manifest_path.read_text(encoding="utf-8")
    assert contents_after_second.startswith(contents_after_first)
    rows = load_manifest(manifest_path)
    assert len(rows) == 2


def test_load_missing_manifest_returns_empty_list(tmp_path):
    assert load_manifest(tmp_path / "does_not_exist.csv") == []


def test_find_prior_ok_row_requires_row_intrinsic_eligibility():
    ineligible = {**BASE_ROW, "http_status": 404, "html_snapshot_path": ""}
    assert find_prior_ok_row([ineligible], "http://example.com/") is None


def test_find_prior_ok_row_returns_most_recent_eligible_attempt():
    older = {**BASE_ROW, "collection_run_date": "2026-01-01"}
    newer = {**BASE_ROW, "collection_run_date": "2026-02-01"}
    found = find_prior_ok_row([older, newer], "http://example.com/")
    assert found["collection_run_date"] == "2026-02-01"


def test_find_prior_ok_row_no_match():
    assert find_prior_ok_row([BASE_ROW], "http://different.example/") is None
