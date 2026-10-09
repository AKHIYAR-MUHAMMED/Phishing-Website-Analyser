"""
Phase 3 dataset collection pipeline.

Implements PHASE3_DATASET_PLAN.md v2 (commit 04fc5d9): a real-data collection pipeline for
phishing (PhishTank/OpenPhish) and benign (Tranco) URLs, built on top of the Phase 2 crawler
(crawler.fetch_url, unmodified except for one additive field — see crawler/fetcher.py's
raw_content_sha256 comment).

No module in this package makes a real PhishTank/OpenPhish/Tranco request when imported; network
calls only happen when their functions are explicitly called, and the test suite never calls
them against a real host (see tests/conftest.py's block_real_network fixture, reused here).
"""
