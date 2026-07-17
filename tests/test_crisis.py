"""Tests for crisis protocol / 0-status democratic consensus (Q&A #11).

Doctrine under test:
  * CRISIS_PROTOCOL = "zero_status_meeting": workforce -> tend, firm runs on.
  * teamlead_consensus_gate(): needs >=77% affirm trits for a definitive Go.
  * crisis_to_zero_status(): firm NEVER down; self-organizes in tend.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import governance as G


def test_crisis_protocol_constants():
    assert G.CRISIS_PROTOCOL == "zero_status_meeting"
    assert G.CONSENSUS_THRESHOLD == 0.77
    assert G.MEETING_STATE == "tend"


def test_consensus_reaches_go_at_77():
    # 10 votes, 8 affirm -> 80% >= 77% -> Go
    votes = [1, 1, 1, 1, 1, 1, 1, 1, -1, 0]
    go, ratio, note = G.teamlead_consensus_gate(votes)
    assert go is True
    assert ratio == 0.8


def test_consensus_holds_below_77():
    # 10 votes, 7 affirm -> 70% < 77% -> hold (meeting continues)
    votes = [1, 1, 1, 1, 1, 1, 1, -1, -1, 0]
    go, ratio, note = G.teamlead_consensus_gate(votes)
    assert go is False
    assert "77%" in note


def test_crisis_to_zero_status_firm_runs():
    state = G.crisis_to_zero_status()
    assert state["workforce_state"] == "tend"
    assert state["firm_running"] is True
    assert state["protocol"] == "zero_status_meeting"
