"""
The single canonical eligibility predicate (PHASE3_DATASET_PLAN.md section 16, approved
decision 1). Implemented once here; called by both selection.py (split generation) and
dataset_card.py (reporting) — never reimplemented per consumer.

Two functions, not one, because the full section-16 predicate needs pool-level information
(is this row a duplicate of another? does its domain carry a label conflict?) that only exists
once the whole manifest has been considered together (selection.py). At the moment a single URL
is captured, only the row's own fetch result is known. row_intrinsic_ok() is exactly the subset
of the full predicate that IS computable from a single row alone, and it is what
manifest.find_prior_ok_row() uses for the cross-run "already_collected" decision (section 5) —
a URL is only skipped on a later run if a prior attempt already cleared this row-level bar.
"""

from typing import Any, Dict

ELIGIBILITY_PREDICATE_DESCRIPTION = (
    "eligible = crawl_status == \"ok\" AND 200 <= http_status < 300 AND the decoded HTML is "
    "non-empty AND content_type is HTML-like AND this row is not a duplicate of another row "
    "AND its registered domain carries no label conflict AND its final domain does not "
    "mismatch its source domain."
)


def row_intrinsic_ok(row: Dict[str, Any]) -> bool:
    """The subset of the full predicate computable from one capture row alone: the fetch
    completed, the HTTP status was 2xx, and non-empty HTML-like content was actually stored
    (a snapshot exists). Does not consider duplicates, label conflicts or domain mismatches —
    those need the full pool (see full_eligible())."""
    if row.get("crawl_status") != "ok":
        return False
    try:
        status = int(row.get("http_status") or 0)
    except (TypeError, ValueError):
        return False
    if not (200 <= status < 300):
        return False
    # The manifest stores a hash and a snapshot path, not the HTML itself (content-addressed
    # storage). capture.py only ever sets html_snapshot_path when non-empty, HTML-like content
    # was received, so a non-empty path is the correct proxy for "decoded HTML is non-empty AND
    # content_type is HTML-like" here.
    if not row.get("html_snapshot_path"):
        return False
    return True


def full_eligible(
    row_intrinsic: bool,
    is_duplicate: bool,
    label_conflict: bool,
    domain_redirect_mismatch: bool,
) -> bool:
    """The complete section-16 predicate, given the pool-level flags computed in selection.py.
    The result is stored directly as the "eligible" column in a derived-selection-artifact row
    (section 12b) — there is no separate stored copy of row_intrinsic to avoid a second,
    divergeable notion of eligibility."""
    return bool(row_intrinsic) and not is_duplicate and not label_conflict and not domain_redirect_mismatch
