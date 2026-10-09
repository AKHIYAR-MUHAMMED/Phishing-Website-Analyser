from dataset.normalize import normalize_url


def test_lowercases_scheme_and_host():
    assert normalize_url("HTTP://Example.COM/Path") == "http://example.com/Path"


def test_strips_www_prefix():
    assert normalize_url("https://www.example.com/") == normalize_url("https://example.com/")


def test_strips_default_port():
    assert normalize_url("http://example.com:80/x") == normalize_url("http://example.com/x")
    assert normalize_url("https://example.com:443/x") == normalize_url("https://example.com/x")


def test_keeps_non_default_port():
    assert normalize_url("http://example.com:8080/x") == "http://example.com:8080/x"


def test_strips_fragment():
    assert normalize_url("http://example.com/x#frag") == normalize_url("http://example.com/x")


def test_sorts_query_params():
    assert normalize_url("http://example.com/x?b=2&a=1") == normalize_url("http://example.com/x?a=1&b=2")


def test_empty_path_becomes_slash():
    assert normalize_url("http://example.com") == normalize_url("http://example.com/")


def test_empty_input():
    assert normalize_url("") == ""
    assert normalize_url("   ") == ""
