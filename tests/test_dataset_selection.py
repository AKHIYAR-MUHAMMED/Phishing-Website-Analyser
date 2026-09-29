"""
Section 21.1 items 5, 6, 7, 8: deterministic duplicate canonicalization, no registered domain
spans two splits, no label-conflicted domain enters the modelling pool, frozen split
assignments survive version regeneration.
"""

import random

from dataset.selection import build_selection

OK_BASE = {
    "crawl_status": "ok", "http_status": 200, "html_snapshot_path": "data/raw/html/x.html",
    "domain_redirect_mismatch": False,
}


def _row(url, domain, label, run_date, html_hash, normalized_hash=None):
    return {
        **OK_BASE,
        "normalized_url": url,
        "registered_domain": domain,
        "final_registered_domain": domain,
        "label": label,
        "collection_run_date": run_date,
        "html_sha256": html_hash,
        "normalized_html_sha256": normalized_hash or html_hash,
    }


def _make_duplicate_cluster_manifest():
    # Three phishing URLs on three different domains, all serving the identical kit HTML
    # (same html_sha256). Alphabetically-first normalized_url should be canonicalized, tied
    # to collection_run_date as a secondary key.
    return [
        _row("http://c.example/", "c.example", 1, "2026-01-03", "HASH1"),
        _row("http://a.example/", "a.example", 1, "2026-01-01", "HASH1"),
        _row("http://b.example/", "b.example", 1, "2026-01-02", "HASH1"),
    ]


def test_duplicate_canonicalization_is_deterministic_regardless_of_input_order():
    manifest = _make_duplicate_cluster_manifest()
    results = set()
    for _ in range(5):
        shuffled = manifest[:]
        random.shuffle(shuffled)
        selection = build_selection(shuffled, None, "v1")
        by_url = {r["normalized_url"]: r for r in selection}
        canonical = [u for u, r in by_url.items() if r["eligible"]]
        results.add(tuple(sorted(canonical)))
    assert len(results) == 1
    assert results.pop() == ("http://a.example/",)


def test_no_registered_domain_spans_two_splits():
    manifest = [
        _row(f"http://phish{i}.example/", f"phish{i}.example", 1, "2026-01-01", f"H{i}")
        for i in range(6)
    ] + [
        _row(f"http://benign{i}.example/", f"benign{i}.example", 0, "2026-01-01", f"B{i}")
        for i in range(6)
    ]
    selection = build_selection(manifest, None, "v1")
    domain_splits = {}
    for row in selection:
        if row["split"]:
            domain_splits.setdefault(row["registered_domain_used"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in domain_splits.values())


def test_label_conflicted_domain_is_excluded_from_the_pool():
    manifest = [
        _row("http://shared.example/phish", "shared.example", 1, "2026-01-01", "P1"),
        _row("http://shared.example/benign", "shared.example", 0, "2026-01-01", "B1"),
    ]
    selection = build_selection(manifest, None, "v1")
    by_url = {r["normalized_url"]: r for r in selection}
    assert by_url["http://shared.example/phish"]["label_conflict"] is True
    assert by_url["http://shared.example/benign"]["label_conflict"] is True
    assert by_url["http://shared.example/phish"]["eligible"] is False
    assert by_url["http://shared.example/phish"]["split"] == ""


def test_frozen_splits_survive_version_regeneration():
    manifest_v1 = [
        _row(f"http://phish{i}.example/", f"phish{i}.example", 1, "2026-01-01", f"H{i}")
        for i in range(10)
    ] + [
        _row(f"http://benign{i}.example/", f"benign{i}.example", 0, "2026-01-01", f"B{i}")
        for i in range(10)
    ]
    selection_v1 = build_selection(manifest_v1, None, "v1")
    v1_splits = {r["normalized_url"]: r["split"] for r in selection_v1 if r["split"]}
    assert v1_splits  # sanity: something got assigned

    manifest_v2 = manifest_v1 + [
        _row(f"http://phishnew{i}.example/", f"phishnew{i}.example", 1, "2026-02-01", f"NH{i}")
        for i in range(4)
    ]
    selection_v2 = build_selection(manifest_v2, selection_v1, "v2")
    v2_by_url = {r["normalized_url"]: r for r in selection_v2}

    for url, split in v1_splits.items():
        assert v2_by_url[url]["split"] == split, f"{url} moved from {split} to {v2_by_url[url]['split']}"
        assert v2_by_url[url]["split_frozen_at_version"] == "v1"

    # New domains get assigned in v2, stamped with v2.
    new_assigned = [r for u, r in v2_by_url.items() if u.startswith("http://phishnew")]
    assert all(r["split"] for r in new_assigned)
    assert all(r["split_frozen_at_version"] == "v2" for r in new_assigned)


def test_domain_redirect_mismatch_is_excluded_by_default():
    row = _row("http://phish.example/", "phish.example", 1, "2026-01-01", "H1")
    row["domain_redirect_mismatch"] = True
    selection = build_selection([row], None, "v1")
    assert selection[0]["eligible"] is False
    assert selection[0]["split"] == ""


def test_ineligible_rows_are_still_recorded_with_no_split():
    ineligible = {**_row("http://x.example/", "x.example", 0, "2026-01-01", "H1"), "http_status": 404}
    selection = build_selection([ineligible], None, "v1")
    assert len(selection) == 1
    assert selection[0]["eligible"] is False
    assert selection[0]["split"] == ""
