"""
robots.txt policy (PHASE3_DATASET_PLAN.md section 3, approved decision 7).

robots.txt is honored uniformly for both labels. Checked for the source host only — a
redirect's target host is never robots-checked, a documented limitation (the plan's section 3),
not fixed here since it would require pre-flighting the redirect chain outside crawler.fetch_url.

Fail-open on a robots.txt fetch failure (§3): if we cannot even retrieve robots.txt, the URL is
not blocked on that basis — the subsequent page fetch produces its own, more informative
failure if the host is actually down, rather than a misleading "robots_disallowed".

Revision note (post-review fixes, I6): a robots.txt response is now fetched with
follow_redirects=True, matching crawler.fetch_url's own behavior — previously a 3xx redirect to
robots.txt's real location returned its (near-empty) redirect-stub body, which robotparser then
read as "no rules" (fail-open by accident, not by the documented design). Also adds an optional
per-host cache (a plain dict the caller owns and passes in) so a bulk run fetches each host's
robots.txt once, not once per URL on that host — but the cache stores the PARSED policy (or a
no-file/unreachable sentinel), never a single allowed/disallowed verdict: robots.txt rules are
frequently path-specific (e.g. "Disallow: /admin" only), so the per-URL can_fetch() decision is
still evaluated fresh against the cached parser for every URL.

Reuses crawler.fetcher's client factory and host guard (read-only imports, not a fetcher.py
behavior change) so the same test network guard that blocks the Phase 2 crawler also blocks
this module during tests.
"""

import urllib.parse
import urllib.robotparser
from typing import Dict, Optional, Union

import config
from crawler import fetcher as _fetcher

ROBOTS_ALLOWED = "allowed"
ROBOTS_DISALLOWED = "disallowed"
ROBOTS_NO_FILE = "no_robots_file"
ROBOTS_UNREACHABLE = "unreachable"

# A cache entry is either a fitted RobotFileParser (rules were retrieved) or one of the two
# sentinel strings below (nothing to parse, or couldn't check — always resolves to allowed).
_NO_FILE_SENTINEL = "__no_robots_file__"
_UNREACHABLE_SENTINEL = "__unreachable__"

RobotsCacheEntry = Union[urllib.robotparser.RobotFileParser, str]
RobotsCache = Dict[str, RobotsCacheEntry]


async def _fetch_robots_policy(netloc: str, scheme: str, hostname: str, user_agent: str) -> RobotsCacheEntry:
    """Fetches and parses one origin's robots.txt (or a sentinel on 404 / any failure). Never
    raises; never makes a network call for anything but the robots.txt endpoint itself.
    `netloc` (host[:port]) is what actually goes into the request URL; `hostname` (no port) is
    what the network guard checks, matching crawler.fetcher's own usage."""
    robots_url = urllib.parse.urlunsplit((scheme, netloc, "/robots.txt", "", ""))
    try:
        _fetcher._host_guard(hostname)
        async with _fetcher._client_factory(
            timeout=config.CRAWLER_TIMEOUT_SECONDS,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        ) as client:
            response = await client.get(robots_url)
    except Exception:
        return _UNREACHABLE_SENTINEL  # fail-open: caller proceeds to the real fetch

    if response.status_code == 404:
        return _NO_FILE_SENTINEL
    if response.status_code >= 400:
        return _UNREACHABLE_SENTINEL

    parser = urllib.robotparser.RobotFileParser()
    try:
        parser.parse(response.text.splitlines())
    except Exception:
        return _UNREACHABLE_SENTINEL
    return parser


def _entry_to_result(entry: RobotsCacheEntry, user_agent: str, url: str) -> str:
    if entry == _NO_FILE_SENTINEL:
        return ROBOTS_NO_FILE
    if entry == _UNREACHABLE_SENTINEL:
        return ROBOTS_UNREACHABLE
    return ROBOTS_ALLOWED if entry.can_fetch(user_agent, url) else ROBOTS_DISALLOWED


async def check_robots(
    url: str,
    user_agent: str = None,
    cache: Optional[RobotsCache] = None,
) -> str:
    """Returns one of ROBOTS_ALLOWED / ROBOTS_DISALLOWED / ROBOTS_NO_FILE / ROBOTS_UNREACHABLE.

    If `cache` is given (a plain dict the caller owns — one per collection run, per section 3),
    the robots.txt *policy* for a host is fetched once and reused for every subsequent URL on
    that host within the run; the per-URL allow/disallow decision is still re-evaluated fresh
    each call against that cached policy, since robots.txt rules can be path-specific.

    Note: urllib.robotparser does not honor a Crawl-delay directive; the crawl policy's own
    fixed per-host delay is the only rate limit actually enforced (see
    PHASE3_DATASET_PLAN.md section 3)."""
    user_agent = user_agent or config.CRAWLER_USER_AGENT
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ROBOTS_UNREACHABLE

    # Cache key includes the port (cache key = origin): two different ports on the same host
    # are different origins and can serve different robots.txt content.
    cache_key = parsed.netloc
    if cache is not None and cache_key in cache:
        entry = cache[cache_key]
    else:
        entry = await _fetch_robots_policy(parsed.netloc, parsed.scheme, parsed.hostname, user_agent)
        if cache is not None:
            cache[cache_key] = entry

    return _entry_to_result(entry, user_agent, url)
