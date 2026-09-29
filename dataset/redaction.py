"""
Secret redaction (PHASE3_DATASET_PLAN.md section 18).

No API key or app key is ever written into a committed artifact. redact_url() replaces the
value of any secret-shaped query parameter with "REDACTED" before a URL is recorded anywhere;
scan_text_for_secrets() is the check run over generated artifacts before they're treated as
committable, catching a key that reached a committed file by some other path.
"""

import re
import urllib.parse

SECRET_QUERY_PARAMS = {"app_key", "api_key", "apikey", "key", "token", "secret", "access_token"}

REDACTED_PLACEHOLDER = "REDACTED"

# Matches "<name>=<value-that-looks-like-a-key>" outside of a URL's own query string too (e.g.
# a stray value pasted into free text), so the check is not limited to well-formed URLs.
# The negative lookahead excludes our own REDACTED_PLACEHOLDER: without it, the scanner would
# flag its own output the moment redact_url() had already done its job (confirmed bug — see
# tests/test_dataset_redaction.py's redacted-digest-through-generate_card regression test).
_SECRET_PATTERN = re.compile(
    r"(?i)\b(" + "|".join(re.escape(p) for p in SECRET_QUERY_PARAMS) + r")\s*[=:]\s*"
    r"(?!" + re.escape(REDACTED_PLACEHOLDER) + r"\b)[\w-]{6,}"
)
_ENV_VAR_NAMES = ("PHISHTANK_APP_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
                  "DEEPSEEK_API_KEY", "MISTRAL_API_KEY")


def redact_url(url: str) -> str:
    """Replaces any secret-shaped query parameter's value with REDACTED. Non-query parts of
    the URL (scheme, host, path) are left untouched."""
    if not url:
        return url
    parsed = urllib.parse.urlsplit(url)
    if not parsed.query:
        return url
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted_pairs = [
        (k, REDACTED_PLACEHOLDER if k.lower() in SECRET_QUERY_PARAMS else v) for k, v in pairs
    ]
    new_query = urllib.parse.urlencode(redacted_pairs)
    return urllib.parse.urlunsplit(parsed._replace(query=new_query))


def scan_text_for_secrets(text: str) -> list:
    """Returns the list of matched secret-shaped substrings found in `text` (empty if clean).
    Used to check a generated artifact (dataset card, run summary, log) before it is treated as
    committable."""
    if not text:
        return []
    return [m.group(0) for m in _SECRET_PATTERN.finditer(text)]


def contains_secret(text: str) -> bool:
    return bool(scan_text_for_secrets(text))
