"""Tests for closing the Debate->Launch loop (prototype -> staged trigger).

Doctrine under test:
  * prototype -> staged is READINESS-GATED: needs a resolved debate AND
    >= STAGE_MIN_LEADS real leads. No auto-promotion on thin air.
  * staging registers a spawn_candidate (status='staged') for Laura's gate.
  * laura_pass stays False here — this module NEVER self-approves a launch.
  * staged -> launched is never performed by the Virtual Firm orchestrator.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import runtime as R  # noqa: E402
import virtual_firm as VF  # noqa: E402


def _reset(center="gdpr-guard"):
    """Isolate pipeline/leads/debates/spawn_candidates for one center."""
    R.state["pipeline"] = {}
    R.state["leads"] = {center: []}
    R.state["debates"] = {}
    R.state["spawn_candidates"] = {}


def _seed_prototype(center="gdpr-guard"):
    oid = R.seed_offering(center, "test offering")
    R.advance_pipeline(oid, "debate")
    R.advance_pipeline(oid, "prototype")
    return oid


def test_prototype_holds_without_evidence():
    """No resolved debate + no leads -> stays prototype, no candidate."""
    _reset()
    _seed_prototype()
    res = VF.promote_prototype_to_staged("gdpr-guard")
    assert res["advanced"] is False
    assert res["stage"] == "prototype"
    assert R.state["spawn_candidates"] == {}


def test_prototype_holds_with_debate_but_too_few_leads():
    """Resolved debate but < STAGE_MIN_LEADS -> still holds."""
    _reset()
    _seed_prototype()
    R.state["debates"]["d1"] = {"center": "gdpr-guard", "status": "resolved"}
    R.state["leads"]["gdpr-guard"] = [{"question_hash": "x"}]  # only 1
    res = VF.promote_prototype_to_staged("gdpr-guard")
    assert res["advanced"] is False
    assert "leads" in res["reason"]


def test_prototype_stages_with_full_evidence():
    """Resolved debate + enough leads -> staged + spawn_candidate queued."""
    _reset()
    oid = _seed_prototype()
    R.state["debates"]["d1"] = {"center": "gdpr-guard", "status": "resolved"}
    R.state["leads"]["gdpr-guard"] = [
        {"question_hash": f"h{i}"} for i in range(VF.STAGE_MIN_LEADS)
    ]
    res = VF.promote_prototype_to_staged("gdpr-guard")
    assert res["advanced"] is True
    assert res["stage"] == "staged"
    assert R.state["pipeline"][oid]["stage"] == "staged"
    # exactly one spawn_candidate, staged, NOT laura-approved
    cands = R.state["spawn_candidates"]
    assert len(cands) == 1
    cand = list(cands.values())[0]
    assert cand["status"] == "staged"
    assert cand["laura_pass"] is False, "must NOT self-approve"
    assert cand["source"] == "virtual_firm_pipeline"


def test_never_launches():
    """The orchestrator never sets 'launched'."""
    _reset()
    _seed_prototype()
    R.state["debates"]["d1"] = {"center": "gdpr-guard", "status": "resolved"}
    R.state["leads"]["gdpr-guard"] = [
        {"question_hash": f"h{i}"} for i in range(VF.STAGE_MIN_LEADS + 2)
    ]
    VF.promote_prototype_to_staged("gdpr-guard")
    stages = [r["stage"] for r in R.state["pipeline"].values()]
    assert "launched" not in stages, "orchestrator must never launch"


def test_orchestrate_reports_stage_transition():
    """orchestrate() surfaces the stage_transition result."""
    _reset()
    _seed_prototype()
    R.state["debates"]["d1"] = {"center": "gdpr-guard", "status": "resolved"}
    R.state["leads"]["gdpr-guard"] = [
        {"question_hash": f"h{i}", "kind": "session"}
        for i in range(VF.STAGE_MIN_LEADS)
    ]
    out = VF.orchestrate("gdpr-guard")
    assert "stage_transition" in out
    assert out["stage_counts"]["staged"] >= 1
