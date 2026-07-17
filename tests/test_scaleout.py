"""Scale-out tests (Tasks 1, 2 & 3).

conftest.py freezes FT_STATE_DIR to a temp dir so state.json is isolated,
and puts factory/ on sys.path so `import daily_spawn` / `import runtime` work.

TDD discipline: write failing test -> implement -> green.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "factory"))

import daily_spawn as DS


# --- Task 1: batched Laura gate over staged candidates ---------------------

def test_batch_gate_returns_passmap(monkeypatch):
    """One Laura call reviewing all staged candidates returns {slug: bool}.
    Fake Laura flags candidate 'b' only -> {a: True, b: False}."""
    cands = {
        "a": {"name": "A", "mandate": "x", "uncovered_signals": []},
        "b": {"name": "B", "mandate": "y", "uncovered_signals": []},
    }

    def fake(text, title, metadata, **kw):
        # ONE call carries the whole batch; return per-slug verdicts.
        rows = json.loads(text)
        return {
            "verdicts": {
                row["slug"]: {"flags": ["x"] if row["slug"] == "b" else []}
                for row in rows
            }
        }

    monkeypatch.setattr(DS, "mcp_laura_review_plan", fake)
    out = asyncio.run(DS.batch_gate_candidates(cands))
    assert out == {"a": True, "b": False}


# --- Task 2: capacity / health pre-check -----------------------------------

def test_capacity_ok_respects_cap(monkeypatch):
    """capacity_ok() must respect VF_MAX_DAUGHTERS and refuse at cap,
    but allow when below cap — reading the env live (so setenv works)."""
    import runtime as R

    monkeypatch.setenv("VF_MAX_DAUGHTERS", "2")

    # at cap -> refuse
    R.state["daughter_centers"] = {"d1": {}, "d2": {}}
    assert DS.capacity_ok() is False

    # below cap -> ok
    R.state["daughter_centers"] = {"d1": {}}
    assert DS.capacity_ok() is True


def test_capacity_ok_refuses_on_zero_status(monkeypatch):
    """capacity_ok() must refuse while any center is in 0-status
    (engine down) even when below the daughter cap."""
    import runtime as R

    monkeypatch.setenv("VF_MAX_DAUGHTERS", "10")
    R.state["daughter_centers"] = {"d1": {}}
    R.state["center_status"] = {"some-center": {"status": "0-status"}}
    assert DS.capacity_ok() is False

    # clear the 0-status -> ok
    R.state["center_status"] = {}
    assert DS.capacity_ok() is True


# --- Task 3: auto-network co-spawned daughters -----------------------------

def test_network_daughters_links_both_ways():
    """Co-spawned daughters link to each other (both ways) and to the
    parent in CENTER_NETWORK."""
    import runtime as R

    R.CENTER_NETWORK.clear()
    DS.network_daughters("gdpr-guard", ["da", "db"])
    assert "db" in R.CENTER_NETWORK["da"]
    assert "da" in R.CENTER_NETWORK["db"]
    assert "da" in R.CENTER_NETWORK["gdpr-guard"]


def test_network_daughters_is_idempotent():
    """Re-running network_daughters with the same slugs never duplicates
    an edge (no repeated entries in CENTER_NETWORK adjacency lists)."""
    import runtime as R

    R.CENTER_NETWORK.clear()
    DS.network_daughters("gdpr-guard", ["da", "db"])
    DS.network_daughters("gdpr-guard", ["da", "db"])  # second call
    assert R.CENTER_NETWORK["da"].count("db") == 1
    assert R.CENTER_NETWORK["db"].count("da") == 1
    assert R.CENTER_NETWORK["gdpr-guard"].count("da") == 1
    assert R.CENTER_NETWORK["gdpr-guard"].count("db") == 1


# --- Task 4: scale_out() orchestrator --------------------------------------

def test_scale_out_promotes_passed_and_caps(monkeypatch):
    """scale_out() runs the full loop (scan -> batch-gate -> capacity ->
    promote -> network) and reports promoted slugs. Both staged candidates
    are Laura-passed, so both get promoted and registered in CENTERS."""
    import runtime as R

    R.state["daughter_centers"] = {}
    R.state["spawn_candidates"] = {
        "da": {"name": "A", "mandate": "x", "status": "staged",
               "slug": "da", "parent": "gdpr-guard",
               "uncovered_signals": []},
        "db": {"name": "B", "mandate": "y", "status": "staged",
               "slug": "db", "parent": "gdpr-guard",
               "uncovered_signals": []},
    }

    # Laura passes both (0 flags).
    monkeypatch.setattr(DS, "mcp_laura_review_plan",
                        lambda **kw: {"flags": []})
    # Fake scan: returns a scan result, does NOT touch state (candidates are
    # already staged in R.state by the test).
    async def fake_run_spawn_agent():
        return {"staged": 2}
    monkeypatch.setattr(DS, "run_spawn_agent", fake_run_spawn_agent)

    report = asyncio.run(DS.scale_out())

    assert report["promoted"] == ["da", "db"]
    assert "da" in R.CENTERS and "db" in R.CENTERS
    assert report["capacity_ok"] is True
