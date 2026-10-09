import hashlib

from dataset.hashing import sha256_text
from dataset.snapshots import save_snapshot, snapshot_physical_path


def test_save_snapshot_returns_logical_path(tmp_path):
    html = "<html><body>hi</body></html>"
    digest = sha256_text(html)
    logical = save_snapshot(html, digest, tmp_path)
    assert logical == f"data/raw/html/{digest}.html"


def test_save_snapshot_writes_the_physical_file(tmp_path):
    html = "<html><body>hi</body></html>"
    digest = sha256_text(html)
    save_snapshot(html, digest, tmp_path)
    physical = snapshot_physical_path(digest, tmp_path)
    assert physical.exists()
    assert physical.read_text(encoding="utf-8") == html


def test_content_addressed_dedup_does_not_rewrite_existing_file(tmp_path):
    html = "<html><body>same content</body></html>"
    digest = sha256_text(html)
    save_snapshot(html, digest, tmp_path)
    physical = snapshot_physical_path(digest, tmp_path)
    first_mtime = physical.stat().st_mtime_ns

    save_snapshot(html, digest, tmp_path)  # second "collection" of identical content
    assert physical.stat().st_mtime_ns == first_mtime


def test_snapshot_hash_integrity(tmp_path):
    """Section 21.1 item 10: a stored snapshot's own sha256 matches its manifest hash."""
    html = "<html><body>integrity check</body></html>"
    digest = sha256_text(html)
    save_snapshot(html, digest, tmp_path)
    physical = snapshot_physical_path(digest, tmp_path)
    on_disk_hash = hashlib.sha256(physical.read_bytes()).hexdigest()
    assert on_disk_hash == digest
