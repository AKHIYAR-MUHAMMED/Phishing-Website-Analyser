"""
Feed parsing tests (PHASE3_DATASET_PLAN.md section 1, section 4, section 10). Pure functions,
no network — bytes are constructed in-test, never fetched from a real feed.
"""

import io
import zipfile

import pytest

from dataset.sources import (
    TrancoFeedFormatError,
    openphish_feed_url,
    parse_openphish_feed,
    parse_phishtank_feed,
    parse_tranco_feed,
    phishtank_bulk_feed_url,
    tranco_list_url,
    unwrap_tranco_feed_bytes,
)


def test_phishtank_bulk_feed_url_omits_key_when_unset():
    url = phishtank_bulk_feed_url("")
    assert "app_key" not in url


def test_phishtank_bulk_feed_url_appends_key_when_set():
    url = phishtank_bulk_feed_url("secretkey123")
    assert "app_key=secretkey123" in url


def test_openphish_and_tranco_url_builders_are_well_formed():
    assert openphish_feed_url().startswith("https://")
    assert "42" in tranco_list_url("42")


def test_tranco_list_url_matches_the_verified_real_endpoint_shape():
    """Real-feed format probe (2026-09-29): tranco-list.eu/top-1m.csv.zip was observed to
    redirect to tranco-list.eu/download/daily/top-1m.csv.zip. This is the only shape actually
    verified; the default list_id reproduces it exactly."""
    assert tranco_list_url() == "https://tranco-list.eu/download/daily/top-1m.csv.zip"
    assert tranco_list_url("some-list-id") == "https://tranco-list.eu/download/some-list-id/top-1m.csv.zip"


def test_parse_phishtank_feed_filters_on_verified_and_online():
    csv_bytes = (
        b"phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target\n"
        b"1,http://a.example/,http://x,2026-01-01,yes,2026-01-01,yes,PayPal\n"
        b"2,http://b.example/,http://x,2026-01-01,no,2026-01-01,yes,PayPal\n"
        b"3,http://c.example/,http://x,2026-01-01,yes,2026-01-01,no,PayPal\n"
    )
    rows, malformed = parse_phishtank_feed(csv_bytes)
    assert not malformed
    assert [r["url"] for r in rows] == ["http://a.example/"]
    assert rows[0]["source_metadata"]["phish_id"] == "1"


def test_parse_phishtank_feed_flags_malformed_rows():
    csv_bytes = (
        b"phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target\n"
        b"1,http://a.example/,http://x,2026-01-01,yes,2026-01-01,yes,PayPal\n"
        b"2,,http://x,2026-01-01,yes,2026-01-01,yes\n"  # missing url, short row
    )
    rows, malformed = parse_phishtank_feed(csv_bytes)
    assert len(rows) == 1
    assert len(malformed) == 1


def test_parse_openphish_feed_reads_one_url_per_line():
    text_bytes = b"http://a.example/\nhttp://b.example/\n\n# comment\n"
    rows, malformed = parse_openphish_feed(text_bytes)
    assert [r["url"] for r in rows] == ["http://a.example/", "http://b.example/"]
    assert not malformed


def test_parse_openphish_feed_flags_unparseable_lines():
    text_bytes = b"http://a.example/\nnot-a-url\n"
    rows, malformed = parse_openphish_feed(text_bytes)
    assert [r["url"] for r in rows] == ["http://a.example/"]
    assert malformed == ["not-a-url"]


def test_parse_tranco_feed_reads_rank_and_domain():
    csv_bytes = b"1,example.com\n2,other.example\n"
    rows, malformed = parse_tranco_feed(csv_bytes)
    assert rows == [{"rank": 1, "domain": "example.com"}, {"rank": 2, "domain": "other.example"}]
    assert not malformed


def test_parse_tranco_feed_flags_malformed_lines():
    csv_bytes = b"1,example.com\nnot-a-rank,other.example\n3\n"
    rows, malformed = parse_tranco_feed(csv_bytes)
    assert rows == [{"rank": 1, "domain": "example.com"}]
    assert len(malformed) == 2


def _zip_bytes(members: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in members.items():
            z.writestr(name, content)
    return buf.getvalue()


def test_unwrap_tranco_feed_bytes_extracts_the_expected_member():
    """Real-feed format probe (2026-09-29): the real Tranco daily endpoint returns a ZIP
    containing exactly top-1m.csv."""
    zipped = _zip_bytes({"top-1m.csv": "1,example.com\n2,other.example\n"})
    unwrapped = unwrap_tranco_feed_bytes(zipped)
    assert unwrapped == b"1,example.com\n2,other.example\n"
    rows, malformed = parse_tranco_feed(unwrapped)
    assert rows == [{"rank": 1, "domain": "example.com"}, {"rank": 2, "domain": "other.example"}]
    assert not malformed


def test_unwrap_tranco_feed_bytes_passes_through_non_zip_content_unchanged():
    """Not every Tranco-shaped response is necessarily a ZIP (e.g. a specific archived list_id
    was not verified by the probe and may return plain CSV) — non-ZIP bytes must pass straight
    through, not be misinterpreted as an empty/broken archive."""
    plain_csv = b"1,example.com\n2,other.example\n"
    assert unwrap_tranco_feed_bytes(plain_csv) == plain_csv


def test_unwrap_tranco_feed_bytes_rejects_an_unexpected_archive_member_name():
    zipped = _zip_bytes({"unexpected.csv": "1,example.com\n"})
    with pytest.raises(TrancoFeedFormatError):
        unwrap_tranco_feed_bytes(zipped)


def test_unwrap_tranco_feed_bytes_rejects_multiple_archive_members():
    zipped = _zip_bytes({"top-1m.csv": "1,example.com\n", "extra.txt": "not expected"})
    with pytest.raises(TrancoFeedFormatError):
        unwrap_tranco_feed_bytes(zipped)


def test_unwrap_tranco_feed_bytes_rejects_a_corrupt_zip_signature():
    corrupt = b"PK\x03\x04" + b"not actually a valid zip body"
    with pytest.raises(TrancoFeedFormatError):
        unwrap_tranco_feed_bytes(corrupt)
