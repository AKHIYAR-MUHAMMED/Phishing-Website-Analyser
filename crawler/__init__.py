"""
Real HTTP crawler (Phase 2).

Public API: `await fetch_url(url)` returns a plain dict, always one of:

  {"status": "ok", "requested_url", "final_url", "http_status", "content_type", "headers",
   "html", "html_length_bytes", "title", "visible_text", "redirect_count", "crawled_at",
   "elapsed_ms"}

  {"status": "error", "requested_url", "error_type", "error_message", "elapsed_ms"}
  where error_type is one of: invalid_url, timeout, connection_error, ssl_error,
  too_many_redirects, content_too_large, network_disabled, error.

Never claims success when the fetch failed. Issues GET requests only: it never submits a form
or credentials. It does not consult robots.txt or apply crawl-rate limiting; that is acceptable
for a single, human-initiated, on-demand scan of one URL, but would need to be added before any
unattended or bulk crawling (see crawler/fetcher.py docstring and CLAUDE.md section 15).
"""

from crawler.fetcher import NetworkBlockedError, fetch_url

__all__ = ["fetch_url", "NetworkBlockedError"]
