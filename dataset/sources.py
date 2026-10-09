"""
Source-specific feed parsing (PHASE3_DATASET_PLAN.md section 1, section 4).

Each parser takes the raw feed bytes (as returned by dataset.feeds.fetch_feed_bytes) and returns
(rows, malformed_lines): `rows` are ready to become capture targets, `malformed_lines` are raw
lines/records that could not be parsed at all (recorded as `source_parse_error` capture rows by
the caller, per section 10's status vocabulary — never silently dropped).

Endpoint builder functions return the real production URLs; nothing in this module calls them —
callers (dataset.run_collection, tests) supply whatever endpoint they want fetched, so tests can
point collection at the local test server instead.
"""

import csv
import io
import urllib.parse
import zipfile
from typing import Any, Dict, List, Tuple


class TrancoFeedFormatError(RuntimeError):
    """Raised when a Tranco feed response looks like a ZIP archive but is not one, or does not
    contain exactly the expected CSV member. A feed source changing shape underneath the parser
    must be surfaced loudly, never silently misparsed as zero/garbage rows."""


_TRANCO_ZIP_MAGIC = b"PK\x03\x04"
_TRANCO_EXPECTED_CSV_MEMBER = "top-1m.csv"


def phishtank_bulk_feed_url(app_key: str = "") -> str:
    """PHASE3_DATASET_PLAN.md section 1, approved decision 11: anonymous by default, a key
    (once configured) is appended as a query parameter, never embedded any other way."""
    base = "http://data.phishtank.com/data/online-valid.csv"
    return f"{base}?app_key={app_key}" if app_key else base


def openphish_feed_url() -> str:
    return "https://openphish.com/feed.txt"


def tranco_list_url(list_id: str = "daily") -> str:
    """Real-feed format probe (2026-09-29): tranco-list.eu/top-1m.csv.zip redirects to
    tranco-list.eu/download/daily/top-1m.csv.zip, which returns a ZIP archive containing
    top-1m.csv (see unwrap_tranco_feed_bytes()). This builder reproduces that VERIFIED shape,
    parameterized by list_id (default "daily", the always-current list — the only value this
    was actually verified against). A specific archived Tranco list_id's exact response shape
    (ZIP vs. plain CSV) was NOT verified by that probe; unwrap_tranco_feed_bytes() passes
    through unchanged content that isn't a ZIP, so a plain-CSV response for a non-"daily"
    list_id is still handled correctly, but this has not been tested against a real one."""
    return f"https://tranco-list.eu/download/{list_id}/top-1m.csv.zip"


def unwrap_tranco_feed_bytes(raw_bytes: bytes) -> bytes:
    """The real Tranco daily-list endpoint returns a ZIP archive containing one CSV member
    (verified: real-feed format probe, 2026-09-29). If `raw_bytes` does not start with the ZIP
    magic number, it is returned unchanged — safe to call unconditionally regardless of which
    real shape a given endpoint actually returns (e.g. a plain-CSV endpoint needs no unwrapping).

    If `raw_bytes` DOES look like a ZIP, it must contain exactly one member, named exactly
    top-1m.csv — the expected CSV member is validated by name, never assumed to be "whichever
    file happens to be first" in the archive. Any other archive layout, or a response that
    starts with the ZIP magic but isn't a valid ZIP, raises TrancoFeedFormatError rather than
    silently returning zero/garbage parsed rows."""
    if not raw_bytes.startswith(_TRANCO_ZIP_MAGIC):
        return raw_bytes
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as archive:
            names = archive.namelist()
            if names != [_TRANCO_EXPECTED_CSV_MEMBER]:
                raise TrancoFeedFormatError(
                    f"Expected a ZIP containing exactly {_TRANCO_EXPECTED_CSV_MEMBER!r}, "
                    f"found {names!r}."
                )
            with archive.open(_TRANCO_EXPECTED_CSV_MEMBER) as member:
                return member.read()
    except zipfile.BadZipFile as exc:
        raise TrancoFeedFormatError(
            f"Tranco response starts with a ZIP signature but could not be opened: {exc}"
        ) from exc


def parse_phishtank_feed(raw_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """PhishTank bulk feed: CSV with (at least) phish_id, url, verified, verification_time,
    online, target columns. Section 1's correction: filter on BOTH verified=="yes" AND
    online=="yes" — a verified-but-no-longer-online entry is not returned as a row at all
    (it is neither a parse error nor a crawl target)."""
    text = raw_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict[str, Any]] = []
    malformed: List[str] = []
    for raw_row in reader:
        if any(v is None for v in raw_row.values()) or not (raw_row.get("url") or "").strip():
            malformed.append(",".join(str(v) for v in raw_row.values()))
            continue
        if str(raw_row.get("verified", "")).strip().lower() != "yes":
            continue
        if str(raw_row.get("online", "")).strip().lower() != "yes":
            continue
        rows.append({
            "url": raw_row["url"].strip(),
            "source_metadata": {
                "phish_id": raw_row.get("phish_id", ""),
                "verification_time": raw_row.get("verification_time", ""),
                "submission_time": raw_row.get("submission_time", ""),
                "target": raw_row.get("target", ""),
            },
        })
    return rows, malformed


def parse_openphish_feed(raw_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """OpenPhish free feed: plain text, one URL per line, no stable per-entry ID (section 1 —
    this is why the feed digest matters more for OpenPhish than for PhishTank)."""
    text = raw_bytes.decode("utf-8", errors="replace")
    rows: List[Dict[str, Any]] = []
    malformed: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parsed = urllib.parse.urlsplit(stripped)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            malformed.append(stripped)
            continue
        rows.append({"url": stripped, "source_metadata": {}})
    return rows, malformed


def parse_tranco_feed(raw_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Tranco dated list: headerless CSV, "<rank>,<domain>" per line."""
    text = raw_bytes.decode("utf-8", errors="replace")
    rows: List[Dict[str, Any]] = []
    malformed: List[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        parts = next(csv.reader([stripped]))
        if len(parts) < 2:
            malformed.append(stripped)
            continue
        rank_str, domain = parts[0].strip(), parts[1].strip()
        try:
            rank = int(rank_str)
        except ValueError:
            malformed.append(stripped)
            continue
        if not domain:
            malformed.append(stripped)
            continue
        rows.append({"rank": rank, "domain": domain})
    return rows, malformed
