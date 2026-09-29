"""
End-to-end tests of dataset.run_collection.run_collection() (PHASE3_DATASET_PLAN.md section 21.1
and the overall Phase 3 pipeline): fixture feed servers + the local crawl test server only. No
real PhishTank/OpenPhish/Tranco/network access — the benign Tranco domains used for the
"never succeeds" scenarios below are deliberately non-local so these tests also prove the
network guard blocks them rather than silently reaching a real host.
"""

import asyncio
import io
import json
import zipfile

from dataset.manifest import load_manifest
from dataset.persistence import read_used_tranco_ranks
from dataset.run_collection import run_collection
from local_server import FeedTestServer


def _build_feed_server(http_server, tranco_body=b"1,blocked.example\n2,blocked2.example\n"):
    phishtank_csv = (
        "phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target\n"
        f"1,{http_server.url('/ok')},http://x,2026-01-01,yes,2026-01-01,yes,PayPal\n"
    ).encode("utf-8")
    openphish_txt = (http_server.url("/big/50") + "\n").encode("utf-8")
    return FeedTestServer({
        "/phishtank.csv": phishtank_csv,
        "/openphish.txt": openphish_txt,
        "/tranco.csv": tranco_body,
    }).start()


def _paths(tmp_path):
    return dict(
        manifest_path=tmp_path / "manifest.csv",
        raw_html_dir=tmp_path / "raw" / "html",
        derived_dir=tmp_path / "derived",
        splits_dir=tmp_path / "splits",
        feed_digests_dir=tmp_path / "feed_digests",
        backups_dir=tmp_path / "backups",
        card_path=tmp_path / "DATASET_CARD.md",
        tranco_used_ranks_path=tmp_path / "used_ranks.json",
        raw_feeds_dir=tmp_path / "raw" / "feeds",
    )


def test_run_collection_end_to_end_against_fixtures(tmp_path, http_server):
    feed_server = _build_feed_server(http_server)
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, concurrency=5, host_delay_seconds=0.0,
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()

    summary = result["summary"]
    assert summary["phishing_targets"] == 2
    assert summary["benign_homepage_targets"] == 2
    assert summary["by_crawl_status"]["ok"] == 2
    assert summary["by_crawl_status"]["network_disabled"] == 2  # blocked.example, blocked2.example
    assert summary["malformed_feed_lines"] == {"phishtank": 0, "openphish": 0, "tranco": 0}
    assert summary["in_run_duplicate_targets_merged"] == 0
    assert summary["benign_second_page_targets"] == 0  # no homepage succeeded, nothing to discover from
    # C-2: neither benign rank ever got a successful capture, so neither is "used".
    assert summary["ranks_successfully_captured"] == []

    manifest_rows = load_manifest(tmp_path / "manifest.csv")
    assert len(manifest_rows) == 4  # every attempt is recorded, including the 2 blocked ones

    selection_rows = result["selection_rows"]
    assert len(selection_rows) == 2  # only URLs that ever reached crawl_status=="ok" appear here
    eligible_urls = {r["normalized_url"] for r in selection_rows if r["eligible"]}
    assert len(eligible_urls) == 2

    assert read_used_tranco_ranks(tmp_path / "used_ranks.json") == set()

    card_text = (tmp_path / "DATASET_CARD.md").read_text(encoding="utf-8")
    assert "Total capture attempts: 4" in card_text
    assert "Benign second-page (login-link) rows discovered from a homepage: 0" in card_text


def test_run_collection_merges_a_url_shared_by_two_phishing_feeds_c1(tmp_path, http_server):
    """C-1 regression: the same URL listed by both PhishTank and OpenPhish must be crawled
    exactly once, with both sources' provenance preserved, not silently dropped."""
    shared_url = http_server.url("/ok")
    phishtank_csv = (
        "phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target\n"
        f"1,{shared_url},http://x,2026-01-01,yes,2026-01-01,yes,PayPal\n"
    ).encode("utf-8")
    openphish_txt = (shared_url + "\n").encode("utf-8")
    feed_server = FeedTestServer({
        "/phishtank.csv": phishtank_csv, "/openphish.txt": openphish_txt, "/tranco.csv": b"",
    }).start()
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            **_paths(tmp_path),
        ))

        summary = result["summary"]
        assert summary["phishing_targets"] == 2  # 2 feed rows in...
        assert summary["in_run_duplicate_targets_merged"] == 1  # ...merged down to 1 crawl target
        assert summary["by_crawl_status"]["ok"] == 1  # crawled exactly once

        manifest_rows = load_manifest(tmp_path / "manifest.csv")
        assert len(manifest_rows) == 1
        row = manifest_rows[0]
        assert row["source"] == "phishtank;openphish"
        merged_metadata = json.loads(row["source_metadata"])
        assert set(merged_metadata.keys()) == {"phishtank", "openphish"}
        assert merged_metadata["phishtank"]["phish_id"] == "1"

        # Cross-run retry/dedup (section 5) must still work after this in-run merge: a second
        # run listing the SAME url in both feeds again must see it as already_collected, not
        # re-merge-and-recrawl it.
        second = asyncio.run(run_collection(
            run_date="2026-01-02", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            **_paths(tmp_path),
        ))
        assert second["summary"]["by_crawl_status"] == {"already_collected": 1}
        manifest_rows = load_manifest(tmp_path / "manifest.csv")
        assert len(manifest_rows) == 2
    finally:
        feed_server.stop()


def test_run_collection_does_not_consume_a_rank_when_the_capture_never_succeeds_c2(tmp_path, http_server):
    """C-2 regression (interrupted/failed run): a Tranco rank whose collection attempt did not
    succeed must remain available for a later run — it is not permanently burned."""
    feed_server = _build_feed_server(http_server, tranco_body=b"1,blocked.example\n")
    try:
        first = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0, benign_target_count=1,
            **_paths(tmp_path),
        ))
        assert first["summary"]["ranks_sampled"] == [1]
        assert first["summary"]["ranks_successfully_captured"] == []
        assert read_used_tranco_ranks(tmp_path / "used_ranks.json") == set()

        second = asyncio.run(run_collection(
            run_date="2026-01-02", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0, benign_target_count=1,
            **_paths(tmp_path),
        ))
        # Rank 1 was never successfully handled, so it is sampled again, not skipped.
        assert second["summary"]["ranks_sampled"] == [1]
    finally:
        feed_server.stop()


def test_run_collection_marks_a_rank_used_only_after_success_and_never_resamples_it_c2(tmp_path, http_server):
    """C-2 regression (the success side): once a rank's homepage capture DOES succeed, it is
    marked used and a later run must not resample it, preserving without-replacement sampling."""
    port = http_server.base_url.rsplit(":", 1)[1]
    tranco_body = f"1,127.0.0.1:{port}\n".encode("utf-8")
    feed_server = _build_feed_server(http_server, tranco_body=tranco_body)
    try:
        first = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0, benign_target_count=1,
            benign_url_scheme="http",
            **_paths(tmp_path),
        ))
        assert first["summary"]["ranks_sampled"] == [1]
        assert first["summary"]["ranks_successfully_captured"] == [1]
        assert read_used_tranco_ranks(tmp_path / "used_ranks.json") == {1}

        second = asyncio.run(run_collection(
            run_date="2026-01-02", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0, benign_target_count=1,
            benign_url_scheme="http",
            **_paths(tmp_path),
        ))
        # The only rank in this tiny fixture feed was already used successfully: nothing left
        # to sample without replacement.
        assert second["summary"]["ranks_sampled"] == []
    finally:
        feed_server.stop()


def test_run_collection_discovers_and_captures_a_benign_second_page(tmp_path, http_server):
    """Section 8: a successfully-captured Tranco homepage containing a same-domain login link
    triggers a second capture for that link, recorded with discovered_from set."""
    port = http_server.base_url.rsplit(":", 1)[1]
    tranco_body = f"1,127.0.0.1:{port}\n".encode("utf-8")
    feed_server = _build_feed_server(http_server, tranco_body=tranco_body)
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0, benign_target_count=1,
            benign_url_scheme="http",
            **_paths(tmp_path),
        ))
        summary = result["summary"]
        assert summary["benign_second_page_targets"] == 1

        manifest_rows = load_manifest(tmp_path / "manifest.csv")
        second_page_rows = [r for r in manifest_rows if r.get("discovered_from")]
        assert len(second_page_rows) == 1
        assert second_page_rows[0]["crawl_status"] == "ok"
        assert second_page_rows[0]["discovered_from"] == f"http://127.0.0.1:{port}/"
        assert second_page_rows[0]["url"] == f"http://127.0.0.1:{port}/login"

        card_text = (tmp_path / "DATASET_CARD.md").read_text(encoding="utf-8")
        assert "Benign second-page (login-link) rows discovered from a homepage: 1" in card_text
        assert "homepage-triggered" in card_text
    finally:
        feed_server.stop()


def test_run_collection_populates_feed_to_crawl_latency_for_phishtank_rows(tmp_path, http_server):
    phishtank_csv = (
        "phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target\n"
        f"1,{http_server.url('/ok')},http://x,2026-01-01,yes,2026-01-01T00:00:00+00:00,yes,PayPal\n"
    ).encode("utf-8")
    feed_server = FeedTestServer({
        "/phishtank.csv": phishtank_csv, "/openphish.txt": b"", "/tranco.csv": b"",
    }).start()
    try:
        asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            **_paths(tmp_path),
        ))
        manifest_rows = load_manifest(tmp_path / "manifest.csv")
        row = manifest_rows[0]
        assert row["crawl_status"] == "ok"
        latency = float(row["feed_to_crawl_latency_seconds"])
        assert latency > 0  # crawled well after the fixture's 2026-01-01 verification_time
    finally:
        feed_server.stop()


def test_run_collection_normalizes_source_parse_error_labels(tmp_path, http_server):
    """Malformed feed lines are recorded with a label consistent with their source: both
    phishing feeds imply label=1 even for a line that failed to parse; a malformed Tranco line
    has no label at all (never became a specific benign target) and is left empty, not guessed."""
    phishtank_csv = (
        "phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target\n"
        "1,,http://x,2026-01-01,yes,2026-01-01,yes\n"  # missing url: malformed
    ).encode("utf-8")
    openphish_txt = b"not-a-url\n"
    tranco_csv = b"not-a-rank,example.com\n"
    feed_server = FeedTestServer({
        "/phishtank.csv": phishtank_csv, "/openphish.txt": openphish_txt, "/tranco.csv": tranco_csv,
    }).start()
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            **_paths(tmp_path),
        ))
        assert result["summary"]["malformed_feed_lines"] == {"phishtank": 1, "openphish": 1, "tranco": 1}
        manifest_rows = load_manifest(tmp_path / "manifest.csv")
        by_source = {r["source"]: r for r in manifest_rows if r["crawl_status"] == "source_parse_error"}
        assert by_source["phishtank"]["label"] == "1"
        assert by_source["openphish"]["label"] == "1"
        assert by_source["tranco"]["label"] == ""
    finally:
        feed_server.stop()


def test_run_collection_is_reproducible_given_the_same_seed_21_1_item_1(tmp_path, http_server):
    """PHASE3_DATASET_PLAN.md section 21.1 item 1, directly: given the same fixture feeds and
    the same seed, running collection twice from two CLEAN environments produces identical
    manifest rows (ignoring the genuinely time-varying crawled_at/latency fields) and identical
    selection rows."""
    run_a_dir, run_b_dir = tmp_path / "a", tmp_path / "b"
    run_a_dir.mkdir()
    run_b_dir.mkdir()

    async def _run(target_dir):
        feed_server = _build_feed_server(http_server)
        try:
            return await run_collection(
                run_date="2026-01-01", version="v1",
                phishtank_endpoint=feed_server.url("/phishtank.csv"),
                openphish_endpoint=feed_server.url("/openphish.txt"),
                tranco_endpoint=feed_server.url("/tranco.csv"),
                tranco_list_id="test-list", seed=7, host_delay_seconds=0.0,
                **_paths(target_dir),
            )
        finally:
            feed_server.stop()

    result_a = asyncio.run(_run(run_a_dir))
    result_b = asyncio.run(_run(run_b_dir))

    def _strip_time_varying(row):
        return {k: v for k, v in row.items() if k not in ("crawled_at", "feed_to_crawl_latency_seconds")}

    manifest_a = [_strip_time_varying(r) for r in load_manifest(run_a_dir / "manifest.csv")]
    manifest_b = [_strip_time_varying(r) for r in load_manifest(run_b_dir / "manifest.csv")]
    assert manifest_a == manifest_b

    assert result_a["selection_rows"] == result_b["selection_rows"]


def test_run_collection_handles_a_zip_wrapped_tranco_feed(tmp_path, http_server):
    """Real-feed format probe (2026-09-29): the real Tranco endpoint returns a ZIP archive, not
    plain CSV. This proves the fetch-through-parse path for Tranco actually handles that shape,
    not just the unit-level unwrap function in isolation."""
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as z:
        z.writestr("top-1m.csv", "1,blocked.example\n2,blocked2.example\n")
    tranco_zip_body = zip_buf.getvalue()

    feed_server = _build_feed_server(http_server, tranco_body=tranco_zip_body)
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0, benign_target_count=2,
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()

    # Both ranks parsed out of the ZIP-wrapped CSV and sampled — proves the archive was
    # unwrapped and handed to parse_tranco_feed correctly, not silently dropped or garbled.
    assert result["summary"]["ranks_sampled"] == [1, 2]
    # The committed feed digest still hashes the RAW (zipped) response, not the unwrapped CSV.
    tranco_digest = next(d for d in result["summary"]["feed_digests"] if d["source"] == "tranco")
    import hashlib
    assert tranco_digest["sha256"] == hashlib.sha256(tranco_zip_body).hexdigest()
