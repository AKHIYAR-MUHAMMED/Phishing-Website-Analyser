"""
Regression tests for extract_url_lexical_features()'s shortening_service check. It used to
match raw substrings of the whole URL string, so the shortener "t.co" matched inside
"microsoft.com". It now compares the URL's host against known shortener domains (exact or
subdomain match).
"""

from dataset_loader import extract_url_lexical_features


def test_shortening_service_false_positive_is_fixed_for_microsoft():
    assert extract_url_lexical_features("https://www.microsoft.com")["shortening_service"] == 0.0
    assert extract_url_lexical_features("https://www.microsoft.com/en-in")["shortening_service"] == 0.0


def test_shortening_service_still_detects_real_shorteners():
    assert extract_url_lexical_features("https://t.co/abc123")["shortening_service"] == 1.0
    assert extract_url_lexical_features("http://bit.ly/xyz")["shortening_service"] == 1.0
    assert extract_url_lexical_features("https://tinyurl.com/abc")["shortening_service"] == 1.0


def test_shortening_service_detects_a_subdomain_of_a_real_shortener():
    assert extract_url_lexical_features("http://go.bit.ly/xyz")["shortening_service"] == 1.0


def test_shortening_service_does_not_match_an_unrelated_domain_containing_the_substring():
    # "example-t.com" contains the substring "t.co" (the old bug) and "shorttoowner.com" only
    # resembles "short.to"; neither host is a shortener.
    assert extract_url_lexical_features("https://example-t.com")["shortening_service"] == 0.0
    assert extract_url_lexical_features("https://shorttoowner.com")["shortening_service"] == 0.0


def test_shortening_service_handles_a_port_in_the_host():
    assert extract_url_lexical_features("http://bit.ly:8080/x")["shortening_service"] == 1.0
    assert extract_url_lexical_features("http://microsoft.com:8080")["shortening_service"] == 0.0
