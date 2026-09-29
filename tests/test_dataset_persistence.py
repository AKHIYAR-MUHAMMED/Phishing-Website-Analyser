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
    html_file = tmp_path / "abc123.html"
    html_file.write_text("<html>hi</html>", encoding="utf-8")
    expected = hashlib.sha256(html_file.read_bytes()).hexdigest()

    out_dir = tmp_path / "backups"
    path = persistence.write_backup_listing([html_file], "2026-01-01", out_dir)
    assert path.name == "run_2026-01-01_manifest.sha256"
    line = path.read_text(encoding="utf-8").strip()
    assert line == f"{expected}  abc123.html"


def test_used_tranco_ranks_round_trip(tmp_path):
    path = tmp_path / "used_ranks.json"
    assert persistence.read_used_tranco_ranks(path) == set()
    persistence.write_used_tranco_ranks({1, 5, 9}, path)
    assert persistence.read_used_tranco_ranks(path) == {1, 5, 9}
