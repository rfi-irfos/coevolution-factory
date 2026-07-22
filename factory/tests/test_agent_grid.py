"""TDD tests for the /api/agent-grid data endpoint and the /antfarm BI
console page (build_agent_grid, build_antfarm_html, _ANTFARM_CSS/_JS).

These exercise the pure builders directly — no live HTTP server needed.
spawn_background is patched to a no-op so seeding a directive/job never
launches the real engine loop.
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import runtime  # noqa: E402


@pytest.fixture(autouse=True)
def _no_spawn(monkeypatch):
    monkeypatch.setattr(runtime, "spawn_background", lambda coro: None)


_VALID_KINDS = {"develop", "discuss", "improve", "directive", "idle"}


def test_grid_shape():
    grid = runtime.build_agent_grid()
    assert "firms" in grid and "generated" in grid
    firms = grid["firms"]
    assert set(firms.keys()) == set(runtime.CENTERS_META.keys())
    for slug, f in firms.items():
        for key in ("name", "status", "kind", "agents", "open_directives",
                    "sessions", "revenue_eur", "leads", "problems", "accent"):
            assert key in f, f"{slug} missing {key}"
        assert isinstance(f["agents"], list)
        for a in f["agents"]:
            assert "name" in a and "role" in a and "kind" in a
            assert a["kind"] in _VALID_KINDS


def test_grid_kind_from_job():
    """Seed a 'develop' job for a center and assert its agents inherit it."""
    slug = next(iter(runtime.CENTERS_META.keys()))
    runtime.state.setdefault("jobs", {})["job-test-develop"] = {
        "center": slug, "status": "running", "created": runtime.time.time(),
        "kind": "develop", "text": "x", "panel": [], "result": None,
        "error": None,
    }
    try:
        grid = runtime.build_agent_grid()
        kinds = {a["kind"] for a in grid["firms"][slug]["agents"]}
        assert "develop" in kinds
    finally:
        runtime.state.get("jobs", {}).pop("job-test-develop", None)


def test_antfarm_html():
    html = runtime.build_antfarm_html("en")
    assert "gdpr-guard" in html
    assert "data-kind=" in html
    assert 'class="cmd"' in html
    assert "/api/board/directive" in html


def test_css_js_present():
    html = runtime.build_antfarm_html("en")
    assert ".ftile" in html
    assert 'onsubmit="return sendCmd' in html
    assert "fetch('/api/agent-grid')" in html
