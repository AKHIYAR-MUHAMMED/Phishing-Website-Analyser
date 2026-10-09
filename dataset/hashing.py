"""
Content hashing for snapshot integrity and (near-)duplicate detection
(PHASE3_DATASET_PLAN.md section 6).

Three hashes are used across this package:
- raw_content_sha256: computed inside crawler.fetch_url itself (the raw bytes exist only
  there); this module does not recompute it.
- html_sha256: sha256 of the decoded HTML string exactly as fetch_url returns it. Also used
  as the content-addressed snapshot filename (see dataset/snapshots.py).
- normalized_html_sha256: sha256 of the HTML after stripping script/style/comment nodes,
  collapsing whitespace, and removing attributes that look like dynamic per-request tokens.
  Catches phishing-kit templates reused across domains with only a token/timestamp differing.
"""

import hashlib
import re

from bs4 import BeautifulSoup, Comment

# Attribute values that look like dynamic tokens: long hex/base64-ish runs, or a name
# suggesting a CSRF/session/nonce value.
_DYNAMIC_TOKEN_VALUE_RE = re.compile(r"^[A-Za-z0-9+/_-]{16,}={0,2}$")
_DYNAMIC_ATTR_NAME_RE = re.compile(r"(csrf|nonce|session|token|_ts|timestamp)", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def normalize_html(html: str) -> str:
    """Best-effort normalization for near-duplicate detection. Never raises: malformed HTML
    falls back to a whitespace-collapsed copy of the original string."""
    if not html or not html.strip():
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return _WHITESPACE_RE.sub(" ", html).strip()

    for tag in soup(["script", "style"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    for tag in soup.find_all(True):
        for attr_name, attr_value in list(tag.attrs.items()):
            if isinstance(attr_value, list):
                attr_value = " ".join(attr_value)
            if _DYNAMIC_ATTR_NAME_RE.search(attr_name) or (
                isinstance(attr_value, str) and _DYNAMIC_TOKEN_VALUE_RE.match(attr_value)
            ):
                tag[attr_name] = "REDACTED"

    text = str(soup)
    return _WHITESPACE_RE.sub(" ", text).strip()


def compute_hashes(html: str) -> dict:
    """Returns {"html_sha256", "normalized_html_sha256"} for the given decoded HTML string."""
    return {
        "html_sha256": sha256_text(html),
        "normalized_html_sha256": sha256_text(normalize_html(html)),
    }
