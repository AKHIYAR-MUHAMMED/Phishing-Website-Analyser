"""
Section 21.1 item 4: the single canonical eligibility predicate, exercised against every
branch directly.
"""

from dataset.eligibility import full_eligible, row_intrinsic_ok

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
