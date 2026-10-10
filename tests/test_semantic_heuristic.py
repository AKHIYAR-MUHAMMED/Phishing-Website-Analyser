"""
GNN reliability repair, Bug B regression tests: analyze_text_heuristically()'s term matching
previously used a raw substring check (`term in text`), so the brand term "chase" matched
inside "purchase" -- apple.com's real page text legitimately contains "purchase" and got a
false Chase-bank brand hit with no relation to the actual word. Fixed to word-boundary (\\b)
matching for all three term lists (credential/urgency/brand).
"""

from semantic_heuristic import analyze_text_heuristically


def test_chase_substring_false_positive_is_fixed():
    result = analyze_text_heuristically("", "you can purchase items here")
    assert "chase" not in result["evidence"]["brand_terms_found"]


def test_chase_as_its_own_word_still_matches():
    result = analyze_text_heuristically("", "please chase up your order")
    assert "chase" in result["evidence"]["brand_terms_found"]


def test_multi_word_credential_phrase_still_matches():
    result = analyze_text_heuristically("", "please sign in to continue")
    assert "sign in" in result["evidence"]["credential_related_terms_found"]


def test_word_boundary_does_not_break_on_punctuation():
    result = analyze_text_heuristically("", "Sign in, then verify your account.")
    assert "sign in" in result["evidence"]["credential_related_terms_found"]
    assert "verify your account" in result["evidence"]["credential_related_terms_found"]


def test_clean_text_has_no_false_hits():
    result = analyze_text_heuristically("Welcome", "This is an ordinary informational page.")
    assert result["evidence"]["credential_related_terms_found"] == []
    assert result["evidence"]["urgency_terms_found"] == []
    assert result["evidence"]["brand_terms_found"] == []


def test_urgency_term_substring_is_not_falsely_matched():
    # "urgent" must not fire on a word that merely contains it, e.g. "insurgent" (unrelated word).
    result = analyze_text_heuristically("", "the insurgent group was reported")
    assert "urgent" not in result["evidence"]["urgency_terms_found"]
