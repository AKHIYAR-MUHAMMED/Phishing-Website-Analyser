"""
Feed acquisition and digests (PHASE3_DATASET_PLAN.md section 1, section 2, section 18).

fetch_feed_bytes() downloads one feed response; it reuses crawler.fetcher's client factory and
host guard (looked up dynamically, so the test suite's network-block monkeypatch applies here
too) so it is exercised in tests only against the local test server, never a real source.

compute_feed_digest() is the small, redistribution-safe artifact that is committed instead of
the raw feed response (approved decision 13): source name, a secret-redacted endpoint, a
timestamp, the raw response's sha256, and its row count. The raw feed bytes themselves are not
committed (section 2).
"""

import hashlib
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict

import config
from crawler import fetcher as _fetcher
from dataset.redaction import redact_url


async def fetch_feed_bytes(url: str, timeout: float = None) -> bytes:
    """Downloads one feed response. Raises on any transport failure — a feed download failing
    is a run-stopping condition for that source, unlike a single URL's crawl failure."""
    parsed = urllib.parse.urlsplit(url)
    _fetcher._host_guard(parsed.hostname)
    timeout = config.CRAWLER_TIMEOUT_SECONDS if timeout is None else timeout
    async with _fetcher._client_factory(
        timeout=timeout, headers={"User-Agent": config.CRAWLER_USER_AGENT},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def compute_feed_digest(source: str, endpoint: str, raw_bytes: bytes, row_count: int) -> Dict[str, Any]:
    return {
        "source": source,
        "endpoint": redact_url(endpoint),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "row_count": row_count,
    }
