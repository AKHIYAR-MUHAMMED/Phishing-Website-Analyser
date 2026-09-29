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
from pathlib import Path

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


# --- Feed-source isolation (one source's failure must not prevent the others from running) ---
#
# Triggered for real by the small controlled pilot: PhishTank returning a real HTTP 403 aborted
# the entire run before OpenPhish or Tranco were ever fetched. These tests reproduce that failure
# mode locally (a 404 from the fixture feed server stands in for "fetch failed"; a corrupt ZIP
# body stands in for "fetched fine, failed to parse"; a non-local endpoint exercises the network
# guard) and assert every other source still completes normally.

def test_run_collection_all_three_sources_succeed_status_is_ok_for_each(tmp_path, http_server):
    feed_server = _build_feed_server(http_server)
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()
    assert result["summary"]["feed_source_status"] == {
        "phishtank": {"status": "ok", "error_message": ""},
        "openphish": {"status": "ok", "error_message": ""},
        "tranco": {"status": "ok", "error_message": ""},
    }
    assert all(d["status"] == "ok" for d in result["summary"]["feed_digests"])


def test_run_collection_phishtank_fetch_failure_does_not_block_openphish_or_tranco(tmp_path, http_server):
    """Reproduces the real pilot failure locally: PhishTank returning a non-2xx response (here,
    a 404 from the fixture server — the real run hit a 403) must not prevent OpenPhish and
    Tranco from being fetched and processed."""
    feed_server = _build_feed_server(http_server)
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/does-not-exist.csv"),  # 404 from FeedTestServer
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0, benign_target_count=2,
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()

    status = result["summary"]["feed_source_status"]
    assert status["phishtank"]["status"] == "fetch_error"
    assert status["phishtank"]["error_message"]  # non-empty, real diagnostic text
    assert status["openphish"]["status"] == "ok"
    assert status["tranco"]["status"] == "ok"

    # OpenPhish and Tranco actually completed the normal pipeline: OpenPhish's URL was crawled,
    # Tranco's ranks were sampled.
    assert result["summary"]["by_crawl_status"].get("ok", 0) >= 1
    assert result["summary"]["ranks_sampled"] == [1, 2]

    # No fabricated PhishTank rows: zero phishing targets came from the failed source, and no
    # manifest row anywhere claims a phishtank origin.
    manifest_rows = load_manifest(tmp_path / "manifest.csv")
    assert all("phishtank" not in str(r.get("source", "")) for r in manifest_rows)
    assert result["summary"]["malformed_feed_lines"]["phishtank"] == 0


def test_run_collection_openphish_fetch_failure_does_not_block_phishtank_or_tranco(tmp_path, http_server):
    feed_server = _build_feed_server(http_server)
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/does-not-exist.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0, benign_target_count=2,
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()

    status = result["summary"]["feed_source_status"]
    assert status["openphish"]["status"] == "fetch_error"
    assert status["phishtank"]["status"] == "ok"
    assert status["tranco"]["status"] == "ok"
    assert result["summary"]["ranks_sampled"] == [1, 2]
    manifest_rows = load_manifest(tmp_path / "manifest.csv")
    assert all("openphish" not in str(r.get("source", "")) for r in manifest_rows)


def test_run_collection_tranco_fetch_failure_does_not_block_phishtank_or_openphish(tmp_path, http_server):
    feed_server = _build_feed_server(http_server)
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/does-not-exist.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()

    status = result["summary"]["feed_source_status"]
    assert status["tranco"]["status"] == "fetch_error"
    assert status["phishtank"]["status"] == "ok"
    assert status["openphish"]["status"] == "ok"
    # Tranco contributed zero ranks (nothing to sample from) but did not crash the run.
    assert result["summary"]["ranks_sampled"] == []
    assert result["summary"]["benign_homepage_targets"] == 0
    assert result["summary"]["by_crawl_status"].get("ok", 0) >= 2  # phishtank + openphish targets
    manifest_rows = load_manifest(tmp_path / "manifest.csv")
    assert all("tranco" not in str(r.get("source", "")) for r in manifest_rows)


def test_run_collection_tranco_parse_failure_is_isolated_like_a_fetch_failure(tmp_path, http_server):
    """A source can fail AFTER a successful fetch too (Tranco's real ZIP-validation path) — this
    must be isolated exactly the same way as a fetch-layer failure, not treated differently."""
    corrupt_zip = b"PK\x03\x04" + b"this is not a valid zip body"
    feed_server = _build_feed_server(http_server, tranco_body=corrupt_zip)
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()

    status = result["summary"]["feed_source_status"]
    assert status["tranco"]["status"] == "parse_error"
    assert status["tranco"]["error_message"]
    assert status["phishtank"]["status"] == "ok"
    assert status["openphish"]["status"] == "ok"
    assert result["summary"]["ranks_sampled"] == []

    # The raw (corrupt) bytes WERE received, so a real digest is still computed over them —
    # distinguishes "fetched fine, couldn't parse" from "never got a response at all".
    tranco_digest = next(d for d in result["summary"]["feed_digests"] if d["source"] == "tranco")
    import hashlib
    assert tranco_digest["sha256"] == hashlib.sha256(corrupt_zip).hexdigest()
    assert tranco_digest["status"] == "parse_error"


def test_run_collection_network_guard_still_applies_to_an_individual_feed_source(tmp_path, http_server):
    """The autouse block_real_network fixture (conftest.py) must still block a non-local feed
    endpoint exactly as before — feed-source isolation must not weaken or bypass it."""
    feed_server = _build_feed_server(http_server)
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint="https://blocked-host.example/online-valid.csv",
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()

    status = result["summary"]["feed_source_status"]
    assert status["phishtank"]["status"] == "network_disabled"
    assert status["openphish"]["status"] == "ok"
    assert status["tranco"]["status"] == "ok"


def test_run_collection_survives_all_three_sources_failing_at_once(tmp_path, http_server):
    """Freebuff review follow-up: per-source isolation is safe by inspection even when EVERY
    source fails in the same run (not just one) — the whole pipeline (targets, orchestrator,
    manifest append, selection/split build, card/run-summary generation) must complete cleanly
    on a fully empty target pool, not just tolerate one failure at a time."""
    feed_server = FeedTestServer({}).start()  # every path 404s: all three feeds fail to fetch
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()

    status = result["summary"]["feed_source_status"]
    assert status["phishtank"]["status"] == "fetch_error"
    assert status["openphish"]["status"] == "fetch_error"
    assert status["tranco"]["status"] == "fetch_error"
    assert all(d["status"] != "ok" for d in result["summary"]["feed_digests"])

    # Zero fabricated rows of either label.
    assert result["summary"]["phishing_targets"] == 0
    assert result["summary"]["benign_homepage_targets"] == 0
    assert result["summary"]["benign_second_page_targets"] == 0
    assert result["summary"]["targets_attempted"] == 0
    assert result["summary"]["ranks_sampled"] == []
    assert result["summary"]["by_crawl_status"] == {}

    # Nothing crashed downstream on the empty pool: manifest is empty (no attempts to record),
    # selection/split build produced an empty-but-valid result, and every committed artifact
    # was still written.
    manifest_rows = load_manifest(tmp_path / "manifest.csv")
    assert manifest_rows == []
    assert result["selection_rows"] == []
    for split_path in result["split_paths"].values():
        assert Path(split_path).read_text(encoding="utf-8") == ""

    card_text = Path(result["card_path"]).read_text(encoding="utf-8")
    assert "Total capture attempts: 0" in card_text
    assert "3 source(s) failed this run" in card_text
    from dataset.redaction import scan_text_for_secrets
    assert scan_text_for_secrets(card_text) == []

    run_summary = json.loads(Path(result["run_summary_path"]).read_text(encoding="utf-8"))
    assert run_summary["targets_attempted"] == 0


def test_run_collection_redacts_a_secret_embedded_in_a_fetch_error_message(tmp_path, http_server):
    """A fetch failure's exception text can embed the request URL (httpx's own error strings do)
    — if that URL carried a real app_key, the raw key must never reach the run summary or
    dataset card via error_message."""
    feed_server = _build_feed_server(http_server)
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/does-not-exist.csv?app_key=SuperSecretValue123456"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()
    error_message = result["summary"]["feed_source_status"]["phishtank"]["error_message"]
    assert "SuperSecretValue123456" not in error_message
    card_text = (tmp_path / "DATASET_CARD.md").read_text(encoding="utf-8")
    assert "SuperSecretValue123456" not in card_text


def test_run_collection_feed_source_status_appears_in_the_dataset_card(tmp_path, http_server):
    """Section 14 item 2: a failed source must be visible in the generated card, not silently
    absent from it."""
    feed_server = _build_feed_server(http_server)
    try:
        asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/does-not-exist.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()
    card_text = (tmp_path / "DATASET_CARD.md").read_text(encoding="utf-8")
    assert "fetch_error" in card_text
    assert "source(s) failed this run" in card_text
    assert "phishtank" in card_text


def test_run_collection_isolation_is_deterministic_across_repeated_runs(tmp_path, http_server):
    """Section 21.1 item 1's reproducibility guarantee must hold even when one source
    consistently fails: the successful sources' results must be identical run to run."""
    feed_server = _build_feed_server(http_server)
    try:
        results = []
        for i, run_date in enumerate(("2026-01-01", "2026-01-02")):
            results.append(asyncio.run(run_collection(
                run_date=run_date, version="v1",
                phishtank_endpoint=feed_server.url("/does-not-exist.csv"),
                openphish_endpoint=feed_server.url("/openphish.txt"),
                tranco_endpoint=feed_server.url("/tranco.csv"),
                tranco_list_id="test-list", seed=1, host_delay_seconds=0.0, benign_target_count=1,
                **_paths(tmp_path / f"run{i}"),
            )))
    finally:
        feed_server.stop()

    assert results[0]["summary"]["feed_source_status"]["phishtank"]["status"] == "fetch_error"
    assert results[1]["summary"]["feed_source_status"]["phishtank"]["status"] == "fetch_error"
    assert results[0]["summary"]["ranks_sampled"] == results[1]["summary"]["ranks_sampled"]
    assert results[0]["summary"]["by_crawl_status"] == results[1]["summary"]["by_crawl_status"]


# --- Bug 1 follow-up: run_collection() must still complete when a snapshot goes missing
# between being captured and the finalization step re-reading it (the real pilot's failure). ---

def test_run_collection_completes_when_a_snapshot_vanishes_before_finalization(tmp_path, http_server, monkeypatch):
    """Simulates external interference mid-run (the pilot's working theory: antivirus/quarantine
    removed a just-written phishing snapshot before write_backup_listing() re-read it) via a
    monkeypatched save_snapshot() that deletes an EARLIER snapshot as a side effect of writing a
    LATER one. run_collection() must still complete: run_summary.json written, the integrity
    failure reported (not silently dropped, not a crash), and DATASET_CARD.md must warn about it."""
    import dataset.capture as capture_module

    real_save_snapshot = capture_module.save_snapshot
    state = {"written": [], "sabotaged": False}

    def sabotaging_save_snapshot(html, html_sha256, base_dir):
        logical_path = real_save_snapshot(html, html_sha256, base_dir)
        physical_path = Path(base_dir) / f"{html_sha256}.html"
        state["written"].append(physical_path)
        if len(state["written"]) == 2 and not state["sabotaged"]:
            state["written"][0].unlink()  # remove the FIRST successfully-written snapshot
            state["sabotaged"] = True
        return logical_path

    monkeypatch.setattr(capture_module, "save_snapshot", sabotaging_save_snapshot)

    phishtank_csv = (
        "phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target\n"
        f"1,{http_server.url('/ok')},http://x,2026-01-01,yes,2026-01-01,yes,PayPal\n"
    ).encode("utf-8")
    openphish_txt = (http_server.url("/big/50") + "\n").encode("utf-8")
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
    finally:
        feed_server.stop()

    assert state["sabotaged"] is True  # the test actually exercised the failure path

    # run_summary.json was still written despite the integrity failure — this is exactly what
    # crashed (never got written at all) in the real pilot run.
    assert Path(result["run_summary_path"]).exists()
    run_summary = json.loads(Path(result["run_summary_path"]).read_text(encoding="utf-8"))
    assert len(run_summary["snapshot_integrity_failures"]) == 1
    assert run_summary["snapshot_integrity_failures"][0]["type"] == "missing_or_unreadable"

    assert len(result["summary"]["snapshot_integrity_failures"]) == 1

    card_text = Path(result["card_path"]).read_text(encoding="utf-8")
    assert "WARNING" in card_text
    assert "1 snapshot(s) failed integrity verification" in card_text

    from dataset.redaction import scan_text_for_secrets
    assert scan_text_for_secrets(card_text) == []


# --- Bug 2: opt-in phishing-side pilot cap ---

def _phishing_scale_feed_server(http_server, phishtank_count=6, openphish_count=4):
    phishtank_lines = "".join(
        f"{i},{http_server.url(f'/big/{i}')},http://x,2026-01-01,yes,2026-01-01,yes,T{i}\n"
        for i in range(1, phishtank_count + 1)
    )
    phishtank_csv = (
        "phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target\n"
        + phishtank_lines
    ).encode("utf-8")
    openphish_txt = "".join(
        http_server.url(f"/big/{100 + i}") + "\n" for i in range(1, openphish_count + 1)
    ).encode("utf-8")
    return FeedTestServer({
        "/phishtank.csv": phishtank_csv, "/openphish.txt": openphish_txt, "/tranco.csv": b"",
    }).start()


def test_run_collection_phishing_target_count_caps_the_final_crawl_target_count(tmp_path, http_server):
    feed_server = _phishing_scale_feed_server(http_server)  # 10 distinct phishing URLs total
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            phishing_target_count=4, benign_target_count=0,
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()

    assert result["summary"]["phishing_feed_row_count"] == 10  # true feed size, unaffected
    assert result["summary"]["phishing_targets"] <= 4
    manifest_rows = load_manifest(tmp_path / "manifest.csv")
    phishing_rows = [r for r in manifest_rows if "phishtank" in r["source"] or "openphish" in r["source"]]
    assert len(phishing_rows) <= 4


def test_run_collection_phishing_target_count_same_seed_is_deterministic(tmp_path, http_server):
    feed_server = _phishing_scale_feed_server(http_server)
    try:
        results = []
        for i in range(2):
            results.append(asyncio.run(run_collection(
                run_date="2026-01-01", version="v1",
                phishtank_endpoint=feed_server.url("/phishtank.csv"),
                openphish_endpoint=feed_server.url("/openphish.txt"),
                tranco_endpoint=feed_server.url("/tranco.csv"),
                tranco_list_id="test-list", seed=7, host_delay_seconds=0.0,
                phishing_target_count=4, benign_target_count=0,
                **_paths(tmp_path / f"run{i}"),
            )))
    finally:
        feed_server.stop()

    urls_a = {r["url"] for r in results[0]["captured_rows"] if r["label"] == 1}
    urls_b = {r["url"] for r in results[1]["captured_rows"] if r["label"] == 1}
    assert urls_a == urls_b


def test_run_collection_phishing_target_count_different_seeds_can_differ(tmp_path, http_server):
    feed_server = _phishing_scale_feed_server(http_server)
    try:
        result_a = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            phishing_target_count=3, benign_target_count=0,
            **_paths(tmp_path / "a"),
        ))
        result_b = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=99, host_delay_seconds=0.0,
            phishing_target_count=3, benign_target_count=0,
            **_paths(tmp_path / "b"),
        ))
    finally:
        feed_server.stop()

    urls_a = {r["url"] for r in result_a["captured_rows"] if r["label"] == 1}
    urls_b = {r["url"] for r in result_b["captured_rows"] if r["label"] == 1}
    assert urls_a != urls_b


def test_run_collection_phishing_target_count_omitted_preserves_unlimited_behavior(tmp_path, http_server):
    feed_server = _phishing_scale_feed_server(http_server)
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            benign_target_count=0,  # phishing_target_count intentionally omitted
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()
    assert result["summary"]["phishing_targets"] == 10
    assert result["summary"]["phishing_feed_row_count"] == 10


def test_run_collection_phishing_target_count_negative_selects_zero_not_a_negative_slice(tmp_path, http_server):
    """Freebuff review follow-up: Python's negative-index slicing (shuffled[:-1], shuffled[:-3])
    would silently keep almost the entire list for a negative count — the opposite of what a
    safety-oriented pilot-size parameter should do. count <= 0 must select zero phishing
    targets, matching sample_benign_ranks()'s own target_count <= 0 convention."""
    feed_server = _phishing_scale_feed_server(http_server)  # 10 distinct phishing URLs total
    try:
        result = asyncio.run(run_collection(
            run_date="2026-01-01", version="v1",
            phishtank_endpoint=feed_server.url("/phishtank.csv"),
            openphish_endpoint=feed_server.url("/openphish.txt"),
            tranco_endpoint=feed_server.url("/tranco.csv"),
            tranco_list_id="test-list", seed=1, host_delay_seconds=0.0,
            phishing_target_count=-1, benign_target_count=0,
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()

    assert result["summary"]["phishing_feed_row_count"] == 10  # true feed size still reported
    assert result["summary"]["phishing_targets"] == 0
    assert result["summary"]["targets_attempted"] == 0
    manifest_rows = load_manifest(tmp_path / "manifest.csv")
    assert manifest_rows == []


def test_run_collection_phishing_cap_sizes_the_implicit_benign_default(tmp_path, http_server):
    """Section 9's benign target_count defaults to len(phishing_targets) when benign_target_count
    is omitted — this must use the CAPPED phishing count, not the original 10-row feed size."""
    tranco_csv = b"".join(f"{i},blocked{i}.example\n".encode() for i in range(1, 11))
    phishtank_lines = "".join(
        f"{i},{http_server.url(f'/big/{i}')},http://x,2026-01-01,yes,2026-01-01,yes,T{i}\n"
        for i in range(1, 7)
    )
    phishtank_csv = (
        "phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target\n"
        + phishtank_lines
    ).encode("utf-8")
    openphish_txt = "".join(
        http_server.url(f"/big/{100 + i}") + "\n" for i in range(1, 5)
    ).encode("utf-8")
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
            phishing_target_count=3,  # benign_target_count intentionally omitted
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()
    assert result["summary"]["phishing_targets"] == 3
    assert result["summary"]["benign_homepage_targets"] == 3


def test_run_collection_phishing_cap_composes_with_in_run_dedup(tmp_path, http_server):
    """C-1's cross-source dedup must still work on whatever survives the cap: a URL shared by
    both phishing feeds should still merge into one crawl target with combined provenance, even
    when phishing_target_count is capping the overall list. The invariant is <=k after dedup,
    never necessarily ==k (duplicates among the capped survivors legitimately reduce it further)."""
    shared_url = http_server.url("/ok")
    phishtank_csv = (
        "phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target\n"
        f"1,{shared_url},http://x,2026-01-01,yes,2026-01-01,yes,PayPal\n"
    ).encode("utf-8")
    openphish_txt = (shared_url + "\n").encode("utf-8")  # same URL, second source
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
            phishing_target_count=2, benign_target_count=0,  # cap >= the 2 pre-dedup rows
            **_paths(tmp_path),
        ))
    finally:
        feed_server.stop()

    manifest_rows = load_manifest(tmp_path / "manifest.csv")
    assert len(manifest_rows) == 1  # merged into one crawl attempt, not two
    assert manifest_rows[0]["source"] == "phishtank;openphish"
    assert result["summary"]["phishing_targets"] <= 2
