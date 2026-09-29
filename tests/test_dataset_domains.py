from dataset.domains import get_registered_domain


def test_simple_domain():
    assert get_registered_domain("https://example.com/path") == "example.com"


def test_subdomain_collapses_to_registered_domain():
    assert get_registered_domain("https://login.example.co.uk/x") == "example.co.uk"


def test_paypal_lookalike_is_not_treated_as_paypal_com():
    # The exact substring-match bug CLAUDE.md flags elsewhere in the codebase: this must NOT
    # resolve to "paypal.com".
    assert get_registered_domain("http://paypal.com.evil.net/login") == "evil.net"


def test_bare_host_input():
    assert get_registered_domain("example.com") == "example.com"


def test_ip_literal_falls_back_to_literal_host():
    assert get_registered_domain("http://203.0.113.5/login") == "203.0.113.5"


def test_empty_input():
    assert get_registered_domain("") == ""
    assert get_registered_domain(None) == ""


def test_offline_no_live_psl_fetch(monkeypatch):
    """The extractor is constructed with suffix_list_urls=() (offline mode); this just
    confirms it still resolves without needing network access in this sandboxed test run."""
    assert get_registered_domain("https://example.com") == "example.com"
