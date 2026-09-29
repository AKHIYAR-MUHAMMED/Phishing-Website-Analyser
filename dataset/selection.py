"""
Derived selection artifact: eligibility, duplicate canonicalization, label-conflict detection
and frozen split assignment, computed over the FULL accumulated manifest, per dataset version
(PHASE3_DATASET_PLAN.md sections 6, 7, 8, 12b, 13).

build_selection() is a pure function of (manifest_rows, previous_selection_rows, version, seed)
— it never touches the manifest file itself, so it can be re-run at any time without risk to
the immutable capture manifest. The capture manifest holds only collection-time facts; every
judgment computed here (is this a duplicate? does this domain have conflicting labels? which
split is this in?) lives only in the returned selection rows (section 12b schema).

Revision note (post-review fixes, independent review round 2): SELECTION_COLUMNS now includes
`label` — its earlier absence meant dataset_card.py could never compute a real class balance
from actual build_selection() output (every fixture test injected a hand-typed "label" key,
masking the disconnect). Also fixed: domain_redirect_mismatch rows no longer contaminate
duplicate/label-conflict detection for other rows (I5); a hash cluster spanning both labels is
now excluded entirely rather than picking one label arbitrarily (I2); split assignment now uses
the seed (I3); a frozen domain's historical split is preserved for lineage even if a row becomes
ineligible in a later version, while dataset_card.py's own counts filter to eligible AND split
(I4) — see build_selection()'s docstring below for the reasoning on why these are separate.
"""

import random
from collections import defaultdict
from typing import Any, Dict, List, Optional

import config
from dataset.eligibility import full_eligible, row_intrinsic_ok

SELECTION_COLUMNS = [
    "normalized_url", "dataset_version", "source_collection_run_date", "registered_domain_used",
    "label", "eligible", "duplicate_of_normalized_url", "duplicate_basis",
    "cross_label_duplicate", "label_conflict", "domain_redirect_mismatch", "split",
    "split_frozen_at_version",
]

SPLIT_TARGETS = {"train": 0.6, "val": 0.2, "test": 0.2}


def _latest_ok_row_per_url(manifest_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """The most recent crawl_status=="ok" row per normalized_url, as of this manifest snapshot.
    "ok" here means the HTTP transaction completed (section 0) — it may still fail row_intrinsic
    eligibility (non-2xx, empty body, ...); those rows are kept so their outcome is visible, but
    they will not be marked eligible below."""
    best: Dict[str, Dict[str, Any]] = {}
    for row in manifest_rows:
        if row.get("crawl_status") != "ok":
            continue
        url = row.get("normalized_url")
        if not url:
            continue
        current = best.get(url)
        if current is None or str(row.get("collection_run_date", "")) >= str(current.get("collection_run_date", "")):
            best[url] = row
    return best


def _canonicalize(rows: List[Dict[str, Any]], hash_key: str) -> Dict[str, tuple]:
    """Groups `rows` by `hash_key` and, within each group of size >= 2, sorts by
    (normalized_url, collection_run_date) ascending and marks every row but the first as a
    duplicate of the first. Sorting depends only on the data, never on crawl/processing order
    (section 6's determinism correction). Returns {url: (canonical_url, basis, group)}."""
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = row.get(hash_key) or ""
        if key:
            groups[key].append(row)

    duplicate_map: Dict[str, tuple] = {}
    basis = "exact" if hash_key == "html_sha256" else "near"
    for key, group in groups.items():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda r: (r["normalized_url"], str(r.get("collection_run_date", ""))))
        canonical_url = ordered[0]["normalized_url"]
        for row in ordered[1:]:
            duplicate_map[row["normalized_url"]] = (canonical_url, basis, ordered)
        # Also register the canonical row itself against its own group, so callers (I2) can
        # inspect whether the WHOLE group spans more than one label, not just the non-canonical
        # members.
        duplicate_map.setdefault(canonical_url, (canonical_url, basis, ordered))
    return duplicate_map


def _detect_duplicates_and_cross_label_groups(ok_rows: List[Dict[str, Any]]):
    """
    Exact duplicates first (html_sha256); near-duplicates computed only among rows not already
    marked as an exact duplicate of something else.

    I5 fix: `ok_rows` must already have domain_redirect_mismatch rows excluded by the caller —
    a row that will be excluded anyway must not be allowed to determine which row is "canonical"
    for a content cluster (that would orphan a legitimate sibling's eligibility for an unrelated
    reason). This function itself is domain-agnostic and just trusts its input.

    I2 fix: returns cross_label_urls too — the set of normalized_urls belonging to any hash
    cluster (exact OR near) that contains more than one distinct label. Such a cluster is not
    a same-kit-different-domain situation the plan's dedup was designed for; it is either a
    mislabel or shared, label-irrelevant infrastructure (a parking-page template, a hosting
    provider's default page), and every row in it is excluded, not just all-but-one.
    """
    exact_map = _canonicalize(ok_rows, "html_sha256")
    # Every key present in exact_map belongs to a group of size >= 2 (see _canonicalize); such
    # a row is already accounted for by exact-duplicate detection and is excluded from the
    # near-duplicate pass entirely (including its canonical member — no need to also near-dup it).
    remaining = [r for r in ok_rows if r["normalized_url"] not in exact_map]
    near_map = _canonicalize(remaining, "normalized_html_sha256")

    combined = {**{u: (c, b) for u, (c, b, _g) in exact_map.items()},
                **{u: (c, b) for u, (c, b, _g) in near_map.items()}}

    cross_label_urls = set()
    for mapping in (exact_map, near_map):
        for _canonical_url, (_c, _b, group) in mapping.items():
            labels = set()
            for row in group:
                try:
                    labels.add(int(row.get("label")))
                except (TypeError, ValueError):
                    continue
            if len(labels) > 1:
                cross_label_urls.update(r["normalized_url"] for r in group)

    # duplicate_of_normalized_url is only meaningful for the non-canonical members; strip the
    # canonical-row self-entries we added above purely to support the cross-label scan.
    duplicate_map = {u: (c, b) for u, (c, b) in combined.items() if c != u}
    return duplicate_map, cross_label_urls


def _detect_label_conflicts(ok_rows: List[Dict[str, Any]], excluded_urls: set) -> set:
    """Registered domains that carry more than one distinct label among rows that are otherwise
    still in play (row-intrinsically eligible, not a duplicate, not a cross-label-duplicate
    member). `ok_rows` must already have domain_redirect_mismatch rows excluded by the caller
    (I5) — such a row will never be eligible regardless, so it must not be allowed to flag an
    unrelated legitimate row on the domain it happened to redirect into."""
    labels_by_domain: Dict[str, set] = defaultdict(set)
    for row in ok_rows:
        if row["normalized_url"] in excluded_urls:
            continue
        domain = row.get("registered_domain_used")
        if not domain:
            continue
        try:
            labels_by_domain[domain].add(int(row.get("label")))
        except (TypeError, ValueError):
            continue
    return {domain for domain, labels in labels_by_domain.items() if len(labels) > 1}


def _frozen_assignments(previous_selection_rows: Optional[List[Dict[str, Any]]]) -> Dict[str, tuple]:
    frozen: Dict[str, tuple] = {}
    for row in previous_selection_rows or []:
        domain = row.get("registered_domain_used")
        split = row.get("split")
        if domain and split and domain not in frozen:
            frozen[domain] = (split, row.get("split_frozen_at_version") or "")
    return frozen


def build_selection(
    manifest_rows: List[Dict[str, Any]],
    previous_selection_rows: Optional[List[Dict[str, Any]]],
    version: str,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Builds one dataset version's derived selection artifact from the full manifest.

    Freeze-on-assign (section 8): a registered domain's split, once present in
    `previous_selection_rows`, is carried forward for EVERY row belonging to that domain in this
    version, including a row that has newly become ineligible (e.g. a new same-domain row in
    this run created a label conflict). This is deliberate: the split value is a lineage marker
    for "which split this domain was permanently assigned to," independent of whether a specific
    row currently qualifies for the modelling pool. Consumers that must only read rows actually
    usable for modelling (e.g. dataset_card.py's counts) filter on `eligible AND split`, not
    `split` alone — see PHASE3_DATASET_PLAN.md section 8 vs. the I4 finding this revision fixes.

    New domain groups (not yet frozen) are only assigned a split if currently eligible — you
    cannot meaningfully place an ineligible row into a split for the first time.

    Seeded: domain-group processing order is shuffled with a Random seeded from `seed` (falling
    back to config.RANDOM_SEED) before the proportional-deficit greedy assignment runs, so which
    specific domain lands in which split among near-ties is reproducible-given-seed rather than
    a fixed artifact of alphabetical domain names (the bias an earlier revision had, per the I3
    finding this revision fixes).
    """
    latest = _latest_ok_row_per_url(manifest_rows)
    prepped: Dict[str, Dict[str, Any]] = {}
    for url, row in latest.items():
        domain = row.get("final_registered_domain") or row.get("registered_domain") or ""
        prepped[url] = {**row, "registered_domain_used": domain}

    # I5: rows that will never be eligible regardless of dup/conflict status (domain_redirect_
    # mismatch) must not participate in the pool-level computations that could exclude OTHER,
    # unrelated rows.
    intrinsic_rows = [r for r in prepped.values() if row_intrinsic_ok(r)]
    mismatch_free_rows = [r for r in intrinsic_rows if not r.get("domain_redirect_mismatch")]

    duplicate_map, cross_label_urls = _detect_duplicates_and_cross_label_groups(mismatch_free_rows)
    excluded_for_conflict_scan = set(duplicate_map.keys()) | cross_label_urls
    conflicted_domains = _detect_label_conflicts(mismatch_free_rows, excluded_for_conflict_scan)

    selection_by_url: Dict[str, Dict[str, Any]] = {}
    for url, row in prepped.items():
        intrinsic = row_intrinsic_ok(row)
        mismatch = bool(row.get("domain_redirect_mismatch"))
        dup_entry = duplicate_map.get(url)
        cross_label = url in cross_label_urls
        domain = row["registered_domain_used"]
        label_conflict = (not mismatch) and domain in conflicted_domains
        is_duplicate = (dup_entry is not None) or cross_label
        eligible = full_eligible(intrinsic, is_duplicate, label_conflict, mismatch)
        try:
            label_value = int(row.get("label"))
        except (TypeError, ValueError):
            label_value = row.get("label")
        selection_by_url[url] = {
            "normalized_url": url,
            "dataset_version": version,
            "source_collection_run_date": row.get("collection_run_date", ""),
            "registered_domain_used": domain,
            "label": label_value,
            "eligible": eligible,
            "duplicate_of_normalized_url": dup_entry[0] if dup_entry else "",
            "duplicate_basis": dup_entry[1] if dup_entry else ("cross_label" if cross_label else ""),
            "cross_label_duplicate": cross_label,
            "label_conflict": label_conflict,
            "domain_redirect_mismatch": mismatch,
            "split": "",
            "split_frozen_at_version": "",
        }

    frozen = _frozen_assignments(previous_selection_rows)

    split_counts = {s: {0: 0, 1: 0} for s in SPLIT_TARGETS}
    for url, sel in selection_by_url.items():
        domain = sel["registered_domain_used"]
        if domain in frozen:
            split, frozen_version = frozen[domain]
            sel["split"] = split
            sel["split_frozen_at_version"] = frozen_version
            if sel["eligible"]:
                try:
                    split_counts[split][int(sel["label"])] += 1
                except (TypeError, ValueError, KeyError):
                    pass

    domain_groups: Dict[str, List[str]] = defaultdict(list)
    for url, sel in selection_by_url.items():
        if sel["split"]:  # already handled above (frozen), whether or not eligible
            continue
        if not sel["eligible"]:
            continue  # a brand-new, ineligible row cannot be newly placed into a split
        domain_groups[sel["registered_domain_used"]].append(url)

    rng = random.Random(config.RANDOM_SEED if seed is None else seed)
    ordered_domains = list(domain_groups.keys())
    rng.shuffle(ordered_domains)

    for domain in ordered_domains:
        urls = domain_groups[domain]
        try:
            label = int(selection_by_url[urls[0]]["label"])
        except (TypeError, ValueError):
            label = 0
        total_for_label = sum(split_counts[s][label] for s in SPLIT_TARGETS) or 1

        def deficit(split_name: str) -> float:
            share = split_counts[split_name][label] / total_for_label
            return SPLIT_TARGETS[split_name] - share

        # Deficit is the primary key; ties (common at the very start) are broken by the same
        # seeded shuffle order already applied to `ordered_domains`/`SPLIT_TARGETS` iteration
        # rather than alphabetically, per I3.
        split_names = list(SPLIT_TARGETS.keys())
        rng.shuffle(split_names)
        chosen = max(split_names, key=deficit)
        for url in urls:
            selection_by_url[url]["split"] = chosen
            selection_by_url[url]["split_frozen_at_version"] = version
        split_counts[chosen][label] += len(urls)

    return list(selection_by_url.values())
