"""
Content-addressed HTML snapshot storage (PHASE3_DATASET_PLAN.md section 11, approved
decision 10).

Files are named by html_sha256, not by URL: every distinct piece of HTML ever collected gets
one permanent file, so a manifest row's html_snapshot_path is always correct regardless of how
many times the source URL is later re-crawled with different content, and identical content
across different URLs (e.g. copies of the same phishing kit) visibly shares one file on disk.

save_snapshot() takes base_dir explicitly so tests can point it at a temporary directory; the
returned, stored path is always the plan's documented logical path
("data/raw/html/<hash>.html"), independent of where a given test actually wrote the file.
"""

from pathlib import Path
from typing import Union

LOGICAL_PREFIX = "data/raw/html"


def snapshot_filename(html_sha256: str) -> str:
    return f"{html_sha256}.html"


def snapshot_physical_path(html_sha256: str, base_dir: Union[str, Path]) -> Path:
    return Path(base_dir) / snapshot_filename(html_sha256)


def save_snapshot(html: str, html_sha256: str, base_dir: Union[str, Path]) -> str:
    """Writes `html` to <base_dir>/<html_sha256>.html if that file does not already exist
    (content-addressed: an existing file for this hash already holds identical content).
    Returns the logical path recorded in the manifest, e.g. "data/raw/html/<hash>.html"."""
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_physical_path(html_sha256, base_dir)
    if not path.exists():
        path.write_text(html, encoding="utf-8", newline="")
    return f"{LOGICAL_PREFIX}/{snapshot_filename(html_sha256)}"
