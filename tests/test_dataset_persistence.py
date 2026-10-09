"""
File-persistence writer tests (PHASE3_DATASET_PLAN.md section 11). All writers are pointed at
tmp_path; no test touches a tracked data/ path (see tests/conftest.py's tracked_data_unchanged
guard).
"""

import hashlib
import json

from dataset import persistence


def test_write_run_summary_writes_valid_json(tmp_path):
    path = persistence.write_run_summary({"a": 1}, "2026-01-01", tmp_path)
    assert path.name == "run_2026-01-01_summary.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}


def test_write_feed_digest_writes_valid_json(tmp_path):
    digest = {"source": "phishtank", "endpoint": "http://x?app_key=REDACTED", "timestamp": "t",
              "sha256": "h", "row_count": 3}
    path = persistence.write_feed_digest(digest, "phishtank", "2026-01-01", tmp_path)
    assert path.name == "phishtank_2026-01-01.json"
    assert json.loads(path.read_text(encoding="utf-8")) == digest


def test_write_and_load_selection_round_trips(tmp_path):
    rows = [{
        "normalized_url": "http://a.example/", "dataset_version": "v1",
        "source_collection_run_date": "2026-01-01", "registered_domain_used": "a.example",
        "label": 1, "eligible": True, "duplicate_of_normalized_url": "", "duplicate_basis": "",
        "cross_label_duplicate": False, "label_conflict": False, "domain_redirect_mismatch": False,
        "split": "train", "split_frozen_at_version": "v1",
    }]
    path = persistence.write_selection(rows, "v1", tmp_path)
    assert path.name == "selection_v1.csv"
    loaded = persistence.load_selection(path)
    assert len(loaded) == 1
    assert loaded[0]["normalized_url"] == "http://a.example/"
    assert loaded[0]["eligible"] is True
    assert loaded[0]["split"] == "train"


def test_write_splits_only_includes_eligible_split_assigned_rows(tmp_path):
    rows = [
        {"normalized_url": "http://a.example/", "eligible": True, "split": "train"},
        {"normalized_url": "http://b.example/", "eligible": False, "split": "train"},  # frozen, excluded
        {"normalized_url": "http://c.example/", "eligible": True, "split": ""},  # not split-assigned
        {"normalized_url": "http://d.example/", "eligible": True, "split": "test"},
    ]
    paths = persistence.write_splits(rows, tmp_path)
    assert paths["train"].read_text(encoding="utf-8").splitlines() == ["http://a.example/"]
    assert paths["test"].read_text(encoding="utf-8").splitlines() == ["http://d.example/"]
    assert paths["val"].read_text(encoding="utf-8") == ""


def test_write_dataset_card_writes_generated_card(tmp_path):
    path = persistence.write_dataset_card([], [], "v1", tmp_path / "DATASET_CARD.md")
    text = path.read_text(encoding="utf-8")
    assert "PhishGuard Dataset Card" in text


def test_write_backup_listing_records_correct_sha256(tmp_path):
    html_content = "<html>hi</html>"
    expected = hashlib.sha256(html_content.encode("utf-8")).hexdigest()
    html_file = tmp_path / f"{expected}.html"
    html_file.write_text(html_content, encoding="utf-8")

    out_dir = tmp_path / "backups"
    path, failures = persistence.write_backup_listing([(html_file, expected)], "2026-01-01", out_dir)
    assert path.name == "run_2026-01-01_manifest.sha256"
    line = path.read_text(encoding="utf-8").strip()
    assert line == f"{expected}  {expected}.html"
    assert failures == []
    assert not (out_dir / "run_2026-01-01_manifest.integrity_failures.json").exists()


def test_write_backup_listing_records_a_missing_file_as_an_integrity_failure_not_a_crash(tmp_path):
    """C1 regression: a real pilot run showed a manifest-recorded, previously-written snapshot
    can vanish before this step re-reads it. One missing file must not abort the whole listing
    or crash the caller — it must be reported, and every other file must still be processed."""
    valid_content = "<html>real page</html>"
    valid_hash = hashlib.sha256(valid_content.encode("utf-8")).hexdigest()
    valid_file = tmp_path / f"{valid_hash}.html"
    valid_file.write_text(valid_content, encoding="utf-8")

    missing_hash = "b34e32d5d612cfed0da86998fce248b5146f66914c1d4d1ab33cb9bfefaac21"
    missing_file = tmp_path / f"{missing_hash}.html"  # never created

    out_dir = tmp_path / "backups"
    path, failures = persistence.write_backup_listing(
        [(valid_file, valid_hash), (missing_file, missing_hash)], "2026-01-01", out_dir,
    )
    listing_text = path.read_text(encoding="utf-8")
    assert f"{valid_hash}  {valid_hash}.html" in listing_text
    assert missing_hash not in listing_text  # never fabricated a checksum line for it

    assert len(failures) == 1
    assert failures[0]["type"] == "missing_or_unreadable"
    assert failures[0]["expected_sha256"] == missing_hash

    failures_path = out_dir / "run_2026-01-01_manifest.integrity_failures.json"
    assert failures_path.exists()
    on_disk = json.loads(failures_path.read_text(encoding="utf-8"))
    assert on_disk == failures


def test_write_backup_listing_detects_corruption_against_the_manifest_hash(tmp_path):
    """The manifest's recorded html_sha256 is the source of truth — not the filename — per the
    approved design. A file whose actual content no longer matches what the manifest recorded
    for it (corruption, partial write, tampering) must be flagged distinctly from "missing"."""
    real_content = "<html>original</html>"
    tampered_content = "<html>tampered</html>"
    expected_hash = hashlib.sha256(real_content.encode("utf-8")).hexdigest()
    corrupt_file = tmp_path / f"{expected_hash}.html"
    corrupt_file.write_text(tampered_content, encoding="utf-8")  # content no longer matches its own name

    out_dir = tmp_path / "backups"
    path, failures = persistence.write_backup_listing(
        [(corrupt_file, expected_hash)], "2026-01-01", out_dir,
    )
    assert path.read_text(encoding="utf-8") == ""  # no fabricated checksum line
    assert len(failures) == 1
    assert failures[0]["type"] == "corrupted"
    assert failures[0]["expected_sha256"] == expected_hash
    assert failures[0]["actual_sha256"] == hashlib.sha256(tampered_content.encode("utf-8")).hexdigest()


def test_write_backup_listing_detects_a_filename_content_mismatch_as_a_distinct_condition(tmp_path):
    """The content-addressed filename is checked too, but only as an ADDITIONAL signal, never
    the sole source of truth (the manifest's expected_sha256 is authoritative) — a file whose
    content matches the manifest but is stored under the wrong filename is a real anomaly,
    reported as its own distinct type, not silently accepted and not conflated with content
    corruption (which is a manifest-vs-content mismatch, not a filename-vs-content one)."""
    content = "<html>real</html>"
    real_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    misnamed_file = tmp_path / "0000000000000000000000000000000000000000000000000000000000000000.html"
    misnamed_file.write_text(content, encoding="utf-8")

    out_dir = tmp_path / "backups"
    # expected_sha256 (from the manifest) correctly matches the file's actual content —
    # only the filename itself disagrees.
    path, failures = persistence.write_backup_listing(
        [(misnamed_file, real_hash)], "2026-01-01", out_dir,
    )
    assert path.read_text(encoding="utf-8") == ""
    assert len(failures) == 1
    assert failures[0]["type"] == "filename_mismatch"
    assert failures[0]["actual_sha256"] == real_hash


def test_write_backup_listing_mixed_valid_and_failing_files_processes_every_file_independently(tmp_path):
    good_content = "<html>good</html>"
    good_hash = hashlib.sha256(good_content.encode("utf-8")).hexdigest()
    good_file = tmp_path / f"{good_hash}.html"
    good_file.write_text(good_content, encoding="utf-8")

    missing_hash = "f" * 64
    missing_file = tmp_path / f"{missing_hash}.html"

    out_dir = tmp_path / "backups"
    path, failures = persistence.write_backup_listing(
        [(good_file, good_hash), (missing_file, missing_hash)], "2026-01-01", out_dir,
    )
    assert f"{good_hash}  {good_hash}.html" in path.read_text(encoding="utf-8")
    assert len(failures) == 1
    assert failures[0]["expected_sha256"] == missing_hash


def test_used_tranco_ranks_round_trip(tmp_path):
    path = tmp_path / "used_ranks.json"
    assert persistence.read_used_tranco_ranks(path) == set()
    persistence.write_used_tranco_ranks({1, 5, 9}, path)
    assert persistence.read_used_tranco_ranks(path) == {1, 5, 9}
