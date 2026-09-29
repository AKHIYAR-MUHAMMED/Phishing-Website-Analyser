"""
URL normalization for deduplication (PHASE3_DATASET_PLAN.md section 5).

Lowercases scheme and host, strips a default port, strips the fragment, sorts query
parameters, strips a leading "www." label, and normalizes an empty path to "/".
"""

import urllib.parse

NORMALIZATION_VERSION = "v1"

DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urllib.parse.urlsplit(url)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    port = parsed.port
    netloc = hostname
    if port is not None and DEFAULT_PORTS.get(scheme) != port:
        netloc = f"{hostname}:{port}"

    path = parsed.path or "/"
    if path == "":
        path = "/"

    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = urllib.parse.urlencode(sorted(query_pairs))

    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))
