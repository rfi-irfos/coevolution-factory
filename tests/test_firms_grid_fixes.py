"""Tests for the public Firm Grid fixes (Simeon review 2026-07-17).

Doctrine under test:
  * firms_grid() must show PER-CENTER stats, not identical global numbers
    on every tile (the old "19 everywhere" looked fake).
  * Title must reflect the real center count (no hardcoded 50).
  * Price floor must be realistic (>= 25 EUR/session, not 0.2 loss-leader).

NOTE: we call firms_grid() directly with a mocked request (no TestClient)
to avoid aiohttp app-loop sharing across the full suite (R.app is a
module-global singleton; starting it twice raises).
"""
import os, sys, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import MagicMock
import pytest


@pytest.fixture
def seeded():
    import runtime as R
    R.state["usage"] = [
        {"center": "gdpr-guard", "ts": 1, "cost": 25.0},
        {"center": "gdpr-guard", "ts": 2, "cost": 25.0},
        {"center": "ai-act-guard", "ts": 3, "cost": 25.0},
    ]
    R.state["debates"] = {
        "d1": {"center": "gdpr-guard", "status": "done"},
        "d2": {"center": "ai-act-guard", "status": "done"},
    }
    return R


def test_firms_grid_per_center_problems_and_title(seeded):
    import runtime as R
    req = MagicMock()
    resp = asyncio.run(R.firms_grid(req))
    html = resp.text
    # gdpr-guard: 2 usage + 1 resolved debate = 3
    # ai-act-guard: 1 usage + 1 resolved debate = 2
    assert "3" in html and "2" in html, "per-center problem counts must differ"
    assert "19" not in html.split("Geld")[0], "global fake '19' should be gone"
    expected = str(len(R.CENTERS))
    assert f"{expected} autonome Firmen" in html, \
        f"title should say {expected} firms, not hardcoded 50"


def test_center_price_floor():
    from catalog import CENTERS_META
    for slug, meta in CENTERS_META.items():
        assert meta["price"] >= 25.0, \
            f"{slug} price {meta['price']} is below 25 EUR floor (loss-leader)"
