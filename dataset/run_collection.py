"""
Phase 3 collection entry point (PHASE3_DATASET_PLAN.md, all sections — this module wires the
individually-tested pieces together into one run). `python -m dataset.run_collection` re-runs
collection against the real feed endpoints (see the __main__ block); every other caller,
including the test suite, passes explicit `*_endpoint` URLs so a test run can point collection
at the local test server instead (no default ever reaches a real PhishTank/OpenPhish/Tranco
host by accident).

One call to run_collection() performs one full run:
  1. fetch the three feeds, parse them, write feed digests;
  2. build phishing targets and rank-progressively sample benign homepage targets (section 9);
  3. deduplicate ALL of this run's targets by normalized URL (section 5/10 — the same URL can
     legitimately appear in more than one phishing feed; it is crawled once, with every
     contributing source's name and metadata preserved — see _dedupe_targets_by_normalized_url);
  4. capture every deduplicated target through the rate-limited bulk orchestrator (section 3);
  5. from homepages that were successfully captured, discover a same-domain login-link second
     page (section 8) and capture those too, in a second orchestrator pass;
  6. append every result (plus any unparseable feed lines) to the immutable manifest;
  7. mark a Tranco rank as "used" (never resampled again) ONLY if its homepage capture actually
     succeeded (section 9 — an interrupted/failed run must not permanently burn a rank it never
     got usable content for);
  8. rebuild the derived selection artifact for `version` and write every committed artifact
     (selection, splits, dataset card, run summary, backup checksum listing).
"""

import asyncio
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import config
from crawler import fetcher as _fetcher
from dataset import persistence, sources
from dataset.domains import PSL_SOURCE
from dataset.eligibility import row_intrinsic_ok
from dataset.feeds import compute_feed_digest, fetch_feed_bytes
from dataset.link_discovery import find_login_link
from dataset.manifest import append_capture_row, load_manifest
from dataset.normalize import normalize_url
from dataset.orchestrator import run_bulk_capture
from dataset.redaction import redact_text, redact_url
from dataset.sampling import sample_benign_ranks
from dataset.selection import build_selection

# One feed source's failure must never prevent the other independent sources from being
# collected (a real PhishTank block, for example, must not also stop OpenPhish/Tranco). Every
# source ends up with exactly one of these statuses, recorded in the run summary and dataset
# card — never silently merged with "fetched zero rows" (a real empty-but-successful feed).
FEED_STATUS_OK = "ok"
FEED_STATUS_NETWORK_DISABLED = "network_disabled"
FEED_STATUS_FETCH_ERROR = "fetch_error"
FEED_STATUS_PARSE_ERROR = "parse_error"

# section 10: a malformed feed line is recorded with a label where the source itself implies
# one (both phishing feeds only ever list phishing URLs); a Tranco line has no label at all
# until it is turned into a specific benign target (a malformed rank/domain pair was never
# associated with a label to begin with), so it is left empty rather than guessed at 0.
_MALFORMED_ROW_LABELS = {"phishtank": 1, "openphish": 1}


def _malformed_row(source: str, raw_line: str, run_date: str) -> Dict[str, Any]:
    """A manifest row for a feed line that could not be parsed at all (section 10's
    `source_parse_error` status) — recorded, never silently dropped. Columns not set here
    default to "" via manifest.serialize_row's `row.get(col, "")`."""
    return {
        "url": raw_line,
        "source": source,
        "source_metadata": "{}",
        "label": _MALFORMED_ROW_LABELS.get(source, ""),
        "collection_run_date": run_date,
        "crawl_status": "source_parse_error",
        "error_type": "source_parse_error",
        "error_message": raw_line,
    }


def _dedupe_targets_by_normalized_url(targets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Section 1/4/10: the same URL can legitimately appear in more than one phishing feed (e.g.
    both PhishTank and OpenPhish list it). Crawling it twice would waste an attempt and produce
    two manifest rows for one URL in the same run — worse, capture_url()'s already_collected
    check only sees rows that existed BEFORE this run started, so within-run duplicates are
    invisible to it and would both be captured independently.

    Deduplicates by normalize_url(url), preserving first-seen order. `source` becomes a
    `;`-joined string of every contributing source (manifest.py's documented convention for
    multi-source rows). `source_metadata` becomes {source: that source's own metadata} once
    more than one source contributed, so no source's provenance is lost; a URL from only one
    source keeps its original flat metadata shape, unchanged from before this fix.

    This has no effect on cross-run retry/dedup (capture_url's own already_collected check,
    section 5): that logic is untouched and still runs per target exactly as before, using
    whatever manifest_rows snapshot the caller passed in.
    """
    merged: "dict[str, Dict[str, Any]]" = {}
    order: List[str] = []
    for target in targets:
        key = normalize_url(target["url"])
        if key not in merged:
            merged[key] = dict(target)
            merged[key]["_sources"] = [target["source"]]
            merged[key]["_metadata_by_source"] = {target["source"]: target.get("source_metadata") or {}}
            order.append(key)
        else:
            entry = merged[key]
            if target["source"] not in entry["_sources"]:
                entry["_sources"].append(target["source"])
            entry["_metadata_by_source"][target["source"]] = target.get("source_metadata") or {}

    result = []
    for key in order:
        entry = merged[key]
        sources_list = entry.pop("_sources")
        metadata_by_source = entry.pop("_metadata_by_source")
        entry["source"] = ";".join(sources_list)
        entry["source_metadata"] = (
            metadata_by_source[sources_list[0]] if len(sources_list) == 1 else metadata_by_source
        )
        result.append(entry)
    return result


def _cap_targets(
    targets: List[Dict[str, Any]], count: Optional[int], seed: Optional[int],
) -> List[Dict[str, Any]]:
    """Pilot-scale control (independent of Tranco's own without-replacement rank sampling): if
    `count` is given and smaller than `len(targets)`, returns a deterministic, seeded-shuffle
    subset of that size; otherwise returns `targets` unchanged (in particular, `count=None` —
    the default — never alters production/full-collection behavior).

    Applied to the COMBINED, pre-dedup target list, before any real network request — a target
    surviving the cap still goes through the normal dedup/provenance-merge logic afterward
    unchanged, so the final crawl-target count can be <= `count` (never >), not necessarily
    exactly `count` (duplicate URLs among the capped survivors may still merge).

    A seeded shuffle-then-truncate, not "first N of source A then source B", so a small cap is
    not structurally biased toward whichever source happened to be concatenated first.

    `count <= 0` returns [] (not Python's negative-slice behavior, which would silently keep
    almost the entire list for e.g. count=-1) — matches sample_benign_ranks()'s own
    `target_count <= 0` convention, appropriate for a safety-oriented pilot-size parameter.
    """
    if count is None or count >= len(targets):
        return targets
    if count <= 0:
        return []
    rng = random.Random(config.RANDOM_SEED if seed is None else seed)
    shuffled = list(targets)
    rng.shuffle(shuffled)
    return shuffled[:count]


async def _fetch_and_parse_feed_source(fetch_fn, parse_fn):
    """Runs one feed source's fetch step, then its parse step, both isolated from every OTHER
    source: any exception here is caught and turned into a status record instead of propagating
    out of run_collection() and aborting sources that would otherwise have succeeded (a single
    real PhishTank block must not also prevent OpenPhish/Tranco from being collected).

    Fetch and parse are deliberately two separate try blocks, not one: if the fetch succeeds but
    parsing then fails, the already-fetched raw bytes must still be returned (and still get a
    real digest computed over them — see run_collection()) rather than being lost along with the
    parse exception. A single combined try/except would silently discard bytes that were, in
    fact, successfully received.

    `fetch_fn` is a zero-arg async callable returning raw bytes; `parse_fn` is a sync callable
    taking those raw bytes and returning (rows, malformed). Returns
    (raw_bytes_or_None, rows, malformed, status_dict). On any failure, rows and malformed are
    both [] — a failed source contributes zero fabricated rows, and its row_count of 0 is never
    confused with "fetched fine, feed just happened to be empty" because status_dict['status']
    is never FEED_STATUS_OK in that case.

    Status classification:
      - FEED_STATUS_NETWORK_DISABLED: the test suite's (or any caller's) network guard blocked
        the request outright — crawler.fetcher.NetworkBlockedError, the same exception/status
        name already used elsewhere in this codebase for a blocked host (capture.py's
        "network_disabled" crawl_status).
      - FEED_STATUS_FETCH_ERROR: the fetch itself failed — HTTP error status, timeout,
        connection error, too-many-redirects, DNS failure, etc. (dataset.feeds.fetch_feed_bytes
        is documented to raise on any transport failure; this is exactly that raise, now caught
        per-source instead of aborting the whole run).
      - FEED_STATUS_PARSE_ERROR: the feed WAS fetched but its content could not be turned into
        rows — currently only reachable via dataset.sources.TrancoFeedFormatError (the ZIP
        archive didn't contain the expected member). PhishTank/OpenPhish's parsers are designed
        to never raise (malformed lines are skipped and reported, not raised) so this path is
        not currently reachable for them, but is handled generically all the same.
    """
    try:
        raw_bytes = await fetch_fn()
    except _fetcher.NetworkBlockedError as exc:
        return None, [], [], {
            "status": FEED_STATUS_NETWORK_DISABLED, "error_message": redact_text(str(exc)),
        }
    except Exception as exc:
        # redact_text(): an exception's string form can embed the request URL (httpx's own
        # error messages do), which can carry a real secret-shaped query parameter — section 18
        # applies to this new error_message field exactly as it does to every other committed
        # artifact, not just to endpoint URLs recorded the normal way.
        return None, [], [], {
            "status": FEED_STATUS_FETCH_ERROR,
            "error_message": redact_text(f"{type(exc).__name__}: {exc}"),
        }

    try:
        rows, malformed = parse_fn(raw_bytes)
    except Exception as exc:
        return raw_bytes, [], [], {
            "status": FEED_STATUS_PARSE_ERROR,
            "error_message": redact_text(f"{type(exc).__name__}: {exc}"),
        }
    return raw_bytes, rows, malformed, {"status": FEED_STATUS_OK, "error_message": ""}


def _compute_feed_to_crawl_latency_seconds(row: Dict[str, Any]) -> str:
    """Section 9: `crawled_at` minus the source's own listing/verification timestamp, where
    available. Only PhishTank's `verification_time` is currently a usable comparison point
    (OpenPhish and Tranco carry no per-entry timestamp) — every other row is left "", not 0 or
    a guess."""
    if row.get("crawl_status") != "ok" or not row.get("crawled_at"):
        return ""
    try:
        metadata = json.loads(row.get("source_metadata") or "{}")
    except (TypeError, ValueError):
        return ""
    verification_time = metadata.get("verification_time")
    if not verification_time and isinstance(metadata.get("phishtank"), dict):
        verification_time = metadata["phishtank"].get("verification_time")
    if not verification_time:
        return ""
    try:
        crawled_dt = datetime.fromisoformat(str(row["crawled_at"]))
        verified_dt = datetime.fromisoformat(str(verification_time))
        if crawled_dt.tzinfo is None or verified_dt.tzinfo is None:
            # A source's timestamp may be a bare date/naive datetime (no offset) — compare as
            # naive-vs-naive (drop crawled_at's offset) rather than raising or guessing a zone.
            crawled_dt = crawled_dt.replace(tzinfo=None)
            verified_dt = verified_dt.replace(tzinfo=None)
    except (ValueError, TypeError):
        return ""
    return str((crawled_dt - verified_dt).total_seconds())


def _discover_second_page_targets(
    stage1_rows: List[Dict[str, Any]],
    raw_html_dir: Path,
    tranco_list_id: str,
) -> List[Dict[str, Any]]:
    """Section 8: for every successfully-captured Tranco homepage, look for a same-domain
    login-link (dataset.link_discovery.find_login_link, document-order-first-match) and, if
    found, add it as a second capture target. Single hop only — a link found on a discovered
    second page is never itself explored."""
    targets: List[Dict[str, Any]] = []
    for row in stage1_rows:
        if row.get("label") != 0 or "tranco" not in str(row.get("source", "")).split(";"):
            continue
        if row.get("crawl_status") != "ok" or not row.get("html_snapshot_path"):
            continue
        snapshot_path = raw_html_dir / Path(row["html_snapshot_path"]).name
        try:
            html = snapshot_path.read_text(encoding="utf-8")
        except OSError:
            continue
        homepage_url = row.get("final_url") or row["url"]
        login_url = find_login_link(html, homepage_url)
        if not login_url or normalize_url(login_url) == normalize_url(row["url"]):
            continue
        try:
            rank = json.loads(row.get("source_metadata") or "{}").get("rank")
        except (TypeError, ValueError):
            rank = None
        targets.append({
            "url": login_url, "source": "tranco", "label": 0,
            "source_metadata": {"rank": rank, "list_id": tranco_list_id, "stage": "second_page"},
            "discovered_from": row["url"],
        })
    return targets


async def run_collection(
    *,
    run_date: str,
    version: str,
    phishtank_endpoint: str,
    openphish_endpoint: str,
    tranco_endpoint: str,
    tranco_list_id: str = "",
    seed: Optional[int] = None,
    phishing_target_count: Optional[int] = None,
    benign_target_count: Optional[int] = None,
    benign_url_scheme: str = "https",
    concurrency: Optional[int] = None,
    host_delay_seconds: Optional[float] = None,
    manifest_path: Union[str, Path, None] = None,
    raw_html_dir: Union[str, Path, None] = None,
    derived_dir: Union[str, Path, None] = None,
    splits_dir: Union[str, Path, None] = None,
    feed_digests_dir: Union[str, Path, None] = None,
    backups_dir: Union[str, Path, None] = None,
    card_path: Union[str, Path, None] = None,
    tranco_used_ranks_path: Union[str, Path, None] = None,
    previous_selection_path: Union[str, Path, None] = None,
    raw_feeds_dir: Union[str, Path, None] = None,
) -> Dict[str, Any]:
    manifest_path = Path(manifest_path) if manifest_path else config.DATASET_MANIFEST_PATH
    raw_html_dir = Path(raw_html_dir) if raw_html_dir else config.DATASET_RAW_HTML_DIR
    derived_dir = Path(derived_dir) if derived_dir else config.DATASET_DERIVED_DIR
    splits_dir = Path(splits_dir) if splits_dir else config.DATASET_SPLITS_DIR
    feed_digests_dir = Path(feed_digests_dir) if feed_digests_dir else config.DATASET_FEED_DIGESTS_DIR
    backups_dir = Path(backups_dir) if backups_dir else config.DATASET_BACKUPS_DIR
    card_path = Path(card_path) if card_path else config.DATASET_CARD_PATH
    tranco_used_ranks_path = (
        Path(tranco_used_ranks_path) if tranco_used_ranks_path else config.DATASET_TRANCO_USED_RANKS_PATH
    )
    raw_feeds_dir = Path(raw_feeds_dir) if raw_feeds_dir else config.DATASET_RAW_FEEDS_DIR

    # --- Fetch + parse the three feeds, each isolated from the others' failures ---
    def _tranco_parse(raw: bytes):
        # The real Tranco endpoint returns a ZIP archive (real-feed format probe, 2026-09-29);
        # an unexpected archive raises TrancoFeedFormatError, caught by
        # _fetch_and_parse_feed_source and classified as a parse failure — the raw response WAS
        # fetched (and still gets a real digest), it just couldn't be turned into rows.
        return sources.parse_tranco_feed(sources.unwrap_tranco_feed_bytes(raw))

    phishtank_bytes, phishtank_rows, phishtank_malformed, phishtank_status = (
        await _fetch_and_parse_feed_source(
            lambda: fetch_feed_bytes(phishtank_endpoint), sources.parse_phishtank_feed,
        )
    )
    openphish_bytes, openphish_rows, openphish_malformed, openphish_status = (
        await _fetch_and_parse_feed_source(
            lambda: fetch_feed_bytes(openphish_endpoint), sources.parse_openphish_feed,
        )
    )
    tranco_bytes, tranco_rows, tranco_malformed, tranco_status = (
        await _fetch_and_parse_feed_source(
            lambda: fetch_feed_bytes(tranco_endpoint), _tranco_parse,
        )
    )
    feed_source_status = {
        "phishtank": phishtank_status, "openphish": openphish_status, "tranco": tranco_status,
    }

    # A digest can only be computed over bytes that were actually received — a source that
    # failed before any response arrived (raw_bytes is None) gets no digest entry at all; a
    # source that fetched fine but failed to PARSE (raw_bytes present, e.g. Tranco's ZIP
    # validation) still gets a real digest of what was actually received. Either way, a
    # placeholder record is added for a failed source too, so dataset_card.py's sources table
    # shows every source and its status rather than a failed source silently disappearing from
    # the report (never conflated with "endpoint returned a valid, empty feed").
    feed_digests = []
    for source_name, endpoint, raw_bytes, rows, status in (
        ("phishtank", phishtank_endpoint, phishtank_bytes, phishtank_rows, phishtank_status),
        ("openphish", openphish_endpoint, openphish_bytes, openphish_rows, openphish_status),
        ("tranco", tranco_endpoint, tranco_bytes, tranco_rows, tranco_status),
    ):
        if raw_bytes is not None:
            digest = compute_feed_digest(source_name, endpoint, raw_bytes, row_count=len(rows))
            persistence.write_feed_digest(digest, source_name, run_date, feed_digests_dir)
        else:
            digest = {
                "source": source_name, "endpoint": redact_url(endpoint),
                "timestamp": datetime.now(timezone.utc).isoformat(), "sha256": "", "row_count": 0,
            }
        digest["status"] = status["status"]
        digest["error_message"] = status["error_message"]
        feed_digests.append(digest)

    # --- Build phishing targets (labeled 1) ---
    phishing_targets: List[Dict[str, Any]] = [
        {"url": r["url"], "source": "phishtank", "label": 1, "source_metadata": r["source_metadata"]}
        for r in phishtank_rows
    ] + [
        {"url": r["url"], "source": "openphish", "label": 1, "source_metadata": r["source_metadata"]}
        for r in openphish_rows
    ]
    true_phishing_feed_row_count = len(phishing_targets)
    # Pilot-scale control (opt-in; None preserves today's unlimited behavior). Applied BEFORE
    # real crawling AND before benign's own implicit sizing below, so a capped pilot doesn't
    # accidentally sample a benign count matching the ORIGINAL uncapped phishing volume.
    phishing_targets = _cap_targets(phishing_targets, phishing_target_count, seed)

    # --- Sample benign homepage targets (labeled 0), rank-progressive w/o replacement (section 9) ---
    used_ranks = persistence.read_used_tranco_ranks(tranco_used_ranks_path)
    rank_to_domain = {r["rank"]: r["domain"] for r in tranco_rows}
    target_count = benign_target_count if benign_target_count is not None else len(phishing_targets)
    chosen_ranks = sample_benign_ranks(rank_to_domain.keys(), used_ranks, target_count, seed=seed)
    benign_homepage_targets: List[Dict[str, Any]] = [
        {
            "url": f"{benign_url_scheme}://{rank_to_domain[rank]}/", "source": "tranco", "label": 0,
            "source_metadata": {"rank": rank, "list_id": tranco_list_id, "stage": "homepage"},
        }
        for rank in chosen_ranks
    ]

    # --- Stage 1: dedupe (C-1) + capture phishing + benign-homepage targets together ---
    stage1_targets = _dedupe_targets_by_normalized_url(phishing_targets + benign_homepage_targets)
    prior_manifest_rows = load_manifest(manifest_path)
    stage1_rows = await run_bulk_capture(
        stage1_targets,
        collection_run_date=run_date,
        manifest_rows=prior_manifest_rows,
        snapshot_dir=raw_html_dir,
        concurrency=concurrency,
        host_delay_seconds=host_delay_seconds,
    )

    # --- C-2: a rank is "used" (never resampled) only if its homepage capture actually
    # succeeded (row_intrinsic_ok) — an interrupted/failed run leaves the rank available again.
    homepage_url_to_rank = {t["url"]: t["source_metadata"]["rank"] for t in benign_homepage_targets}
    successfully_captured_ranks = {
        homepage_url_to_rank[row["url"]]
        for row in stage1_rows
        if row["url"] in homepage_url_to_rank and row_intrinsic_ok(row)
    }
    persistence.write_used_tranco_ranks(used_ranks | successfully_captured_ranks, tranco_used_ranks_path)

    # --- Stage 2: second-page login-link discovery + capture (section 8) ---
    stage1_normalized_urls = {normalize_url(t["url"]) for t in stage1_targets}
    stage2_targets_raw = _discover_second_page_targets(stage1_rows, raw_html_dir, tranco_list_id)
    stage2_targets = [
        t for t in _dedupe_targets_by_normalized_url(stage2_targets_raw)
        if normalize_url(t["url"]) not in stage1_normalized_urls
    ]
    stage2_rows: List[Dict[str, Any]] = []
    if stage2_targets:
        # manifest_rows for stage 2 includes stage 1's own results so a discovered second-page
        # URL that happens to coincide with something already captured this run is skipped as
        # already_collected rather than re-fetched.
        stage2_rows = await run_bulk_capture(
            stage2_targets,
            collection_run_date=run_date,
            manifest_rows=prior_manifest_rows + stage1_rows,
            snapshot_dir=raw_html_dir,
            concurrency=concurrency,
            host_delay_seconds=host_delay_seconds,
        )

    captured_rows = stage1_rows + stage2_rows
    for row in captured_rows:
        row["feed_to_crawl_latency_seconds"] = _compute_feed_to_crawl_latency_seconds(row)

    for row in captured_rows:
        append_capture_row(row, manifest_path)
    for source_name, malformed_lines in (
        ("phishtank", phishtank_malformed), ("openphish", openphish_malformed), ("tranco", tranco_malformed),
    ):
        for raw_line in malformed_lines:
            append_capture_row(_malformed_row(source_name, raw_line, run_date), manifest_path)

    # --- Rebuild the derived selection artifact for this version (section 12b) ---
    full_manifest_rows = load_manifest(manifest_path)
    previous_selection_rows = (
        persistence.load_selection(previous_selection_path) if previous_selection_path else []
    )
    selection_rows = build_selection(full_manifest_rows, previous_selection_rows, version, seed=seed)

    selection_path = persistence.write_selection(selection_rows, version, derived_dir)
    split_paths = persistence.write_splits(selection_rows, splits_dir)

    # --- Out-of-band backup checksum listing (section 19; the archive/copy step is manual, 21.2)
    # --- Computed BEFORE the card so a snapshot integrity failure can be reported in it (a real
    # pilot run hit exactly this: a captured, manifest-recorded snapshot vanished before this
    # step re-read it — handled per-file now, never aborts the rest of finalization). Each
    # file's EXPECTED hash comes from the manifest row that captured it (the source of truth),
    # not guessed from the filename.
    this_run_html_records = [
        (raw_html_dir / Path(row["html_snapshot_path"]).name, row["html_sha256"])
        for row in captured_rows
        if row.get("crawl_status") == "ok" and row.get("html_snapshot_path")
    ]
    backup_listing_path, snapshot_integrity_failures = persistence.write_backup_listing(
        this_run_html_records, run_date, backups_dir,
    )

    card_written_path = persistence.write_dataset_card(
        full_manifest_rows, selection_rows, version, card_path,
        feed_digests=feed_digests, psl_snapshot_date=PSL_SOURCE,
        snapshot_integrity_failures=snapshot_integrity_failures,
    )

    status_counts: Dict[str, int] = {}
    for row in captured_rows:
        status_counts[row["crawl_status"]] = status_counts.get(row["crawl_status"], 0) + 1

    summary = {
        "run_date": run_date,
        "version": version,
        "targets_attempted": len(stage1_targets) + len(stage2_targets),
        "phishing_feed_row_count": true_phishing_feed_row_count,
        "phishing_targets": len(phishing_targets),
        "benign_homepage_targets": len(benign_homepage_targets),
        "benign_second_page_targets": len(stage2_targets),
        "in_run_duplicate_targets_merged": (len(phishing_targets) + len(benign_homepage_targets)) - len(stage1_targets),
        "ranks_sampled": sorted(chosen_ranks),
        "ranks_successfully_captured": sorted(successfully_captured_ranks),
        "by_crawl_status": status_counts,
        "malformed_feed_lines": {
            "phishtank": len(phishtank_malformed),
            "openphish": len(openphish_malformed),
            "tranco": len(tranco_malformed),
        },
        "feed_source_status": feed_source_status,
        "feed_digests": feed_digests,
        "backup_listing_path": str(backup_listing_path),
        "snapshot_integrity_failures": snapshot_integrity_failures,
        "backup_archive_off_machine_confirmed": False,  # manual step, section 21.2 — never asserted true by code
        "psl_snapshot_date": PSL_SOURCE,
    }
    run_summary_path = persistence.write_run_summary(summary, run_date, raw_feeds_dir)

    return {
        "summary": summary,
        "manifest_path": str(manifest_path),
        "selection_path": str(selection_path),
        "split_paths": {k: str(v) for k, v in split_paths.items()},
        "card_path": str(card_written_path),
        "run_summary_path": str(run_summary_path),
        "backup_listing_path": str(backup_listing_path),
        "captured_rows": captured_rows,
        "selection_rows": selection_rows,
    }


def main() -> None:
    """`python -m dataset.run_collection` — real feed endpoints, real network. Requires
    TRANCO_LIST_ID (no sensible default exists) and honors PHISHTANK_APP_KEY if set."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Run one Phase 3 real dataset collection pass.")
    parser.add_argument("--version", required=True, help='Dataset version tag, e.g. "v1".')
    parser.add_argument("--tranco-list-id", default=os.getenv("TRANCO_LIST_ID", ""), required=False)
    parser.add_argument("--previous-selection", default=None)
    args = parser.parse_args()
    if not args.tranco_list_id:
        raise SystemExit("--tranco-list-id (or TRANCO_LIST_ID) is required: no default Tranco list exists.")

    run_date = datetime.now(timezone.utc).date().isoformat()
    result = asyncio.run(run_collection(
        run_date=run_date,
        version=args.version,
        phishtank_endpoint=sources.phishtank_bulk_feed_url(config.PHISHTANK_APP_KEY),
        openphish_endpoint=sources.openphish_feed_url(),
        tranco_endpoint=sources.tranco_list_url(args.tranco_list_id),
        tranco_list_id=args.tranco_list_id,
        previous_selection_path=args.previous_selection,
    ))
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
