"""
Bulk, rate-limited multi-URL capture orchestrator (PHASE3_DATASET_PLAN.md section 3).

dataset.capture.capture_url() implements one URL's attempt; this module fans that out over many
URLs with a concurrency semaphore and a per-host minimum delay, sharing one robots-policy cache
(dataset.robots) across the whole run so a host's robots.txt is fetched once regardless of how
many of its URLs are queued (section 3's "bulk-crawl policy layer").
"""

import asyncio
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import config
from dataset.capture import capture_url


class _HostRateLimiter:
    """Serializes requests to the same host with a minimum delay between them; different hosts
    are independent of each other and can proceed concurrently up to the outer semaphore."""

    def __init__(self, delay_seconds: float):
        self._delay = delay_seconds
        self._locks: Dict[str, asyncio.Lock] = {}
        self._last_request: Dict[str, float] = {}

    def _lock_for(self, host: str) -> asyncio.Lock:
        if host not in self._locks:
            self._locks[host] = asyncio.Lock()
        return self._locks[host]

    async def wait_turn(self, host: str) -> None:
        lock = self._lock_for(host)
        async with lock:
            last = self._last_request.get(host)
            if last is not None:
                remaining = self._delay - (time.monotonic() - last)
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_request[host] = time.monotonic()


async def run_bulk_capture(
    targets: List[Dict[str, Any]],
    *,
    collection_run_date: str,
    manifest_rows: List[Dict[str, Any]],
    snapshot_dir,
    concurrency: Optional[int] = None,
    host_delay_seconds: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Runs capture_url() for every target dict — each `{"url", "source", "label",
    "source_metadata" (optional), "discovered_from" (optional)}` — bounded by a concurrency
    semaphore (config.DATASET_CRAWL_CONCURRENCY by default) and a per-host minimum delay
    (config.DATASET_CRAWL_HOST_DELAY_SECONDS), sharing one robots-policy cache for the whole run.

    `manifest_rows` is one snapshot of prior rows, consulted for the already_collected check for
    every target — it is not updated mid-run as new rows complete, matching capture_url()'s own
    contract (each attempt only sees history that existed before this run started). Returns
    results in the same order as `targets`.
    """
    concurrency = config.DATASET_CRAWL_CONCURRENCY if concurrency is None else concurrency
    host_delay_seconds = (
        config.DATASET_CRAWL_HOST_DELAY_SECONDS if host_delay_seconds is None else host_delay_seconds
    )
    semaphore = asyncio.Semaphore(max(1, concurrency))
    rate_limiter = _HostRateLimiter(host_delay_seconds)
    robots_cache: Dict[str, str] = {}

    async def _run_one(target: Dict[str, Any]) -> Dict[str, Any]:
        host = urllib.parse.urlsplit(target["url"]).hostname or ""
        async with semaphore:
            await rate_limiter.wait_turn(host)
            return await capture_url(
                target["url"],
                source=target["source"],
                label=target["label"],
                collection_run_date=collection_run_date,
                manifest_rows=manifest_rows,
                snapshot_dir=snapshot_dir,
                source_metadata=target.get("source_metadata"),
                discovered_from=target.get("discovered_from", ""),
                robots_cache=robots_cache,
            )

    return list(await asyncio.gather(*(_run_one(t) for t in targets)))
