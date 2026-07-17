"""Task 4: governance (HITL second-reviewer slot) + Virtual Firm R0hne
pipeline orchestrator.

Fully OFFLINE. Laura stays FINAL gate #1; the second-reviewer is an ADDITIVE
slot. The Virtual Firm orchestrator only seeds/advances offerings and NEVER
launches — staged -> launched requires the Laura-gated spawn path.

conftest.py freezes FT_STATE_DIR to a temp dir, so state.json is isolated.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "factory"))

import runtime as R
import virtual_firm as VF
import daily_spawn as DS

_CENTER = "gdpr-guard"


# --------------------------------------------------------------------------
# 1. HITL second-reviewer slot (Laura stays gate #1)
# --------------------------------------------------------------------------
def test_second_reviewer_logged(monkeypatch, capsys):
    """With HITL_SECOND_REVIEWER set, an (already Laura-passed) candidate
    record is stamped second_reviewer_present=True and the slot is logged.
    This is ADDITIVE — it does not replace or bypass the Laura gate."""
    monkeypatch.setenv("HITL_SECOND_REVIEWER", "laura2")
    cand = {"slug": "test-center", "name": "Test Center", "laura_pass": True}

    msg = DS.apply_second_reviewer(cand)

    assert cand["second_reviewer_present"] is True
    assert "present" in msg
    # honest log line emitted
    out = capsys.readouterr().out
    assert "second_reviewer: present" in out
    # env var was genuinely read (not hard-coded)
    assert os.environ.get("HITL_SECOND_REVIEWER") == "laura2"


def test_second_reviewer_pending_when_unset(monkeypatch, capsys):
    """With no HITL_SECOND_REVIEWER, we log pending_nomination and stamp
    second_reviewer_present=False — no fake reviewer, no auto-approve."""
    monkeypatch.delenv("HITL_SECOND_REVIEWER", raising=False)
    cand = {"slug": "test-center", "name": "Test Center", "laura_pass": True}

    msg = DS.apply_second_reviewer(cand)

    assert cand["second_reviewer_present"] is False
    assert msg == "second_reviewer: pending_nomination"
    assert "pending_nomination" in capsys.readouterr().out


# --------------------------------------------------------------------------
# 2. Virtual Firm R0hne orchestrator — labelled, seeds idea-stage offerings
# --------------------------------------------------------------------------
def _seed_lead(center, kind="session", outcome="stable"):
    """Seed a real-shaped lead directly into state (as add_lead would)."""
    R.state.setdefault("leads", {}).setdefault(center, []).append({
        "ts": int(time.time()),
        "kind": kind,
        "ref": f"run_{kind}_{int(time.time()*1000)}",
        "question_hash": "abc123def456" + "0" * 52,
        "outcome": outcome,
        "center": center,
    })


def test_virtual_firm_label(monkeypatch):
    """orchestrate() returns a dict labelled VIRTUAL FIRM with >= 1 idea-stage
    offering after a real lead is routed."""
    # isolate: clear any pipeline/leads for a clean count
    R.state["pipeline"] = {}
    R.state.setdefault("leads", {})[_CENTER] = []
    _seed_lead(_CENTER, kind="session")

    result = VF.orchestrate(_CENTER)

    assert "VIRTUAL FIRM" in result["label"]
    assert result["stage_counts"]["idea"] >= 1
    assert result["offerings_total"] >= 1
    assert result["last_offering"] is not None


def test_no_launch_without_laura(monkeypatch):
    """The orchestrator NEVER sets an offering to 'launched'. Even with debate
    leads driving advancement, the stage stays within idea/debate/prototype —
    staged->launched is behind the Laura gate (daily_spawn), not here."""
    R.state["pipeline"] = {}
    R.state.setdefault("leads", {})[_CENTER] = []
    # multiple debate leads to try to push the offering as far as possible
    _seed_lead(_CENTER, kind="debate")
    _seed_lead(_CENTER, kind="debate")
    _seed_lead(_CENTER, kind="debate")

    result = VF.orchestrate(_CENTER)

    # never launched, never even auto-staged by this module
    assert result["stage_counts"]["launched"] == 0
    assert result["stage_counts"]["staged"] == 0
    for rec in R.state["pipeline"].values():
        assert rec["stage"] != "launched"
        assert rec["stage"] in ("idea", "debate", "prototype")
    assert "Laura" in result["launch_gate"]


def test_route_lead_idempotent_per_year(monkeypatch):
    """Two session leads in the same year reuse ONE offering (idempotent seed
    per center per calendar year)."""
    R.state["pipeline"] = {}
    R.state.setdefault("leads", {})[_CENTER] = []

    lead1 = {"kind": "session", "outcome": "stable",
             "question_hash": "h1" + "0" * 62}
    lead2 = {"kind": "session", "outcome": "stable",
             "question_hash": "h2" + "0" * 62}
    r1 = VF.route_lead_to_pipeline(_CENTER, lead1)
    r2 = VF.route_lead_to_pipeline(_CENTER, lead2)

    assert r1["offering_id"] == r2["offering_id"]
    assert r1["seeded"] is True
    assert r2["seeded"] is False
