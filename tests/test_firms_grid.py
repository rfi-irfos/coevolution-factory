"""Task 7: public Firm Grid at GET /firms.

An Instagram-style grid of tiles (CSS grid, responsive, calm Palantir palette),
one tile per center, each showing 4 live stats and a 'Jetzt buchen' book button
linking to that center's page (which carries the Stripe signup).

Server-rendered ONCE from state — no JS fetch loop, no auto-refresh. We call the
firms_grid() handler directly with a tiny fake request (only .headers/.query are
read) so this file coexists with the loop-owning test modules.

conftest.py freezes FT_STATE_DIR to a temp dir, so state.json is isolated.
"""

import os
import sys
import asyncio
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "factory"))

import runtime as R


class _FakeRequest:
    def __init__(self, accept=""):
        self.headers = {"Accept": accept} if accept else {}
        self.query = {}


def _run(coro):
    return asyncio.run(coro)


def _seed():
    """Seed a known, honest snapshot: a session (revenue), a resolved debate."""
    slug = "gdpr-guard"  # a real catalog center with a known name
    R.state.setdefault("center_status", {})[slug] = {
        "status": "healthy", "detail": None, "updated": int(time.time())}
    R.state.setdefault("usage", []).append(
        {"center": slug, "cost": 0.20, "ts": int(time.time())})
    R.state.setdefault("debates", {})["dbg_fg_1"] = {
        "center": slug, "adjacent": [], "status": "done",
        "created": int(time.time()), "resolution": {"posture": "stable"}}
    return slug


def test_firms_grid_returns_200_html():
    slug = _seed()
    resp = _run(R.firms_grid(_FakeRequest()))
    assert resp.status == 200
    assert resp.content_type == "text/html"
    body = resp.text
    assert "<html" in body.lower()
    # title / heading names the grid (English or German)
    assert ("Firm Grid" in body) or ("Firmen" in body)
    # at least one real center name renders
    assert "GDPRGuard Center" in body
    # a 'Jetzt buchen' book button links to the center page (Stripe signup)
    assert "Jetzt buchen" in body
    assert 'href="/gdpr-guard"' in body


def test_firms_grid_is_static_no_fetch_loop():
    """Rendered once from state: no auto-refresh meta, no polling loop."""
    _seed()
    body = _run(R.firms_grid(_FakeRequest())).text
    assert "http-equiv=refresh" not in body.lower()
    assert "setInterval" not in body
    assert "setTimeout" not in body
    # calm Palantir palette reused from index()/observatory()
    assert "#0a0e14" in body
    # responsive CSS grid (not a JS layout)
    assert "grid-template-columns" in body


def test_firms_grid_shows_four_stat_labels():
    """Each tile surfaces the 4 promised live zones: Sessions/Revenue/Leads/Gelöst
    (Simeon's explicit spec 2026-07-17: 'in vier zonen aufgeteilt in sessions
    und revenue und leads und so')."""
    _seed()
    body = _run(R.firms_grid(_FakeRequest())).text
    assert "SESSIONS" in body.upper()
    assert "REVENUE" in body.upper()
    assert "LEADS" in body.upper()
    assert "GEL" in body.upper()  # "Gelöst" — umlaut-safe substring check
