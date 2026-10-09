from dataset.hashing import compute_hashes, normalize_html, sha256_text

PAGE_A = (
    "<html><head><title>Sign in</title><script>var x=1;</script></head>"
    "<body><!-- ad slot --><form data-csrf-token='AbCdEfGhIjKlMnOpQrStUv123456'>"
    "<input type='password'></form></body></html>"
)
# Same template, different dynamic token: exact hash should differ, normalized hash should match.
PAGE_B = (
    "<html><head><title>Sign in</title><script>var x=2;</script></head>"
    "<body><!-- different comment --><form data-csrf-token='ZzYyXxWwVvUuTtSsRrQq654321'>"
    "<input type='password'></form></body></html>"
)


def test_sha256_text_is_deterministic():
    assert sha256_text("abc") == sha256_text("abc")
    assert sha256_text("abc") != sha256_text("abd")


def test_normalize_html_strips_scripts_and_comments():
    normalized = normalize_html(PAGE_A)
    assert "script" not in normalized.lower() or "<script" not in normalized
    assert "ad slot" not in normalized


def test_normalize_html_redacts_dynamic_looking_tokens():
    normalized = normalize_html(PAGE_A)
    assert "AbCdEfGhIjKlMnOpQrStUv123456" not in normalized


def test_near_duplicate_kits_share_normalized_hash_but_not_exact_hash():
    hashes_a = compute_hashes(PAGE_A)
    hashes_b = compute_hashes(PAGE_B)
    assert hashes_a["html_sha256"] != hashes_b["html_sha256"]
    assert hashes_a["normalized_html_sha256"] == hashes_b["normalized_html_sha256"]


def test_empty_html():
    hashes = compute_hashes("")
    assert hashes["html_sha256"] == sha256_text("")
    assert hashes["normalized_html_sha256"] == sha256_text("")


def test_normalize_html_never_raises_on_malformed_input():
    normalize_html("<html><body><div><p>unterminated")
