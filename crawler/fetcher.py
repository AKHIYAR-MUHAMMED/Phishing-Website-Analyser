"""
HTTP GET fetcher with explicit safety limits and explicit failure states.

Scope decision (Phase 2): this fetches one URL per call, for a human-initiated, on-demand scan.
It does not read robots.txt and applies no crawl-delay/rate-limiting of its own — appropriate
for single interactive requests, not for unattended bulk crawling. Add both before any future
bulk-collection use (Phase 3 dataset collection) of this module.
"""

import hashlib
import ssl
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

import config
from crawler.extract import extract_title_and_text

ALLOWED_SCHEMES = {"http", "https"}
TEXTUAL_CONTENT_TYPE_MARKERS = ("text/", "html", "xml", "json")


class NetworkBlockedError(RuntimeError):
    """Raised by the test suite's network guard; never raised in normal operation."""


def _default_client(**kwargs) -> httpx.AsyncClient:
    return httpx.AsyncClient(**kwargs)


_client_factory = _default_client


def _allow_all_hosts(host: Optional[str]) -> None:
    return None


# The test suite's conftest.py monkeypatches this to reject any host but 127.0.0.1/localhost,
# so a test that forgets to point at the local test server fails immediately and clearly
# instead of making a live request. No-op (allows everything) in normal operation.
_host_guard = _allow_all_hosts


def _validate_url(url: str) -> Optional[str]:
    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.netloc:
        return None
    return url.strip()


def _looks_textual(content_type: str) -> bool:
    lowered = content_type.lower()
    return any(marker in lowered for marker in TEXTUAL_CONTENT_TYPE_MARKERS)


def _error(requested_url: str, error_type: str, message: str, started: float, **extra) -> Dict[str, Any]:
    return {
        "status": "error",
        "requested_url": requested_url,
        "error_type": error_type,
        "error_message": message,
        "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 1),
        **extra,
    }


async def fetch_url(
    url: str,
    *,
    timeout: Optional[float] = None,
    max_redirects: Optional[int] = None,
    max_content_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    """Fetches `url` with a GET request. Never raises; every outcome is returned as a dict."""
    requested_url = url
    started = time.perf_counter()

    validated = _validate_url(url)
    if validated is None:
        return _error(requested_url, "invalid_url", "URL must be an absolute http:// or https:// URL.", started)

    try:
        _host_guard(urllib.parse.urlsplit(validated).hostname)
    except NetworkBlockedError as exc:
        return _error(requested_url, "network_disabled", str(exc), started)

    timeout = config.CRAWLER_TIMEOUT_SECONDS if timeout is None else timeout
    max_redirects = config.CRAWLER_MAX_REDIRECTS if max_redirects is None else max_redirects
    max_content_bytes = config.CRAWLER_MAX_CONTENT_BYTES if max_content_bytes is None else max_content_bytes

    try:
        async with _client_factory(
            follow_redirects=True,
            max_redirects=max_redirects,
            timeout=timeout,
            headers={"User-Agent": config.CRAWLER_USER_AGENT},
        ) as client:
            async with client.stream("GET", validated) as response:
                content_length = response.headers.get("content-length")
                if content_length is not None and int(content_length) > max_content_bytes:
                    return _error(requested_url, "content_too_large",
                                  f"Content-Length {content_length} exceeds the {max_content_bytes}-byte limit.",
                                  started, final_url=str(response.url), http_status=response.status_code)

                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > max_content_bytes:
                        return _error(requested_url, "content_too_large",
                                      f"Response body exceeds the {max_content_bytes}-byte limit.",
                                      started, final_url=str(response.url), http_status=response.status_code)

        content_type = response.headers.get("content-type", "")
        if _looks_textual(content_type):
            html = body.decode(response.encoding or "utf-8", errors="replace")
            title, visible_text = extract_title_and_text(html)
        else:
            html, title, visible_text = "", "", ""

        return {
            "status": "ok",
            "requested_url": requested_url,
            "final_url": str(response.url),
            "http_status": response.status_code,
            "content_type": content_type,
            "headers": dict(response.headers),
            "html": html,
            "html_length_bytes": len(body),
            # Hash of the raw wire bytes, before decoding. Added for Phase 3 (see
            # PHASE3_DATASET_PLAN.md section 6): this is the only one of that section's three
            # hashes that cannot be computed by a caller after the fact, since the raw bytes
            # exist only here, briefly, before being decoded and discarded. Additive field;
            # does not change any existing behavior or key.
            "raw_content_sha256": hashlib.sha256(bytes(body)).hexdigest(),
            "title": title,
            "visible_text": visible_text,
            "redirect_count": len(response.history),
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 1),
        }

    except httpx.TooManyRedirects as exc:
        return _error(requested_url, "too_many_redirects", str(exc), started)
    except httpx.TimeoutException as exc:
        return _error(requested_url, "timeout", f"{type(exc).__name__}: {exc}", started)
    except httpx.ConnectError as exc:
        if isinstance(exc.__cause__, ssl.SSLError) or "ssl" in str(exc).lower():
            return _error(requested_url, "ssl_error", str(exc), started)
        return _error(requested_url, "connection_error", str(exc), started)
    except httpx.HTTPError as exc:
        return _error(requested_url, "error", f"{type(exc).__name__}: {exc}", started)
    except Exception as exc:  # never let a malformed response crash the scan pipeline
        return _error(requested_url, "error", f"{type(exc).__name__}: {exc}", started)
