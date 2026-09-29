from dataset.redaction import REDACTED_PLACEHOLDER, contains_secret, redact_url, scan_text_for_secrets


def test_redact_url_masks_app_key():
    url = "http://data.phishtank.com/data/online-valid.csv?app_key=abcdef1234567890"
    redacted = redact_url(url)
    assert "abcdef1234567890" not in redacted
    assert "app_key=REDACTED" in redacted


def test_redact_url_leaves_non_secret_params_alone():
    url = "http://example.com/x?page=2&sort=asc"
    assert redact_url(url) == url


def test_redact_url_leaves_url_without_query_alone():
    assert redact_url("http://example.com/x") == "http://example.com/x"


def test_scan_text_for_secrets_finds_known_pattern():
    hits = scan_text_for_secrets("endpoint used: app_key=SuperSecretValue123")
    assert hits
    assert contains_secret("endpoint used: app_key=SuperSecretValue123")


def test_scan_text_for_secrets_clean_text():
    assert scan_text_for_secrets("no secrets here, just prose about phishing detection") == []
    assert not contains_secret("clean dataset card text")


def test_empty_input():
    assert redact_url("") == ""
    assert scan_text_for_secrets("") == []


def test_scanner_does_not_flag_its_own_redaction_placeholder():
    """C2 regression: redact_url() produces "app_key=REDACTED"; the scanner must not then flag
    that as a leaked secret — it previously did, meaning the normal card-generation flow (which
    always redacts before scanning) would crash on its own correctly-redacted output."""
    already_redacted = redact_url("http://example.com/feed?app_key=SuperSecretValue123456")
    assert already_redacted.endswith(f"app_key={REDACTED_PLACEHOLDER}")
    assert scan_text_for_secrets(already_redacted) == []
    assert not contains_secret(already_redacted)


def test_scanner_exemption_is_the_exact_placeholder_only():
    # The negative lookahead is `(?!REDACTED\b)`: it only suppresses a match when the value is
    # EXACTLY the placeholder (word-boundary right after "REDACTED"). A value that merely starts
    # with those letters but continues ("REDACTEDBUTNOTREALLY...") has no boundary there, so the
    # lookahead does NOT fire and the string is still flagged — the exemption is not a prefix
    # match, only an exact one.
    assert scan_text_for_secrets("app_key=REDACTEDBUTNOTREALLY123456") != []
    assert scan_text_for_secrets("app_key=notredactedActualSecret123456") != []
    assert scan_text_for_secrets("app_key=REDACTED") == []
    assert scan_text_for_secrets("app_key=REDACTED and some other prose") == []
