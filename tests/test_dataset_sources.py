"""
Feed parsing tests (PHASE3_DATASET_PLAN.md section 1, section 4, section 10). Pure functions,
no network — bytes are constructed in-test, never fetched from a real feed.
"""

from dataset.sources import (
    openphish_feed_url,
    parse_openphish_feed,
    parse_phishtank_feed,
    parse_tranco_feed,
    phishtank_bulk_feed_url,
    tranco_list_url,
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
