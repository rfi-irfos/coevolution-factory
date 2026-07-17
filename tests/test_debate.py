"""Task 2: inter-center debate convener.

Tests the POST /api/center/debate endpoint fully OFFLINE:
  - the engine is neutralised by monkeypatching call_engine / engine_synthesize
  - a valid entitlement key is injected into state['keys'] so require_key passes
  - the slow pooled-panel job is captured (spawn_background mocked) and awaited
    directly, so we never reach into the real engine and never need a live loop
    background waiter.

conftest.py freezes FT_STATE_DIR to a temp dir, so state.json is isolated.

NOTE: aiohttp's web.Application binds to the event loop on first server
start, so all three tests share ONE module-level loop (otherwise a second
asyncio.run would open a different loop and start_server fails with
"initialized with different loop"). No pytest-asyncio needed.
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "factory"))

import runtime as R

# Single shared loop for the whole module (see note above).
_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


# gdpr-guard is a real catalog center: own panel + many adjacent centers
# (ai-act-guard, breach-readiness, hipaa-check, ...). It exercises the pooled
# panel + adjacent-invite logic without any fake-center scaffolding.
_CENTER = "gdpr-guard"
_TEST_KEY = "ct_gdpr_test_0123456789abcdef"


def _inject_key():
    R.state.setdefault("keys", {})[_TEST_KEY] = {
        "center": _CENTER, "email": "t@t.co",
        "created": 0, "sessions": 0}


async def _fake_upstream(text, panel):
    # engine returns nothing useful; engine_synthesize is what we spy on.
    return {"responses": []}, 200, None


async def _fake_synth(upstream, panel, url, key):
    return {"posture": "stable", "panel_size": len(panel),
            "disciplines_fired": 0, "disciplines_silent": panel,
            "flags": [], "notes": [], "conflicts": [],
            "flag_count": 0, "note_count": 0}


async def _make_client():
    from aiohttp.test_utils import TestClient, TestServer
    server = TestServer(R.app, loop=_LOOP)
    client = TestClient(server)
    await client.start_server()
    return client


def test_debate_returns_run_id(monkeypatch):
    """POST /api/center/debate with a valid key + body returns 200 + run_id."""
    _inject_key()
    monkeypatch.setattr(R, "DEMO_MODE", False)
    monkeypatch.setattr(R, "call_engine", _fake_upstream)
    monkeypatch.setattr(R, "engine_synthesize", _fake_synth)

    # capture the background job coroutine so we can await it deterministically
    captured = []
    monkeypatch.setattr(R, "spawn_background", lambda coro: captured.append(coro))

    async def go():
        client = await _make_client()
        try:
            resp = await client.post(
                f"/api/center/debate?center={_CENTER}",
                json={"text": "x"},
                headers={"Authorization": f"Bearer {_TEST_KEY}"})
            body = await resp.json()
            assert resp.status == 200, body
            assert "run_id" in body, body
            assert body["run_id"].startswith("debate_")
            assert body["status"] == "queued"
            # adjacent quorum surfaced in the immediate response
            assert isinstance(body["adjacent"], list) and len(body["adjacent"]) > 0
            # let the background job run so it isn't GC'd mid-flight (avoids
            # "coroutine never awaited" warning on monkeypatch restore)
            if captured:
                await captured[0]
        finally:
            await client.close()

    _run(go())


def test_debate_invites_adjacent(monkeypatch):
    """The pooled panel passed to engine_synthesize includes adjacent centers'
    panel disciplines (OQ3: adjacent-only quorum)."""
    _inject_key()
    monkeypatch.setattr(R, "DEMO_MODE", False)
    monkeypatch.setattr(R, "call_engine", _fake_upstream)

    spy = {"panel": None}
    async def spy_synth(upstream, panel, url, key):
        spy["panel"] = list(panel)
        return {"posture": "stable", "panel_size": len(panel),
                "disciplines_fired": 0, "disciplines_silent": panel,
                "flags": [], "notes": [], "conflicts": [],
                "flag_count": 0, "note_count": 0}
    monkeypatch.setattr(R, "engine_synthesize", spy_synth)

    captured = []
    monkeypatch.setattr(R, "spawn_background", lambda coro: captured.append(coro))

    async def go():
        client = await _make_client()
        try:
            resp = await client.post(
                f"/api/center/debate?center={_CENTER}",
                json={"text": "x"},
                headers={"Authorization": f"Bearer {_TEST_KEY}"})
            assert resp.status == 200
            # run the captured background job to completion
            await captured[0]

            pooled = spy["panel"]
            assert pooled is not None, "engine_synthesize was never called"
            own_panel = R.CENTERS[_CENTER]["panel"]
            # always includes the origin center's own disciplines
            for a in own_panel:
                assert a in pooled, \
                    f"origin discipline {a} missing from pooled panel"
            # and invites at least one adjacent center's discipline
            adjacent = R.CENTER_NETWORK[_CENTER]
            assert len(adjacent) > 0
            invited = False
            for adj in adjacent:
                adj_panel = R.CENTERS[adj]["panel"]
                if any(a in pooled for a in adj_panel):
                    invited = True
                    break
            assert invited, \
                "no adjacent-center discipline present in pooled panel"
        finally:
            await client.close()

    _run(go())


def test_debate_advances_pipeline(monkeypatch):
    """A seeded 'idea' offering for the center advances to 'debate' after the
    debate resolves."""
    _inject_key()
    monkeypatch.setattr(R, "DEMO_MODE", False)
    monkeypatch.setattr(R, "call_engine", _fake_upstream)
    monkeypatch.setattr(R, "engine_synthesize", _fake_synth)

    captured = []
    monkeypatch.setattr(R, "spawn_background", lambda coro: captured.append(coro))

    # seed an offering at the 'idea' stage for this center
    oid = R.seed_offering(_CENTER, "a tension worth debating")
    assert R.state["pipeline"][oid]["stage"] == "idea"

    async def go():
        client = await _make_client()
        try:
            resp = await client.post(
                f"/api/center/debate?center={_CENTER}",
                json={"text": "x"},
                headers={"Authorization": f"Bearer {_TEST_KEY}"})
            assert resp.status == 200
            body = await resp.json()
            await captured[0]

            # the related offering moved idea -> debate
            assert R.state["pipeline"][oid]["stage"] == "debate", \
                R.state["pipeline"][oid]
            # and the resolution is stored in state['debates']
            run_id = body["run_id"]
            assert run_id in R.state["debates"]
            assert R.state["debates"][run_id]["status"] == "done"
            assert R.state["debates"][run_id]["advanced_offering"] == oid
        finally:
            await client.close()

    _run(go())
