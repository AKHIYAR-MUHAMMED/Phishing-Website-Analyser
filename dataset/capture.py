"""
Single-URL capture: the unit the manifest/capture pipeline is built from
(PHASE3_DATASET_PLAN.md section 10, section 5, section 3).

capture_url() performs one collection attempt and returns a capture-manifest row (section 12a
shape) — it does not itself append to the manifest (the caller does, via
dataset.manifest.append_capture_row), keeping this function simple to test in isolation.

Note on scope: this module implements the per-URL attempt (robots check, same-run retry,
hashing, domain/TLS/rendering-stat capture) required by PHASE3_DATASET_PLAN.md. A bulk,
rate-limited, many-URL orchestrator (the concurrency semaphore and per-host delay described in
section 3) is not built in this pass — see the implementation report's "known gaps". Nothing
here is invoked against a real PhishTank/OpenPhish/Tranco host; every test uses the local
tests/local_server.py fixture.
"""

import json
import re
import subprocess
import urllib.parse
from typing import Any, Dict, List, Optional

import config
from crawler.fetcher import fetch_url
from dataset.domains import PSL_SOURCE, get_registered_domain
from dataset.hashing import compute_hashes
from dataset.manifest import find_prior_ok_row
from dataset.normalize import NORMALIZATION_VERSION, normalize_url
from dataset.rendering_stats import compute_rendering_stats
from dataset.robots import ROBOTS_DISALLOWED, check_robots
from dataset.snapshots import save_snapshot
from dataset.tls_probe import probe_tls

RETRYABLE_ERROR_TYPES = {"timeout", "connection_error"}

# I1 fix: crawler.fetch_url populates `html` for anything "textual" (text/*, xml, json), which
# is broader than "HTML-like" — the plan's section 10 explicitly makes a 2xx non-HTML response
# ineligible. This module makes its own, stricter check rather than relying on fetch_url's
# `html` being non-empty as a proxy for "this is a real page" (the review's C1/I1 finding).
_HTML_CONTENT_TYPE_RE = re.compile(r"\bhtml\b", re.IGNORECASE)
_HTML_SNIFF_RE = re.compile(r"^\s*(<!doctype\s+html|<html\b)", re.IGNORECASE)

_META_REFRESH_RE = re.compile(r"<meta[^>]+http-equiv=[\"']?refresh[\"']?", re.IGNORECASE)
_BOT_CHALLENGE_MARKERS = (
    "cf-browser-verification", "checking your browser", "cf-challenge", "attention required",
    "just a moment", "captcha-delivery", "please verify you are a human",
)


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(config.REPO_ROOT),
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _looks_like_html(content_type: str, html: str) -> bool:
    if content_type and _HTML_CONTENT_TYPE_RE.search(content_type):
        return True
    # Some servers mislabel content-type (e.g. text/plain for an HTML error page); fall back to
    # sniffing the start of the decoded body. A missing/wrong content-type is common enough on
    # low-quality phishing infrastructure that this fallback matters in practice.
    if html and _HTML_SNIFF_RE.match(html):
        return True
    return False


def _detect_meta_refresh(html: str) -> bool:
    return bool(html) and bool(_META_REFRESH_RE.search(html))


def _detect_bot_challenge(html: str) -> bool:
    if not html:
        return False
    lowered = html.lower()
    if any(marker in lowered for marker in _BOT_CHALLENGE_MARKERS):
        return True
    # Near-empty body relative to script content: a common interstitial shape.
    body_match = re.search(r"<body[^>]*>(.*)</body>", html, re.IGNORECASE | re.DOTALL)
    if body_match:
        body_text = re.sub(r"<[^>]+>", "", body_match.group(1)).strip()
        script_count = len(re.findall(r"<script", html, re.IGNORECASE))
        if len(body_text) < 200 and script_count >= 2:
            return True
    return False


def _empty_capture_fields() -> Dict[str, Any]:
    return {
        "crawled_at": "", "final_url": "", "final_registered_domain": "",
        "domain_redirect_mismatch": False, "http_status": "", "redirect_count": "",
        "content_type": "", "html_length_bytes": "", "decoded_text_length": "",
        "visible_text_length": "", "dom_node_count": "", "script_count": "",
        "raw_content_sha256": "", "html_sha256": "", "normalized_html_sha256": "",
        "html_snapshot_path": "", "error_type": "", "error_message": "",
        "meta_refresh_detected": False, "bot_challenge_suspected": False,
        "tls_captured": False, "tls_version": "", "certificate_subject": "",
        "certificate_issuer": "", "certificate_self_signed": None, "certificate_not_after": "",
        "discovered_from": "", "feed_to_crawl_latency_seconds": "",
    }


async def capture_url(
    url: str,
    *,
    source: str,
    label: int,
    collection_run_date: str,
    manifest_rows: List[Dict[str, Any]],
    snapshot_dir,
    source_metadata: Optional[Dict[str, Any]] = None,
    discovered_from: str = "",
    check_robots_txt: bool = True,
    robots_cache: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Performs one collection attempt for `url` and returns a capture-manifest row
    (dataset.manifest.CAPTURE_COLUMNS shape). Never raises."""
    normalized = normalize_url(url)
    source_domain = get_registered_domain(url)

    base_row: Dict[str, Any] = {
        "url": url,
        "normalized_url": normalized,
        "source": source,
        "source_metadata": json.dumps(source_metadata or {}, sort_keys=True),
        "label": label,
        "collection_run_date": collection_run_date,
        "registered_domain": source_domain,
        "discovered_from": discovered_from,
        "collection_tool_version": _git_sha(),
        "normalization_version": NORMALIZATION_VERSION,
        "psl_snapshot_date": PSL_SOURCE,
        "retry_count": 0,
        "robots_result": "",
    }

    prior = find_prior_ok_row(manifest_rows, normalized)
    if prior is not None:
        row = {**base_row, "crawl_status": "already_collected", **_empty_capture_fields()}
        return row

    if check_robots_txt:
        robots_result = await check_robots(url, config.CRAWLER_USER_AGENT, cache=robots_cache)
    else:
        robots_result = ""
    base_row["robots_result"] = robots_result

    if robots_result == ROBOTS_DISALLOWED:
        row = {**base_row, "crawl_status": "robots_disallowed", **_empty_capture_fields()}
        row["robots_result"] = robots_result
        return row

    retry_count = 0
    result = await fetch_url(url)
    if result["status"] == "error" and result.get("error_type") in RETRYABLE_ERROR_TYPES:
        retry_count = 1
        result = await fetch_url(url)
    base_row["retry_count"] = retry_count

    if result["status"] != "ok":
        row = {
            **base_row,
            "crawl_status": result.get("error_type", "error"),
            **_empty_capture_fields(),
            "error_type": result.get("error_type", ""),
            "error_message": result.get("error_message", ""),
        }
        return row

    raw_html = result.get("html", "") or ""
    content_type = result.get("content_type", "") or ""
    final_url = result.get("final_url", "") or ""
    final_domain = get_registered_domain(final_url) if final_url else ""
    domain_mismatch = bool(source_domain) and bool(final_domain) and source_domain != final_domain

    # I1: only content that is actually HTML-like is treated as page content — a non-HTML
    # textual response (JSON, CSV, plain text) that crawler.fetch_url happily decoded is NOT
    # hashed, snapshotted, or counted as html for eligibility purposes.
    is_html = bool(raw_html.strip()) and _looks_like_html(content_type, raw_html)
    html = raw_html if is_html else ""

    hashes = compute_hashes(html) if html.strip() else {"html_sha256": "", "normalized_html_sha256": ""}
    stats = compute_rendering_stats(html)

    snapshot_path = ""
    if html.strip():
        snapshot_path = save_snapshot(html, hashes["html_sha256"], snapshot_dir)

    tls_fields = {
        "tls_captured": False, "tls_version": "", "certificate_subject": "",
        "certificate_issuer": "", "certificate_self_signed": None, "certificate_not_after": "",
    }
    if urllib.parse.urlsplit(final_url or url).scheme == "https":
        host = urllib.parse.urlsplit(final_url or url).hostname
        tls_fields = await probe_tls(host)

    row = {
        **base_row,
        "crawl_status": "ok",
        "crawled_at": result.get("crawled_at", ""),
        "final_url": final_url,
        "final_registered_domain": final_domain,
        "domain_redirect_mismatch": domain_mismatch,
        "http_status": result.get("http_status", ""),
        "redirect_count": result.get("redirect_count", ""),
        "content_type": result.get("content_type", ""),
        "html_length_bytes": result.get("html_length_bytes", ""),
        "decoded_text_length": len(html),
        "visible_text_length": stats["visible_text_length"],
        "dom_node_count": stats["dom_node_count"],
        "script_count": stats["script_count"],
        "raw_content_sha256": result.get("raw_content_sha256", ""),
        "html_sha256": hashes["html_sha256"],
        "normalized_html_sha256": hashes["normalized_html_sha256"],
        "html_snapshot_path": snapshot_path,
        "error_type": "",
        "error_message": "",
        "meta_refresh_detected": _detect_meta_refresh(html),
        "bot_challenge_suspected": _detect_bot_challenge(html),
        **tls_fields,
        "feed_to_crawl_latency_seconds": "",
    }
    return row
