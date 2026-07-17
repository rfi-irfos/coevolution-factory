"""Task 1: center 0-status FSM + per-offering pipeline stage.

These tests must run fully OFFLINE. We never touch the real engine: a fake
``c`` meta + panel stand in for a center, and network calls are neutralised by
monkeypatching ``call_engine`` / ``engine_synthesize`` in factory.runtime.

conftest.py freezes FT_STATE_DIR to a temp dir, so state.json is isolated.
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "factory"))

import runtime as R


# A realistic stand-in center meta (keys mirror CENTERS_META from catalog.py).
_FAKE_CENTER = {
    "slug": "test-center",
    "name": "Test Center",
    "mandate": "test mandate",
    "icp": "testers",
    "resilient": "test resilient",
    "price": 9.0,
    "free": 1,
    "panel": ["risk-gdpr", "ai-act", "sec-ops"],
    "disciplines": ["Legal", "AI-Safety", "Security"],
    "sample_question": "test question?",
    "use_cases": [],
    "icp_pain": "",
    "value_prop": "test",
    "standing_prompt": "test",
}


def _fake_acct():
    return {"center": "test-center", "email": "t@t.co",
            "created": 0, "sessions": 0}


def _patch_center(monkeypatch):
    """Register the fake center in the module-level registries so the handler
    and job worker see it."""
    monkeypatch.setitem(R.CENTERS, "test-center", _FAKE_CENTER)
    if "test-center" not in R.CENTER_SLUGS:
        R.CENTER_SLUGS.append("test-center")


def test_degraded_on_engine_error(monkeypatch):
    """Engine error -> center goes 'degraded'; a cached center page GET still
    returns 200 with an honest reduced-mode note (no fabricated verdict)."""
    _patch_center(monkeypatch)
    R.state.setdefault("center_status", {}).pop("test-center", None)

    async def boom_upstream(text, panel):
        return None, 502, "connection refused"

    async def boom_synth(upstream, panel, url, key):
        raise AssertionError("should not be called")

    monkeypatch.setattr(R, "call_engine", boom_upstream)
    monkeypatch.setattr(R, "engine_synthesize", boom_synth)
    # neutralise any real DEMO_MODE side effects
    monkeypatch.setattr(R, "DEMO_MODE", False)

    import asyncio
    run_id = "run_test_err"
    R.state.setdefault("jobs", {})[run_id] = {
        "center": "test-center", "status": "queued",
        "created": int(__import__("time").time()), "text": "x",
        "panel": _FAKE_CENTER["panel"], "result": None, "error": None}
    asyncio.run(
        R.run_panel_job(run_id, "test-center", "q", _FAKE_CENTER["panel"],
                        _FAKE_CENTER, _fake_acct()))

    assert R.state["center_status"]["test-center"]["status"] == "degraded"
    assert R.state["jobs"][run_id]["status"] == "error"

    # center page must still render 200 with an honest reduced-mode banner.
    import aiohttp
    from aiohttp.test_utils import make_mocked_request

    request = make_mocked_request("GET", f"/test-center")
    request.match_info["slug"] = "test-center"
    resp = asyncio.run(R.center_page_handler(request))
    body = resp.text
    assert resp.status == 200
    assert "reduced mode" in body.lower()
    assert "last known synthesis" in body.lower()


def test_healthy_on_success(monkeypatch):
    """Successful engine call -> center auto-recovers to 'healthy'."""
    _patch_center(monkeypatch)
    # start degraded to prove recovery
    R.set_center_status("test-center", "degraded", detail="pre")
    R.state.setdefault("jobs", {}).pop("run_test_ok", None)

    async def ok_upstream(text, panel):
        return {"responses": []}, 200, None

    async def ok_synth(upstream, panel, url, key):
        return {"posture": "stable", "panel_size": len(panel),
                "disciplines_fired": 0, "disciplines_silent": panel,
                "flags": [], "notes": [], "conflicts": [],
                "flag_count": 0, "note_count": 0}

    monkeypatch.setattr(R, "call_engine", ok_upstream)
    monkeypatch.setattr(R, "engine_synthesize", ok_synth)
    monkeypatch.setattr(R, "DEMO_MODE", False)

    import asyncio
    run_id = "run_test_ok"
    R.state.setdefault("jobs", {})[run_id] = {
        "center": "test-center", "status": "queued",
        "created": int(__import__("time").time()), "text": "x",
        "panel": _FAKE_CENTER["panel"], "result": None, "error": None}
    asyncio.run(
        R.run_panel_job(run_id, "test-center", "q", _FAKE_CENTER["panel"],
                        _FAKE_CENTER, _fake_acct()))

    assert R.get_center_status("test-center") == "healthy"
    assert R.state["jobs"][run_id]["status"] == "done"


def test_pipeline_stage_present(monkeypatch):
    """state has a 'pipeline' dict with the idea->...->launched stages; an
    offering seeded at 'idea' is readable and the stages are valid."""
    _patch_center(monkeypatch)
    R.state.setdefault("pipeline", {})
    assert R.PIPELINE_STAGES == ["idea", "debate", "prototype", "staged", "launched"]

    oid = R.seed_offering("test-center", "build a thing")
    rec = R.state["pipeline"][oid]
    assert rec["stage"] == "idea"
    assert rec["center"] == "test-center"
    assert rec["idea"] == "build a thing"

    # advance through every valid stage
    for stage in R.PIPELINE_STAGES[1:]:
        R.advance_pipeline(oid, stage)
        assert R.state["pipeline"][oid]["stage"] == stage

    # invalid stage rejected
    import pytest
    with pytest.raises(ValueError):
        R.advance_pipeline(oid, "not-a-stage")
