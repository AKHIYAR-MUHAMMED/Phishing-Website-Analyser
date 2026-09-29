"""
Dataset card generation (PHASE3_DATASET_PLAN.md section 14).

generate_card() builds data/DATASET_CARD.md's content entirely from the manifest and a
version's selection rows — nothing here is hand-typed data, satisfying CLAUDE.md section 14
rule 1 ("every reported number must be produced by code run on data"). The generator scans its
own output for secret-shaped text before returning (section 18) and refuses to return an
artifact that fails that check, rather than relying on a person catching it after the fact.

Revision note (post-review fixes, independent review round 2):
- C3: selection rows now carry a real "label" column (dataset/selection.py fix); this module no
  longer needs (and never worked with) a hand-injected label — it reads the real column.
- I3/I4: every count and table here is scoped to rows that are BOTH eligible AND split-assigned.
  A row can carry a non-empty `split` for lineage while `eligible=False` (a frozen domain whose
  split is preserved even though this row is currently excluded — see selection.py's
  build_selection() docstring) — such a row must not be counted as part of the modelling pool.
"""

import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional

from dataset.eligibility import ELIGIBILITY_PREDICATE_DESCRIPTION
from dataset.redaction import scan_text_for_secrets


class RedactionFailure(RuntimeError):
    """Raised when a generated dataset card would contain a secret-shaped string. The card is
    never returned in this case — see section 18."""


def _in_pool(row: Dict[str, Any]) -> bool:
    """I3/I4: a selection row counts toward the modelling pool only if it is both eligible and
    has a split assigned. `split` alone is not sufficient — see the module docstring."""
    return bool(row.get("eligible")) and bool(row.get("split"))


def _label_status_matrix(manifest_rows: List[Dict[str, Any]]) -> Dict[Any, Dict[str, int]]:
    matrix: Dict[Any, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in manifest_rows:
        matrix[row.get("label")][row.get("crawl_status", "")] += 1
    return {k: dict(v) for k, v in matrix.items()}


def _label_robots_matrix(manifest_rows: List[Dict[str, Any]]) -> Dict[Any, Dict[str, int]]:
    matrix: Dict[Any, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in manifest_rows:
        robots = row.get("robots_result") or "not_checked"
        matrix[row.get("label")][robots] += 1
    return {k: dict(v) for k, v in matrix.items()}


def _quantiles_by_label(manifest_rows: List[Dict[str, Any]], field: str) -> Dict[Any, Dict[str, float]]:
    """Only rows with actual stored HTML content contribute (crawl_status ok AND a non-empty
    html_snapshot_path) — an ok-but-empty-body or non-HTML row has no meaningful rendering
    stats and would otherwise skew the medians (a Freebuff minor-issue fix)."""
    values_by_label: Dict[Any, List[float]] = defaultdict(list)
    for row in manifest_rows:
        if row.get("crawl_status") != "ok" or not row.get("html_snapshot_path"):
            continue
        raw = row.get(field)
        try:
            values_by_label[row.get("label")].append(float(raw))
        except (TypeError, ValueError):
            continue
    out = {}
    for label, values in values_by_label.items():
        if not values:
            continue
        values.sort()
        out[label] = {
            "median": statistics.median(values),
            "min": values[0],
            "max": values[-1],
            "n": len(values),
        }
    return out


def _tls_capture_rate(manifest_rows: List[Dict[str, Any]]) -> Optional[float]:
    """Denominator is https:// rows where a TLS probe was actually attempted (crawl_status ok),
    not every row whose URL happens to start with https:// — a row that never got past a
    connection error was never eligible for a TLS probe in the first place (a Freebuff-found
    reporting bug in the earlier revision)."""
    https_ok_rows = [
        r for r in manifest_rows
        if r.get("crawl_status") == "ok"
        and str(r.get("final_url") or r.get("url") or "").startswith("https://")
    ]
    if not https_ok_rows:
        return None
    captured = sum(1 for r in https_ok_rows if str(r.get("tls_captured")).lower() == "true")
    return captured / len(https_ok_rows)


def _markdown_table(headers: List[str], rows: List[List[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines)


def _check_split_invariants(selection_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Section 14 items 6a/6b: generated assertions, not claims. Scoped to in-pool rows
    (eligible AND split) — a frozen-but-currently-ineligible row's lineage split marker is not
    a claim about the modelling pool and must not trip these invariants."""
    pool_rows = [r for r in selection_rows if _in_pool(r)]
    domain_splits: Dict[str, set] = defaultdict(set)
    for row in pool_rows:
        domain_splits[row["registered_domain_used"]].add(row["split"])
    domains_spanning = {d: splits for d, splits in domain_splits.items() if len(splits) > 1}

    label_conflict_in_pool = [row for row in pool_rows if row.get("label_conflict")]
    return {
        "no_domain_spans_two_splits": len(domains_spanning) == 0,
        "domains_spanning_two_splits": domains_spanning,
        "no_label_conflict_in_pool": len(label_conflict_in_pool) == 0,
        "label_conflicted_rows_in_pool": len(label_conflict_in_pool),
    }


def generate_card(
    manifest_rows: List[Dict[str, Any]],
    selection_rows: List[Dict[str, Any]],
    version: str,
    feed_digests: Optional[List[Dict[str, Any]]] = None,
    psl_snapshot_date: str = "",
    snapshot_integrity_failures: Optional[List[Dict[str, Any]]] = None,
) -> str:
    feed_digests = feed_digests or []
    snapshot_integrity_failures = snapshot_integrity_failures or []

    run_dates = sorted({r.get("collection_run_date", "") for r in manifest_rows if r.get("collection_run_date")})
    label_status = _label_status_matrix(manifest_rows)
    label_robots = _label_robots_matrix(manifest_rows)
    invariants = _check_split_invariants(selection_rows)

    pool_rows = [r for r in selection_rows if _in_pool(r)]

    split_sizes: Dict[str, int] = defaultdict(int)
    domains_by_split: Dict[str, set] = defaultdict(set)
    for row in pool_rows:
        split_sizes[row["split"]] += 1
        domains_by_split[row["split"]].add(row["registered_domain_used"])

    eligible_count = len(pool_rows)
    duplicate_count = sum(1 for r in selection_rows if r.get("duplicate_of_normalized_url"))
    cross_label_count = sum(1 for r in selection_rows if r.get("cross_label_duplicate"))
    label_conflict_count = sum(1 for r in selection_rows if r.get("label_conflict"))
    mismatch_count = sum(1 for r in selection_rows if r.get("domain_redirect_mismatch"))
    frozen_but_excluded = sum(1 for r in selection_rows if r.get("split") and not r.get("eligible"))

    phishing_eligible = sum(1 for r in pool_rows if str(r.get("label")) == "1")
    benign_eligible = eligible_count - phishing_eligible

    tls_rate = _tls_capture_rate(manifest_rows)
    rendering = {
        field: _quantiles_by_label(manifest_rows, field)
        for field in ("html_length_bytes", "decoded_text_length", "visible_text_length",
                      "dom_node_count", "script_count")
    }

    lines = []
    lines.append("# PhishGuard Dataset Card")
    lines.append("")
    lines.append(f"Generated by `dataset/dataset_card.py`, dataset version `{version}`.")
    lines.append("Every number below is computed from `data/manifest.csv` and this version's")
    lines.append("`data/derived/selection_" + version + ".csv` — none is hand-typed. Counts are")
    lines.append("scoped to rows that are both `eligible` AND `split`-assigned (the modelling")
    lines.append("pool); a frozen domain's split marker can appear on an otherwise-excluded row")
    lines.append("for lineage only and is not counted here.")
    lines.append("")

    lines.append("## 1. Collection dates")
    lines.append(", ".join(run_dates) if run_dates else "(no collection runs recorded yet)")
    lines.append("")

    lines.append("## 2. Sources")
    if feed_digests:
        # "status" defaults to "ok" for a digest that carries no status field at all (the
        # shape compute_feed_digest() has always produced) — a source that FAILED to fetch or
        # parse always carries an explicit non-"ok" status, so a failed source is never
        # rendered indistinguishably from a normal, successful one that simply had no error.
        lines.append(_markdown_table(
            ["source", "status", "endpoint", "timestamp", "sha256", "row_count", "error"],
            [[d.get("source", ""), d.get("status", "ok"), d.get("endpoint", ""), d.get("timestamp", ""),
              d.get("sha256", ""), d.get("row_count", ""), d.get("error_message", "")] for d in feed_digests],
        ))
        failed_sources = [d for d in feed_digests if d.get("status", "ok") != "ok"]
        if failed_sources:
            lines.append("")
            lines.append(
                f"**{len(failed_sources)} source(s) failed this run** "
                f"({', '.join(d['source'] for d in failed_sources)}) — see the `status`/`error` "
                "columns above. A failed source contributes zero rows to this run; it is not "
                "treated as an empty-but-successful feed, and it does not prevent any other "
                "source from being collected."
            )
    else:
        lines.append("(no feed digests recorded yet)")
    lines.append("")
    lines.append(f"PSL snapshot used for domain grouping: `{psl_snapshot_date or 'not recorded'}`")
    lines.append("")

    lines.append("## 3. Counts")
    lines.append(f"- Total capture attempts: {len(manifest_rows)}")
    lines.append(f"- In modelling pool (eligible AND split): {eligible_count}")
    lines.append(f"  - phishing (label 1): {phishing_eligible}")
    lines.append(f"  - benign (label 0): {benign_eligible}")
    lines.append(f"- Duplicate (exact or near, single-label) rows excluded: {duplicate_count}")
    lines.append(f"- Cross-label duplicate-content rows excluded (both labels shared one hash cluster): {cross_label_count}")
    lines.append(f"- Label-conflicted rows excluded: {label_conflict_count}")
    lines.append(f"- domain_redirect_mismatch rows excluded: {mismatch_count}")
    lines.append(f"- Frozen-split rows currently excluded from the pool (lineage marker only, not counted above): {frozen_but_excluded}")
    second_page_count = sum(
        1 for r in manifest_rows if r.get("discovered_from") and str(r.get("label")) == "0"
    )
    lines.append(f"- Benign second-page (login-link) rows discovered from a homepage: {second_page_count}")
    lines.append("")

    lines.append("## 4. Label x crawl-status matrix")
    all_statuses = sorted({s for m in label_status.values() for s in m})
    lines.append(_markdown_table(
        ["label"] + all_statuses,
        [[label] + [label_status.get(label, {}).get(s, 0) for s in all_statuses]
         for label in sorted(label_status.keys(), key=str)],
    ))
    lines.append("")
    lines.append("### Label x robots_result matrix")
    all_robots = sorted({s for m in label_robots.values() for s in m})
    lines.append(_markdown_table(
        ["label"] + all_robots,
        [[label] + [label_robots.get(label, {}).get(s, 0) for s in all_robots]
         for label in sorted(label_robots.keys(), key=str)],
    ))
    lines.append("")

    lines.append("## 5. Class balance")
    total_eligible = max(eligible_count, 1)
    lines.append(f"phishing {phishing_eligible}/{eligible_count} "
                 f"({phishing_eligible / total_eligible:.1%}), "
                 f"benign {benign_eligible}/{eligible_count} "
                 f"({benign_eligible / total_eligible:.1%})")
    lines.append("(Realized, not targeted — see section 9's survivorship-bias note above.)")
    lines.append("")

    lines.append("## 6. Split sizes and generated assertions")
    lines.append(_markdown_table(
        ["split", "rows", "distinct_domains"],
        [[s, split_sizes.get(s, 0), len(domains_by_split.get(s, set()))] for s in ("train", "val", "test")],
    ))
    lines.append("")
    lines.append(f"- No registered domain spans two splits: **{invariants['no_domain_spans_two_splits']}**")
    if not invariants["no_domain_spans_two_splits"]:
        lines.append(f"  - VIOLATION: {invariants['domains_spanning_two_splits']}")
    lines.append(f"- No label-conflicted domain entered the modelling pool: **{invariants['no_label_conflict_in_pool']}**")
    lines.append("")

    lines.append("## 7. Filtering and exclusion decisions")
    lines.append(f"- Duplicate exclusions (single-label hash clusters): {duplicate_count}")
    lines.append(f"- Cross-label duplicate-content exclusions: {cross_label_count}")
    lines.append(f"- Label-conflict exclusions: {label_conflict_count}")
    lines.append(f"- domain_redirect_mismatch exclusions: {mismatch_count}")
    robots_disallowed_count = sum(1 for r in manifest_rows if r.get("crawl_status") == "robots_disallowed")
    lines.append(f"- robots_disallowed: {robots_disallowed_count}")
    bot_challenge_count = sum(1 for r in manifest_rows if str(r.get("bot_challenge_suspected")).lower() == "true")
    lines.append(f"- bot_challenge_suspected (flagged, not auto-excluded): {bot_challenge_count}")
    lines.append("")

    lines.append("## 8. Rendering-gap measurement (by label)")
    for field, by_label in rendering.items():
        lines.append(f"### {field}")
        rows = [[label, v["n"], f"{v['median']:.1f}", v["min"], v["max"]] for label, v in sorted(by_label.items(), key=lambda kv: str(kv[0]))]
        lines.append(_markdown_table(["label", "n", "median", "min", "max"], rows) if rows else "(no rows with stored content yet)")
    lines.append("")

    lines.append("## 9. Known limitations")
    lines.append("- Label-trust caveats: labels are taken from each source's own verification status (section 4).")
    lines.append("- OpenPhish's free feed caps live phishing URLs at roughly 500 at any moment (section 1).")
    lines.append("- Same-run retries are capped at one; cross-run retry of failed URLs is supported (section 5).")
    lines.append("- No visual/screenshot data is collected.")
    lines.append("- No manual verification pass has been performed on any row.")
    lines.append("- No browser-rendered content: snapshots are the served, static HTML only "
                 "(section 16); the rendering-gap table above measures this asymmetry directly.")
    lines.append("- No cloaking detection beyond meta-refresh (section 10); full "
                 "user-agent-differential cloaking detection is deferred.")
    lines.append("- Near-duplicate detection uses a single normalized-HTML hash, not full "
                 "MinHash/kit clustering (bounded recall; full clustering deferred to Phase 4).")
    lines.append("- Benign second-page discovery (section 8) is homepage-triggered, single-hop "
                 "only: it looks for the first same-registered-domain link (document order) on "
                 "an already-captured homepage whose href or link text matches a fixed "
                 "login-related keyword list; it never follows a link found on a discovered "
                 "second page, and does no JavaScript-rendered link discovery.")
    if tls_rate is None:
        lines.append("- SSL/TLS metadata capture rate: no https:// rows with a completed crawl recorded yet.")
    else:
        lines.append(f"- SSL/TLS metadata capture rate among https:// rows that completed a crawl: {tls_rate:.1%}.")
    lines.append("")

    lines.append("## 10. Canonical modelling-view definition")
    lines.append(f"> {ELIGIBILITY_PREDICATE_DESCRIPTION}")
    lines.append("> A row additionally requires a non-empty `split` to be read by any experiment "
                 "(see PHASE3_DATASET_PLAN.md section 16).")
    lines.append("")

    lines.append("## 11. Reproducibility instructions")
    lines.append("- Re-run collection: `python -m dataset.run_collection` (per-source; see PHASE3_DATASET_PLAN.md).")
    lines.append("- Regenerate this version's selection: `dataset.selection.build_selection(manifest_rows, "
                 "previous_selection_rows, version, seed)`.")
    lines.append("- Regenerate this card: `dataset.dataset_card.generate_card(...)`.")
    lines.append("")

    lines.append("## 12. Redaction confirmation")
    lines.append("This card was scanned for secret-shaped text before being returned; none was found.")
    lines.append("")

    lines.append("## 13. Backup confirmation")
    if snapshot_integrity_failures:
        lines.append(
            f"**WARNING: {len(snapshot_integrity_failures)} snapshot(s) failed integrity "
            "verification** (missing, unreadable, or content that does not match the manifest's "
            "recorded `html_sha256`) — see this run's `run_<date>_summary.json` "
            "(`snapshot_integrity_failures`) and the backup directory's "
            "`run_<date>_manifest.integrity_failures.json` for exactly which files and why. "
            "A failed snapshot's manifest row is NOT rewritten because of this — capture-time "
            "truth remains immutable — but the underlying file may need to be re-crawled or "
            "restored from an earlier backup before this version's affected rows can be trusted."
        )
    lines.append("**MANUAL** — confirm the out-of-band backup for this version's contributing "
                 "runs completed (PHASE3_DATASET_PLAN.md section 19) before treating this "
                 "version as final. Not verifiable by this generator.")
    lines.append("")

    card = "\n".join(lines)
    hits = scan_text_for_secrets(card)
    if hits:
        raise RedactionFailure(f"Generated dataset card contains secret-shaped text: {hits}")
    return card
