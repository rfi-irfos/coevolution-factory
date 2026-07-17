"""Tests for reversible self-launch (all gates true + rollback).

Doctrine under test:
  * launch_staged_offering() only launches when VF_AUTO_LAUNCH + HITL_SECOND_
    REVIEWER + candidate.laura_pass are ALL true.
  * Without laura_pass (Laura gate #1), it NEVER launches — even with the
    other two gates set.
  * On launch it snapshots pre-launch state; rollback_launch(oid) reverses it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import runtime as R  # noqa: E402
import virtual_firm as VF  # noqa: E402


def _reset(center="gdpr-guard"):
    R.state["pipeline"] = {}
    R.state["leads"] = {center: []}
    R.state["debates"] = {}
    R.state["spawn_candidates"] = {}
    R.state["rollback"] = {}
    R.state["centers"] = {}
    R.state["daughter_centers"] = {}
    # ensure runtime registry is clean for promote/rollback
    for s in [c for c in list(R.CENTERS.keys()) if R.CENTERS[c].get("is_daughter")]:
        R.CENTERS.pop(s, None)
        if s in R.CENTER_SLUGS:
            R.CENTER_SLUGS.remove(s)
        R.CENTER_NETWORK.pop(s, None)


def _seed_staged(center="gdpr-guard"):
    """Create a staged virtual-firm offering + candidate (like the live loop)."""
    oid = R.seed_offering(center, "offer")
    R.advance_pipeline(oid, "debate")
    R.advance_pipeline(oid, "prototype")
    R.advance_pipeline(oid, "staged")
    R.state["spawn_candidates"][f"{center}-vf-{oid[-6:]}"] = {
        "slug": f"{center}-vf-{oid[-6:]}",
        "name": f"{center} VF", "mandate": "x", "parent": center,
        "status": "staged", "laura_pass": False,
        "source": "virtual_firm_pipeline", "offering_id": oid,
        "created": int(__import__("time").time()),
    }
    R.state["leads"][center] = [{"question_hash": f"h{i}"} for i in range(3)]
    R.state["debates"]["d1"] = {"center": center, "status": "resolved"}
    return oid


def test_no_launch_without_auto_flag(monkeypatch):
    _reset()
    oid = _seed_staged()
    monkeypatch.setattr(VF, "_AUTO_LAUNCH", False)
    monkeypatch.setattr(VF, "_SECOND_REVIEWER", True)
    R.state["spawn_candidates"][f"gdpr-guard-vf-{oid[-6:]}"]["laura_pass"] = True
    res = VF.launch_staged_offering(oid)
    assert res["launched"] is False
    assert "VF_AUTO_LAUNCH" in res["reason"]


def test_laura_gate_is_final(monkeypatch):
    """Auto-launch + second-reviewer set, but laura_pass=False -> NO launch."""
    _reset()
    oid = _seed_staged()
    monkeypatch.setattr(VF, "_AUTO_LAUNCH", True)
    monkeypatch.setattr(VF, "_SECOND_REVIEWER", True)
    # deliberately leave laura_pass=False
    res = VF.launch_staged_offering(oid)
    assert res["launched"] is False
    assert "Laura" in res["reason"]
    assert R.state["pipeline"][oid]["stage"] == "staged"


def test_launch_when_all_gates_true(monkeypatch):
    _reset()
    oid = _seed_staged()
    monkeypatch.setattr(VF, "_AUTO_LAUNCH", True)
    monkeypatch.setattr(VF, "_SECOND_REVIEWER", True)
    R.state["spawn_candidates"][f"gdpr-guard-vf-{oid[-6:]}"]["laura_pass"] = True
    res = VF.launch_staged_offering(oid)
    assert res["launched"] is True
    assert res["slug"] == f"gdpr-guard-vf-{oid[-6:]}"
    assert R.state["pipeline"][oid]["stage"] == "launched"
    # rollback record exists
    assert oid in R.state["rollback"]


def test_rollback_reverses_launch(monkeypatch):
    _reset()
    oid = _seed_staged()
    monkeypatch.setattr(VF, "_AUTO_LAUNCH", True)
    monkeypatch.setattr(VF, "_SECOND_REVIEWER", True)
    R.state["spawn_candidates"][f"gdpr-guard-vf-{oid[-6:]}"]["laura_pass"] = True
    VF.launch_staged_offering(oid)
    assert f"gdpr-guard-vf-{oid[-6:]}" in R.CENTERS  # launched
    rb = VF.rollback_launch(oid)
    assert rb["ok"] is True
    assert f"gdpr-guard-vf-{oid[-6:]}" not in R.CENTERS  # reversed
    assert R.state["pipeline"][oid]["stage"] == "staged"  # back to staged
