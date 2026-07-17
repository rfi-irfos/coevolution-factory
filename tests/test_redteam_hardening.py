"""Red-team hardening tests: CORS policy + operator rate-limit.

Doctrine under test:
  * require_operator() = key + rate-limit + explicit strict CORS.
  * CORS: no wildcard (*); only reflect same-origin. Cross-origin gets nothing.
  * Rate-limit: > VF_RATE_MAX hits in VF_RATE_WINDOW on (ip, route) -> 429.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import runtime as R  # noqa: E402


class _FakeReq:
    def __init__(self, headers=None, remote="1.2.3.4"):
        self.headers = headers or {}
        self.remote = remote


def test_cors_no_wildcard():
    """Cross-origin request gets NO Access-Control-Allow-Origin (no '*')."""
    req = _FakeReq(headers={"Origin": "https://evil.example.com",
                            "Host": "coevolution-factory.fly.dev"})
    hdrs = R.cors_headers(req)
    assert "Access-Control-Allow-Origin" not in hdrs, "wildcard/foreign CORS allowed"


def test_cors_same_origin_reflected():
    """Same-origin Origin is reflected (legit first-party use)."""
    req = _FakeReq(headers={"Origin": "https://coevolution-factory.fly.dev",
                            "Host": "coevolution-factory.fly.dev"})
    hdrs = R.cors_headers(req)
    assert hdrs.get("Access-Control-Allow-Origin") == "https://coevolution-factory.fly.dev"


def test_rate_limit_triggers():
    """Exceeding VF_RATE_MAX hits in window -> rate_limited True."""
    R._RATE_HITS.clear()
    route = "test_route"
    req = _FakeReq(remote="9.9.9.9")
    # exhaust the budget
    for _ in range(R._RATE_MAX):
        assert R.rate_limited(req, route) is False
    # next one blocked
    assert R.rate_limited(req, route) is True


def test_rate_limit_window_expires():
    """Old hits fall out of the sliding window."""
    R._RATE_HITS.clear()
    route = "test_route2"
    req = _FakeReq(remote="8.8.8.8")
    for _ in range(R._RATE_MAX):
        R.rate_limited(req, route)
    assert R.rate_limited(req, route) is True
    # simulate window passing
    old = R._RATE_HITS[("8.8.8.8", route)]
    R._RATE_HITS[("8.8.8.8", route)] = [t - (R._RATE_WINDOW + 5) for t in old]
    assert R.rate_limited(req, route) is False  # allowed again
