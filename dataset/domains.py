"""
Registered-domain grouping (PHASE3_DATASET_PLAN.md section 7, approved decision 9).

Uses tldextract in offline mode (suffix_list_urls=()), which resolves only against the Public
Suffix List snapshot bundled inside the installed tldextract package — no network fetch, ever.
requirements.txt pins an exact tldextract version specifically so this snapshot is fixed and
identical across machines/runs of the same pinned dependency (tldextract does not expose a
separate "PSL date" in offline mode; the pinned package version is the concrete mechanism that
makes registered-domain grouping deterministic here — see PHASE3_DATASET_PLAN.md section 13).

For a bare IP host or a name tldextract cannot resolve to a registered domain (empty suffix),
the literal host string is used as the grouping key instead, per the plan's approved fallback.
"""

import urllib.parse

import tldextract

_extractor = tldextract.TLDExtract(suffix_list_urls=())

PSL_SOURCE = f"tldextract=={tldextract.__version__} (bundled offline snapshot, suffix_list_urls=())"


def get_registered_domain(url_or_host: str) -> str:
    """Returns the eTLD+1 registered domain, or the literal host when none resolves (IP
    addresses, unresolvable names). Returns "" for an empty/unparseable input."""
    value = (url_or_host or "").strip()
    if not value:
        return ""

    if "://" in value:
        host = urllib.parse.urlsplit(value).hostname or ""
    else:
        # Accept a bare host too (e.g. already-extracted hostname).
        host = urllib.parse.urlsplit(f"//{value}").hostname or value

    if not host:
        return ""

    result = _extractor(host)
    if result.registered_domain:
        return result.registered_domain.lower()

    # No registered domain resolved (IP literal, single-label host, or an unrecognized
    # suffix): fall back to the literal host so unrelated hosts never collide on "".
    return host.lower()
