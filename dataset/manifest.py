"""
The immutable capture manifest (PHASE3_DATASET_PLAN.md section 12a, approved decision 12).

One row per collection attempt, append-only: append_capture_row() only ever adds a row, never
rewrites an existing one. All derived judgments (eligibility, duplicate canonicalization, label
conflicts, split assignment) live in selection.py's separate, per-version artifact instead.
"""

import csv
import os
from typing import Any, Dict, List, Optional

from dataset.eligibility import row_intrinsic_ok

CAPTURE_COLUMNS = [
    "url", "normalized_url", "source", "source_metadata", "label", "collection_run_date",
    "retry_count", "crawl_status", "crawled_at", "final_url", "registered_domain",
    "final_registered_domain", "domain_redirect_mismatch", "http_status", "redirect_count",
    "content_type", "html_length_bytes", "decoded_text_length", "visible_text_length",
    "dom_node_count", "script_count", "raw_content_sha256", "html_sha256",
    "normalized_html_sha256", "html_snapshot_path", "error_type", "error_message",
    "robots_result", "meta_refresh_detected", "bot_challenge_suspected", "tls_captured",
    "tls_version", "certificate_subject", "certificate_issuer", "certificate_self_signed",
    "certificate_not_after", "discovered_from", "feed_to_crawl_latency_seconds",
    "collection_tool_version", "normalization_version", "psl_snapshot_date",
]

_BOOL_COLUMNS = {"domain_redirect_mismatch", "meta_refresh_detected", "bot_challenge_suspected", "tls_captured"}
_TRISTATE_BOOL_COLUMNS = {"certificate_self_signed"}  # True / False / "" (unknown, not captured)


def _serialize_value(column: str, value: Any) -> str:
    if value is None:
        return ""
    if column in _BOOL_COLUMNS:
        return "True" if value else "False"
    if column in _TRISTATE_BOOL_COLUMNS:
        if value is None or value == "":
            return ""
        return "True" if value else "False"
    return str(value)


def serialize_row(row: Dict[str, Any]) -> Dict[str, str]:
    return {col: _serialize_value(col, row.get(col, "")) for col in CAPTURE_COLUMNS}


def _deserialize_value(column: str, value: str):
    if column in _BOOL_COLUMNS:
        return str(value).strip().lower() == "true"
    if column in _TRISTATE_BOOL_COLUMNS:
        v = str(value).strip().lower()
        if v == "true":
            return True
        if v == "false":
            return False
        return None
    return value


def deserialize_row(csv_row: Dict[str, str]) -> Dict[str, Any]:
    return {col: _deserialize_value(col, csv_row.get(col, "")) for col in CAPTURE_COLUMNS}


def append_capture_row(row: Dict[str, Any], manifest_path) -> None:
    """Appends one capture row. Writes the header first if the file does not exist yet.
    Never opens the file for writing except in append mode — existing rows are never touched."""
    manifest_path = str(manifest_path)
    write_header = not (os.path.exists(manifest_path) and os.path.getsize(manifest_path) > 0)
    os.makedirs(os.path.dirname(manifest_path) or ".", exist_ok=True)
    with open(manifest_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAPTURE_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(serialize_row(row))


def load_manifest(manifest_path) -> List[Dict[str, Any]]:
    manifest_path = str(manifest_path)
    if not os.path.exists(manifest_path):
        return []
    with open(manifest_path, newline="", encoding="utf-8") as f:
        return [deserialize_row(r) for r in csv.DictReader(f)]


def find_prior_ok_row(manifest_rows: List[Dict[str, Any]], normalized_url: str) -> Optional[Dict[str, Any]]:
    """The most recent row-intrinsically-eligible prior attempt for this URL, or None. Used for
    the cross-run "already_collected" skip (section 5, approved decision 6): a URL whose most
    recent attempt failed or was ineligible is NOT returned here, so it remains attemptable."""
    candidates = [
        r for r in manifest_rows
        if r.get("normalized_url") == normalized_url and row_intrinsic_ok(r)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda r: str(r.get("collection_run_date", "")))
    return candidates[-1]
