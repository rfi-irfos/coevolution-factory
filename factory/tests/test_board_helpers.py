"""TDD tests for board directive endpoint + roster/CEO helpers.

These tests exercise runtime.py's board_directives state init, the
resolve_ceo helper, the board_directive_handler_logic core, and the
board_status backing logic — all without needing a live HTTP server.

spawn_background() is patched to a no-op so the slow/loop-bound engine
job never actually launches during the unit tests; we only assert that
the directive is recorded and a board-priority job is queued.

Guards: resolve_ceo uses .get with a fallback so a center whose
roster field has not yet been added by the parallel agent does not crash.
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import runtime  # noqa: E402


@pytest.fixture(autouse=True)
def _no_spawn(monkeypatch):
    """Suppress the real background engine job during unit tests."""
    monkeypatch.setattr(runtime, "spawn_background", lambda coro: None)


def test_state_has_board_directives():
    """The global state dict must carry a 'board_directives' key."""
    assert "board_directives" in runtime.state


def test_resolve_ceo_returns_primary_lead():
    """resolve_ceo returns the lead agent of the first roster department."""
    slug = "gdpr-guard"
    # The roster field is added at runtime by a parallel agent; guard the
    # test so it still passes until that lands (and matches once it does).
    meta = runtime.CENTERS_META.get(slug, {})
    roster = meta.get("roster", {})
    deps = roster.get("departments") or []
    expected = deps[0]["lead"]["agent"] if deps else None
    assert runtime.resolve_ceo(slug) == expected


def test_board_directive_registers_and_spawns():
    """A board directive records a routed rec and queues a board-priority job."""
    slug = "gdpr-guard"
    before = len(runtime.state.get("board_directives", {}).get(slug, []))

    out = runtime.board_directive_handler_logic(
        slug, "Prioritize DPIA turnaround under 1h", acct="board")

    # return shape
    assert out["status"] == "routed_to_ceo"
    assert out["ceo"] == runtime.resolve_ceo(slug)
    did = out["directive_id"]
    run_id = out["run_id"]

    # board_directives grew by exactly one and the new rec is well-formed
    recs = runtime.state["board_directives"][slug]
    assert len(recs) == before + 1
    last = recs[-1]
    assert last["id"] == did
    assert last["status"] == "routed_to_ceo"
    assert last["ceo_ack"] is True
    assert last["priority"] == "board"

    # a board-priority job was queued and tied to the directive
    job = runtime.state["jobs"][run_id]
    assert job["priority"] == "board"
    assert job["board_directive_id"] == did
    assert job["center"] == slug


def test_board_directive_unknown_center_returns_none():
    """An unknown center short-circuits to None."""
    assert runtime.board_directive_handler_logic("no-such-center", "x") is None


def test_board_status_returns_directives():
    """board_status surfaces the seeded directives for a center."""
    slug = "gdpr-guard"
    seed = {"id": "d-seed1", "directive": "Seed directive",
            "issued": 0, "status": "routed_to_ceo", "ceo_ack": True,
            "teamlead_acks": 0, "priority": "board", "center": slug}
    runtime.state.setdefault("board_directives", {})[slug] = [seed]

    result = runtime.board_status(slug)
    assert result["center"] == slug
    assert result["directives"][0]["id"] == "d-seed1"
