"""
Bulk orchestrator tests (PHASE3_DATASET_PLAN.md section 3): concurrency + per-host delay,
against the local test server only.
"""

import asyncio
import time

from dataset.orchestrator import run_bulk_capture


def test_run_bulk_capture_captures_every_target(tmp_path, http_server):
    targets = [
        {"url": http_server.url("/ok"), "source": "test", "label": 1},
        {"url": http_server.url("/big/50"), "source": "test", "label": 0},
    ]
    results = asyncio.run(run_bulk_capture(
        targets, collection_run_date="2026-01-01", manifest_rows=[], snapshot_dir=tmp_path,
        concurrency=5, host_delay_seconds=0.0,
    ))
    assert len(results) == 2
    assert {r["crawl_status"] for r in results} == {"ok"}
    assert results[0]["label"] == 1
    assert results[1]["label"] == 0


def test_run_bulk_capture_enforces_a_minimum_per_host_delay(tmp_path, http_server):
    """Two targets on the SAME host must be spaced at least host_delay_seconds apart, even
    though both are within the concurrency limit."""
    targets = [
        {"url": http_server.url("/ok"), "source": "test", "label": 1},
        {"url": http_server.url("/big/50"), "source": "test", "label": 1},
    ]
    start = time.monotonic()
    asyncio.run(run_bulk_capture(
        targets, collection_run_date="2026-01-01", manifest_rows=[], snapshot_dir=tmp_path,
        concurrency=5, host_delay_seconds=0.3,
    ))
    elapsed = time.monotonic() - start
    assert elapsed >= 0.3


def test_run_bulk_capture_does_not_delay_across_different_hosts(tmp_path, http_server):
    """A per-host delay must not become a global delay: two DIFFERENT hosts should not be
    serialized against each other. Both targets hit the same underlying server, but through two
    different hostnames the network guard allows ("127.0.0.1" and "localhost") — this exercises
    the rate limiter's per-HOST keying (not port), so this only tests timing, not content."""
    port = http_server.base_url.rsplit(":", 1)[1]
    targets = [
        {"url": http_server.url("/ok"), "source": "test", "label": 1},
        {"url": f"http://localhost:{port}/big/50", "source": "test", "label": 1},
    ]
    start = time.monotonic()
    results = asyncio.run(run_bulk_capture(
        targets, collection_run_date="2026-01-01", manifest_rows=[], snapshot_dir=tmp_path,
        concurrency=5, host_delay_seconds=5.0,
    ))
    elapsed = time.monotonic() - start
    assert elapsed < 4.0  # would be >= 5s if the two different hosts were wrongly serialized
    assert len(results) == 2
    assert {r["crawl_status"] for r in results} == {"ok"}
