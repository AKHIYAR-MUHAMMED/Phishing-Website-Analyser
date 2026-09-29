"""
Section 21.1 items 11 and 12: the dataset card is generated from the manifest/selection
artifacts rather than manually typed, and TLS/robots/crawl-status reporting is generated
correctly where applicable.
"""

import pytest

from dataset.dataset_card import RedactionFailure, generate_card

MANIFEST_ROWS = [
    {"label": 1, "crawl_status": "ok", "robots_result": "allowed", "final_url": "https://phish.example/",
     "url": "https://phish.example/", "tls_captured": "True", "html_length_bytes": "1200",
     "decoded_text_length": "1000", "visible_text_length": "50", "dom_node_count": "20", "script_count": "3",
     "domain_redirect_mismatch": "False", "bot_challenge_suspected": "False"},
    {"label": 1, "crawl_status": "timeout", "robots_result": "", "final_url": "", "url": "http://dead.example/",
     "tls_captured": "False", "domain_redirect_mismatch": "False", "bot_challenge_suspected": "False"},
    {"label": 0, "crawl_status": "ok", "robots_result": "disallowed", "final_url": "https://benign.example/",
     "url": "https://benign.example/", "tls_captured": "True", "html_length_bytes": "20000",
     "decoded_text_length": "18000", "visible_text_length": "10", "dom_node_count": "5", "script_count": "10",
     "domain_redirect_mismatch": "False", "bot_challenge_suspected": "False"},
]

SELECTION_ROWS = [
    {"normalized_url": "https://phish.example/", "registered_domain_used": "phish.example",
     "eligible": True, "duplicate_of_normalized_url": "", "label_conflict": False, "split": "train",
     "label": 1},
    {"normalized_url": "https://dead.example/", "registered_domain_used": "dead.example",
     "eligible": False, "duplicate_of_normalized_url": "", "label_conflict": False, "split": "",
     "label": 1},
    {"normalized_url": "https://benign.example/", "registered_domain_used": "benign.example",
     "eligible": True, "duplicate_of_normalized_url": "", "label_conflict": False, "split": "test",
     "label": 0},
]


def test_generate_card_counts_match_input_arithmetic():
    card = generate_card(MANIFEST_ROWS, SELECTION_ROWS, "v1")
    assert "Total capture attempts: 3" in card
    assert "phishing (label 1): 1" in card
    assert "benign (label 0): 1" in card


def test_generate_card_includes_label_crawl_status_matrix():
    card = generate_card(MANIFEST_ROWS, SELECTION_ROWS, "v1")
    assert "Label x crawl-status matrix" in card
    assert "timeout" in card


def test_generate_card_includes_label_robots_matrix():
    card = generate_card(MANIFEST_ROWS, SELECTION_ROWS, "v1")
    assert "robots_result matrix" in card
    assert "disallowed" in card


def test_generate_card_reports_tls_capture_rate():
    card = generate_card(MANIFEST_ROWS, SELECTION_ROWS, "v1")
    assert "SSL/TLS metadata capture rate" in card
    assert "100.0%" in card  # both https rows in the fixture have tls_captured=True


def test_generate_card_reports_split_invariants_as_true_for_clean_fixture():
    card = generate_card(MANIFEST_ROWS, SELECTION_ROWS, "v1")
    assert "No registered domain spans two splits: **True**" in card
    assert "No label-conflicted domain entered the modelling pool: **True**" in card


def test_generate_card_flags_a_domain_spanning_two_splits():
    bad_selection = SELECTION_ROWS + [{
        "normalized_url": "https://phish.example/other", "registered_domain_used": "phish.example",
        "eligible": True, "duplicate_of_normalized_url": "", "label_conflict": False, "split": "test",
        "label": 1,
    }]
    card = generate_card(MANIFEST_ROWS, bad_selection, "v1")
    assert "No registered domain spans two splits: **False**" in card


def test_generate_card_includes_canonical_predicate_text():
    card = generate_card(MANIFEST_ROWS, SELECTION_ROWS, "v1")
    assert "eligible = crawl_status" in card


def test_generate_card_refuses_to_return_a_card_containing_a_secret():
    leaking_digest = [{"source": "phishtank", "endpoint": "http://x?app_key=LeakedSecretValue123",
                        "timestamp": "t", "sha256": "h", "row_count": 1}]
    with pytest.raises(RedactionFailure):
        generate_card(MANIFEST_ROWS, SELECTION_ROWS, "v1", feed_digests=leaking_digest)


def test_generate_card_notes_backup_is_a_manual_check():
    card = generate_card(MANIFEST_ROWS, SELECTION_ROWS, "v1")
    assert "MANUAL" in card
    assert "Not verifiable by this generator" in card


def test_generate_card_reports_a_failed_source_explicitly():
    digests = [
        {"source": "phishtank", "status": "fetch_error", "error_message": "HTTPStatusError: 403 Forbidden",
         "endpoint": "http://data.phishtank.com/data/online-valid.csv", "timestamp": "t", "sha256": "", "row_count": 0},
        {"source": "openphish", "status": "ok", "error_message": "",
         "endpoint": "https://openphish.com/feed.txt", "timestamp": "t", "sha256": "h2", "row_count": 300},
    ]
    card = generate_card(MANIFEST_ROWS, SELECTION_ROWS, "v1", feed_digests=digests)
    assert "fetch_error" in card
    assert "403 Forbidden" in card
    assert "1 source(s) failed this run" in card
    assert "phishtank" in card


def test_generate_card_omits_the_failed_source_note_when_everything_succeeded():
    digests = [
        {"source": "phishtank", "status": "ok", "error_message": "",
         "endpoint": "http://x", "timestamp": "t", "sha256": "h", "row_count": 1},
    ]
    card = generate_card(MANIFEST_ROWS, SELECTION_ROWS, "v1", feed_digests=digests)
    assert "source(s) failed this run" not in card


def test_generate_card_defaults_status_to_ok_for_a_digest_without_a_status_field():
    """Backward compatibility: a digest produced the old way (compute_feed_digest's original
    shape, no "status" key at all) must still render as "ok", not blank or crash."""
    digests = [{"source": "tranco", "endpoint": "http://x", "timestamp": "t", "sha256": "h", "row_count": 5}]
    card = generate_card(MANIFEST_ROWS, SELECTION_ROWS, "v1", feed_digests=digests)
    assert "source(s) failed this run" not in card
