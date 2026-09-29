"""
robots.txt policy tests against local servers only (local_server.RobotsTestServer). No test in
this file touches a real website.
"""

import asyncio

from dataset.robots import (
    ROBOTS_ALLOWED,
    ROBOTS_DISALLOWED,
    ROBOTS_NO_FILE,
    ROBOTS_UNREACHABLE,
    check_robots,
)
from local_server import RobotsTestServer, closed_port_url


def test_no_robots_file_is_allowed_by_convention():
    server = RobotsTestServer(robots_body=None).start()
    try:
        result = asyncio.run(check_robots(server.url("/some-page")))
        assert result == ROBOTS_NO_FILE
    finally:
        server.stop()


def test_allow_all_robots_txt():
    server = RobotsTestServer(robots_body=b"User-agent: *\nAllow: /\n").start()
    try:
        result = asyncio.run(check_robots(server.url("/some-page")))
        assert result == ROBOTS_ALLOWED
    finally:
        server.stop()


def test_disallow_all_robots_txt():
    server = RobotsTestServer(robots_body=b"User-agent: *\nDisallow: /\n").start()
    try:
        result = asyncio.run(check_robots(server.url("/some-page")))
        assert result == ROBOTS_DISALLOWED
    finally:
        server.stop()


def test_unreachable_host_fails_open_to_unreachable_status():
    # Fail-open (section 3): robots.txt unreachable must NOT be reported as "disallowed".
    result = asyncio.run(check_robots(closed_port_url()))
    assert result == ROBOTS_UNREACHABLE


def test_invalid_url_is_unreachable():
    assert asyncio.run(check_robots("not-a-url")) == ROBOTS_UNREACHABLE


def test_cache_avoids_a_second_fetch_for_the_same_host(monkeypatch):
    server = RobotsTestServer(robots_body=b"User-agent: *\nDisallow: /admin\n").start()
    try:
        import dataset.robots as robots_module
        call_count = {"n": 0}
        real_fetch = robots_module._fetch_robots_policy

        async def counting_fetch(*args, **kwargs):
            call_count["n"] += 1
            return await real_fetch(*args, **kwargs)
        monkeypatch.setattr(robots_module, "_fetch_robots_policy", counting_fetch)

        cache = {}
        r1 = asyncio.run(check_robots(server.url("/page-a"), cache=cache))
        r2 = asyncio.run(check_robots(server.url("/page-b"), cache=cache))
        assert r1 == ROBOTS_ALLOWED
        assert r2 == ROBOTS_ALLOWED
        assert call_count["n"] == 1  # second call reused the cached policy
    finally:
        server.stop()


def test_cache_still_applies_path_specific_rules_per_url():
    """A cached policy is per-host, but the allow/disallow decision must still be evaluated
    per-URL: caching the wrong (host-level-only) verdict was a real bug this test guards."""
    server = RobotsTestServer(robots_body=b"User-agent: *\nDisallow: /admin\n").start()
    try:
        cache = {}
        allowed = asyncio.run(check_robots(server.url("/public"), cache=cache))
        disallowed = asyncio.run(check_robots(server.url("/admin/secret"), cache=cache))
        assert allowed == ROBOTS_ALLOWED
        assert disallowed == ROBOTS_DISALLOWED
    finally:
        server.stop()


def test_real_host_is_blocked_by_network_guard():
    # The autouse block_real_network fixture (tests/conftest.py) blocks this non-local host;
    # check_robots must fail open (unreachable), never make the real request.
    result = asyncio.run(check_robots("https://example.com/"))
    assert result == ROBOTS_UNREACHABLE
