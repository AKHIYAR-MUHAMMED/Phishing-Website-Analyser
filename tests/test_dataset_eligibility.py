"""
Section 21.1 item 4: the single canonical eligibility predicate, exercised against every
branch directly.
"""

import hashlib

from dataset.eligibility import full_eligible, row_intrinsic_ok, snapshot_integrity_ok

OK_ROW = {"crawl_status": "ok", "http_status": 200, "html_snapshot_path": "data/raw/html/x.html"}


def test_row_intrinsic_ok_happy_path():
    assert row_intrinsic_ok(OK_ROW) is True


def test_row_intrinsic_ok_requires_crawl_status_ok():
    assert row_intrinsic_ok({**OK_ROW, "crawl_status": "timeout"}) is False


def test_row_intrinsic_ok_requires_2xx_status():
    assert row_intrinsic_ok({**OK_ROW, "http_status": 404}) is False
    assert row_intrinsic_ok({**OK_ROW, "http_status": 500}) is False
    assert row_intrinsic_ok({**OK_ROW, "http_status": 301}) is False


def test_row_intrinsic_ok_requires_a_stored_snapshot():
    # Proxy for "non-empty HTML AND HTML-like content-type": capture.py only ever sets
    # html_snapshot_path when both hold.
    assert row_intrinsic_ok({**OK_ROW, "html_snapshot_path": ""}) is False


def test_row_intrinsic_ok_handles_missing_or_garbage_http_status():
    assert row_intrinsic_ok({**OK_ROW, "http_status": ""}) is False
    assert row_intrinsic_ok({**OK_ROW, "http_status": "not-a-number"}) is False


def test_full_eligible_truth_table():
    assert full_eligible(True, False, False, False) is True
    assert full_eligible(False, False, False, False) is False
    assert full_eligible(True, True, False, False) is False   # duplicate
    assert full_eligible(True, False, True, False) is False   # label conflict
    assert full_eligible(True, False, False, True) is False   # domain redirect mismatch
    assert full_eligible(True, False, False, False, False) is True
    assert full_eligible(True, False, False, False, True) is False  # snapshot integrity failed


def test_snapshot_integrity_ok_missing_file_from_disk(tmp_path):
    # Regression: a real pilot run had a manifest row whose html_snapshot_path was a correct,
    # non-empty value (set at capture time) but whose underlying file had since vanished from
    # disk. row_intrinsic_ok alone cannot catch this since it only reads the manifest row.
    row = {"html_snapshot_path": "data/raw/html/deadbeef.html", "html_sha256": "deadbeef"}
    assert snapshot_integrity_ok(row, tmp_path) is False


def test_snapshot_integrity_ok_matching_file():
    content = b"<html><body>hi</body></html>"
    digest = hashlib.sha256(content).hexdigest()
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / f"{digest}.html").write_bytes(content)
        row = {"html_snapshot_path": f"data/raw/html/{digest}.html", "html_sha256": digest}
        assert snapshot_integrity_ok(row, d) is True


def test_snapshot_integrity_ok_corrupted_content():
    content = b"<html><body>hi</body></html>"
    digest = hashlib.sha256(content).hexdigest()
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / f"{digest}.html").write_bytes(b"corrupted")
        row = {"html_snapshot_path": f"data/raw/html/{digest}.html", "html_sha256": digest}
        assert snapshot_integrity_ok(row, d) is False
