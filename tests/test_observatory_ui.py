"""Task 5: /observatory HTML watch-page (calm Palantir aesthetic) while the
JSON contract stays 100% intact for Accept: application/json.

Fully OFFLINE. We seed R.state with a small, known snapshot (a center status,
a debate, a lead, a spawn candidate, a pipeline offering) and then call the
observatory() handler directly with a tiny fake request whose .headers select
JSON vs HTML. No TestServer / event loop binding required, so this file
coexists with the loop-owning test modules.

conftest.py freezes FT_STATE_DIR to a temp dir, so state.json is isolated.
"""

import os
import sys
import asyncio
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "factory"))

import runtime as R


class _FakeRequest:
    """Minimal stand-in for aiohttp.web.Request: only .headers + .query are
    read by observatory()."""

    def __init__(self, accept=""):
        self.headers = {"Accept": accept} if accept else {}
        self.query = {}


def _run(coro):
    return asyncio.run(coro)


def _seed():
    """Seed a known, honest snapshot into the real state dict."""
    slug = next(iter(R.CENTERS))  # a real catalog center
    # a persisted center status (healthy so a blue badge renders)
    R.state.setdefault("center_status", {})[slug] = {
        "status": "healthy", "detail": None, "updated": int(time.time())}
    # one resolved debate
    R.state.setdefault("debates", {})["dbg_obs_1"] = {
        "center": slug, "adjacent": [], "status": "done",
        "created": int(time.time()),
        "resolution": {"posture": "stable"}}
    # one lead
    R.state.setdefault("leads", {}).setdefault(slug, []).append(
        {"ts": int(time.time()), "kind": "session", "ref": "run_obs",
         "question_hash": "deadbeef", "outcome": "stable", "center": slug})
    # one spawn candidate (factory-factory transparency row)
    R.state.setdefault("spawn_candidates", {})["cand-obs"] = {
        "name": "Observatory Candidate Center", "mandate": "watch the watchers",
        "status": "staged", "laura_pass": False, "uncovered_signals": []}
    # one pipeline offering (Virtual Firm)
    R.state.setdefault("pipeline", {})["offer_obs"] = {
        "center": slug, "idea": "a virtual firm offering",
        "stage": "idea", "created": int(time.time())}
    return slug


def test_observatory_html_default():
    """No/HTML Accept header -> a calm HTML watch-page, status 200,
    content-type text/html, carrying every required section."""
    slug = _seed()
    resp = _run(R.observatory(_FakeRequest(accept="text/html")))
    assert resp.status == 200
    assert resp.content_type == "text/html"
    body = resp.text
    assert "<html" in body.lower()
    # header + core sections
    assert "Observatory" in body
    assert "VIRTUAL FIRM" in body.upper()
    # a center status badge (healthy center -> the word 'healthy' appears)
    assert "healthy" in body.lower()
    # spawn candidate surfaced by name
    assert "Observatory Candidate Center" in body
    # leads section
    assert "leads" in body.lower()
    # debates section
    assert "debate" in body.lower()
    # calm aesthetic: reuses the index palette, no auto-refresh loop
    assert "#0a0e14" in body
    assert "http-equiv=refresh" not in body.lower()
    assert "setInterval" not in body


def test_observatory_json_intact():
    """Accept: application/json -> the ORIGINAL JSON dict, untouched."""
    _seed()
    resp = _run(R.observatory(_FakeRequest(accept="application/json")))
    assert resp.status == 200
    assert resp.content_type == "application/json"
    import json
    data = json.loads(resp.text)
    # the exact JSON contract from Tasks 0-4 is preserved
    for key in ("centers_total", "centers_active", "total_sessions",
                "total_revenue_eur", "total_paid_eur", "virtual_firm",
                "debates_total", "leads_total", "spawn_candidates",
                "cashflow", "stripe_account"):
        assert key in data, f"missing JSON key: {key}"
    assert data["virtual_firm"]["label"].startswith("VIRTUAL FIRM")
    assert "cand-obs" in data["spawn_candidates"]


def test_observatory_json_via_wildcard_is_html():
    """A browser-style Accept (text/html,...) must NOT be served JSON: the
    branch keys strictly on application/json prefix."""
    _seed()
    resp = _run(R.observatory(_FakeRequest(
        accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")))
    assert resp.content_type == "text/html"
