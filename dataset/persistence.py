"""
File-persistence writers for Phase 3 collection artifacts (PHASE3_DATASET_PLAN.md section 11).

Each function takes an in-memory artifact and an explicit output path/directory (tests point
these at a temp directory; dataset.run_collection passes the real config.DATASET_* paths for a
real run) and returns the path it wrote — the same testable-path pattern as
dataset.snapshots.save_snapshot. Nothing here makes a network call.
"""

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Union

from dataset.dataset_card import generate_card
from dataset.selection import SELECTION_COLUMNS


def write_run_summary(summary: Dict[str, Any], run_date: str, out_dir: Union[str, Path]) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"run_{run_date}_summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return path


def write_feed_digest(digest: Dict[str, Any], source: str, run_date: str, out_dir: Union[str, Path]) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{source}_{run_date}.json"
    path.write_text(json.dumps(digest, indent=2, sort_keys=True), encoding="utf-8")
    return path


def write_selection(selection_rows: List[Dict[str, Any]], version: str, out_dir: Union[str, Path]) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"selection_{version}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SELECTION_COLUMNS)
        writer.writeheader()
        for row in selection_rows:
            writer.writerow({col: row.get(col, "") for col in SELECTION_COLUMNS})
    return path


def load_selection(path: Union[str, Path]) -> List[Dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = []
        for raw in csv.DictReader(f):
            row = dict(raw)
            for bool_col in ("eligible", "cross_label_duplicate", "label_conflict", "domain_redirect_mismatch"):
                row[bool_col] = str(row.get(bool_col, "")).strip().lower() == "true"
            rows.append(row)
        return rows


def write_splits(selection_rows: List[Dict[str, Any]], out_dir: Union[str, Path]) -> Dict[str, Path]:
    """One text file per split (train/val/test), one normalized_url per line, restricted to the
    modelling pool (eligible AND split — the same rule dataset_card.py's _in_pool applies, not
    reimplemented, just re-checked here since these writers do not import each other's helpers)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    by_split: Dict[str, List[str]] = {"train": [], "val": [], "test": []}
    for row in selection_rows:
        split = row.get("split")
        if split in by_split and row.get("eligible"):
            by_split[split].append(row["normalized_url"])
    paths = {}
    for split, urls in by_split.items():
        path = out_dir / f"{split}.txt"
        urls = sorted(urls)
        path.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
        paths[split] = path
    return paths


def write_dataset_card(
    manifest_rows: List[Dict[str, Any]],
    selection_rows: List[Dict[str, Any]],
    version: str,
    card_path: Union[str, Path],
    feed_digests=None,
    psl_snapshot_date: str = "",
) -> Path:
    card = generate_card(
        manifest_rows, selection_rows, version,
        feed_digests=feed_digests, psl_snapshot_date=psl_snapshot_date,
    )
    card_path = Path(card_path)
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(card, encoding="utf-8")
    return card_path


def write_backup_listing(html_paths: Iterable[Union[str, Path]], run_date: str, out_dir: Union[str, Path]) -> Path:
    """Writes a sha256sum-style checksum listing for the given files (PHASE3_DATASET_PLAN.md
    section 19). The archive itself is produced and copied off-machine by hand (a manual,
    unautomatable step — see the plan's section 21.2); only this small, versionable checksum
    listing is written here, so the checksums are committed even though the archive is not."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"run_{run_date}_manifest.sha256"
    lines = []
    for file_path in sorted(str(p) for p in html_paths):
        with open(file_path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        lines.append(f"{digest}  {os.path.basename(file_path)}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def read_used_tranco_ranks(path: Union[str, Path]) -> Set[int]:
    """The cumulative set of Tranco ranks already sampled across all prior runs (section 9,
    approved decision 8), so rank-progressive sampling never re-draws the same rank twice."""
    path = Path(path)
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError, ValueError):
        return set()


def write_used_tranco_ranks(ranks: Set[int], path: Union[str, Path]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(ranks)), encoding="utf-8")
    return path
