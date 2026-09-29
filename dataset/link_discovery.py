"""
Same-domain login-link discovery for Tranco benign second-page collection
(PHASE3_DATASET_PLAN.md section 8; CLAUDE.md section 15 requires benign data include login
pages, "not only homepages, so the model can't learn 'login page vs homepage'").

find_login_link() picks the FIRST matching anchor in document order — the plan's section 8
correction over v1's unstated ordering ("the link selection rule is document order"), so the
choice is deterministic and auditable even though the homepage's own content can change between
runs. Scope, stated plainly (also repeated in the dataset card, dataset_card.py): single hop
(the homepage only, never a page found via a discovered page), a fixed login-related keyword
list on the href/link text, no JavaScript-rendered link discovery (this project has no
browser-rendering crawler — see PHASE3_DATASET_PLAN.md section 16's rendering-gap note).
"""

import re
import urllib.parse
from typing import Optional

from bs4 import BeautifulSoup

from dataset.domains import get_registered_domain

_LOGIN_KEYWORDS = re.compile(r"log[-_\s]?in|sign[-_\s]?in|account|my[-_\s]?account", re.IGNORECASE)


def find_login_link(html: str, base_url: str) -> Optional[str]:
    """Returns the absolute URL of the first same-registered-domain anchor (document order)
    whose href or visible text looks login-related, or None if none is found or `html` is
    unparseable. Never raises."""
    if not html or not base_url:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return None

    base_domain = get_registered_domain(base_url)
    if not base_domain:
        return None

    for anchor in soup.find_all("a"):
        href = anchor.get("href")
        if not href:
            continue
        absolute = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlsplit(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        if get_registered_domain(absolute) != base_domain:
            continue
        text = anchor.get_text() or ""
        if _LOGIN_KEYWORDS.search(href) or _LOGIN_KEYWORDS.search(text):
            return absolute
    return None
