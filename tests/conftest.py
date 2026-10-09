"""
Shared test configuration.

Guard: the suite must not modify tracked data files (CLAUDE.md section 17.9). The previous
suite rewrote data/phishguard_x_dataset_metadata.json and wrote uploads into data/screenshots/.
"""

import hashlib
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import crawler.fetcher as fetcher  # noqa: E402
from local_server import LocalTestServer  # noqa: E402

GUARDED_PATHS = [os.path.join(REPO_ROOT, "data"), os.path.join(REPO_ROOT, "phishguard_x.db")]

LLM_KEY_VARS = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "DEEPSEEK_API_KEY", "MISTRAL_API_KEY"]


def _snapshot():
    digests = {}
    for path in GUARDED_PATHS:
        if os.path.isfile(path):
            files = [path]
        else:
            files = [os.path.join(d, f) for d, _, fs in os.walk(path) for f in fs]
        for f in files:
            with open(f, "rb") as fh:
                digests[os.path.relpath(f, REPO_ROOT)] = hashlib.sha256(fh.read()).hexdigest()
    return digests


@pytest.fixture(scope="session", autouse=True)
def tracked_data_unchanged():
    before = _snapshot()
    yield
    after = _snapshot()
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    assert not changed, f"Tests modified tracked data files: {changed}"


@pytest.fixture(autouse=True)
def no_llm_keys(monkeypatch):
    """Tests never call real LLM APIs. Individual tests may set a fake key with a mocked transport."""
    for var in LLM_KEY_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def block_real_network(monkeypatch):
    """
    Tests never make a real network request: the crawler is only exercised against the local
    test server (see the `http_server` fixture below). Any attempt to fetch a non-local host
    fails fast with a clear error instead of hanging or depending on the internet.
    """
    def guard(host):
        if host not in (None, "127.0.0.1", "localhost", "::1"):
            raise fetcher.NetworkBlockedError(
                f"Real network access is disabled in tests (host was {host!r}). "
                "Use the http_server fixture instead of a real URL."
            )
    monkeypatch.setattr(fetcher, "_host_guard", guard)


@pytest.fixture(scope="session")
def http_server():
    server = LocalTestServer().start()
    yield server
    server.stop()
