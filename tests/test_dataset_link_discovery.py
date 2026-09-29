"""
Login-link discovery tests (PHASE3_DATASET_PLAN.md section 8): pure HTML parsing, no network.
"""

from dataset.link_discovery import find_login_link


def test_finds_the_first_same_domain_login_link_in_document_order():
    html = (
        "<html><body>"
        "<a href='/about'>About</a>"
        "<a href='/login'>Sign in</a>"
        "<a href='/account/login'>Also sign in</a>"
        "</body></html>"
    )
    result = find_login_link(html, "https://example.com/")
    assert result == "https://example.com/login"


def test_matches_on_link_text_even_without_a_login_shaped_href():
    html = "<html><body><a href='/u/42'>Sign In</a></body></html>"
    result = find_login_link(html, "https://example.com/")
    assert result == "https://example.com/u/42"


def test_ignores_a_login_link_on_a_different_registered_domain():
    html = "<html><body><a href='https://other.example/login'>Sign in</a></body></html>"
    assert find_login_link(html, "https://example.com/") is None


def test_returns_none_when_no_login_link_present():
    html = "<html><body><a href='/about'>About</a><a href='/contact'>Contact</a></body></html>"
    assert find_login_link(html, "https://example.com/") is None


def test_handles_empty_and_malformed_input_without_raising():
    assert find_login_link("", "https://example.com/") is None
    assert find_login_link("<html><body>no links", "https://example.com/") is None
    assert find_login_link("<a href='/login'>hi</a>", "") is None
